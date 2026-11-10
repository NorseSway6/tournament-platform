import { useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { organizerApi } from "../../api/endpoints";
import type { Organization } from "../../api/types";
import { useAuth } from "../../auth/AuthContext";
import { Empty, FormError, QueryView, Spinner, TournamentStatusBadge } from "../../components/ui";
import { VISIBILITY, formatDateRange } from "../../lib/format";
import { makeSlug } from "../../lib/misc";

export function OrganizerHome() {
  const { roles } = useAuth();
  const orgs = useQuery({
    queryKey: ["organizer", "orgs"],
    queryFn: organizerApi.organizations,
    enabled: roles.includes("organizer"),
  });

  if (!roles.includes("organizer")) return <CreateOrganization first />;

  return (
    <div className="container page stack">
      <div className="row-between">
        <h1>Мои турниры</h1>
        <Link to="/organizer/tournaments/new" className="btn">
          + Создать турнир
        </Link>
      </div>
      <QueryView query={orgs}>
        {(data) =>
          data.items.length ? (
            <div className="stack">
              {data.items.map((org) => (
                <OrganizationBlock key={org.id} org={org} showName={data.items.length > 1} />
              ))}
            </div>
          ) : (
            <CreateOrganization first />
          )
        }
      </QueryView>
    </div>
  );
}

function OrganizationBlock({ org, showName }: { org: Organization; showName: boolean }) {
  const tournaments = useQuery({
    queryKey: ["organizer", "tournaments", org.id],
    queryFn: () => organizerApi.tournaments(org.id),
  });
  return (
    <section className="stack">
      {showName && <h2>{org.name}</h2>}
      <QueryView query={tournaments}>
        {(data) =>
          data.items.length ? (
            <div className="t-grid">
              {data.items
                .slice()
                .reverse()
                .map((t) => (
                  <Link key={t.id} to={`/organizer/tournaments/${t.id}`} className="card card-link t-card">
                    <div className="trophy" aria-hidden="true">
                      🏆
                    </div>
                    <div className="stack-sm" style={{ gap: 4 }}>
                      <h3>{t.name}</h3>
                      <div className="muted small">{formatDateRange(t.starts_on, t.ends_on)}</div>
                      <div className="row" style={{ gap: 6 }}>
                        <TournamentStatusBadge status={t.status} />
                        <span className="badge">{VISIBILITY[t.visibility]}</span>
                      </div>
                    </div>
                  </Link>
                ))}
            </div>
          ) : (
            <Empty>
              Турниров пока нет. <Link to="/organizer/tournaments/new">Создайте первый турнир</Link>
            </Empty>
          )
        }
      </QueryView>
      <div className="grid-2">
        <JudgesCard org={org} />
        <VenuesCard org={org} />
      </div>
    </section>
  );
}

/** Судьи организации: их можно назначать на матчи. */
function JudgesCard({ org }: { org: Organization }) {
  const qc = useQueryClient();
  const [login, setLogin] = useState("");
  const judges = useQuery({
    queryKey: ["organizer", "judges", org.id],
    queryFn: () => organizerApi.judges(org.id),
  });
  const add = useMutation({
    mutationFn: () => organizerApi.addMember(org.id, login.trim(), "referee"),
    onSuccess: () => {
      setLogin("");
      qc.invalidateQueries({ queryKey: ["organizer", "judges", org.id] });
    },
  });
  return (
    <div className="card stack-sm">
      <div className="card-title" style={{ marginBottom: 0 }}>
        Судьи
      </div>
      <QueryView query={judges}>
        {(data) =>
          data.items.length ? (
            <ul style={{ margin: 0, paddingLeft: 18 }}>
              {data.items.map((j) => (
                <li key={j.id}>{j.name}</li>
              ))}
            </ul>
          ) : (
            <span className="muted small">Судей пока нет</span>
          )
        }
      </QueryView>
      <form
        className="row"
        style={{ flexWrap: "nowrap" }}
        onSubmit={(e) => {
          e.preventDefault();
          if (login.trim()) add.mutate();
        }}
      >
        <input
          className="input"
          placeholder="Логин или e-mail судьи"
          value={login}
          onChange={(e) => setLogin(e.target.value)}
        />
        <button className="btn" disabled={add.isPending || !login.trim()}>
          Добавить
        </button>
      </form>
      <span className="hint">Судья должен сначала зарегистрироваться на сайте.</span>
      <FormError error={add.error} />
    </div>
  );
}

function VenuesCard({ org }: { org: Organization }) {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const venues = useQuery({
    queryKey: ["organizer", "venues", org.id],
    queryFn: () => organizerApi.venues(org.id),
  });
  const add = useMutation({
    mutationFn: () => organizerApi.createVenue(org.id, { name: name.trim() }),
    onSuccess: () => {
      setName("");
      qc.invalidateQueries({ queryKey: ["organizer", "venues", org.id] });
    },
  });
  return (
    <div className="card stack-sm">
      <div className="card-title" style={{ marginBottom: 0 }}>
        Площадки
      </div>
      <QueryView query={venues}>
        {(data) =>
          data.items.length ? (
            <ul style={{ margin: 0, paddingLeft: 18 }}>
              {data.items.map((v) => (
                <li key={v.id}>
                  {v.name}
                  {v.address && <span className="muted small"> · {v.address}</span>}
                </li>
              ))}
            </ul>
          ) : (
            <span className="muted small">Площадок пока нет</span>
          )
        }
      </QueryView>
      <form
        className="row"
        style={{ flexWrap: "nowrap" }}
        onSubmit={(e) => {
          e.preventDefault();
          if (name.trim()) add.mutate();
        }}
      >
        <input
          className="input"
          placeholder="Название площадки"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <button className="btn" disabled={add.isPending || !name.trim()}>
          Добавить
        </button>
      </form>
      <FormError error={add.error} />
    </div>
  );
}

const TIMEZONES = [
  { value: "Asia/Yekaterinburg", label: "Екатеринбург (UTC+5)" },
  { value: "Europe/Moscow", label: "Москва (UTC+3)" },
  { value: "Europe/Samara", label: "Самара (UTC+4)" },
  { value: "Asia/Omsk", label: "Омск (UTC+6)" },
  { value: "Asia/Novosibirsk", label: "Новосибирск (UTC+7)" },
];

/** Первый шаг организатора: создать организацию (лигу). */
function CreateOrganization({ first }: { first?: boolean }) {
  const { refreshMe } = useAuth();
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [city, setCity] = useState("Екатеринбург");
  const [timezone, setTimezone] = useState("Asia/Yekaterinburg");
  const create = useMutation({
    mutationFn: () =>
      organizerApi.createOrganization({ name: name.trim(), city, timezone, slug: makeSlug(name) }),
    onSuccess: async () => {
      await refreshMe();
      qc.invalidateQueries({ queryKey: ["organizer", "orgs"] });
    },
  });
  if (create.isSuccess) return <Spinner />;

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    create.mutate();
  };
  return (
    <div className="container page" style={{ maxWidth: 560 }}>
      <form className="card stack" onSubmit={onSubmit}>
        <h1>{first ? "Станьте организатором" : "Новая организация"}</h1>
        <p className="muted" style={{ margin: 0 }}>
          Турниры создаются от имени организации — лиги, клуба или федерации. Укажите её название.
        </p>
        <div className="field">
          <label htmlFor="org-name">Название организации</label>
          <input
            id="org-name"
            className="input"
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Например, Лига любителей футбола"
          />
        </div>
        <div className="form-grid">
          <div className="field">
            <label htmlFor="org-city">Город</label>
            <input id="org-city" className="input" value={city} onChange={(e) => setCity(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="org-tz">Часовой пояс</label>
            <select
              id="org-tz"
              className="select"
              value={timezone}
              onChange={(e) => setTimezone(e.target.value)}
            >
              {TIMEZONES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </div>
        </div>
        <FormError error={create.error} />
        <button className="btn btn-lg" disabled={create.isPending}>
          Создать организацию
        </button>
      </form>
    </div>
  );
}
