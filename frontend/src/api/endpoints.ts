// Все обращения к бэкенду собраны здесь, сгруппированы по ролям.
import { request } from "./client";
import type {
  AuthTokenPair,
  EntryCreated,
  EntryPlayerInput,
  EntryPlayers,
  JudgeLineups,
  JudgeOption,
  LineupCheck,
  LineupUpdateIn,
  ListOut,
  Match,
  MatchConfirmOut,
  MatchDetail,
  MatchEventAppendOut,
  MatchEventFields,
  MatchLease,
  MatchLineup,
  MatchStatus,
  Me,
  OfficialRole,
  OfficialsOut,
  Organization,
  OrganizerEntry,
  OrganizerMatch,
  OrganizerMatchIn,
  OrganizerTournament,
  OrganizerTournamentIn,
  Paged,
  PublicTeam,
  RegisterIn,
  Round,
  Stage,
  Standings,
  TeamOut,
  TodayOut,
  Tournament,
  TournamentStatus,
  Venue,
} from "./types";

// ---------- Вход ----------
export const authApi = {
  login: (identifier: string, password: string) =>
    request<AuthTokenPair>("/auth/login", {
      method: "POST",
      body: { identifier, password },
      auth: false,
    }),
  register: (data: RegisterIn) =>
    request<AuthTokenPair>("/auth/register", { method: "POST", body: data, auth: false }),
  logout: (refresh_token: string) =>
    request<void>("/auth/logout", { method: "POST", body: { refresh_token }, auth: false }),
  me: () => request<Me>("/me"),
};

// ---------- Публичная часть ----------
/** Загружает все страницы списка (бэкенд отдаёт максимум 100 за раз). */
async function fetchAllPages<T>(path: string, query: Record<string, string | number | undefined>) {
  const pageSize = 100;
  const first = await request<Paged<T>>(path, {
    query: { ...query, page: 1, page_size: pageSize },
    auth: false,
  });
  const items = [...first.items];
  const pages = Math.ceil(first.total / pageSize);
  for (let page = 2; page <= pages; page++) {
    const next = await request<Paged<T>>(path, {
      query: { ...query, page, page_size: pageSize },
      auth: false,
    });
    items.push(...next.items);
  }
  return items;
}

export const publicApi = {
  tournaments: (status?: Exclude<TournamentStatus, "draft">) =>
    fetchAllPages<Tournament>("/tournaments", { status }),
  tournament: (id: number) => request<Tournament>(`/tournaments/${id}`, { auth: false }),
  standings: (id: number) => request<Standings>(`/tournaments/${id}/standings`, { auth: false }),
  teams: (id: number) =>
    request<ListOut<TeamOut>>(`/tournaments/${id}/entries`, { auth: false }),
  matches: (id: number, params: { team?: number; status?: MatchStatus } = {}) =>
    fetchAllPages<Match>(`/tournaments/${id}/matches`, params),
  match: (id: number) => request<MatchDetail>(`/matches/${id}`, { auth: false }),
  team: (id: number) => request<PublicTeam>(`/teams/${id}`, { auth: false }),
  today: (timezone?: string) =>
    request<TodayOut>("/today", { query: { timezone }, auth: false }),
};

