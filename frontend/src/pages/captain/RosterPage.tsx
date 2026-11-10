import { useEffect, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { captainApi, publicApi } from "../../api/endpoints";
import { useAuth } from "../../auth/AuthContext";
import { EntryStatusBadge, ErrorBox, FormError, Spinner } from "../../components/ui";
import { playerFullName } from "../../lib/misc";
import { PlayersEditor, toPlayerInputs, validatePlayers } from "./PlayersEditor";
import type { PlayerDraft } from "./PlayersEditor";

/** Состав команды в турнире: просмотр и правка (пока открыта регистрация). */
export function RosterPage() {
  const entryId = Number(useParams().entryId);
  const location = useLocation();
  const initialError = (location.state as { error?: unknown } | null)?.error ?? null;
  const qc = useQueryClient();
  const { me, refreshMe } = useAuth();

  const team = me?.roles.captain.teams.find((t) => t.entries.some((e) => e.id === entryId));
  const entry = team?.entries.find((e) => e.id === entryId);

  const roster = useQuery({
    queryKey: ["captain", "roster", entryId],
    queryFn: () => captainApi.entryPlayers(entryId),
  });
  const tournament = useQuery({
    queryKey: ["tournament", entry?.tournament_id],
    queryFn: () => publicApi.tournament(entry!.tournament_id),
    enabled: !!entry,
    retry: false,
  });

  const [players, setPlayers] = useState<PlayerDraft[] | null>(null);
  const [localError, setLocalError] = useState<unknown>(initialError);

  useEffect(() => {
    if (roster.data && players === null) {
      setPlayers(
        roster.data.players
          .filter((p) => p.status === "active")
          .map((p) => ({
            key: `e${p.entry_player_id}`,
            player_id: p.player_id,
            fullName: playerFullName(p),
            number: String(p.number),
            birth_date: p.birth_date ?? "",
          })),
      );
    }
  }, [roster.data, players]);

  const save = useMutation({
    mutationFn: () => captainApi.setEntryPlayers(entryId, toPlayerInputs(players ?? [])),
    onSuccess: async () => {
      setLocalError(null);
      setPlayers(null);
      await qc.invalidateQueries({ queryKey: ["captain", "roster", entryId] });
      refreshMe();
    },
  });

  if (roster.isLoading || players === null) {
    if (roster.error)
      return (
        <div className="container page">
          <ErrorBox error={roster.error} onRetry={() => roster.refetch()} />
        </div>
      );
    return <Spinner />;
  }

  // Состав можно менять только пока идёт регистрация (так требует бэкенд).
  const editable =
    !!entry && ["pending", "accepted"].includes(entry.status) && tournament.data?.status === "registration";

  return (
    <div className="container page" style={{ maxWidth: 760 }}>
      <div className="breadcrumbs">
        <Link to="/captain">Кабинет капитана</Link> › Состав
      </div>
      <div className="stack">
        <div className="row-between">
          <div>
            <h1>{team?.name ?? "Состав команды"}</h1>
            {entry && (
              <div className="row small" style={{ gap: 8, marginTop: 4 }}>
                <Link to={`/tournaments/${entry.tournament_id}`}>{entry.tournament_name}</Link>
                <EntryStatusBadge status={entry.status} />
              </div>
            )}
          </div>
        </div>

        {!editable && (
          <div className="alert">
            Состав можно менять только пока открыта регистрация на турнир. Сейчас он доступен только для
            просмотра.
          </div>
        )}

        <section className="card stack-sm">
          <div className="card-title" style={{ marginBottom: 0 }}>
            Игроки ({players.length})
          </div>
          <PlayersEditor players={players} onChange={setPlayers} readOnly={!editable} />
        </section>

        <FormError error={localError ?? save.error} />
        {save.isSuccess && !localError && <div className="alert alert-success">Состав сохранён</div>}
        {editable && (
          <div>
            <button
              className="btn btn-lg"
              disabled={save.isPending}
              onClick={() => {
                const err = validatePlayers(players);
                if (err) return setLocalError(new Error(err));
                setLocalError(null);
                save.mutate();
              }}
            >
              {save.isPending ? "Сохраняю…" : "Сохранить состав"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
