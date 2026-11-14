import { Link } from "react-router-dom";
import { useQueries } from "@tanstack/react-query";
import { publicApi } from "../../api/endpoints";
import type { MeJudgeMatch } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { MatchRow } from "../../components/match";
import { Empty, MatchStatusBadge } from "../../components/ui";
import { DEFAULT_TZ, formatDateTime, isToday } from "../../lib/format";

const DONE = ["confirmed", "cancelled", "technical"];

export function JudgeHome() {
  const { me } = useAuth();
  // GET /me/matches на бэкенде пока возвращает только «захваченные» матчи,
  // поэтому берём назначения судьи из /me и фильтруем по дате здесь.
  const all = me?.roles.judge.matches ?? [];
  const live = all.filter((m) => m.status === "live" || m.status === "finished");
  const today = all.filter((m) => !live.includes(m) && isToday(m.scheduled_at, DEFAULT_TZ) && !DONE.includes(m.status));
  const upcoming = all
    .filter((m) => !live.includes(m) && !today.includes(m) && !DONE.includes(m.status))
    .sort((a, b) => (a.scheduled_at ?? "").localeCompare(b.scheduled_at ?? ""));
  const past = all
    .filter((m) => DONE.includes(m.status))
    .sort((a, b) => (b.scheduled_at ?? "").localeCompare(a.scheduled_at ?? ""))
    .slice(0, 10);

  return (
    <div className="container page stack" style={{ maxWidth: 860 }}>
      <h1>Мои матчи</h1>
      {live.length > 0 && <Section title="Идут сейчас" items={live} />}
      <Section title="Мои матчи на сегодня" items={today} empty="На сегодня матчей нет" />
      {upcoming.length > 0 && <Section title="Ближайшие" items={upcoming} />}
      {past.length > 0 && <Section title="Прошедшие" items={past} />}
    </div>
  );
}

function Section({ title, items, empty }: { title: string; items: MeJudgeMatch[]; empty?: string }) {
  // Подтягиваем команды и площадку из публичной карточки матча.
  const details = useQueries({
    queries: items.map((m) => ({
      queryKey: ["match", m.id],
      queryFn: () => publicApi.match(m.id),
      retry: false,
      staleTime: 30_000,
    })),
  });
  return (
    <section className="stack-sm">
      <h2>{title}</h2>
      {items.length ? (
        <div className="card stack-sm">
          {items.map((m, i) => {
            const d = details[i]?.data;
            return d ? (
              <MatchRow key={m.id} match={d} to={`/judge/matches/${m.id}`} />
            ) : (
              <Link key={m.id} to={`/judge/matches/${m.id}`} className="match-row">
                <span className="when">
                  <MatchStatusBadge status={m.status} />
                </span>
                <span className="home">{m.tournament_name}</span>
                <span className="sc">—</span>
                <span className="away">Матч №{m.id}</span>
                <span className="where">{formatDateTime(m.scheduled_at)}</span>
              </Link>
            );
          })}
        </div>
      ) : (
        <div className="card">
          <Empty>{empty}</Empty>
        </div>
      )}
    </section>
  );
}
