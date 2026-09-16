import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from 'react';
import type { ReactNode } from 'react';
import { Auth, AuthExpiredError, getTokens, login as apiLogin, logout as apiLogout, normalizeUser, register as apiRegister, setTokens } from '../lib/api';
import type { AuthUser, TokenPair } from '../lib/api';
import { storeLang } from '../i18n/LangContext';
import type { AppLang } from '../i18n/LangContext';

interface AuthState {
  user: AuthUser | null;
  loading: boolean;
  error: string | null;
  login: (email: string, password: string) => Promise<AuthUser>;
  loginWithTelegram: (tokens: TokenPair, rawUser: Record<string, unknown>) => AuthUser;
  register: (payload: {
    email: string;
    password: string;
    password_confirm: string;
    first_name: string;
    last_name: string;
  }) => Promise<AuthUser>;
  logout: () => Promise<void>;
}

const Ctx = createContext<AuthState | null>(null);

// Last-used password, memory-only (never persisted) — solely so the Django
// session bridge (arena WS + session JSON) can run same-origin after login.
let cachedPassword: string | null = null;

/** Public SPA paths where an expired session must NOT force a /login bounce. */
const PUBLIC_PREFIXES = ['/login', '/register', '/password-reset', '/verify', '/certificates/verify'];

function isProtectedPath(pathname: string): boolean {
  if (pathname === '/') return false;
  return !PUBLIC_PREFIXES.some((p) => pathname === p || pathname.startsWith(`${p}/`));
}

/** Adopt the server-side language preference (local choice wins if already set). */
function adoptServerLang(language: unknown): void {
  if (language !== 'uz' && language !== 'ru' && language !== 'en') return;
  try {
    if (!localStorage.getItem('lms_lang')) storeLang(language as AppLang);
  } catch {
    /* ignore */
  }
}

export function getCachedPassword(): string | null {
  return cachedPassword;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Restore session on mount if tokens exist (api() auto-refreshes if needed).
  // A refresh failure means the refresh token was rotated/blacklisted or
  // expired: tokens are already cleared by api(), the user is dropped, and
  // protected deep links bounce to /login (public pages stay put).
  useEffect(() => {
    const { access, refresh } = getTokens();
    if (!access && !refresh) {
      setLoading(false);
      return;
    }
    Auth.me()
      .then((u) => {
        setUser(u);
        adoptServerLang(u.language);
      })
      .catch((e) => {
        setUser(null);
        if (e instanceof AuthExpiredError && isProtectedPath(window.location.pathname)) {
          window.location.assign('/login');
        }
      })
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    setError(null);
    try {
      const { user } = await apiLogin(email, password);
      cachedPassword = password;
      adoptServerLang(user.language);
      setUser(user);
      return user;
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Login failed.');
      throw e;
    }
  }, []);

  const register = useCallback(
    async (payload: {
      email: string;
      password: string;
      password_confirm: string;
      first_name: string;
      last_name: string;
    }) => {
      setError(null);
      try {
        const { user } = await apiRegister(payload);
        cachedPassword = payload.password;
        adoptServerLang(user.language);
        setUser(user);
        return user;
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Registration failed.');
        throw e;
      }
    },
    [],
  );

  const logout = useCallback(async () => {
    await apiLogout();
    cachedPassword = null;
    setUser(null);
  }, []);

  // Adopt a Telegram bot login: the backend already created the Django
  // session (same response), so only the JWT pair needs storing.
  const loginWithTelegram = useCallback((tokens: TokenPair, rawUser: Record<string, unknown>) => {
    setError(null);
    setTokens(tokens.access, tokens.refresh);
    const user = normalizeUser(rawUser);
    adoptServerLang(user.language);
    setUser(user);
    return user;
  }, []);

  return (
    <Ctx.Provider value={{ user, loading, error, login, register, logout, loginWithTelegram }}>
      {children}
    </Ctx.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}
