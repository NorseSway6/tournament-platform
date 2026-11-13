// Типы ответов и запросов бэкенда (/api/v1). Сверены с OpenAPI-схемой бэкенда.

export type MatchStatus =
  | "scheduled"
  | "lineups_open"
  | "live"
  | "finished"
  | "confirmed"
  | "postponed"
  | "cancelled"
  | "technical";
export type MatchResultType = "played" | "tech_win_home" | "tech_win_away" | "walkover";
export type StageKind = "league" | "groups" | "playoff";
export type EntryStatus = "pending" | "accepted" | "rejected" | "withdrawn";
export type TournamentStatus = "draft" | "registration" | "ongoing" | "finished";
export type Visibility = "public" | "unlisted" | "private";
export type LineupStatus = "draft" | "submitted" | "accepted" | "rejected";
export type LineupRole = "player" | "captain";
export type OfficialRole = "referee" | "assistant_referee" | "fourth_official" | "delegate";
export type EventType =
  | "goal"
  | "own_goal"
  | "yellow"
  | "red"
  | "sub"
  | "period_start"
  | "period_end"
  | "pause"
  | "resume"
  | "finish"
  | "void"
  | "review_ok"
  | "note";
export type Period =
  | "first_half"
  | "half_time"
  | "second_half"
  | "extra_time_first"
  | "extra_time_second"
  | "penalties";

export interface Paged<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}
export interface ListOut<T> {
  items: T[];
  total: number;
}

export interface ApiErrorBody {
  code: string;
  message: string;
  problems: { location: (string | number)[]; message: string; code: string }[] | null;
}

// ---------- Auth ----------
export interface AuthUser {
  id: number;
  username: string;
  email: string | null;
  phone: string | null;
  display_name: string;
}
export interface AuthTokenPair {
  access_token: string;
  refresh_token: string;
  token_type: "Bearer";
  expires_in: number;
  refresh_expires_at: string;
  user: AuthUser;
}
export interface RegisterIn {
  username: string;
  password: string;
  email?: string | null;
  display_name?: string;
  first_name?: string;
  last_name?: string;
}

export interface MeTeam {
  id: number;
  name: string;
  city: string;
  entries: { id: number; tournament_id: number; tournament_name: string; status: EntryStatus }[];
}
export interface MeOrganization {
  id: number;
  slug: string;
  name: string;
  city: string;
  timezone: string;
  tournaments: { id: number; slug: string; name: string; status: TournamentStatus }[];
}
export interface MeJudgeMatch {
  id: number;
  tournament_id: number;
  tournament_name: string;
  status: MatchStatus;
  scheduled_at: string | null;
}
export interface Me {
  authenticated: boolean;
  profile: {
    id: number;
    username: string;
    display_name: string;
    first_name: string;
    last_name: string;
  } | null;
  roles: {
    captain: { enabled: boolean; teams: MeTeam[] };
    organizer: { enabled: boolean; organizations: MeOrganization[] };
    judge: { enabled: boolean; matches: MeJudgeMatch[] };
    admin: { enabled: boolean };
  };
}

// ---------- Public ----------
export interface Tournament {
  id: number;
  organization: { id: number; name: string; slug: string; timezone: string };
  slug: string;
  name: string;
  season: string;
  status: TournamentStatus;
  visibility: Visibility;
  registration_deadline: string | null;
  starts_on: string | null;
  ends_on: string | null;
  stages: {
    id: number;
    name: string;
    kind: StageKind;
    ord: number;
    groups: { id: number; name: string; ord: number }[];
    rounds: { id: number; name: string; ord: number }[];
  }[];
}

export interface EntrySummary {
  id: number;
  status: EntryStatus;
  team: { id: number; name: string; city: string };
}

export interface Match {
  id: number;
  tournament: { id: number; slug: string; name: string; timezone: string };
  stage: { id: number; name: string; kind: StageKind; ord: number };
  round: { id: number; name: string; ord: number } | null;
  group: { id: number; name: string; ord: number } | null;
  home_entry: EntrySummary | null;
  away_entry: EntrySummary | null;
  venue: { id: number; name: string; address: string } | null;
  scheduled_at: string | null;
  scheduled_end: string | null;
  duration_min: number;
  status: MatchStatus;
  result_type: MatchResultType;
  home_score: number | null;
  away_score: number | null;
  started_at: string | null;
  finished_at: string | null;
  confirmed_at: string | null;
}

export interface MatchEvent {
  id: string;
  seq: number;
  device_id: string | null;
  client_seq: number | null;
  type: EventType;
  entry_id: number | null;
  player: { entry_player_id: number; player_id: number; name: string; number: number } | null;
  related_entry_player_id: number | null;
  period: Period | null;
  clock_ms: number | null;
  minute: number | null;
  second: number | null;
  client_created_at: string | null;
  created_at: string;
  target_event_id: string | null;
  needs_review: boolean;
  source: "judge" | "organizer" | "system";
  voided: boolean;
}

export interface MatchDetail extends Match {
  events: MatchEvent[];
}

export interface StandingRow {
  position: number;
  entry_id: number;
  team_id: number;
  team_name: string;
  played: number;
  wins: number;
  draws: number;
  losses: number;
  goals_for: number;
  goals_against: number;
  goal_difference: number;
  points: number;
}
export interface Standings {
  tournament_id: number;
  stages: {
    stage_id: number;
    stage_name: string;
    stage_kind: StageKind;
    items: StandingRow[];
    groups: { group_id: number; group_name: string; items: StandingRow[] }[];
  }[];
  rules: {
    points_for_win: number;
    points_for_draw: number;
    points_for_loss: number;
    tie_breakers: string[];
  };
}

