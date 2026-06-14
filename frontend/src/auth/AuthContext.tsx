import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { api } from "@/lib/api";
import type { Me, HouseholdSummary } from "@/lib/types";

interface AuthContextValue {
  me: Me | null;
  loading: boolean;
  household: HouseholdSummary | null;
  setHouseholdId: (id: number) => void;
  refresh: () => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  register: (payload: RegisterPayload) => Promise<void>;
  logout: () => Promise<void>;
}

interface RegisterPayload {
  email: string;
  password: string;
  display_name: string;
  household_name?: string;
  invite_token?: string;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);
const HOUSEHOLD_KEY = "bibliothek-household";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);
  const [householdId, setHouseholdIdState] = useState<number | null>(() => {
    const stored = localStorage.getItem(HOUSEHOLD_KEY);
    return stored ? Number(stored) : null;
  });

  const refresh = useCallback(async () => {
    try {
      const data = await api.get<Me>("/api/auth/me");
      setMe(data);
    } catch {
      setMe(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const setHouseholdId = useCallback((id: number) => {
    setHouseholdIdState(id);
    localStorage.setItem(HOUSEHOLD_KEY, String(id));
  }, []);

  const household = useMemo(() => {
    if (!me || me.households.length === 0) return null;
    return me.households.find((h) => h.id === householdId) ?? me.households[0];
  }, [me, householdId]);

  const login = useCallback(
    async (email: string, password: string) => {
      const data = await api.post<Me>("/api/auth/login", { email, password });
      setMe(data);
    },
    [],
  );

  const register = useCallback(async (payload: RegisterPayload) => {
    const data = await api.post<Me>("/api/auth/register", payload);
    setMe(data);
  }, []);

  const logout = useCallback(async () => {
    await api.post("/api/auth/logout");
    setMe(null);
  }, []);

  const value: AuthContextValue = {
    me,
    loading,
    household,
    setHouseholdId,
    refresh,
    login,
    register,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
