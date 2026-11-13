import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, errorMessage } from "../../api/client";
import { judgeApi, publicApi } from "../../api/endpoints";
import type { EventType, JudgeLineups, MatchDetail, MatchEvent, MatchEventFields } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { EVENT_LABEL, EventFeed, visibleEvents } from "../../components/match";
import { ErrorBox, FormError, MatchStatusBadge, Modal, Spinner } from "../../components/ui";
import { MATCH_STATUS, formatDateTime, scoreText, teamName } from "../../lib/format";
import { deviceId, uuid } from "../../lib/misc";

const RENEW_MS = 40_000;

type Picking = { type: EventType; entryId: number | null };

/** Экран протокола судьи (по мобильному макету из Wireframes). */
export function ProtocolPage() {
  const matchId = Number(useParams().id);
  const qc = useQueryClient();
  const { refreshMe } = useAuth();

  const match = useQuery({
    queryKey: ["match", matchId],
    queryFn: () => publicApi.match(matchId),
    refetchInterval: (q) => (q.state.data?.status === "live" ? 10_000 : false),
    retry: false,
  });
  const lineups = useQuery({
    queryKey: ["judge", "lineups", matchId],
    queryFn: () => judgeApi.lineups(matchId),
  });

  const lease = useRef<string | null>(null);
  const clientSeq = useRef(0);
  const [leaseError, setLeaseError] = useState<unknown>(null);
  const [actionError, setActionError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [picking, setPicking] = useState<Picking | null>(null);
  const [deleting, setDeleting] = useState<MatchEvent | null>(null);
  const [finishing, setFinishing] = useState(false);
  const [now, setNow] = useState(Date.now());

  const m = match.data;
  const status = m?.status;

  // Номер события для этого устройства продолжает уже отправленные.
  useEffect(() => {
    if (!m) return;
    const mine = m.events.filter((e) => e.device_id === deviceId()).map((e) => e.client_seq ?? 0);
    clientSeq.current = Math.max(clientSeq.current, ...mine, 0);
  }, [m]);

  const setMatchData = useCallback(
    (patch: Partial<MatchDetail>) =>
      qc.setQueryData<MatchDetail>(["match", matchId], (old) => (old ? { ...old, ...patch } : old)),
    [qc, matchId],
  );

  const acquire = useCallback(async () => {
    const res = await judgeApi.lease(matchId);
    lease.current = res.lease_token;
    setLeaseError(null);
    return res.lease_token;
  }, [matchId]);

  // Для идущего или завершённого (но не подтверждённого) матча сразу берём «право ведения».
  useEffect(() => {
    if ((status === "live" || status === "finished") && !lease.current) {
      acquire().catch((e) => setLeaseError(e));
    }
  }, [status, acquire]);

  // Продление права ведения, пока экран открыт; освобождение при уходе.
  useEffect(() => {
    const timer = setInterval(() => {
      if (!lease.current) return;
      judgeApi.renew(matchId, lease.current).catch((e) => {
        if (e instanceof ApiError && e.status === 423) acquire().catch(setLeaseError);
        else setLeaseError(e);
      });
    }, RENEW_MS);
    return () => {
      clearInterval(timer);
      if (lease.current) judgeApi.release(matchId, lease.current).catch(() => undefined);
      lease.current = null;
    };
  }, [matchId, acquire]);

  // Тикающий таймер.
  useEffect(() => {
    if (status !== "live") return;
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, [status]);

  const elapsedMs = m?.started_at ? Math.max(0, now - new Date(m.started_at).getTime()) : 0;
  const clock = formatClock(elapsedMs);
  const minute = Math.floor(elapsedMs / 60000) + 1;

  /** Отправка события; при истёкшем праве ведения переподключаемся и повторяем. */
  const send = useCallback(
    async (fields: Omit<MatchEventFields, "id" | "device_id" | "client_seq">) => {
      const token = lease.current ?? (await acquire());
      clientSeq.current += 1;
      const event: MatchEventFields = {
        id: uuid(),
        device_id: deviceId(),
        client_seq: clientSeq.current,
        client_created_at: new Date().toISOString(),
        ...fields,
      };
      try {
        return await judgeApi.addEvent(matchId, token, event);
      } catch (e) {
        if (e instanceof ApiError && (e.code === "lease_expired" || e.code === "lease_invalid")) {
          const fresh = await acquire();
          return judgeApi.addEvent(matchId, fresh, event);
        }
        throw e;
      }
    },
    [matchId, acquire],
  );

  const afterEvent = (res: { event: MatchEvent; home_score: number | null; away_score: number | null }) => {
    qc.setQueryData<MatchDetail>(["match", matchId], (old) => {
      if (!old) return old;
      let events = [...old.events, res.event];
      if (res.event.type === "void") {
        events = events.map((e) => (e.id === res.event.target_event_id ? { ...e, voided: true } : e));
      }
      return { ...old, events, home_score: res.home_score, away_score: res.away_score };
    });
  };

  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    setActionError(null);
    try {
      await fn();
    } catch (e) {
      setActionError(e);
    } finally {
      setBusy(false);
    }
  };

  const startMatch = () =>
    run(async () => {
      await acquire();
      await match.refetch();
      refreshMe();
    });

  const addEvent = (type: EventType, entryId: number | null, entryPlayerId: number | null) =>
    run(async () => {
      const res = await send({
        type,
        entry_id: entryId,
        entry_player_id: entryPlayerId,
        clock_ms: Math.min(elapsedMs, 7_200_000),
      });
      afterEvent(res);
      setPicking(null);
    });

  const deleteEvent = (e: MatchEvent) =>
    run(async () => {
      const res = await send({ type: "void", target_event_id: e.id });
      afterEvent(res);
      setDeleting(null);
    });

  const finishMatch = () =>
    run(async () => {
      if (status === "live") {
        const res = await send({ type: "finish", clock_ms: Math.min(elapsedMs, 7_200_000) });
        afterEvent(res);
        setMatchData({ status: "finished" });
      }
      const token = lease.current ?? (await acquire());
      const confirmed = await judgeApi.confirm(matchId, token);
      setMatchData({
        status: confirmed.status,
        home_score: confirmed.home_score,
        away_score: confirmed.away_score,
        confirmed_at: confirmed.confirmed_at,
      });
      lease.current = null;
      setFinishing(false);
      qc.invalidateQueries({ queryKey: ["tournament", m?.tournament.id] });
      refreshMe();
    });

  if (match.isLoading || lineups.isLoading) return <Spinner />;
  if (match.error || !m)
    return (
      <div className="container page stack">
        <ErrorBox error={match.error} onRetry={() => match.refetch()} />
      </div>
    );

  const home = m.home_entry;
  const away = m.away_entry;
  const teams = [home, away].filter(Boolean) as NonNullable<typeof home>[];

  return (
    <div className="container page">
      <div className="protocol stack">
        <div className="breadcrumbs" style={{ marginBottom: 0 }}>
          <Link to="/judge">Мои матчи</Link> › Протокол
        </div>

        <div className="board">
          <div className="row-between small" style={{ opacity: 0.85 }}>
            <span>{m.tournament.name}</span>
            <MatchStatusBadge status={m.status} />
          </div>
          <div className="teams" style={{ marginTop: 10 }}>
            <span className="tname">{teamName(m, "home")}</span>
            <span className="big">{scoreText({ home_score: m.home_score ?? 0, away_score: m.away_score ?? 0 })}</span>
            <span className="tname">{teamName(m, "away")}</span>
          </div>
          {status === "live" && (
            <div className="clock" aria-live="off">
              ⏱ {clock} · {minute}-я минута
            </div>
          )}
          {status === "scheduled" || status === "lineups_open" ? (
            <div className="small" style={{ opacity: 0.85 }}>
              Начало: {formatDateTime(m.scheduled_at, m.tournament.timezone)}
              {m.venue && ` · ${m.venue.name}`}
            </div>
          ) : null}
        </div>

        {leaseError ? (
          <div className="alert alert-error row-between">
            <span>{errorMessage(leaseError)}</span>
            <button className="btn btn-sm btn-outline" onClick={() => acquire().catch(setLeaseError)}>
              Повторить
            </button>
          </div>
        ) : null}
        <FormError error={actionError} />

        {(status === "scheduled" || status === "lineups_open") && (
          <>
            <LineupSummary lineups={lineups.data} error={lineups.error} />
            <button className="btn btn-lg btn-block" disabled={busy} onClick={startMatch}>
              ▶ Начать матч
            </button>
          </>
        )}

        {status === "live" && (
          <>
            <div className="actions-grid">
              <button
                className="action-btn"
                disabled={busy || !teams.length}
                onClick={() => setPicking({ type: "goal", entryId: null })}
              >
                <span className="ic">⚽</span>Гол
              </button>
              <button
                className="action-btn"
                disabled={busy || !teams.length}
                onClick={() => setPicking({ type: "yellow", entryId: null })}
              >
                <span className="card-icon yellow" />
                Жёлтая
              </button>
              <button
                className="action-btn"
                disabled={busy || !teams.length}
                onClick={() => setPicking({ type: "red", entryId: null })}
              >
                <span className="card-icon red" />
                Красная
              </button>
            </div>
          </>
        )}

        {status === "confirmed" && (
          <div className="alert alert-success stack-sm">
            <b>Протокол подтверждён.</b>
            <span>Итоговый счёт {scoreText(m)}. Турнирная таблица пересчитана.</span>
            <div className="row">
              <Link to={`/tournaments/${m.tournament.id}?tab=table`} className="btn btn-sm">
                Турнирная таблица
              </Link>
              <Link to="/judge" className="btn btn-sm btn-outline">
                К моим матчам
              </Link>
            </div>
          </div>
        )}
        {status === "finished" && (
          <div className="alert alert-warn row-between">
            <span>Матч завершён, протокол ждёт подтверждения.</span>
            <button className="btn btn-sm" disabled={busy} onClick={() => setFinishing(true)}>
              Подтвердить
            </button>
          </div>
        )}
        {(status === "cancelled" || status === "postponed" || status === "technical") && (
          <div className="alert">Матч недоступен для ведения: статус «{MATCH_STATUS[m.status]}».</div>
        )}

        <section className="card">
          <div className="card-title">События</div>
          <EventFeed
            match={m}
            events={m.events}
            onDelete={status === "live" ? setDeleting : undefined}
            emptyText="Событий пока нет"
          />
        </section>

        {status === "live" && (
          <button className="btn btn-lg btn-block btn-danger" disabled={busy} onClick={() => setFinishing(true)}>
            Завершить матч
          </button>
        )}
      </div>

      {picking && (
        <PickModal
          picking={picking}
          match={m}
          lineups={lineups.data}
          busy={busy}
          minute={minute}
          onPickTeam={(entryId) => setPicking({ ...picking, entryId })}
          onPick={(playerId) => addEvent(picking.type, picking.entryId, playerId)}
          onClose={() => setPicking(null)}
          error={actionError}
        />
      )}

      {deleting && (
        <Modal
          title="Удалить событие?"
          onClose={() => setDeleting(null)}
          actions={
            <>
              <button className="btn btn-ghost" onClick={() => setDeleting(null)}>
                Отмена
              </button>
              <button className="btn btn-danger" disabled={busy} onClick={() => deleteEvent(deleting)}>
                Удалить
              </button>
            </>
          }
        >
          <p style={{ margin: 0 }}>
            {EVENT_LABEL[deleting.type]}
            {deleting.player ? ` — ${deleting.player.name}` : ""}. Счёт будет пересчитан.
          </p>
        </Modal>
      )}

      {finishing && (
        <Modal
          title="Завершить матч?"
          onClose={() => !busy && setFinishing(false)}
          actions={
            <>
              <button className="btn btn-ghost" disabled={busy} onClick={() => setFinishing(false)}>
                Вернуться к матчу
              </button>
              <button className="btn btn-danger" disabled={busy} onClick={finishMatch}>
                {busy ? "Подтверждаю…" : "Завершить и подтвердить"}
              </button>
            </>
          }
        >
          <div className="stack-sm">
            <div className="center" style={{ fontSize: 18 }}>
              {teamName(m, "home")} <b style={{ fontSize: 28, margin: "0 10px" }}>{scoreText(m)}</b>{" "}
              {teamName(m, "away")}
            </div>
            <p style={{ margin: 0 }}>
              Проверьте счёт и события. После подтверждения протокол закрывается, менять его сможет только
              организатор, а результат попадёт в турнирную таблицу.
            </p>
            <span className="muted small">
              Событий в протоколе: {visibleEvents(m.events).filter((e) => !e.voided && e.type !== "finish").length}
            </span>
            <FormError error={actionError} />
          </div>
        </Modal>
      )}
    </div>
  );
}

function PickModal({
  picking,
  match,
  lineups,
  busy,
  minute,
  onPickTeam,
  onPick,
  onClose,
  error,
}: {
  picking: Picking;
  match: MatchDetail;
  lineups: JudgeLineups | undefined;
  busy: boolean;
  minute: number;
  onPickTeam: (entryId: number | null) => void;
  onPick: (entryPlayerId: number) => void;
  onClose: () => void;
  error: unknown;
}) {
  const label = EVENT_LABEL[picking.type] ?? picking.type;
  const teams = [match.home_entry, match.away_entry].filter(Boolean) as NonNullable<MatchDetail["home_entry"]>[];
  const team = lineups?.items.find((i) => i.entry_id === picking.entryId);
  const players = team?.players.slice().sort((a, b) => a.number - b.number) ?? [];
  // Если капитан не подал заявку на матч, бэкенд отдаёт весь состав команды в турнире.
  const fromRoster = team && team.status === null;

  return (
    <Modal title={`${label} · ${minute}-я минута`} onClose={onClose}>
      {picking.entryId === null ? (
        <div className="stack-sm">
          <span className="label">Команда</span>
          {teams.map((t) => (
            <button key={t.id} className="choice" onClick={() => onPickTeam(t.id)}>
              <b>{t.team.name}</b>
            </button>
          ))}
        </div>
      ) : (
        <div className="stack-sm">
          <div className="row-between">
            <span className="label">Игрок — {teams.find((t) => t.id === picking.entryId)?.team.name}</span>
            <button className="btn btn-sm btn-ghost" onClick={() => onPickTeam(null)}>
              ← Команда
            </button>
          </div>
          {fromRoster && players.length > 0 && (
            <div className="hint">Заявки на матч нет — показан весь состав команды в турнире.</div>
          )}
          {players.length ? (
            <div className="choice-list">
              {players.map((p) => (
                <button
                  key={p.entry_player_id}
                  className="choice"
                  disabled={busy}
                  onClick={() => onPick(p.entry_player_id)}
                >
                  <span className="no">{p.number}</span>
                  <span>
                    {p.name}
                    {p.role === "captain" && <span className="muted small"> (капитан)</span>}
                  </span>
                </button>
              ))}
            </div>
          ) : (
            <div className="alert alert-warn small">
              В составе команды нет игроков, поэтому событие записать нельзя. Капитану нужно добавить
              игроков в заявку на турнир.
            </div>
          )}
          <FormError error={error} />
        </div>
      )}
    </Modal>
  );
}

function LineupSummary({ lineups, error }: { lineups: JudgeLineups | undefined; error: unknown }) {
  if (error) return <ErrorBox error={error} />;
  if (!lineups) return null;
  return (
    <div className="card stack-sm">
      <div className="card-title" style={{ marginBottom: 0 }}>
        Заявки команд на матч
      </div>
      {lineups.items.map((l) => (
        <div key={l.entry_id} className="stack-sm" style={{ gap: 2 }}>
          <div className="row-between">
            <span className="bold">{l.team_name}</span>
            <span className="muted small">
              {l.status === null
                ? `заявки нет · в составе ${l.players.length}`
                : `в заявке ${l.players.length} игроков`}
            </span>
          </div>
          {l.comment && <span className="small muted">💬 {l.comment}</span>}
        </div>
      ))}
    </div>
  );
}

function formatClock(ms: number) {
  const total = Math.floor(ms / 1000);
  const mm = Math.floor(total / 60);
  const ss = total % 60;
  return `${String(mm).padStart(2, "0")}:${String(ss).padStart(2, "0")}`;
}
