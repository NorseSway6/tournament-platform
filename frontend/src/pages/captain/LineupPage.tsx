import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { captainApi, publicApi } from "../../api/endpoints";
import { ErrorBox, FormError, LineupStatusBadge, Spinner } from "../../components/ui";
import { ScoreBanner } from "../../components/match";
import { formatDateTime } from "../../lib/format";
import { playerFullName } from "../../lib/misc";

/** Заявка на матч: галочками отмечаем игроков, выбираем капитана, отправляем. */
export function LineupPage() {
  const matchId = Number(useParams().id);
  const qc = useQueryClient();
  const lineup = useQuery({
    queryKey: ["captain", "lineup", matchId],
    queryFn: () => captainApi.lineup(matchId),
  });
  const match = useQuery({
    queryKey: ["match", matchId],
    queryFn: () => publicApi.match(matchId),
    retry: false,
  });

  const [selected, setSelected] = useState<Set<number> | null>(null);
  const [captainId, setCaptainId] = useState<number | null>(null);
  const [comment, setComment] = useState("");

  useEffect(() => {
    if (lineup.data && selected === null) {
      const sel = lineup.data.players.filter((p) => p.selected);
      setSelected(new Set(sel.map((p) => p.entry_player_id)));
      setCaptainId(sel.find((p) => p.role === "captain")?.entry_player_id ?? null);
      setComment(lineup.data.comment ?? "");
    }
  }, [lineup.data, selected]);

  const submit = useMutation({
    mutationFn: async () => {
      const ids = [...(selected ?? [])];
      await captainApi.saveLineup(matchId, {
        players: ids.map((id) => ({
          entry_player_id: id,
          is_starter: true,
          role: id === captainId ? "captain" : "player",
        })),
        comment: comment.trim(),
      });
      return captainApi.submitLineup(matchId);
    },
    onSuccess: () => {
      setSelected(null);
      qc.invalidateQueries({ queryKey: ["captain", "lineup", matchId] });
    },
  });

  const players = useMemo(
    () => (lineup.data?.players ?? []).slice().sort((a, b) => a.number - b.number),
    [lineup.data],
  );

  if (lineup.isLoading || (lineup.data && selected === null)) return <Spinner />;
  if (lineup.error)
    return (
      <div className="container page">
        <ErrorBox error={lineup.error} onRetry={() => lineup.refetch()} />
      </div>
    );
  const data = lineup.data!;
  const m = match.data;
  const matchOpen = !m || ["scheduled", "lineups_open"].includes(m.status);
  const editable = matchOpen && ["draft", "rejected"].includes(data.status);
  const sel = selected ?? new Set<number>();

  const toggle = (id: number) => {
    const next = new Set(sel);
    if (next.has(id)) {
      next.delete(id);
      if (captainId === id) setCaptainId(null);
    } else next.add(id);
    setSelected(next);
  };

  const problem = !sel.size
    ? "Отметьте игроков, которые будут играть."
    : !captainId || !sel.has(captainId)
      ? "Выберите капитана на матч (кнопка «К» рядом с игроком)."
      : null;

  return (
    <div className="container page stack" style={{ maxWidth: 760 }}>
      <div className="breadcrumbs">
        <Link to="/captain">Кабинет капитана</Link> › Заявка на матч
      </div>
      {m && (
        <ScoreBanner
          match={m}
          topRight={formatDateTime(m.scheduled_at, m.tournament.timezone)}
        />
      )}

      <div className="row-between">
        <h1>Заявка на матч</h1>
        <LineupStatusBadge status={data.status} />
      </div>

      {data.status === "submitted" && (
        <div className="alert alert-success">Заявка отправлена. Состав виден судье матча.</div>
      )}
      {data.status === "accepted" && <div className="alert alert-success">Заявка принята организатором.</div>}
      {data.status === "rejected" && (
        <div className="alert alert-error">Заявка отклонена организатором. Исправьте состав и отправьте снова.</div>
      )}
      {!matchOpen && data.status === "draft" && (
        <div className="alert alert-warn">Матч уже начался — заявку на него подать нельзя.</div>
      )}

      <section className="card stack-sm">
        <div className="row-between">
          <div className="card-title" style={{ marginBottom: 0 }}>
            Игроки команды
          </div>
          <span className="muted small">Отмечено: {sel.size}</span>
        </div>
        {players.length ? (
          <div className="choice-list" style={{ maxHeight: "none" }}>
            {players.map((p) => {
              const on = sel.has(p.entry_player_id);
              return (
                <div key={p.entry_player_id} className={`choice${on ? " active" : ""}`}>
                  <label className="checkbox" style={{ flex: 1 }}>
                    <input
                      type="checkbox"
                      checked={on}
                      disabled={!editable}
                      onChange={() => toggle(p.entry_player_id)}
                    />
                    <span className="no">{p.number}</span>
                    <span>{playerFullName(p)}</span>
                  </label>
                  {(editable ? on : p.entry_player_id === captainId) && (
                    <button
                      type="button"
                      className={`btn btn-sm ${captainId === p.entry_player_id ? "" : "btn-outline"}`}
                      disabled={!editable}
                      title="Капитан на матч"
                      onClick={() => setCaptainId(p.entry_player_id)}
                    >
                      К{captainId === p.entry_player_id ? " · капитан" : ""}
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        ) : (
          <div className="empty">
            В составе команды нет игроков. Добавьте их на странице «Состав» в кабинете капитана.
          </div>
        )}
      </section>

      <section className="card stack-sm">
        <div className="field">
          <label htmlFor="lineup-comment">Комментарий к заявке</label>
          {editable ? (
            <textarea
              id="lineup-comment"
              className="textarea"
              maxLength={2000}
              placeholder="Например: опоздает Петров, играем в синей форме"
              value={comment}
              onChange={(e) => setComment(e.target.value)}
            />
          ) : (
            <div>{comment || <span className="muted">Без комментария</span>}</div>
          )}
        </div>
      </section>

      {editable && (
        <>
          {problem && <div className="hint">{problem}</div>}
          <FormError error={submit.error} />
          <div>
            <button
              className="btn btn-lg"
              disabled={!!problem || submit.isPending}
              onClick={() => submit.mutate()}
            >
              {submit.isPending ? "Отправляю…" : "Отправить заявку на матч"}
            </button>
          </div>
        </>
      )}
    </div>
  );
}
