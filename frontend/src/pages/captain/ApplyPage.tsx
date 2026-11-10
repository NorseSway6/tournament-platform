import { useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { captainApi, publicApi } from "../../api/endpoints";
import { useAuth } from "../../auth/AuthContext";
import { FormError, QueryView } from "../../components/ui";
import { formatDateRange, formatDateTime } from "../../lib/format";
import { PlayersEditor, newPlayer, toPlayerInputs, validatePlayers } from "./PlayersEditor";
import type { PlayerDraft } from "./PlayersEditor";

/** Заявка на турнир: турнир → команда → игроки (ФИО, номер). */
export function ApplyPage() {
  const { me, refreshMe } = useAuth();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [params] = useSearchParams();
  const myTeams = me?.roles.captain.teams ?? [];

  const tournaments = useQuery({
    queryKey: ["tournaments", "registration"],
    queryFn: () => publicApi.tournaments("registration"),
  });

  const [tournamentId, setTournamentId] = useState<number>(Number(params.get("tournament")) || 0);
  const [teamId, setTeamId] = useState<number>(myTeams[0]?.id ?? 0); // 0 — новая команда
  const [teamName, setTeamName] = useState("");
  const [city, setCity] = useState("Екатеринбург");
  const [players, setPlayers] = useState<PlayerDraft[]>([newPlayer(), newPlayer(), newPlayer(), newPlayer(), newPlayer()]);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  const selected = tournaments.data?.find((t) => t.id === tournamentId);
  const alreadyApplied = (tid: number, team: number) =>
    myTeams.find((t) => t.id === team)?.entries.some((e) => e.tournament_id === tid);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!tournamentId) return setError(new Error("Выберите турнир."));
    if (!teamId && !teamName.trim()) return setError(new Error("Укажите название команды."));
    const playersError = validatePlayers(players);
    if (playersError) return setError(new Error(playersError));

    setBusy(true);
    let entryId: number | null = null;
    try {
      const team = teamId ? teamId : (await captainApi.createTeam(teamName.trim(), city.trim())).id;
      const entry = await captainApi.applyToTournament(tournamentId, team);
      entryId = entry.id;
      await captainApi.setEntryPlayers(entry.id, toPlayerInputs(players));
      await refreshMe();
      qc.invalidateQueries({ queryKey: ["captain"] });
      navigate("/captain", {
        state: { flash: "Заявка отправлена. Статус появится здесь, когда организатор её рассмотрит." },
      });
    } catch (err) {
      await refreshMe();
      if (entryId) {
        // Заявка создана, но состав не сохранился — продолжим на странице состава.
        navigate(`/captain/entries/${entryId}`, { state: { error: err } });
      } else setError(err);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="container page" style={{ maxWidth: 760 }}>
      <div className="breadcrumbs">
        <Link to="/captain">Кабинет капитана</Link> › Заявка на турнир
      </div>
      <form className="stack" onSubmit={onSubmit}>
        <h1>Заявка на турнир</h1>

        <section className="card stack-sm">
          <div className="card-title" style={{ marginBottom: 0 }}>
            1. Турнир
          </div>
          <QueryView query={tournaments}>
            {(list) =>
              list.length ? (
                <div className="choice-list" style={{ maxHeight: "none" }}>
                  {list.map((t) => (
                    <button
                      type="button"
                      key={t.id}
                      className={`choice${t.id === tournamentId ? " active" : ""}`}
                      onClick={() => setTournamentId(t.id)}
                    >
                      <span style={{ fontSize: 22 }}>🏆</span>
                      <span>
                        <b>{t.name}</b>
                        <div className="muted small">
                          {t.organization.name} · {formatDateRange(t.starts_on, t.ends_on)}
                          {t.registration_deadline &&
                            ` · заявки до ${formatDateTime(t.registration_deadline, t.organization.timezone)}`}
                        </div>
                      </span>
                    </button>
                  ))}
                </div>
              ) : (
                <div className="empty">Сейчас нет турниров с открытой регистрацией.</div>
              )
            }
          </QueryView>
        </section>

        <section className="card stack-sm">
          <div className="card-title" style={{ marginBottom: 0 }}>
            2. Команда
          </div>
          {myTeams.length > 0 && (
            <div className="field">
              <label htmlFor="team">Команда</label>
              <select id="team" className="select" value={teamId} onChange={(e) => setTeamId(Number(e.target.value))}>
                {myTeams.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
                <option value={0}>+ Новая команда</option>
              </select>
            </div>
          )}
          {!teamId && (
            <div className="form-grid">
              <div className="field">
                <label htmlFor="team-name">Название команды</label>
                <input
                  id="team-name"
                  className="input"
                  maxLength={150}
                  placeholder="ФК «Вымпел»"
                  value={teamName}
                  onChange={(e) => setTeamName(e.target.value)}
                />
              </div>
              <div className="field">
                <label htmlFor="city">Город</label>
                <input id="city" className="input" maxLength={100} value={city} onChange={(e) => setCity(e.target.value)} />
              </div>
            </div>
          )}
          {selected && teamId > 0 && alreadyApplied(selected.id, teamId) && (
            <div className="alert alert-warn">Эта команда уже подала заявку на выбранный турнир.</div>
          )}
        </section>

        <section className="card stack-sm">
          <div className="card-title" style={{ marginBottom: 0 }}>
            3. Игроки
          </div>
          <PlayersEditor players={players} onChange={setPlayers} />
          <span className="hint">Пустые строки не учитываются. Номера должны быть разными.</span>
        </section>

        <FormError error={error} />
        <div className="row">
          <button className="btn btn-lg" disabled={busy}>
            {busy ? "Отправляю…" : "Отправить заявку"}
          </button>
          <Link to="/captain" className="btn btn-lg btn-ghost">
            Отмена
          </Link>
        </div>
      </form>
    </div>
  );
}
