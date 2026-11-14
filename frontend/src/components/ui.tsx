import { useEffect } from "react";
import type { ReactNode } from "react";
import { errorMessage } from "../api/client";
import type { EntryStatus, LineupStatus, MatchStatus, TournamentStatus } from "../api/types";
import {
  ENTRY_STATUS,
  LINEUP_STATUS,
  MATCH_STATUS,
  TOURNAMENT_STATUS,
  teamColor,
  teamInitial,
} from "../lib/format";

export function Spinner() {
  return <div className="spinner" role="status" aria-label="Загрузка" />;
}

export function ErrorBox({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  return (
    <div className="alert alert-error row-between" role="alert">
      <span>{errorMessage(error)}</span>
      {onRetry && (
        <button className="btn btn-sm btn-outline" onClick={onRetry}>
          Повторить
        </button>
      )}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="empty">{children}</div>;
}

/** Общая обёртка «загрузка / ошибка / данные» для useQuery. */
export function QueryView<T>({
  query,
  children,
}: {
  query: { data: T | undefined; isLoading: boolean; error: unknown; refetch: () => unknown };
  children: (data: T) => ReactNode;
}) {
  if (query.isLoading) return <Spinner />;
  if (query.error) return <ErrorBox error={query.error} onRetry={() => query.refetch()} />;
  if (query.data === undefined) return null;
  return <>{children(query.data)}</>;
}

export function Modal({
  title,
  onClose,
  children,
  actions,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
  actions?: ReactNode;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [onClose]);

  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal" role="dialog" aria-modal="true" aria-label={title}>
        <h2>{title}</h2>
        {children}
        {actions && <div className="actions">{actions}</div>}
      </div>
    </div>
  );
}

export function MatchStatusBadge({ status }: { status: MatchStatus }) {
  if (status === "live") return <span className="badge badge-live">LIVE</span>;
  const cls =
    status === "confirmed"
      ? "badge"
      : status === "finished"
        ? "badge badge-orange"
        : status === "cancelled" || status === "postponed"
          ? "badge badge-red"
          : status === "technical"
            ? "badge badge-orange"
            : "badge badge-green";
  return <span className={cls}>{MATCH_STATUS[status]}</span>;
}

export function EntryStatusBadge({ status }: { status: EntryStatus }) {
  const cls =
    status === "accepted" ? "badge badge-green" : status === "rejected" ? "badge badge-red" : "badge badge-orange";
  return <span className={cls}>{ENTRY_STATUS[status]}</span>;
}

export function LineupStatusBadge({ status }: { status: LineupStatus | null }) {
  if (!status) return <span className="badge">Нет заявки</span>;
  const cls =
    status === "accepted"
      ? "badge badge-green"
      : status === "submitted"
        ? "badge badge-accent"
        : status === "rejected"
          ? "badge badge-red"
          : "badge badge-orange";
  return <span className={cls}>{LINEUP_STATUS[status]}</span>;
}

export function TournamentStatusBadge({ status }: { status: TournamentStatus }) {
  const cls =
    status === "ongoing"
      ? "badge badge-accent"
      : status === "registration"
        ? "badge badge-green"
        : status === "draft"
          ? "badge badge-orange"
          : "badge";
  return <span className={cls}>{TOURNAMENT_STATUS[status]}</span>;
}

export function TeamAvatar({ id, name, size }: { id: number; name: string; size?: "sm" }) {
  return (
    <span
      className={`team-avatar${size ? ` ${size}` : ""}`}
      style={{ background: teamColor(id) }}
      aria-hidden="true"
    >
      {teamInitial(name)}
    </span>
  );
}

export function FormError({ error }: { error: unknown }) {
  if (!error) return null;
  return <ErrorBox error={error} />;
}
