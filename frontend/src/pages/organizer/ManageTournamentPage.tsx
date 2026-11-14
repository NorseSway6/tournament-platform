import { useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { organizerApi } from "../../api/endpoints";
import type { OrganizerEntry, OrganizerTournament } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { MatchDayList } from "../../components/match";
import { TournamentBand } from "../../components/TournamentBand";
import {
  Empty,
  EntryStatusBadge,
  ErrorBox,
  FormError,
  Modal,
  QueryView,
  Spinner,
} from "../../components/ui";
import { VISIBILITY, formatDateTime } from "../../lib/format";
import { CreateMatchModal } from "./CreateMatchModal";

type TabKey = "entries" | "teams" | "matches";

const NEXT_STEP: Partial<
  Record<OrganizerTournament["status"], { action: "open-registration" | "start" | "finish"; label: string; hint: string }>
> = {
  draft: {
    action: "open-registration",
    label: "Открыть регистрацию",
    hint: "Турнир станет виден, капитаны смогут подавать заявки.",
  },
  registration: {
    action: "start",
    label: "Начать турнир",
    hint: "Составы команд и регламент будут зафиксированы.",
  },
  ongoing: {
    action: "finish",
    label: "Завершить турнир",
    hint: "Турнир получит статус «Завершён».",
  },
};

export function ManageTournamentPage() {
  const id = Number(useParams().id);
  const qc = useQueryClient();
  const { refreshMe } = useAuth();
  const [params, setParams] = useSearchParams();
  const tab = (params.get("tab") as TabKey) || "entries";
  const [confirmStep, setConfirmStep] = useState(false);

  const tournament = useQuery({
    queryKey: ["organizer", "tournament", id],
    queryFn: () => organizerApi.tournament(id),
  });
  const entries = useQuery({
    queryKey: ["organizer", "entries", id],
    queryFn: () => organizerApi.entries(id),
    refetchInterval: 30_000,
  });

  const transition = useMutation({
    mutationFn: (action: "open-registration" | "start" | "finish") => organizerApi.transition(id, action),
    onSuccess: async () => {
      setConfirmStep(false);
      await refreshMe();
      qc.invalidateQueries({ queryKey: ["organizer"] });
      qc.invalidateQueries({ queryKey: ["tournament", id] });
    },
  });

  const pendingCount = entries.data?.items.filter((e) => e.status === "pending").length ?? 0;
  const accepted = useMemo(
    () => (entries.data?.items ?? []).filter((e) => e.status === "accepted"),
    [entries.data],
  );

  if (tournament.isLoading) return <Spinner />;
  if (tournament.error)
    return (
      <div className="container page">
        <ErrorBox error={tournament.error} onRetry={() => tournament.refetch()} />
      </div>
    );
  const t = tournament.data!;
  const step = NEXT_STEP[t.status];
  const isPublicVisible = t.visibility === "public" && t.status !== "draft";

  const setTab = (key: TabKey) => setParams({ tab: key }, { replace: true });

  return (
    <>
      <TournamentBand
        name={t.name}
        season={t.season}
        status={t.status}
        startsOn={t.starts_on}
        endsOn={t.ends_on}
        teamsCount={accepted.length}
        right={
          isPublicVisible ? (
            <Link to={`/tournaments/${t.id}`}>Публичная страница →</Link>
          ) : (
            <span className="small">{VISIBILITY[t.visibility]}</span>
          )
        }
      />
      <div className="container page stack">
        <div className="breadcrumbs">
          <Link to="/organizer">Мои турниры</Link> › {t.name}
        </div>

        {step && (
          <div className="card row-between">
            <div>
              <div className="bold">Следующий шаг: {step.label.toLowerCase()}</div>
              <div className="muted small">{step.hint}</div>
            </div>
            <button className="btn" onClick={() => setConfirmStep(true)}>
              {step.label}
            </button>
          </div>
        )}
        {confirmStep && step && (
          <Modal
            title={`${step.label}?`}
            onClose={() => setConfirmStep(false)}
            actions={
              <>
                <button className="btn btn-ghost" onClick={() => setConfirmStep(false)}>
                  Отмена
                </button>
                <button
                  className="btn"
                  disabled={transition.isPending}
                  onClick={() => transition.mutate(step.action)}
                >
                  {step.label}
                </button>
              </>
            }
          >
            <p style={{ margin: 0 }}>{step.hint} Отменить это действие нельзя.</p>
            <FormError error={transition.error} />
          </Modal>
        )}

        <div>
          <div className="tabs" role="tablist">
            <button
              className={`tab${tab === "entries" ? " active" : ""}`}
              onClick={() => setTab("entries")}
            >
              Заявки
              {pendingCount > 0 && <span className="count">{pendingCount}</span>}
            </button>
            <button className={`tab${tab === "teams" ? " active" : ""}`} onClick={() => setTab("teams")}>
              Команды
            </button>
            <button
              className={`tab${tab === "matches" ? " active" : ""}`}
              onClick={() => setTab("matches")}
            >
              Матчи
            </button>
          </div>

          {tab === "entries" && (
            <QueryView query={entries}>
              {(data) => <EntriesTab entries={data.items} tournament={t} />}
            </QueryView>
          )}
          {tab === "teams" && (
            <QueryView query={entries}>
              {() =>
                accepted.length ? (
                  <div className="table-wrap">
                    <table className="table">
                      <thead>
                        <tr>
                          <th>Команда</th>
                          <th>Капитан</th>
                          <th className="num">Игроков</th>
                        </tr>
                      </thead>
                      <tbody>
                        {accepted.map((e) => (
                          <tr key={e.id}>
                            <td className="bold">{e.team.name}</td>
                            <td>{e.captain?.name ?? "—"}</td>
                            <td className="num">{e.player_count}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <Empty>Принятых команд пока нет. Примите заявки на вкладке «Заявки».</Empty>
                )
              }
            </QueryView>
          )}
          {tab === "matches" && <MatchesTab tournament={t} accepted={accepted} />}
        </div>
      </div>
    </>
  );
}

function EntriesTab({ entries, tournament }: { entries: OrganizerEntry[]; tournament: OrganizerTournament }) {
  const qc = useQueryClient();
  const [rejecting, setRejecting] = useState<OrganizerEntry | null>(null);
  const [comment, setComment] = useState("");
  const decide = useMutation({
    mutationFn: (p: { entry: OrganizerEntry; status: "accepted" | "rejected"; comment?: string }) =>
      organizerApi.decideEntry(p.entry.id, p.status, p.comment),
    onSuccess: () => {
      setRejecting(null);
      setComment("");
      qc.invalidateQueries({ queryKey: ["organizer", "entries", tournament.id] });
      qc.invalidateQueries({ queryKey: ["tournament", tournament.id] });
    },
  });
  const canDecide = tournament.status === "registration" || tournament.status === "ongoing";
  const sorted = entries
    .slice()
    .sort((a, b) => Number(b.status === "pending") - Number(a.status === "pending"));

  if (!entries.length)
    return (
      <Empty>
        Заявок пока нет.
        {tournament.status === "draft" && " Откройте регистрацию, чтобы капитаны могли подавать заявки."}
      </Empty>
    );

  return (
    <div className="stack-sm">
      {!canDecide && (
        <div className="alert alert-warn">
          Решения по заявкам можно принимать, когда открыта регистрация или идёт турнир.
        </div>
      )}
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>Команда</th>
              <th>Капитан</th>
              <th className="num">Игроков</th>
              <th>Подана</th>
              <th>Статус</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {sorted.map((e) => (
              <tr key={e.id}>
                <td className="bold">{e.team.name}</td>
                <td>{e.captain?.name ?? "—"}</td>
                <td className="num">{e.player_count}</td>
                <td className="nowrap small">{formatDateTime(e.submitted_at)}</td>
                <td>
                  <EntryStatusBadge status={e.status} />
                  {e.decision_comment && <div className="hint">{e.decision_comment}</div>}
                </td>
                <td className="nowrap">
                  {e.status === "pending" && canDecide && (
                    <span className="row" style={{ gap: 6, flexWrap: "nowrap" }}>
                      <button
                        className="btn btn-sm"
                        disabled={decide.isPending}
                        onClick={() => decide.mutate({ entry: e, status: "accepted" })}
                      >
                        Принять
                      </button>
                      <button
                        className="btn btn-sm btn-outline"
                        disabled={decide.isPending}
                        onClick={() => setRejecting(e)}
                      >
                        Отклонить
                      </button>
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {decide.error && !rejecting ? <FormError error={decide.error} /> : null}
      {rejecting && (
        <Modal
          title={`Отклонить заявку «${rejecting.team.name}»?`}
          onClose={() => setRejecting(null)}
          actions={
            <>
              <button className="btn btn-ghost" onClick={() => setRejecting(null)}>
                Отмена
              </button>
              <button
                className="btn btn-danger"
                disabled={decide.isPending}
                onClick={() => decide.mutate({ entry: rejecting, status: "rejected", comment })}
              >
                Отклонить
              </button>
            </>
          }
        >
          <div className="field">
            <label htmlFor="reject-comment">Причина (необязательно)</label>
            <textarea
              id="reject-comment"
              className="textarea"
              maxLength={2000}
              value={comment}
              onChange={(e) => setComment(e.target.value)}
            />
          </div>
          <FormError error={decide.error} />
        </Modal>
      )}
    </div>
  );
}

function MatchesTab({ tournament, accepted }: { tournament: OrganizerTournament; accepted: OrganizerEntry[] }) {
  const [creating, setCreating] = useState(false);
  const matches = useQuery({
    queryKey: ["tournament", tournament.id, "matches", "organizer"],
    queryFn: () => organizerApi.matches(tournament.id),
    refetchInterval: 20_000,
  });

  return (
    <div className="stack">
      <div className="row-between">
        <span className="muted small">
          Нажмите на матч, чтобы открыть его страницу и протокол.
        </span>
        <button className="btn" onClick={() => setCreating(true)} disabled={accepted.length < 2}>
          + Создать матч
        </button>
      </div>
      {accepted.length < 2 && (
        <div className="alert alert-warn">Чтобы создать матч, нужно принять хотя бы две команды.</div>
      )}
      <QueryView query={matches}>
        {(data) => <MatchDayList matches={data} emptyText="Матчей пока нет. Создайте первый матч." />}
      </QueryView>
      {creating && (
        <CreateMatchModal tournament={tournament} accepted={accepted} onClose={() => setCreating(false)} />
      )}
    </div>
  );
}
