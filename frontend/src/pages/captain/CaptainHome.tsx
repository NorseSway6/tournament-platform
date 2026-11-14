import { useMemo } from "react";
import { Link, useLocation } from "react-router-dom";
import { useQueries, useQuery } from "@tanstack/react-query";
import { captainApi, publicApi } from "../../api/endpoints";
import type { Match, MeTeam } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { MatchRow } from "../../components/match";
import { Empty, EntryStatusBadge, LineupStatusBadge, QueryView } from "../../components/ui";
import { UPCOMING_STATUSES, formatDateTime, scoreText, teamName } from "../../lib/format";

export function CaptainHome() {
  const { me } = useAuth();
  const location = useLocation();
  const flash = (location.state as { flash?: string } | null)?.flash;
  const teams = me?.roles.captain.teams ?? [];

  const today = useQuery({
    queryKey: ["captain", "today"],
    queryFn: () => captainApi.today(),
    enabled: teams.length > 0,
    refetchInterval: 30_000,
  });

  // Ближайшие матчи по всем принятым заявкам (из публичного расписания турниров).
  const accepted = teams.flatMap((t) =>
    t.entries.filter((e) => e.status === "accepted").map((e) => ({ team: t, entry: e })),
  );
  const upcomingQueries = useQueries({
    queries: accepted.map(({ team, entry }) => ({
      queryKey: ["tournament", entry.tournament_id, "matches", { team: team.id }],
      queryFn: () => publicApi.matches(entry.tournament_id, { team: team.id }),
      retry: false,
    })),
  });
  const todayIds = new Set(today.data?.items.map((m) => m.id));
  const upcoming = useMemo(
    () =>
      upcomingQueries
        .flatMap((q) => q.data ?? [])
        .filter((m) => UPCOMING_STATUSES.includes(m.status) && !todayIds.has(m.id))
        .sort((a, b) => (a.scheduled_at ?? "").localeCompare(b.scheduled_at ?? ""))
        .slice(0, 6),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [upcomingQueries.map((q) => q.dataUpdatedAt).join(), today.data],
  );

  if (!teams.length) {
    return (
      <div className="container page" style={{ maxWidth: 640 }}>
        {flash && <div className="alert alert-success">{flash}</div>}
        <div className="card stack center">
          <h1>Кабинет капитана</h1>
          <p className="muted" style={{ margin: 0 }}>
            Здесь вы подаёте заявку команды на турнир, заявляете состав на матчи и следите за статусами.
          </p>
          <div>
            <Link to="/captain/apply" className="btn btn-lg">
              Подать заявку на турнир
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="container page stack">
      {flash && <div className="alert alert-success">{flash}</div>}
      <div className="row-between">
        <h1>Кабинет капитана</h1>
        <Link to="/captain/apply" className="btn">
          + Заявка на турнир
        </Link>
      </div>

      <section className="stack-sm">
        <h2>Мой матч сегодня</h2>
        <QueryView query={today}>
          {(data) =>
            data.items.length ? (
              <div className="stack-sm">
                {data.items.map((m) => (
                  <TodayMatchCard key={m.id} match={m} />
                ))}
              </div>
            ) : (
              <div className="card">
                <Empty>Сегодня матчей нет</Empty>
              </div>
            )
          }
        </QueryView>
      </section>

      {upcoming.length > 0 && (
        <section className="stack-sm">
          <h2>Ближайшие матчи</h2>
          <div className="card stack-sm">
            {upcoming.map((m) => (
              <div key={m.id} className="stack-sm" style={{ gap: 4 }}>
                <MatchRow match={m} to={`/captain/matches/${m.id}`} />
              </div>
            ))}
            <span className="hint">Нажмите на матч, чтобы заявить состав.</span>
          </div>
        </section>
      )}

      <section className="stack-sm">
        <h2>Мои команды и заявки</h2>
        <div className="grid-2">
          {teams.map((t) => (
            <TeamCard key={t.id} team={t} />
          ))}
        </div>
      </section>
    </div>
  );
}

function TodayMatchCard({ match }: { match: Match }) {
  const lineup = useQuery({
    queryKey: ["captain", "lineup", match.id],
    queryFn: () => captainApi.lineup(match.id),
  });
  const tz = match.tournament.timezone;
  return (
    <div className="card stack-sm">
      <div className="row-between">
        <span className="muted small">
          {match.tournament.name} · {formatDateTime(match.scheduled_at, tz)}
          {match.venue && ` · ${match.venue.name}`}
        </span>
        {lineup.data ? <LineupStatusBadge status={lineup.data.status} /> : lineup.isLoading ? null : null}
      </div>
      <div className="row" style={{ justifyContent: "center", fontSize: 18, fontWeight: 600 }}>
        <span>{teamName(match, "home")}</span>
        <span style={{ fontSize: 22 }}>{scoreText(match)}</span>
        <span>{teamName(match, "away")}</span>
      </div>
      <div className="row" style={{ justifyContent: "center" }}>
        <Link to={`/captain/matches/${match.id}`} className="btn">
          {lineup.data && ["draft", "rejected"].includes(lineup.data.status) &&
          ["scheduled", "lineups_open"].includes(match.status)
            ? "Заявить состав на матч"
            : "Заявка на матч"}
        </Link>
        <Link to={`/matches/${match.id}`} className="btn btn-outline">
          Страница матча
        </Link>
      </div>
    </div>
  );
}

function TeamCard({ team }: { team: MeTeam }) {
  return (
    <div className="card stack-sm">
      <div className="card-title" style={{ marginBottom: 0 }}>
        {team.name}
      </div>
      {team.entries.length ? (
        team.entries.map((e) => (
          <div key={e.id} className="row-between" style={{ borderTop: "1px solid #eee", paddingTop: 8 }}>
            <div>
              <Link to={`/tournaments/${e.tournament_id}`}>{e.tournament_name}</Link>
              <div>
                <EntryStatusBadge status={e.status} />
              </div>
            </div>
            <Link to={`/captain/entries/${e.id}`} className="btn btn-sm btn-outline">
              Состав
            </Link>
          </div>
        ))
      ) : (
        <span className="muted small">Заявок на турниры нет</span>
      )}
    </div>
  );
}
