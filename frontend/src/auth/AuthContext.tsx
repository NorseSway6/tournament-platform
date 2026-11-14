import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getRefreshToken, hasTokens, onTokensChange, setTokens } from "../api/client";
import { authApi } from "../api/endpoints";
import type { Me, RegisterIn } from "../api/types";

export type Role = "organizer" | "captain" | "judge";

export const ROLE_LABEL: Record<Role, string> = {
  organizer: "Организатор",
  captain: "Капитан",
  judge: "Судья",
};
export const ROLE_HOME: Record<Role, string> = {
  organizer: "/organizer",
  captain: "/captain",
  judge: "/judge",
};

interface AuthState {
  /** Есть ли сохранённые токены. */
  loggedIn: boolean;
  /** Данные /me (роли пользователя). */
  me: Me | undefined;
  loading: boolean;
  roles: Role[];
  displayName: string;
  login: (identifier: string, password: string) => Promise<Me>;
  register: (data: RegisterIn) => Promise<Me>;
  logout: () => Promise<void>;
  refreshMe: () => Promise<Me | undefined>;
}

const AuthContext = createContext<AuthState | null>(null);

export function rolesOf(me: Me | undefined): Role[] {
  if (!me) return [];
  const admin = me.roles.admin.enabled;
  const roles: Role[] = [];
  if (me.roles.organizer.enabled || admin) roles.push("organizer");
  if (me.roles.captain.enabled) roles.push("captain");
  if (me.roles.judge.enabled) roles.push("judge");
  return roles;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const [loggedIn, setLoggedIn] = useState(hasTokens());

  useEffect(() => onTokensChange(() => setLoggedIn(hasTokens())), []);

  const meQuery = useQuery({
    queryKey: ["me"],
    queryFn: authApi.me,
    enabled: loggedIn,
    staleTime: 30_000,
    retry: false,
  });

  const refreshMe = useCallback(async () => {
    const res = await meQuery.refetch();
    return res.data;
  }, [meQuery]);

  const afterAuth = useCallback(async () => {
    const me = await qc.fetchQuery({ queryKey: ["me"], queryFn: authApi.me, staleTime: 0 });
    return me;
  }, [qc]);

  const login = useCallback(
    async (identifier: string, password: string) => {
      setTokens(await authApi.login(identifier, password));
      return afterAuth();
    },
    [afterAuth],
  );

  const register = useCallback(
    async (data: RegisterIn) => {
      setTokens(await authApi.register(data));
      return afterAuth();
    },
    [afterAuth],
  );

  const logout = useCallback(async () => {
    const refresh = getRefreshToken();
    if (refresh) await authApi.logout(refresh).catch(() => undefined);
    setTokens(null);
    qc.clear();
  }, [qc]);

  const value = useMemo<AuthState>(() => {
    const me = loggedIn ? meQuery.data : undefined;
    return {
      loggedIn,
      me,
      loading: loggedIn && meQuery.isLoading,
      roles: rolesOf(me),
      displayName: me?.profile?.display_name || me?.profile?.username || "",
      login,
      register,
      logout,
      refreshMe,
    };
  }, [loggedIn, meQuery.data, meQuery.isLoading, login, register, logout, refreshMe]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
