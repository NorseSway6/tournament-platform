import type {
  EntryStatus,
  LineupStatus,
  Match,
  MatchStatus,
  TournamentStatus,
  Visibility,
} from "../api/types";

export const DEFAULT_TZ = "Europe/Moscow";

function fmt(value: string | Date, tz: string | undefined, options: Intl.DateTimeFormatOptions) {
  const date = typeof value === "string" ? new Date(value) : value;
  try {
    return new Intl.DateTimeFormat("ru-RU", { timeZone: tz || DEFAULT_TZ, ...options }).format(date);
  } catch {
    return new Intl.DateTimeFormat("ru-RU", options).format(date);
  }
}

/** «15 июля» */
export const formatDay = (v: string | null, tz?: string) =>
  v ? fmt(v, tz, { day: "numeric", month: "long" }) : "—";

/** «15 июля, 19:00» */
export const formatDateTime = (v: string | null, tz?: string) =>
  v ? fmt(v, tz, { day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" }) : "—";

/** «19:00» */
export const formatTime = (v: string | null, tz?: string) =>
  v ? fmt(v, tz, { hour: "2-digit", minute: "2-digit" }) : "—";

/** «понедельник, 15 июля» — заголовок группы матчей */
export const formatDayHeader = (v: string, tz?: string) => {
  const s = fmt(v, tz, { weekday: "long", day: "numeric", month: "long" });
  return s.charAt(0).toUpperCase() + s.slice(1);
};

/** Даты турнира из полей YYYY-MM-DD: «1 июня – 30 августа» */
export function formatDateRange(from: string | null, to: string | null) {
  const d = (s: string) =>
    new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "long", timeZone: "UTC" }).format(
      new Date(`${s}T00:00:00Z`),
    );
  if (from && to) return `${d(from)} – ${d(to)}`;
  if (from) return `с ${d(from)}`;
  if (to) return `до ${d(to)}`;
  return "даты не указаны";
}

/** Ключ дня (YYYY-MM-DD) в заданном часовом поясе — для группировки и «сегодня». */
export function dayKey(v: string | Date, tz?: string) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: tz || DEFAULT_TZ,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(typeof v === "string" ? new Date(v) : v);
  const get = (t: string) => parts.find((p) => p.type === t)?.value;
  return `${get("year")}-${get("month")}-${get("day")}`;
}

export const isToday = (v: string | null, tz?: string) =>
  !!v && dayKey(v, tz) === dayKey(new Date(), tz);

export const TOURNAMENT_STATUS: Record<TournamentStatus, string> = {
  draft: "Черновик",
  registration: "Регистрация",
  ongoing: "Идёт",
  finished: "Завершён",
};

export const VISIBILITY: Record<Visibility, string> = {
  public: "Публичный",
  unlisted: "По ссылке",
  private: "Закрытый",
};

export const MATCH_STATUS: Record<MatchStatus, string> = {
  scheduled: "Состоится",
  lineups_open: "Приём заявок",
  live: "Идёт",
  finished: "Ждёт подтверждения",
  confirmed: "Завершён",
  postponed: "Перенесён",
  cancelled: "Отменён",
  technical: "Тех. результат",
};

export const ENTRY_STATUS: Record<EntryStatus, string> = {
  pending: "Ожидает",
  accepted: "Принята",
  rejected: "Отклонена",
  withdrawn: "Отозвана",
};

export const LINEUP_STATUS: Record<LineupStatus, string> = {
  draft: "Не отправлена",
  submitted: "Отправлена",
  accepted: "Принята",
  rejected: "Отклонена",
};

export const UPCOMING_STATUSES: MatchStatus[] = ["scheduled", "lineups_open", "live", "postponed"];
export const RESULT_STATUSES: MatchStatus[] = ["finished", "confirmed", "technical", "cancelled"];

export const isUpcoming = (m: Match) => UPCOMING_STATUSES.includes(m.status);
export const hasScore = (m: Match) => m.home_score !== null && m.away_score !== null;

export function scoreText(m: Pick<Match, "home_score" | "away_score">) {
  return m.home_score === null || m.away_score === null
    ? "–:–"
    : `${m.home_score}:${m.away_score}`;
}

export const teamName = (m: Match, side: "home" | "away") =>
  (side === "home" ? m.home_entry : m.away_entry)?.team.name ?? "Команда не определена";

/** Первая буква названия для «аватарки» команды. */
export function teamInitial(name: string) {
  const cleaned = name.replace(/^(ФК|FC|СК|МФК)\s+/i, "").replace(/[«»"']/g, "");
  return (cleaned[0] || name[0] || "?").toUpperCase();
}

const TEAM_COLORS = ["#4C5FD5", "#E5484D", "#00784C", "#D9822B", "#8E4EC6", "#0091C2", "#C2298A", "#5B6B79"];
export function teamColor(id: number) {
  return TEAM_COLORS[Math.abs(id) % TEAM_COLORS.length];
}

/** Окончание слова: plural(5, ["команда", "команды", "команд"]) */
export function plural(n: number, forms: [string, string, string]) {
  const n10 = n % 10;
  const n100 = n % 100;
  if (n10 === 1 && n100 !== 11) return forms[0];
  if (n10 >= 2 && n10 <= 4 && (n100 < 10 || n100 >= 20)) return forms[1];
  return forms[2];
}