export interface PublicTeam {
  id: number;
  name: string;
  city: string;
  captain: { id: number; name: string } | null;
  tournaments: {
    id: number;
    slug: string;
    name: string;
    status: TournamentStatus;
    entry_status: EntryStatus;
  }[];
}

export interface TodayOut {
  date: string;
  timezone: string | null;
  items: Match[];
  total: number;
}

// ---------- Organizer ----------
export interface Organization {
  id: number;
  slug: string;
  name: string;
  description: string;
  city: string;
  timezone: string;
  contacts: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}
export interface Regulation {
  standings?: {
    points_for_win?: number;
    points_for_draw?: number;
    points_for_loss?: number;
    tie_breakers?: string[];
  };
  [key: string]: unknown;
}
export interface OrganizerTournament {
  id: number;
  organization_id: number;
  slug: string;
  name: string;
  season: string;
  status: TournamentStatus;
  visibility: Visibility;
  regulation: Regulation;
  registration_deadline: string | null;
  starts_on: string | null;
  ends_on: string | null;
  created_at: string;
  updated_at: string;
}
export interface OrganizerTournamentIn {
  organization_id: number;
  slug: string;
  name: string;
  season?: string;
  visibility?: Visibility;
  regulation?: Regulation;
  registration_deadline?: string | null;
  starts_on?: string | null;
  ends_on?: string | null;
}
export interface OrganizerEntry {
  id: number;
  tournament_id: number;
  team_id: number;
  team: { id: number; name: string; city: string };
  captain: { id: number; name: string } | null;
  submitted_at: string;
  player_count: number;
  decision_comment: string;
  status: EntryStatus;
}
export interface Stage {
  id: number;
  tournament_id: number;
  ord: number;
  kind: StageKind;
  name: string;
}
export interface Round {
  id: number;
  stage_id: number;
  ord: number;
  name: string;
}
export interface Venue {
  id: number;
  name: string;
  address: string;
  notes: string;
}
export interface JudgeOption {
  id: number;
  name: string;
}
export interface OrganizerMatchIn {
  stage_id: number;
  round_id?: number | null;
  group_id?: number | null;
  home_entry_id: number;
  away_entry_id: number;
  venue_id?: number | null;
  scheduled_at: string;
  duration_min?: number;
}
export interface OrganizerMatch {
  id: number;
  tournament_id: number;
  stage_id: number;
  round_id: number | null;
  group_id: number | null;
  home_entry_id: number | null;
  away_entry_id: number | null;
  venue_id: number | null;
  scheduled_at: string | null;
  scheduled_end: string | null;
  duration_min: number;
  status: MatchStatus;
  result_type: MatchResultType;
  home_score: number | null;
  away_score: number | null;
  finished_at: string | null;
}
export interface OfficialsOut {
  match_id: number;
  officials: { official_id: number; name: string; role: OfficialRole }[];
}

// ---------- Captain ----------
export interface TeamOut {
  id: number;
  name: string;
  city: string;
}
export interface EntryCreated {
  id: number;
  tournament_id: number;
  team: TeamOut;
  status: EntryStatus;
}
export interface EntryPlayerInput {
  player_id?: number | null;
  first_name?: string | null;
  last_name?: string | null;
  middle_name?: string;
  birth_date?: string | null;
  number: number;
}
export interface EntryPlayer {
  entry_player_id: number;
  player_id: number;
  first_name: string;
  last_name: string;
  middle_name: string;
  birth_date: string | null;
  number: number;
  status: "active" | "removed";
}
export interface EntryPlayers {
  entry_id: number;
  players: EntryPlayer[];
}
export interface MatchLineup {
  match_id: number;
  entry_id: number;
  lineup_id: number | null;
  status: LineupStatus;
  comment: string;
  players: {
    entry_player_id: number;
    player_id: number;
    first_name: string;
    last_name: string;
    middle_name: string;
    number: number;
    is_starter: boolean;
    role: LineupRole;
    selected: boolean;
  }[];
}
export interface LineupUpdateIn {
  players: { entry_player_id: number; is_starter?: boolean; role?: LineupRole }[];
  comment?: string;
}
export interface LineupCheck {
  lineup_id: number;
  match_id: number;
  entry_id: number;
  status: LineupStatus;
  valid: boolean;
  issues: string[];
  player_count: number;
  starters_count: number;
  captains_count: number;
}

// ---------- Judge ----------
export interface JudgeLineups {
  match_id: number;
  items: {
    entry_id: number;
    team_id: number;
    team_name: string;
    lineup_id: number | null;
    /** null — заявки на матч нет, в players тогда весь состав команды в турнире. */
    status: LineupStatus | null;
    comment: string;
    reject_reason: string;
    players: {
      entry_player_id: number;
      player_id: number;
      name: string;
      number: number;
      is_starter: boolean;
      role: LineupRole;
    }[];
  }[];
}
export interface MatchLease {
  match_id: number;
  lease_token: string;
  expires_at: string;
  expires_in_seconds: number;
}
export interface MatchEventFields {
  id: string;
  device_id: string;
  client_seq: number;
  type: EventType;
  entry_id?: number | null;
  entry_player_id?: number | null;
  related_entry_player_id?: number | null;
  period?: Period | null;
  clock_ms?: number | null;
  minute?: number | null;
  second?: number | null;
  client_created_at?: string | null;
  target_event_id?: string | null;
  needs_review?: boolean;
}
export interface MatchEventAppendOut {
  event: MatchEvent;
  home_score: number | null;
  away_score: number | null;
  last_seq: number;
}
export interface MatchConfirmOut {
  id: number;
  status: MatchStatus;
  home_score: number;
  away_score: number;
  confirmed_at: string;
}
