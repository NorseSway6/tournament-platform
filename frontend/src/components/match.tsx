import { Link } from "react-router-dom";
import type { Match, MatchEvent } from "../api/types";
import {
  dayKey,
  formatDayHeader,
  formatTime,
  scoreText,
  teamColor,
  teamName,
} from "../lib/format";
import { MatchStatusBadge, TeamAvatar } from "./ui";

/** Строка матча в списке (как в макете «Расписание»). */
export function MatchRow({ match, to }: { match: Match; to?: string }) {
  const tz = match.tournament.timezone;
  return (
    <Link
      to={to ?? `/matches/${match.id}`}
      className={`match-row${match.status === "live" ? " live" : ""}`}
    >
      <span className="when">
        <MatchStatusBadge status={match.status} />
        <b>{formatTime(match.scheduled_at, tz)}</b>
      </span>
      <span className="home">{teamName(match, "home")}</span>
      <span className="sc">{scoreText(match)}</span>
      <span className="away">{teamName(match, "away")}</span>
      <span className="where">
        {match.venue ? `📍 ${match.venue.name}` : match.round?.name ?? ""}
      </span>
    </Link>
  );
}

/** Матчи, сгруппированные по дням. */
export function MatchDayList({
  matches,
  linkFor,
  emptyText = "Матчей нет",
}: {
  matches: Match[];
  linkFor?: (m: Match) => string;
  emptyText?: string;
}) {
  if (!matches.length) return <div className="empty">{emptyText}</div>;
  const groups = new Map<string, Match[]>();
  for (const m of matches) {
    const key = m.scheduled_at ? dayKey(m.scheduled_at, m.tournament.timezone) : "none";
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(m);
  }
  return (
    <div className="stack">
      {[...groups.entries()].map(([key, items]) => (
        <section key={key} className="day-group">
          <div className="head">
            {key === "none"
              ? "Дата не назначена"
              : formatDayHeader(items[0].scheduled_at!, items[0].tournament.timezone)}
          </div>
          <div className="body">
            {items.map((m) => (
              <MatchRow key={m.id} match={m} to={linkFor?.(m)} />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

/** Большой баннер со счётом (как LIVE-блок в макете главной). */
export function ScoreBanner({ match, topLeft, topRight }: {
  match: Match;
  topLeft?: React.ReactNode;
  topRight?: React.ReactNode;
}) {
  const home = match.home_entry?.team;
  const away = match.away_entry?.team;
  return (
    <div
      className="score-banner"
      style={
        {
          "--home": home ? teamColor(home.id) : "#5b6b79",
          "--away": away ? teamColor(away.id) : "#5b6b79",
        } as React.CSSProperties
      }
    >
      <div className="top">
        <span>{topLeft ?? <MatchStatusBadge status={match.status} />}</span>
        <span>{topRight}</span>
      </div>
      <div className="main">
        <div className="team">
          {home && <TeamAvatar id={home.id} name={home.name} />}
          <span>{teamName(match, "home")}</span>
        </div>
        <div className="score">{scoreText(match)}</div>
        <div className="team away">
          {away && <TeamAvatar id={away.id} name={away.name} />}
          <span>{teamName(match, "away")}</span>
        </div>
      </div>
    </div>
  );
}

export const EVENT_LABEL: Partial<Record<MatchEvent["type"], string>> = {
  goal: "Гол",
  own_goal: "Автогол",
  yellow: "Жёлтая карточка",
  red: "Красная карточка",
  sub: "Замена",
  pause: "Пауза",
  resume: "Возобновление",
  period_start: "Начало периода",
  period_end: "Конец периода",
  finish: "Матч завершён",
  note: "Заметка",
};

export function EventIcon({ type }: { type: MatchEvent["type"] }) {
  if (type === "goal" || type === "own_goal") return <span>⚽</span>;
  if (type === "yellow") return <span className="card-icon yellow" />;
  if (type === "red") return <span className="card-icon red" />;
  if (type === "finish") return <span>🏁</span>;
  if (type === "sub") return <span>🔄</span>;
  return <span>•</span>;
}

/** События, которые показываем в ленте (без служебных). */
export function visibleEvents(events: MatchEvent[]) {
  return events.filter((e) => e.type !== "void" && e.type !== "review_ok");
}

export function eventMinute(e: MatchEvent) {
  if (e.minute !== null && e.minute !== undefined) return `${e.minute + 1}'`;
  if (e.clock_ms !== null && e.clock_ms !== undefined) return `${Math.floor(e.clock_ms / 60000) + 1}'`;
  return "";
}

/** Лента событий матча; новые сверху. */
export function EventFeed({
  match,
  events,
  onDelete,
  emptyText = "Событий пока нет",
}: {
  match: Match;
  events: MatchEvent[];
  onDelete?: (e: MatchEvent) => void;
  emptyText?: string;
}) {
  // Удалённые судьёй события не показываем.
  const list = visibleEvents(events)
    .filter((e) => !e.voided)
    .slice()
    .reverse();
  if (!list.length) return <div className="empty small">{emptyText}</div>;
  const teamOf = (entryId: number | null) =>
    entryId === match.home_entry?.id
      ? match.home_entry.team.name
      : entryId === match.away_entry?.id
        ? match.away_entry.team.name
        : "";
  return (
    <ul className="events">
      {list.map((e) => (
        <li key={e.id} className={e.voided ? "voided" : ""}>
          <span className="min">{eventMinute(e)}</span>
          <span className="ico">
            <EventIcon type={e.type} />
          </span>
          <span className="grow">
            <b>{EVENT_LABEL[e.type] ?? e.type}</b>
            {e.player && (
              <>
                {" — "}
                {e.player.name} <span className="muted">№{e.player.number}</span>
              </>
            )}
            {teamOf(e.entry_id) && <span className="muted"> ({teamOf(e.entry_id)})</span>}
          </span>
          {onDelete && e.type !== "finish" && (
            <button
              className="icon-btn"
              title="Удалить событие"
              aria-label="Удалить событие"
              onClick={() => onDelete(e)}
            >
              ✕
            </button>
          )}
        </li>
      ))}
    </ul>
  );
}
