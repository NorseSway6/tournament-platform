import type { EntryPlayerInput } from "../../api/types";
import { splitFullName } from "../../lib/misc";

export interface PlayerDraft {
  key: string;
  player_id?: number;
  fullName: string;
  number: string;
  birth_date: string;
}

let counter = 0;
export const newPlayer = (): PlayerDraft => ({
  key: `p${++counter}`,
  fullName: "",
  number: "",
  birth_date: "",
});

/** Проверка списка игроков. Возвращает текст ошибки или null. */
export function validatePlayers(players: PlayerDraft[]): string | null {
  const filled = players.filter((p) => p.fullName.trim() || p.number);
  if (!filled.length) return "Добавьте хотя бы одного игрока.";
  for (const p of filled) {
    const { first_name, last_name } = splitFullName(p.fullName);
    if (!last_name || !first_name) return `Укажите фамилию и имя игрока «${p.fullName || "без имени"}».`;
    const n = Number(p.number);
    if (!Number.isInteger(n) || n < 1 || n > 99) return `Номер игрока «${p.fullName}» должен быть от 1 до 99.`;
  }
  const numbers = filled.map((p) => Number(p.number));
  const dup = numbers.find((n, i) => numbers.indexOf(n) !== i);
  if (dup) return `Номер ${dup} указан у нескольких игроков.`;
  return null;
}

export function toPlayerInputs(players: PlayerDraft[]): EntryPlayerInput[] {
  return players
    .filter((p) => p.fullName.trim() || p.number)
    .map((p) => {
      const name = splitFullName(p.fullName);
      return {
        ...(p.player_id ? { player_id: p.player_id } : {}),
        last_name: name.last_name,
        first_name: name.first_name,
        middle_name: name.middle_name,
        birth_date: p.birth_date || null,
        number: Number(p.number),
      };
    });
}

/** Таблица ввода игроков: ФИО, номер, дата рождения. */
export function PlayersEditor({
  players,
  onChange,
  readOnly,
}: {
  players: PlayerDraft[];
  onChange: (p: PlayerDraft[]) => void;
  readOnly?: boolean;
}) {
  const update = (key: string, patch: Partial<PlayerDraft>) =>
    onChange(players.map((p) => (p.key === key ? { ...p, ...patch } : p)));
  return (
    <div className="stack-sm">
      <div className="player-row label" aria-hidden="true">
        <span>Фамилия Имя Отчество</span>
        <span>Номер</span>
        <span className="bd">Дата рождения</span>
        <span />
      </div>
      {players.map((p, i) => (
        <div key={p.key} className="player-row">
          <input
            className="input"
            placeholder="Иванов Иван"
            aria-label={`ФИО игрока ${i + 1}`}
            value={p.fullName}
            readOnly={readOnly}
            onChange={(e) => update(p.key, { fullName: e.target.value })}
          />
          <input
            className="input"
            type="number"
            min={1}
            max={99}
            placeholder="№"
            aria-label={`Номер игрока ${i + 1}`}
            value={p.number}
            readOnly={readOnly}
            onChange={(e) => update(p.key, { number: e.target.value })}
          />
          <input
            className="input bd"
            type="date"
            aria-label={`Дата рождения игрока ${i + 1}`}
            value={p.birth_date}
            readOnly={readOnly}
            onChange={(e) => update(p.key, { birth_date: e.target.value })}
          />
          {!readOnly ? (
            <button
              type="button"
              className="icon-btn"
              aria-label="Удалить игрока"
              title="Удалить игрока"
              onClick={() => onChange(players.filter((x) => x.key !== p.key))}
            >
              ✕
            </button>
          ) : (
            <span />
          )}
        </div>
      ))}
      {!readOnly && (
        <div>
          <button type="button" className="btn btn-outline" onClick={() => onChange([...players, newPlayer()])}>
            + Добавить игрока
          </button>
        </div>
      )}
    </div>
  );
}
