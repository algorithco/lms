import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from 'react';
import type { ReactNode } from 'react';
import {
  Auth,
  AuthExpiredError,
  GoogleAuth,
  SessionAuth,
  getTokens,
  login as apiLogin,
  logout as apiLogout,
  normalizeUser,
  register as apiRegister,
  setTokens,
} from '../lib/api';
import type { AuthUser, TokenPair } from '../lib/api';
import { storeLang } from '../i18n/LangContext';

interface AuthState {
  user: AuthUser | null;
  loading: boolean;
  error: string | null;
  isAuthModalOpen: boolean;
  authModalMode: 'login' | 'register';
  openAuthModal: (mode?: 'login' | 'register') => void;
  closeAuthModal: () => void;
  login: (email: string, password: string) => Promise<AuthUser>;
  loginWithTokens: (tokens: TokenPair, rawUser?: Record<string, unknown>) => Promise<AuthUser>;
  loginWithTelegram: (tokens: TokenPair, rawUser: Record<string, unknown>) => AuthUser;
  loginWithGoogle: (credential: string) => Promise<AuthUser>;
  register: (payload: {
    email: string;
    password: string;
    password_confirm: string;
    first_name: string;
    last_name: string;
    role?: string;
  }) => Promise<AuthUser>;
  logout: () => Promise<void>;
}

const Ctx = createContext<AuthState | null>(null);

/** Public SPA paths where an expired session must NOT force a /login bounce. */
const PUBLIC_PREFIXES = ['/login', '/register', '/password-reset', '/verify', '/certificates/verify'];

function isProtectedPath(pathname: string): boolean {
  if (pathname === '/') return false;
  return !PUBLIC_PREFIXES.some((p) => pathname === p || pathname.startsWith(`${p}/`));
}

/** Keep local language preference or default strictly to Uzbek (uz). */
function adoptServerLang(language: unknown): void {
  try {
    const existing = localStorage.getItem('lms_lang');
    if (!existing) {
      storeLang('uz');
      return;
    }
    if (language === 'uz' || language === 'ru' || language === 'en') {
      // Local choice always wins if already set
    }
  } catch {
    /* ignore */
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [authModalMode, setAuthModalMode] = useState<'login' | 'register'>('login');

  const openAuthModal = useCallback((mode: 'login' | 'register' = 'login') => {
    setAuthModalMode(mode);
    setIsAuthModalOpen(true);
  }, []);

  const closeAuthModal = useCallback(() => {
    setIsAuthModalOpen(false);
  }, []);

  // Restore session on mount if tokens exist (api() auto-refreshes if needed).
  // Also check URL parameters for OAuth redirect tokens (?access=...&refresh=...)
  // and fallback to active Django session.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const oauthAccess = params.get('access');
    const oauthRefresh = params.get('refresh');

    if (oauthAccess && oauthRefresh) {
      setTokens(oauthAccess, oauthRefresh);
      // Clean up URL without reload and redirect to /dashboard if on auth page
      const isAuthPath = window.location.pathname === '/login' || window.location.pathname === '/register';
      const cleanUrl = isAuthPath ? '/dashboard' : window.location.pathname;
      window.history.replaceState({}, document.title, cleanUrl);
      if (isAuthPath) {
        window.location.assign('/dashboard');
        return;
      }
    }

    const { access, refresh } = getTokens();
    if (!access && !refresh) {
      SessionAuth.status()
        .then((st) => {
          if (st.authenticated && st.tokens) {
            setTokens(st.tokens.access, st.tokens.refresh);
            if (st.user) {
              const u = normalizeUser(st.user);
              setUser(u);
              adoptServerLang(u.language);
              setLoading(false);
              return;
            }
          }
          setLoading(false);
        })
        .catch(() => setLoading(false));
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
      adoptServerLang(user.language);
      setUser(user);
      return user;
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Login failed.');
      throw e;
    }
  }, []);

  const loginWithTokens = useCallback(
    async (tokens: TokenPair, rawUser?: Record<string, unknown>) => {
      setError(null);
      setTokens(tokens.access, tokens.refresh);
      let resolvedUser: AuthUser;
      if (rawUser) {
        resolvedUser = normalizeUser(rawUser);
      } else {
        resolvedUser = await Auth.me();
      }
      adoptServerLang(resolvedUser.language);
      setUser(resolvedUser);
      return resolvedUser;
    },
    [],
  );

  const loginWithGoogle = useCallback(
    async (credential: string) => {
      setError(null);
      try {
        const data = await GoogleAuth.verify(credential);
        setTokens(data.tokens.access, data.tokens.refresh);
        const user = normalizeUser(data.user);
        adoptServerLang(user.language);
        setUser(user);
        return user;
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Google login failed.');
        throw e;
      }
    },
    [],
  );

  // Google One Tap automatic prompt on landing/public pages
  useEffect(() => {
    if (loading || user) return;

    let cancelled = false;
    GoogleAuth.getConfig().then((cfg) => {
      if (cancelled || !cfg.enabled || !cfg.client_id) return;
      const google = (window as unknown as {
        google?: {
          accounts?: {
            id?: {
              initialize: (options: Record<string, unknown>) => void;
              prompt: () => void;
            };
          };
        };
      }).google;

      if (!google?.accounts?.id) return;

      try {
        google.accounts.id.initialize({
          client_id: cfg.client_id,
          callback: async (resp: { credential?: string }) => {
            if (resp.credential) {
              try {
                await loginWithGoogle(resp.credential);
              } catch (err) {
                console.error('Google One Tap verification failed:', err);
              }
            }
          },
          auto_select: false,
          cancel_on_tap_outside: true,
        });
        google.accounts.id.prompt();
      } catch {
        /* ignore GIS initialization errors */
      }
    });

    return () => {
      cancelled = true;
    };
  }, [loading, user, loginWithGoogle]);

  const register = useCallback(
    async (payload: {
      email: string;
      password: string;
      password_confirm: string;
      first_name: string;
      last_name: string;
      role?: string;
    }) => {
      setError(null);
      try {
        const { user } = await apiRegister(payload);
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
    setUser(null);
  }, []);

  const loginWithTelegram = useCallback((tokens: TokenPair, rawUser: Record<string, unknown>) => {
    setError(null);
    setTokens(tokens.access, tokens.refresh);
    const user = normalizeUser(rawUser);
    adoptServerLang(user.language);
    setUser(user);
    return user;
  }, []);

  return (
    <Ctx.Provider
      value={{
        user,
        loading,
        error,
        isAuthModalOpen,
        authModalMode,
        openAuthModal,
        closeAuthModal,
        login,
        loginWithTokens,
        loginWithTelegram,
        loginWithGoogle,
        register,
        logout,
      }}
    >
      {children}
    </Ctx.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}
