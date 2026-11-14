import { useMemo } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { publicApi } from "../../api/endpoints";
import type { Match } from "../../api/types";
import { MatchDayList } from "../../components/match";
import { ErrorBox, Spinner, TeamAvatar } from "../../components/ui";
import { UPCOMING_STATUSES, formatDay } from "../../lib/format";

type Outcome = "w" | "d" | "l";

function outcomeFor(m: Match, teamId: number): Outcome | null {
  if (m.home_score === null || m.away_score === null) return null;
  const home = m.home_entry?.team.id === teamId;
  const my = home ? m.home_score : m.away_score;
  const their = home ? m.away_score : m.home_score;
  return my > their ? "w" : my < their ? "l" : "d";
}

const OUTCOME_TEXT: Record<Outcome, string> = { w: "Победа", d: "Ничья", l: "Поражение" };
const OUTCOME_LETTER: Record<Outcome, string> = { w: "В", d: "Н", l: "П" };

/** Карточка команды в турнире (по макету «Карточка команды»). */
export function TeamPage() {
  const params = useParams();
  const tournamentId = Number(params.id);
  const teamId = Number(params.teamId);
  const navigate = useNavigate();

  const team = useQuery({ queryKey: ["team", teamId], queryFn: () => publicApi.team(teamId) });
  const tournament = useQuery({
    queryKey: ["tournament", tournamentId],
    queryFn: () => publicApi.tournament(tournamentId),
  });
  const matches = useQuery({
    queryKey: ["tournament", tournamentId, "matches", { team: teamId }],
    queryFn: () => publicApi.matches(tournamentId, { team: teamId }),
  });
  const standings = useQuery({
    queryKey: ["tournament", tournamentId, "standings"],
    queryFn: () => publicApi.standings(tournamentId),
  });

  const played = useMemo(
    () =>
      (matches.data ?? [])
        .filter((m) => ["confirmed", "technical"].includes(m.status))
        .sort((a, b) => (b.scheduled_at ?? "").localeCompare(a.scheduled_at ?? "")),
    [matches.data],
  );
  const upcoming = useMemo(
    () => (matches.data ?? []).filter((m) => UPCOMING_STATUSES.includes(m.status)),
    [matches.data],
  );

  const row = standings.data?.stages
    .flatMap((s) => [...s.items, ...s.groups.flatMap((g) => g.items)])
    .find((r) => r.team_id === teamId);

  if (team.isLoading) return <Spinner />;
  if (team.error)
    return (
      <div className="container page">
        <ErrorBox error={team.error} onRetry={() => team.refetch()} />
      </div>
    );
  const t = team.data!;
  const form = played
    .slice(0, 5)
    .map((m) => outcomeFor(m, teamId))
    .filter(Boolean) as Outcome[];

  return (
    <>
      <div className="t-band" style={{ background: "linear-gradient(90deg, #00784c, #00c27a)" }}>
        <div className="container">
          <TeamAvatar id={t.id} name={t.name} />
          <div>
            <h1 style={{ textTransform: "none" }}>{t.name}</h1>
            <div className="meta">
              {[t.captain ? `Капитан: ${t.captain.name}` : null, t.city].filter(Boolean).join(" · ")}
            </div>
            {form.length > 0 && (
              <div className="row small" style={{ gap: 8, marginTop: 6 }}>
                Форма:
                <span className="form-dots">
                  {form.map((o, i) => (
                    <span key={i} className={o} title={OUTCOME_TEXT[o]}>
                      {OUTCOME_LETTER[o]}
                    </span>
                  ))}
                </span>
              </div>
            )}
          </div>
          {row && (
            <div className="right">
              <span className="badge badge-accent">{row.position} место</span>
            </div>
          )}
        </div>
      </div>

      <div className="container page stack" style={{ maxWidth: 900 }}>
        <div className="breadcrumbs">
          <Link to={`/tournaments/${tournamentId}`}>{tournament.data?.name ?? "Турнир"}</Link>
          {" › "}
          <Link to={`/tournaments/${tournamentId}?tab=teams`}>Команды</Link>
        </div>

        <section className="card">
          <div className="card-title center">Последние матчи</div>
          {played.length ? (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>Дата</th>
                    <th>Соперник</th>
                    <th className="num">Счёт</th>
                    <th className="num">Результат</th>
                  </tr>
                </thead>
                <tbody>
                  {played.map((m) => {
                    const home = m.home_entry?.team.id === teamId;
                    const opp = (home ? m.away_entry : m.home_entry)?.team.name ?? "—";
                    const o = outcomeFor(m, teamId);
                    return (
                      <tr key={m.id} className="clickable" onClick={() => navigate(`/matches/${m.id}`)}>
                        <td className="nowrap">{formatDay(m.scheduled_at, m.tournament.timezone)}</td>
                        <td>{opp}</td>
                        <td className="num">
                          {home ? `${m.home_score}:${m.away_score}` : `${m.away_score}:${m.home_score}`}
                        </td>
                        <td className="num">{o ? OUTCOME_TEXT[o] : "—"}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="empty">Сыгранных матчей пока нет</div>
          )}
        </section>

        {upcoming.length > 0 && (
          <section className="stack-sm">
            <h2>Ближайшие матчи</h2>
            <MatchDayList matches={upcoming} />
          </section>
        )}

        {row && (
          <section className="stack-sm">
            <h2>Статистика игр</h2>
            <div className="stat-tiles">
              <div className="stat-tile">
                <b>{row.played}</b>
                <span>игр сыграно</span>
              </div>
              <div className="stat-tile">
                <b>{row.wins}</b>
                <span>побед</span>
              </div>
              <div className="stat-tile">
                <b>{row.losses}</b>
                <span>поражений</span>
              </div>
              <div className="stat-tile">
                <b>{row.draws}</b>
                <span>ничьих</span>
              </div>
              <div className="stat-tile">
                <b>{row.goals_for}</b>
                <span>мячей забито</span>
              </div>
              <div className="stat-tile">
                <b>{row.goals_against}</b>
                <span>пропущено</span>
              </div>
            </div>
          </section>
        )}
      </div>
    </>
  );
}
