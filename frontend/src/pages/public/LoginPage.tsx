import { useState } from "react";
import type { FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { ROLE_HOME, rolesOf, useAuth } from "../../auth/AuthContext";
import type { Me } from "../../api/types";
import { FormError } from "../../components/ui";

function homeFor(me: Me | undefined) {
  const roles = rolesOf(me);
  return roles.length ? ROLE_HOME[roles[0]] : "/";
}

export function LoginPage() {
  const { login, register, loggedIn, me } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: string } | null)?.from;
  const [alreadyLoggedIn] = useState(loggedIn);
  const [mode, setMode] = useState<"login" | "register">("login");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({
    identifier: "",
    password: "",
    username: "",
    email: "",
    display_name: "",
  });
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  // Уже вошедшего пользователя сразу отправляем в кабинет (но не во время отправки формы —
  // туда ведёт обработчик onSubmit).
  if (alreadyLoggedIn && me) return <Navigate to={from || homeFor(me)} replace />;

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const me =
        mode === "login"
          ? await login(form.identifier.trim(), form.password)
          : await register({
              username: form.username.trim(),
              password: form.password,
              email: form.email.trim() || null,
              display_name: form.display_name.trim(),
            });
      navigate(from || (mode === "register" ? "/captain" : homeFor(me)), { replace: true });
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="container page" style={{ maxWidth: 440 }}>
      <form className="card stack" onSubmit={onSubmit}>
        <div className="chips">
          <button
            type="button"
            className={`chip${mode === "login" ? " active" : ""}`}
            onClick={() => setMode("login")}
          >
            Вход
          </button>
          <button
            type="button"
            className={`chip${mode === "register" ? " active" : ""}`}
            onClick={() => setMode("register")}
          >
            Регистрация
          </button>
        </div>
        <h1>{mode === "login" ? "Вход" : "Регистрация"}</h1>

        {mode === "login" ? (
          <div className="field">
            <label htmlFor="identifier">Логин или e-mail</label>
            <input
              id="identifier"
              className="input"
              autoComplete="username"
              required
              value={form.identifier}
              onChange={set("identifier")}
            />
          </div>
        ) : (
          <>
            <div className="field">
              <label htmlFor="display_name">Имя и фамилия</label>
              <input
                id="display_name"
                className="input"
                required
                value={form.display_name}
                onChange={set("display_name")}
              />
            </div>
            <div className="field">
              <label htmlFor="username">Логин</label>
              <input
                id="username"
                className="input"
                autoComplete="username"
                required
                pattern="[^@]+"
                title="Логин не должен содержать @"
                value={form.username}
                onChange={set("username")}
              />
            </div>
            <div className="field">
              <label htmlFor="email">E-mail</label>
              <input
                id="email"
                className="input"
                type="email"
                autoComplete="email"
                required
                value={form.email}
                onChange={set("email")}
              />
            </div>
          </>
        )}
        <div className="field">
          <label htmlFor="password">Пароль</label>
          <input
            id="password"
            className="input"
            type="password"
            autoComplete={mode === "login" ? "current-password" : "new-password"}
            required
            minLength={mode === "register" ? 8 : 1}
            value={form.password}
            onChange={set("password")}
          />
          {mode === "register" && <span className="hint">Не короче 8 символов, не только цифры.</span>}
        </div>

        <FormError error={error} />
        <button className="btn btn-lg btn-block" disabled={busy}>
          {busy ? "Подождите…" : mode === "login" ? "Войти" : "Зарегистрироваться"}
        </button>
        {mode === "register" && (
          <p className="hint" style={{ margin: 0 }}>
            После регистрации вы сможете создать команду и подать заявку на турнир. Судей и
            организаторов добавляет организатор турнира по вашему логину.
          </p>
        )}
      </form>
    </div>
  );
}
