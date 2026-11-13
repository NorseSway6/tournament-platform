import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { publicApi } from "../../api/endpoints";
import type { TournamentStatus } from "../../api/types";
import { MatchRow } from "../../components/match";
import { Empty, QueryView, TournamentStatusBadge } from "../../components/ui";
import { DEFAULT_TZ, formatDateRange } from "../../lib/format";

type Filter = "all" | Exclude<TournamentStatus, "draft">;
const FILTERS: { key: Filter; label: string }[] = [
  { key: "all", label: "Все" },
  { key: "ongoing", label: "Идут" },
  { key: "registration", label: "Регистрация" },
  { key: "finished", label: "Завершённые" },
];
const ORDER: Record<string, number> = { ongoing: 0, registration: 1, finished: 2 };

export function HomePage() {
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<Filter>("all");

  // Поиск по названию выполняет сервер; запрос уходит через 300 мс после ввода.
  useEffect(() => {
    const t = setTimeout(() => setQuery(search.trim()), 300);
    return () => clearTimeout(t);
  }, [search]);

  const tournaments = useQuery({
    queryKey: ["tournaments", { search: query }],
    queryFn: () => publicApi.tournaments(undefined, query),
    placeholderData: keepPreviousData,
  });
  const today = useQuery({
    queryKey: ["today"],
    queryFn: () => publicApi.today(DEFAULT_TZ),
    refetchInterval: 30_000,
  });

  const list = useMemo(() => {
    return (tournaments.data ?? [])
      .filter((t) => filter === "all" || t.status === filter)
      .sort(
        (a, b) =>
          (ORDER[a.status] ?? 9) - (ORDER[b.status] ?? 9) ||
          (b.starts_on ?? "").localeCompare(a.starts_on ?? "") ||
          a.name.localeCompare(b.name, "ru"),
      );
  }, [tournaments.data, filter]);

  return (
    <>
      <section className="hero">
        <div className="container">
          <h1>Любительские футбольные турниры</h1>
          <p>Расписание, результаты и таблицы турниров Екатеринбурга и Свердловской области</p>
        </div>
      </section>
      <div className="container page stack">
        {today.data && today.data.items.length > 0 && (
          <section className="card stack-sm">
            <div className="card-title" style={{ marginBottom: 4 }}>
              Матчи сегодня
            </div>
            {today.data.items.map((m) => (
              <MatchRow key={m.id} match={m} />
            ))}
          </section>
        )}

        <section className="stack">
          <div className="row-between">
            <h2>Турниры</h2>
            <div className="search">
              <input
                className="input"
                type="search"
                placeholder="Поиск по названию"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                aria-label="Поиск турнира по названию"
              />
            </div>
          </div>
          <div className="chips" role="tablist">
            {FILTERS.map((f) => (
              <button
                key={f.key}
                role="tab"
                aria-selected={filter === f.key}
                className={`chip${filter === f.key ? " active" : ""}`}
                onClick={() => setFilter(f.key)}
              >
                {f.label}
              </button>
            ))}
          </div>
          <QueryView query={tournaments}>
            {() =>
              list.length ? (
                <div className="t-grid">
                  {list.map((t) => (
                    <Link key={t.id} to={`/tournaments/${t.id}`} className="card card-link t-card">
                      <div className="trophy" aria-hidden="true">
                        🏆
                      </div>
                      <div className="stack-sm" style={{ gap: 4, minWidth: 0 }}>
                        <h3>{t.name}</h3>
                        <div className="muted small">
                          {t.organization.name}
                          {t.season ? ` · ${t.season}` : ""}
                        </div>
                        <div className="muted small">{formatDateRange(t.starts_on, t.ends_on)}</div>
                        <div>
                          <TournamentStatusBadge status={t.status} />
                        </div>
                      </div>
                    </Link>
                  ))}
                </div>
              ) : (
                <Empty>
                  {query ? `По запросу «${query}» ничего не найдено` : "Турниров пока нет"}
                </Empty>
              )
            }
          </QueryView>
        </section>
      </div>
    </>
  );
}
