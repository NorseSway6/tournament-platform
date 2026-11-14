// HTTP-клиент: добавляет токен, при 401 один раз обновляет его и повторяет запрос.
import type { ApiErrorBody, AuthTokenPair } from "./types";

export const API_BASE: string = import.meta.env.VITE_API_URL || "/api/v1";

const STORAGE_KEY = "tp.auth";

interface StoredTokens {
  access: string;
  refresh: string;
}

let tokens: StoredTokens | null = readTokens();
const listeners = new Set<() => void>();

function readTokens(): StoredTokens | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? (JSON.parse(raw) as StoredTokens) : null;
  } catch {
    return null;
  }
}

export function setTokens(pair: AuthTokenPair | null) {
  tokens = pair ? { access: pair.access_token, refresh: pair.refresh_token } : null;
  try {
    if (tokens) localStorage.setItem(STORAGE_KEY, JSON.stringify(tokens));
    else localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* хранилище недоступно — токены живут только в памяти */
  }
  listeners.forEach((fn) => fn());
}

export function getRefreshToken() {
  return tokens?.refresh ?? null;
}

export function hasTokens() {
  return tokens !== null;
}

/** Подписка на изменение токенов (вход/выход/обновление). */
export function onTokensChange(fn: () => void) {
  listeners.add(fn);
  return () => {
    listeners.delete(fn);
  };
}

export class ApiError extends Error {
  status: number;
  code: string;
  problems: ApiErrorBody["problems"];

  constructor(status: number, body: Partial<ApiErrorBody> | null) {
    super(body?.message || `Ошибка ${status}`);
    this.status = status;
    this.code = body?.code || "unknown";
    this.problems = body?.problems ?? null;
  }
}

let refreshing: Promise<boolean> | null = null;

async function refreshTokens(): Promise<boolean> {
  if (!tokens) return false;
  if (!refreshing) {
    const refresh = tokens.refresh;
    refreshing = fetch(`${API_BASE}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refresh }),
    })
      .then(async (res) => {
        if (!res.ok) {
          setTokens(null);
          return false;
        }
        setTokens((await res.json()) as AuthTokenPair);
        return true;
      })
      .catch(() => false)
      .finally(() => {
        refreshing = null;
      });
  }
  return refreshing;
}

type Query = Record<string, string | number | boolean | null | undefined>;

export interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  query?: Query;
  /** false — не отправлять токен (публичные запросы). */
  auth?: boolean;
}

function buildUrl(path: string, query?: Query) {
  const url = `${API_BASE}${path}`;
  if (!query) return url;
  const params = new URLSearchParams();
  Object.entries(query).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") params.set(k, String(v));
  });
  const qs = params.toString();
  return qs ? `${url}?${qs}` : url;
}

export async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, query, auth = true } = opts;

  const doFetch = () => {
    const headers: Record<string, string> = { Accept: "application/json" };
    if (body !== undefined) headers["Content-Type"] = "application/json";
    if (auth && tokens) headers.Authorization = `Bearer ${tokens.access}`;
    return fetch(buildUrl(path, query), {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  };

  let res: Response;
  try {
    res = await doFetch();
  } catch {
    throw new ApiError(0, { code: "network", message: "Нет связи с сервером" });
  }

  if (res.status === 401 && auth && tokens && !path.startsWith("/auth/")) {
    if (await refreshTokens()) res = await doFetch();
  }

  if (res.status === 204) return undefined as T;

  const text = await res.text();
  const data = text ? safeJson(text) : null;
  if (!res.ok) throw new ApiError(res.status, data as ApiErrorBody | null);
  return data as T;
}

function safeJson(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

/** Понятное пользователю сообщение об ошибке. */
export function errorMessage(err: unknown): string {
  if (err instanceof ApiError) {
    const known = ERROR_TEXTS[err.code];
    if (known) return known;
    if (err.status === 422 && err.problems?.length) {
      return err.problems.map((p) => p.message).join("; ");
    }
    if (err.status === 0) return "Нет связи с сервером. Проверьте интернет.";
    if (err.status === 401) return "Нужно войти в аккаунт.";
    if (err.status === 403) return "Недостаточно прав для этого действия.";
    if (err.status === 404) return "Не найдено.";
    if (err.status >= 500) return "Ошибка сервера. Попробуйте ещё раз позже.";
    return err.message;
  }
  return err instanceof Error ? err.message : "Неизвестная ошибка";
}

const ERROR_TEXTS: Record<string, string> = {
  network: "Нет связи с сервером. Проверьте интернет.",
  identifier_taken: "Пользователь с таким логином или почтой уже существует.",
  slug_taken: "Такой адрес уже занят, попробуйте другое название.",
  entry_exists: "Эта команда уже подала заявку на турнир.",
  registration_closed: "Регистрация на турнир закрыта.",
  registration_deadline_passed: "Срок подачи заявок истёк.",
  roster_closed: "Состав больше нельзя менять: регистрация закрыта.",
  player_already_in_tournament: "Один из игроков уже заявлен за другую команду в этом турнире.",
  entry_not_pending: "Решение по заявке уже принято.",
  entry_decision_closed: "Сейчас нельзя принимать решения по заявкам.",
  invalid_status_transition: "Это действие недоступно в текущем статусе турнира.",
  lineup_closed: "Заявку на матч уже нельзя менять.",
  lineup_not_editable: "Заявка на матч уже отправлена.",
  lineup_missing: "Сначала сохраните состав.",
  lease_taken: "Матч сейчас ведёт другой судья.",
  lease_status_invalid: "Матч нельзя вести в текущем статусе.",
  lease_expired: "Сессия ведения матча истекла — переподключаюсь.",
  lease_invalid: "Сессия ведения матча недействительна — откройте протокол заново.",
  match_not_live: "Матч не идёт — события добавлять нельзя.",
  match_not_finished: "Матч ещё не завершён.",
  officials_locked: "Судью нельзя поменять после начала матча.",
  participants_missing: "У матча не указаны команды.",
  venue_name_taken: "Площадка с таким названием уже есть.",
  regulation_frozen: "Регламент нельзя менять после старта турнира.",
};