// ---------- Организатор ----------
export const organizerApi = {
  organizations: () => request<ListOut<Organization>>("/organizer/organizations"),
  createOrganization: (data: { slug: string; name: string; city?: string; timezone?: string }) =>
    request<Organization>("/organizer/organizations", { method: "POST", body: data }),
  addMember: (orgId: number, identifier: string, role: "organizer" | "referee") =>
    request<unknown>(`/organizer/organizations/${orgId}/members`, {
      method: "POST",
      body: { identifier, role },
    }),

  tournaments: (organizationId: number) =>
    request<ListOut<OrganizerTournament>>("/organizer/tournaments", {
      query: { organization_id: organizationId },
    }),
  tournament: (id: number) => request<OrganizerTournament>(`/organizer/tournaments/${id}`),
  createTournament: (data: OrganizerTournamentIn) =>
    request<OrganizerTournament>("/organizer/tournaments", { method: "POST", body: data }),
  transition: (id: number, action: "open-registration" | "start" | "finish") =>
    request<OrganizerTournament>(`/organizer/tournaments/${id}/${action}`, { method: "POST" }),

  entries: (tournamentId: number) =>
    request<ListOut<OrganizerEntry>>(`/organizer/tournaments/${tournamentId}/entries`),
  decideEntry: (entryId: number, status: "accepted" | "rejected", decision_comment = "") =>
    request<unknown>(`/organizer/entries/${entryId}`, {
      method: "PATCH",
      body: { status, decision_comment },
    }),

  stages: (tournamentId: number) =>
    request<ListOut<Stage>>(`/organizer/tournaments/${tournamentId}/stages`),
  createStage: (tournamentId: number, data: { ord: number; kind: Stage["kind"]; name: string }) =>
    request<Stage>(`/organizer/tournaments/${tournamentId}/stages`, { method: "POST", body: data }),
  rounds: (stageId: number) => request<ListOut<Round>>(`/organizer/stages/${stageId}/rounds`),

  venues: (orgId: number) => request<ListOut<Venue>>(`/organizer/organizations/${orgId}/venues`),
  createVenue: (orgId: number, data: { name: string; address?: string }) =>
    request<Venue>(`/organizer/organizations/${orgId}/venues`, { method: "POST", body: data }),
  judges: (orgId: number) =>
    request<ListOut<JudgeOption>>(`/organizer/organizations/${orgId}/judges`),

  createMatch: (tournamentId: number, data: OrganizerMatchIn) =>
    request<OrganizerMatch>(`/organizer/tournaments/${tournamentId}/matches`, {
      method: "POST",
      body: data,
    }),
  setOfficials: (matchId: number, officials: { official_id: number; role: OfficialRole }[]) =>
    request<OfficialsOut>(`/organizer/matches/${matchId}/officials`, {
      method: "PUT",
      body: { officials },
    }),
  cancelMatch: (matchId: number) =>
    request<OrganizerMatch>(`/organizer/matches/${matchId}/cancel`, { method: "POST" }),
};

// ---------- Капитан ----------
export const captainApi = {
  createTeam: (name: string, city = "") =>
    request<TeamOut>("/teams", { method: "POST", body: { name, city } }),
  applyToTournament: (tournamentId: number, teamId: number) =>
    request<EntryCreated>(`/tournaments/${tournamentId}/entries`, {
      method: "POST",
      body: { team_id: teamId },
    }),
  entryPlayers: (entryId: number) => request<EntryPlayers>(`/entries/${entryId}/players`),
  setEntryPlayers: (entryId: number, players: EntryPlayerInput[]) =>
    request<EntryPlayers>(`/entries/${entryId}/players`, { method: "PUT", body: { players } }),
  today: (timezone?: string) => request<TodayOut>("/me/today", { query: { timezone } }),
  lineup: (matchId: number) => request<MatchLineup>(`/matches/${matchId}/lineup`),
  saveLineup: (matchId: number, data: LineupUpdateIn) =>
    request<MatchLineup>(`/matches/${matchId}/lineup`, { method: "PUT", body: data }),
  submitLineup: (matchId: number) =>
    request<LineupCheck>(`/matches/${matchId}/lineup/submit`, { method: "POST" }),
};

// ---------- Судья ----------
export const judgeApi = {
  lineups: (matchId: number) => request<JudgeLineups>(`/matches/${matchId}/lineups`),
  lease: (matchId: number) => request<MatchLease>(`/matches/${matchId}/lease`, { method: "POST" }),
  renew: (matchId: number, lease_token: string) =>
    request<MatchLease>(`/matches/${matchId}/lease/renew`, {
      method: "POST",
      body: { lease_token },
    }),
  release: (matchId: number, lease_token: string) =>
    request<unknown>(`/matches/${matchId}/lease/release`, {
      method: "POST",
      body: { lease_token },
    }),
  addEvent: (matchId: number, lease_token: string, event: MatchEventFields) =>
    request<MatchEventAppendOut>(`/matches/${matchId}/events`, {
      method: "POST",
      body: { ...event, lease_token },
    }),
  confirm: (matchId: number, lease_token: string) =>
    request<MatchConfirmOut>(`/matches/${matchId}/confirm`, {
      method: "POST",
      body: { lease_token },
    }),
};
