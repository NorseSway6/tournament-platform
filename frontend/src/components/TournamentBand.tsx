import type { ReactNode } from "react";
import type { TournamentStatus } from "../api/types";
import { TOURNAMENT_STATUS, formatDateRange, plural } from "../lib/format";

/** Зелёная полоса с названием турнира (как в макетах). */
export function TournamentBand({
  name,
  season,
  status,
  startsOn,
  endsOn,
  teamsCount,
  right,
}: {
  name: string;
  season?: string;
  status: TournamentStatus;
  startsOn: string | null;
  endsOn: string | null;
  teamsCount?: number;
  right?: ReactNode;
}) {
  const meta = [
    season ? `Сезон ${season}` : null,
    formatDateRange(startsOn, endsOn),
    teamsCount !== undefined
      ? `${teamsCount} ${plural(teamsCount, ["команда", "команды", "команд"])}`
      : null,
  ].filter(Boolean);
  return (
    <div className="t-band">
      <div className="container">
        <div className="trophy" aria-hidden="true">
          🏆
        </div>
        <div>
          <h1>{name}</h1>
          <div className="meta">{meta.join(" · ")}</div>
        </div>
        <div className="right">
          <span className={`status-dot${status === "ongoing" ? "" : " off"}`}>
            {TOURNAMENT_STATUS[status]}
          </span>
          {right}
        </div>
      </div>
    </div>
  );
}
