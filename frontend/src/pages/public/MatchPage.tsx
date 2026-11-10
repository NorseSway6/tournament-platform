import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { publicApi } from "../../api/endpoints";
import { EventFeed, ScoreBanner } from "../../components/match";
import { ErrorBox, Spinner } from "../../components/ui";
import { formatDateTime } from "../../lib/format";

const POLL_MS = 10_000;

export function MatchPage() {
  const id = Number(useParams().id);
  const match = useQuery({
    queryKey: ["match", id],
    queryFn: () => publicApi.match(id),
    // Счёт и лента обновляются раз в 10 секунд, пока матч не подтверждён.
    refetchInterval: (q) =>
      q.state.data && ["confirmed", "cancelled", "technical"].includes(q.state.data.status)
        ? false
        : POLL_MS,
  });

  if (match.isLoading) return <Spinner />;
  if (match.error)
    return (
      <div className="container page">
        <ErrorBox error={match.error} onRetry={() => match.refetch()} />
      </div>
    );
  const m = match.data!;
  const tz = m.tournament.timezone;

  return (
    <div className="container page stack" style={{ maxWidth: 860 }}>
      <div className="breadcrumbs">
        <Link to={`/tournaments/${m.tournament.id}`}>{m.tournament.name}</Link>
        {" › "}
        <Link to={`/tournaments/${m.tournament.id}?tab=matches`}>Матчи</Link>
      </div>
      <ScoreBanner match={m} topRight={[m.stage.name, m.round?.name].filter(Boolean).join(" · ")} />

      <div className="card row" style={{ gap: 24 }}>
        <div>
          <div className="label">Начало</div>
          <div>{formatDateTime(m.scheduled_at, tz)}</div>
        </div>
        {m.venue && (
          <div>
            <div className="label">Площадка</div>
            <div>
              {m.venue.name}
              {m.venue.address && <span className="muted"> · {m.venue.address}</span>}
            </div>
          </div>
        )}
        {m.status === "live" && (
          <div className="muted small" style={{ marginLeft: "auto" }}>
            Обновляется автоматически
          </div>
        )}
      </div>

      <section className="card">
        <div className="card-title">Ход матча</div>
        <EventFeed
          match={m}
          events={m.events}
          emptyText={m.status === "scheduled" ? "Матч ещё не начался" : "Событий пока нет"}
        />
      </section>
    </div>
  );
}
