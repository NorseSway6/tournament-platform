import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { organizerApi } from "../../api/endpoints";
import type { OrganizerEntry, OrganizerTournament } from "../../api/types";
import { FormError, Modal } from "../../components/ui";
import { localInputToIso, todayInput } from "../../lib/misc";

export function CreateMatchModal({
  tournament,
  accepted,
  onClose,
}: {
  tournament: OrganizerTournament;
  accepted: OrganizerEntry[];
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const orgId = tournament.organization_id;
  const stages = useQuery({
    queryKey: ["organizer", "stages", tournament.id],
    queryFn: () => organizerApi.stages(tournament.id),
  });
  const venues = useQuery({ queryKey: ["organizer", "venues", orgId], queryFn: () => organizerApi.venues(orgId) });
  const judges = useQuery({ queryKey: ["organizer", "judges", orgId], queryFn: () => organizerApi.judges(orgId) });

  const [form, setForm] = useState({
    home: accepted[0]?.id ?? 0,
    away: accepted[1]?.id ?? 0,
    date: todayInput(),
    time: "19:00",
    duration: 60,
    venue: 0,
    newVenue: "",
    judge: 0,
  });
  const set = <K extends keyof typeof form>(k: K, v: (typeof form)[K]) =>
    setForm((f) => ({ ...f, [k]: v }));

  const create = useMutation({
    mutationFn: async () => {
      if (form.home === form.away) throw new Error("Выберите две разные команды.");
      let stageId = stages.data?.items[0]?.id;
      if (!stageId) {
        stageId = (await organizerApi.createStage(tournament.id, { ord: 1, kind: "league", name: "Основной этап" })).id;
      }
      let venueId: number | null = form.venue || null;
      if (form.venue === -1 && form.newVenue.trim()) {
        venueId = (await organizerApi.createVenue(orgId, { name: form.newVenue.trim() })).id;
      }
      const match = await organizerApi.createMatch(tournament.id, {
        stage_id: stageId,
        home_entry_id: form.home,
        away_entry_id: form.away,
        venue_id: venueId,
        scheduled_at: localInputToIso(form.date, form.time),
        duration_min: form.duration,
      });
      if (form.judge) {
        await organizerApi.setOfficials(match.id, [{ official_id: form.judge, role: "referee" }]);
      }
      return match;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tournament", tournament.id] });
      qc.invalidateQueries({ queryKey: ["organizer", "venues", orgId] });
      onClose();
    },
  });

  const loading = stages.isLoading || venues.isLoading || judges.isLoading;

  return (
    <Modal
      title="Новый матч"
      onClose={onClose}
      actions={
        <>
          <button className="btn btn-ghost" onClick={onClose}>
            Отмена
          </button>
          <button className="btn" disabled={create.isPending || loading} onClick={() => create.mutate()}>
            {create.isPending ? "Создаю…" : "Создать матч"}
          </button>
        </>
      }
    >
      <div className="form-grid">
        <div className="field">
          <label htmlFor="home">Хозяева</label>
          <select id="home" className="select" value={form.home} onChange={(e) => set("home", Number(e.target.value))}>
            {accepted.map((e) => (
              <option key={e.id} value={e.id}>
                {e.team.name}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="away">Гости</label>
          <select id="away" className="select" value={form.away} onChange={(e) => set("away", Number(e.target.value))}>
            {accepted.map((e) => (
              <option key={e.id} value={e.id}>
                {e.team.name}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label htmlFor="date">Дата</label>
          <input id="date" type="date" className="input" value={form.date} onChange={(e) => set("date", e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="time">Время начала</label>
          <input id="time" type="time" className="input" value={form.time} onChange={(e) => set("time", e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="venue">Площадка</label>
          <select id="venue" className="select" value={form.venue} onChange={(e) => set("venue", Number(e.target.value))}>
            <option value={0}>Не указана</option>
            {venues.data?.items.map((v) => (
              <option key={v.id} value={v.id}>
                {v.name}
              </option>
            ))}
            <option value={-1}>+ Новая площадка…</option>
          </select>
        </div>
        <div className="field">
          <label htmlFor="duration">Длительность, мин</label>
          <input
            id="duration"
            type="number"
            min={10}
            max={240}
            className="input"
            value={form.duration}
            onChange={(e) => set("duration", Number(e.target.value))}
          />
        </div>
        {form.venue === -1 && (
          <div className="field full">
            <label htmlFor="new-venue">Название новой площадки</label>
            <input
              id="new-venue"
              className="input"
              value={form.newVenue}
              onChange={(e) => set("newVenue", e.target.value)}
            />
          </div>
        )}
        <div className="field full">
          <label htmlFor="judge">Судья</label>
          <select id="judge" className="select" value={form.judge} onChange={(e) => set("judge", Number(e.target.value))}>
            <option value={0}>Назначить позже</option>
            {judges.data?.items.map((j) => (
              <option key={j.id} value={j.id}>
                {j.name}
              </option>
            ))}
          </select>
          {judges.data && !judges.data.items.length && (
            <span className="hint">
              В организации нет судей. Добавьте судью на странице «Мои турниры».
            </span>
          )}
        </div>
      </div>
      <div style={{ marginTop: 12 }}>
        <FormError error={create.error} />
      </div>
    </Modal>
  );
}
