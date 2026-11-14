import { useNavigate } from "react-router-dom";
import type { StandingRow, Standings } from "../api/types";
import { TeamAvatar } from "./ui";

function Table({
  rows,
  tournamentId,
  compact,
  highlightTeamId,
}: {
  rows: StandingRow[];
  tournamentId: number;
  compact?: boolean;
  highlightTeamId?: number;
}) {
  const navigate = useNavigate();
  const n = rows.length;
  // Подсветка как в макете: первые 3 — зелёные, последние 2 — красные (если команд достаточно).
  const rowClass = (pos: number) =>
    compact || n < 6 ? "" : pos <= 3 ? "promo" : pos > n - 2 ? "releg" : "";
  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            <th className="num">#</th>
            <th>Команда</th>
            <th className="num">Игры</th>
            {!compact && (
              <>
                <th className="num">В</th>
                <th className="num">Н</th>
                <th className="num">П</th>
                <th className="num">Мячи</th>
                <th className="num">Разница</th>
              </>
            )}
            <th className="num">Очки</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr
              key={r.entry_id}
              className={`clickable ${rowClass(r.position)}`}
              style={r.team_id === highlightTeamId ? { outline: "2px solid var(--c-main)" } : undefined}
              onClick={() => navigate(`/tournaments/${tournamentId}/teams/${r.team_id}`)}
            >
              <td className="num">{r.position}</td>
              <td>
                <span className="row" style={{ gap: 8, flexWrap: "nowrap" }}>
                  <TeamAvatar id={r.team_id} name={r.team_name} size="sm" />
                  {r.team_name}
                </span>
              </td>
              <td className="num">{r.played}</td>
              {!compact && (
                <>
                  <td className="num">{r.wins}</td>
                  <td className="num">{r.draws}</td>
                  <td className="num">{r.losses}</td>
                  <td className="num">
                    {r.goals_for}:{r.goals_against}
                  </td>
                  <td className="num">
                    {r.goal_difference > 0 ? `+${r.goal_difference}` : r.goal_difference}
                  </td>
                </>
              )}
              <td className="num bold">{r.points}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function StandingsView({
  standings,
  compact,
  highlightTeamId,
}: {
  standings: Standings;
  compact?: boolean;
  highlightTeamId?: number;
}) {
  if (!standings.stages.length)
    return <div className="empty">Таблица появится, когда организатор настроит турнир.</div>;
  const r = standings.rules;
  return (
    <div className="stack">
      {standings.stages.map((stage) => (
        <div key={stage.stage_id} className="stack-sm">
          {standings.stages.length > 1 && <h3>{stage.stage_name}</h3>}
          {stage.items.length > 0 && (
            <Table
              rows={stage.items}
              tournamentId={standings.tournament_id}
              compact={compact}
              highlightTeamId={highlightTeamId}
            />
          )}
          {stage.groups.map((g) => (
            <div key={g.group_id} className="stack-sm">
              <h3>{g.group_name}</h3>
              <Table rows={g.items} tournamentId={standings.tournament_id} compact={compact} />
            </div>
          ))}
          {!stage.items.length && !stage.groups.length && (
            <div className="empty">Команды ещё не приняты в турнир.</div>
          )}
        </div>
      ))}
      {!compact && (
        <p className="muted small" style={{ margin: 0 }}>
          Очки: победа — {r.points_for_win}, ничья — {r.points_for_draw}, поражение —{" "}
          {r.points_for_loss}. Учитываются только подтверждённые матчи.
        </p>
      )}
    </div>
  );
}
