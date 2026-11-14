import type { ReactNode } from "react";
import { Link, Navigate, useLocation } from "react-router-dom";
import { ROLE_LABEL, useAuth } from "../auth/AuthContext";
import type { Role } from "../auth/AuthContext";
import { Spinner } from "./ui";

/**
 * Пускает на страницу только вошедших пользователей с нужной ролью.
 * allowWithoutRole — страница доступна любому вошедшему (например, «стать капитаном»).
 */
export function RequireRole({
  role,
  children,
  allowWithoutRole,
}: {
  role?: Role;
  children: ReactNode;
  allowWithoutRole?: boolean;
}) {
  const { loggedIn, loading, roles, me } = useAuth();
  const location = useLocation();

  if (!loggedIn) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  if (loading || !me) return <Spinner />;
  if (role && !allowWithoutRole && !roles.includes(role)) {
    return (
      <div className="container page">
        <div className="card center stack">
          <h2>Раздел «{ROLE_LABEL[role]}» недоступен</h2>
          <p className="muted">У вашего аккаунта нет этой роли.</p>
          <div>
            <Link to="/" className="btn">
              На главную
            </Link>
          </div>
        </div>
      </div>
    );
  }
  return <>{children}</>;
}
