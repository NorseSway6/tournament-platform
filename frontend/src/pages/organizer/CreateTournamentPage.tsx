import { useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { organizerApi } from "../../api/endpoints";
import type { Visibility } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { FormError, QueryView } from "../../components/ui";
import { localInputToIso, makeSlug } from "../../lib/misc";

/** Фиксированный порядок тай-брейков (по требованиям MVP он не настраивается). */
export const TIE_BREAKERS = ["points", "goal_difference", "goals_for", "team_name"];
export const TIE_BREAKER_LABEL: Record<string, string> = {
  points: "Очки",
  goal_difference: "Разница мячей",
  goals_for: "Забитые мячи",
  team_name: "Название команды (по алфавиту)",
  team_id: "Порядок регистрации",
};

export function CreateTournamentPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { refreshMe } = useAuth();
  const orgs = useQuery({ queryKey: ["organizer", "orgs"], queryFn: organizerApi.organizations });

  const [form, setForm] = useState({
    organization_id: 0,
    name: "",
    season: String(new Date().getFullYear()),
    starts_on: "",
    ends_on: "",
    registration_deadline: "",
    visibility: "public" as Visibility,
    win: 3,
    draw: 1,
    loss: 0,
    openRegistration: true,
  });
  const set = <K extends keyof typeof form>(k: K, v: (typeof form)[K]) =>
    setForm((f) => ({ ...f, [k]: v }));

  const create = useMutation({
    mutationFn: async () => {
      const organization_id = form.organization_id || orgs.data!.items[0].id;
      const t = await organizerApi.createTournament({
        organization_id,
        slug: makeSlug(form.name),
        name: form.name.trim(),
        season: form.season.trim(),
        visibility: form.visibility,
        starts_on: form.starts_on || null,
        ends_on: form.ends_on || null,
        registration_deadline: form.registration_deadline
          ? localInputToIso(form.registration_deadline, "23:59")
          : null,
        regulation: {
          standings: {
            points_for_win: form.win,
            points_for_draw: form.draw,
            points_for_loss: form.loss,
            tie_breakers: TIE_BREAKERS,
          },
        },
      });
      // Без этапа нельзя создавать матчи и считать таблицу — создаём круговой этап сразу.
      await organizerApi.createStage(t.id, { ord: 1, kind: "league", name: "Основной этап" });
      if (form.openRegistration) await organizerApi.transition(t.id, "open-registration");
      return t;
    },
    onSuccess: async (t) => {
      await refreshMe();
      qc.invalidateQueries({ queryKey: ["organizer"] });
      navigate(`/organizer/tournaments/${t.id}`);
    },
  });

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    create.mutate();
  };

  return (
    <div className="container page" style={{ maxWidth: 720 }}>
      <div className="breadcrumbs">
        <Link to="/organizer">Мои турниры</Link> › Новый турнир
      </div>
      <QueryView query={orgs}>
        {(data) => (
          <form className="card stack" onSubmit={onSubmit}>
            <h1>Новый турнир</h1>

            {data.items.length > 1 && (
              <div className="field">
                <label htmlFor="org">Организация</label>
                <select
                  id="org"
                  className="select"
                  value={form.organization_id || data.items[0].id}
                  onChange={(e) => set("organization_id", Number(e.target.value))}
                >
                  {data.items.map((o) => (
                    <option key={o.id} value={o.id}>
                      {o.name}
                    </option>
                  ))}
                </select>
              </div>
            )}

            <div className="form-grid">
              <div className="field full">
                <label htmlFor="name">Название</label>
                <input
                  id="name"
                  className="input"
                  required
                  maxLength={200}
                  placeholder="Например, Летний кубок"
                  value={form.name}
                  onChange={(e) => set("name", e.target.value)}
                />
              </div>
              <div className="field">
                <label htmlFor="season">Сезон</label>
                <input
                  id="season"
                  className="input"
                  maxLength={50}
                  value={form.season}
                  onChange={(e) => set("season", e.target.value)}
                />
              </div>
              <div className="field">
                <label htmlFor="visibility">Видимость</label>
                <select
                  id="visibility"
                  className="select"
                  value={form.visibility}
                  onChange={(e) => set("visibility", e.target.value as Visibility)}
                >
                  <option value="public">Публичный — виден всем</option>
                  <option value="private">Закрытый — только для участников</option>
                </select>
              </div>
              <div className="field">
                <label htmlFor="starts">Дата начала</label>
                <input
                  id="starts"
                  className="input"
                  type="date"
                  value={form.starts_on}
                  onChange={(e) => set("starts_on", e.target.value)}
                />
              </div>
              <div className="field">
                <label htmlFor="ends">Дата окончания</label>
                <input
                  id="ends"
                  className="input"
                  type="date"
                  min={form.starts_on || undefined}
                  value={form.ends_on}
                  onChange={(e) => set("ends_on", e.target.value)}
                />
              </div>
              <div className="field">
                <label htmlFor="deadline">Приём заявок до (включительно)</label>
                <input
                  id="deadline"
                  className="input"
                  type="date"
                  value={form.registration_deadline}
                  onChange={(e) => set("registration_deadline", e.target.value)}
                />
                <span className="hint">Можно оставить пустым</span>
              </div>
            </div>

            <fieldset className="card flat stack-sm" style={{ margin: 0 }}>
              <legend className="bold" style={{ padding: "0 6px" }}>
                Регламент
              </legend>
              <div className="form-grid" style={{ gridTemplateColumns: "repeat(3, minmax(0,1fr))" }}>
                {(
                  [
                    ["win", "Очки за победу"],
                    ["draw", "За ничью"],
                    ["loss", "За поражение"],
                  ] as const
                ).map(([k, label]) => (
                  <div className="field" key={k}>
                    <label htmlFor={k}>{label}</label>
                    <input
                      id={k}
                      className="input"
                      type="number"
                      min={0}
                      max={10}
                      required
                      value={form[k]}
                      onChange={(e) => set(k, Number(e.target.value))}
                    />
                  </div>
                ))}
              </div>
              <div className="small">
                <span className="label">Порядок определения мест при равенстве очков:</span>
                <ol style={{ margin: "6px 0 0", paddingLeft: 20 }}>
                  {TIE_BREAKERS.slice(1).map((tb) => (
                    <li key={tb}>{TIE_BREAKER_LABEL[tb]}</li>
                  ))}
                </ol>
              </div>
            </fieldset>

            <label className="checkbox">
              <input
                type="checkbox"
                checked={form.openRegistration}
                onChange={(e) => set("openRegistration", e.target.checked)}
              />
              Сразу открыть регистрацию команд
            </label>

            <FormError error={create.error} />
            <div className="row">
              <button className="btn btn-lg" disabled={create.isPending}>
                {create.isPending ? "Создаю…" : "Создать турнир"}
              </button>
              <Link to="/organizer" className="btn btn-lg btn-ghost">
                Отмена
              </Link>
            </div>
          </form>
        )}
      </QueryView>
    </div>
  );
}
