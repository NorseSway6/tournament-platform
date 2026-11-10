import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { ROLE_HOME, ROLE_LABEL, useAuth } from "../auth/AuthContext";

function LogoMark() {
  return (
    <svg className="logo-mark" viewBox="0 0 32 32" aria-hidden="true">
      <circle cx="16" cy="16" r="13" fill="#fff" />
      <path d="M16 9.5l4.2 3-1.6 4.9h-5.2l-1.6-4.9z" fill="#154E3A" />
      <path
        d="M16 3v6.5M27.4 11.5l-7.2 1M23 25.5l-4.4-8.1M9 25.5l4.4-8.1M4.6 11.5l7.2 1"
        stroke="#154E3A"
        strokeWidth="1.6"
      />
    </svg>
  );
}

export function Layout() {
  const { loggedIn, roles, displayName, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => setOpen(false), [location.pathname]);

  return (
    <>
      <header className={`site-header${open ? " open" : ""}`}>
        <div className="container">
          <Link to="/" className="logo">
            <LogoMark />
            Горизонт
          </Link>
          <button
            className="menu-toggle"
            aria-label="Меню"
            aria-expanded={open}
            onClick={() => setOpen((v) => !v)}
          >
            {open ? "✕" : "☰"}
          </button>
          <nav className="nav">
            <NavLink to="/" end>
              Турниры
            </NavLink>
            {roles.map((r) => (
              <NavLink key={r} to={ROLE_HOME[r]}>
                {ROLE_LABEL[r]}
              </NavLink>
            ))}
          </nav>
          <div className="header-user">
            {loggedIn ? (
              <>
                <span className="name" title={displayName}>
                  {displayName}
                </span>
                <button
                  className="btn btn-sm btn-light"
                  onClick={async () => {
                    // Сначала уходим на публичную страницу, иначе закрытая страница
                    // успеет перенаправить на форму входа.
                    navigate("/");
                    await logout();
                  }}
                >
                  Выйти
                </button>
              </>
            ) : (
              <Link to="/login" className="btn btn-sm btn-light">
                Вход
              </Link>
            )}
          </div>
        </div>
      </header>
      <main>
        <Outlet />
      </main>
      <footer className="site-footer">
        <div className="container">
          <span>Горизонт — любительские футбольные турниры Свердловской области</span>
          <span>© {new Date().getFullYear()}</span>
        </div>
      </footer>
    </>
  );
}
