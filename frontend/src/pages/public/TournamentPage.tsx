import { useMemo } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { publicApi } from "../../api/endpoints";
import type { Match } from "../../api/types";
import { MatchDayList, ScoreBanner } from "../../components/match";
import { StandingsView } from "../../components/StandingsTable";
import { TournamentBand } from "../../components/TournamentBand";
import { Empty, ErrorBox, QueryView, Spinner, TeamAvatar } from "../../components/ui";
import { RESULT_STATUSES, UPCOMING_STATUSES, formatDateTime } from "../../lib/format";

const TABS = [
  { key: "table", label: "Таблица" },
  { key: "matches", label: "Матчи" },
  { key: "teams", label: "Команды" },
] as const;
type TabKey = (typeof TABS)[number]["key"];

export function TournamentPage() {
  const id = Number(useParams().id);
  const [params, setParams] = useSearchParams();
  const tab = (params.get("tab") as TabKey) || "table";
  const matchFilter = params.get("filter") === "results" ? "results" : "schedule";

  const tournament = useQuery({ queryKey: ["tournament", id], queryFn: () => publicApi.tournament(id) });
  const teams = useQuery({ queryKey: ["tournament", id, "teams"], queryFn: () => publicApi.teams(id) });
  const matches = useQuery({
    queryKey: ["tournament", id, "matches"],
    queryFn: () => publicApi.matches(id),
    refetchInterval: 30_000,
  });
  const standings = useQuery({
    queryKey: ["tournament", id, "standings"],
    queryFn: () => publicApi.standings(id),
    enabled: tab === "table",
    refetchInterval: 30_000,
  });

  const live = useMemo(() => (matches.data ?? []).filter((m) => m.status === "live"), [matches.data]);
  const filtered = useMemo(() => {
    const all = matches.data ?? [];
    if (matchFilter === "schedule") return all.filter((m) => UPCOMING_STATUSES.includes(m.status));
    return all
      .filter((m) => RESULT_STATUSES.includes(m.status))
      .slice()
      .sort(byDateDesc);
  }, [matches.data, matchFilter]);

  const setTab = (key: TabKey) => {
    const next = new URLSearchParams(params);
    next.set("tab", key);
    setParams(next, { replace: true });
  };
  const setFilter = (f: "schedule" | "results") => {
    const next = new URLSearchParams(params);
    next.set("tab", "matches");
    next.set("filter", f);
    setParams(next, { replace: true });
  };

  if (tournament.isLoading) return <Spinner />;
  if (tournament.error)
    return (
      <div className="container page">
        <ErrorBox error={tournament.error} onRetry={() => tournament.refetch()} />
      </div>
    );
  const t = tournament.data!;

  return (
    <>
      <TournamentBand
        name={t.name}
        season={t.season}
        status={t.status}
        startsOn={t.starts_on}
        endsOn={t.ends_on}
        teamsCount={teams.data?.total}
        right={<span className="small">{t.organization.name}</span>}
      />
      <div className="container page stack">
        {live.map((m) => (
          <Link key={m.id} to={`/matches/${m.id}`} style={{ color: "inherit", textDecoration: "none" }}>
            <ScoreBanner match={m} topRight={m.round?.name} />
          </Link>
        ))}

        {t.status === "registration" && (
          <div className="alert alert-success row-between">
            <span>
              Идёт регистрация команд
              {t.registration_deadline
                ? ` до ${formatDateTime(t.registration_deadline, t.organization.timezone)}`
                : ""}
              .
            </span>
            <Link to={`/captain/apply?tournament=${t.id}`} className="btn btn-sm">
              Подать заявку
            </Link>
          </div>
        )}

        <div>
          <div className="tabs" role="tablist">
            {TABS.map((tb) => (
              <button
                key={tb.key}
                role="tab"
                aria-selected={tab === tb.key}
                className={`tab${tab === tb.key ? " active" : ""}`}
                onClick={() => setTab(tb.key)}
              >
                {tb.label}
              </button>
            ))}
          </div>

          {tab === "table" && (
            <div className="card">
              <QueryView query={standings}>{(s) => <StandingsView standings={s} />}</QueryView>
            </div>
          )}

          {tab === "matches" && (
            <div className="stack">
              <div className="chips">
                <button
                  className={`chip${matchFilter === "schedule" ? " active" : ""}`}
                  onClick={() => setFilter("schedule")}
                >
                  Расписание
                </button>
                <button
                  className={`chip${matchFilter === "results" ? " active" : ""}`}
                  onClick={() => setFilter("results")}
                >
                  Результаты
                </button>
              </div>
              <QueryView query={matches}>
                {() => (
                  <MatchDayList
                    matches={filtered}
                    emptyText={
                      matchFilter === "schedule" ? "Предстоящих матчей нет" : "Сыгранных матчей пока нет"
                    }
                  />
                )}
              </QueryView>
            </div>
          )}

          {tab === "teams" && (
            <QueryView query={teams}>
              {(data) =>
                data.items.length ? (
                  <div className="t-grid">
                    {data.items.map((team) => (
                      <Link
                        key={team.id}
                        to={`/tournaments/${id}/teams/${team.id}`}
                        className="card card-link row"
                        style={{ flexWrap: "nowrap" }}
                      >
                        <TeamAvatar id={team.id} name={team.name} />
                        <div>
                          <div className="bold">{team.name}</div>
                          {team.city && <div className="muted small">{team.city}</div>}
                        </div>
                      </Link>
                    ))}
                  </div>
                ) : (
                  <Empty>Команды ещё не приняты в турнир</Empty>
                )
              }
            </QueryView>
          )}
        </div>
      </div>
    </>
  );
}

function byDateDesc(a: Match, b: Match) {
  return (b.scheduled_at ?? "").localeCompare(a.scheduled_at ?? "");
}
