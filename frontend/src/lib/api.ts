/**
 * LMS API client — JWT (access 60m / refresh 7d with rotation).
 * Matches config/settings/base.py SIMPLE_JWT + apps/accounts/urls.py.
 *
 * Tokens live in sessionStorage (cleared on tab close). All calls go
 * same-origin (Vite proxy in dev, nginx in prod) so no CORS is needed.
 */

const API_BASE = import.meta.env.VITE_API_URL ?? '';

const ACCESS_KEY = 'lms_access';
const REFRESH_KEY = 'lms_refresh';

export class AuthExpiredError extends Error {
  constructor() {
    super('Session expired — please log in again.');
  }
}

export function getTokens(): { access: string | null; refresh: string | null } {
  return {
    access: sessionStorage.getItem(ACCESS_KEY),
    refresh: sessionStorage.getItem(REFRESH_KEY),
  };
}

export function setTokens(access: string, refresh: string): void {
  sessionStorage.setItem(ACCESS_KEY, access);
  sessionStorage.setItem(REFRESH_KEY, refresh);
}

export function clearTokens(): void {
  sessionStorage.removeItem(ACCESS_KEY);
  sessionStorage.removeItem(REFRESH_KEY);
}

// Cross-tab sync: keep sessionStorage as store, listen for lms_access changes via storage event
if (typeof window !== 'undefined') {
  window.addEventListener('storage', (e) => {
    if (e.key === ACCESS_KEY) {
      if (e.newValue) sessionStorage.setItem(ACCESS_KEY, e.newValue);
      else sessionStorage.removeItem(ACCESS_KEY);
    }
    if (e.key === REFRESH_KEY) {
      if (e.newValue) sessionStorage.setItem(REFRESH_KEY, e.newValue);
      else sessionStorage.removeItem(REFRESH_KEY);
    }
  });
}

let refreshAttempt: Promise<string> | null = null;

async function refreshTokens(): Promise<string> {
  // Single-flight: concurrent 401s share one refresh so rotation does not
  // blacklist the refresh token out from under a parallel caller.
  if (refreshAttempt) return refreshAttempt;
  refreshAttempt = (async () => {
    const { refresh } = getTokens();
    if (!refresh) throw new AuthExpiredError();
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);
    let res: Response;
    try {
      res = await fetch(`${API_BASE}/api/auth/token/refresh/`, {
        method: 'POST',
        credentials: 'omit',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh }),
        signal: controller.signal,
      });
    } finally {
      clearTimeout(timeout);
    }
    if (!res.ok) {
      clearTokens();
      throw new AuthExpiredError();
    }
    // Rotation: backend returns a NEW pair — replace both (old refresh is blacklisted).
    const data = (await res.json()) as { access: string; refresh: string };
    setTokens(data.access, data.refresh);
    return data.access;
  })();
  try {
    return await refreshAttempt;
  } finally {
    refreshAttempt = null;
  }
}

export interface ApiError extends Error {
  status: number;
  detail: string;
}

/** Authenticated fetch with one automatic refresh-and-retry on 401. */
export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const doFetch = async (access: string | null): Promise<Response> => {
    const headers = new Headers(init.headers);
    if (access) headers.set('Authorization', `Bearer ${access}`);
    if (init.body && !(init.body instanceof FormData) && !headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json');
    }
    return fetch(`${API_BASE}${path}`, { ...init, headers });
  };

  let res = await doFetch(getTokens().access);
  if (res.status === 401 && getTokens().refresh) {
    try {
      const access = await refreshTokens();
      res = await doFetch(access);
    } catch (e) {
      if (e instanceof AuthExpiredError) throw e;
      throw e;
    }
  }
  if (res.status === 401) {
    clearTokens();
    throw new AuthExpiredError();
  }
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = (await res.json()) as unknown;
      if (typeof body === 'object' && body !== null && 'detail' in body) {
        detail = String((body as { detail: unknown }).detail);
      } else {
        detail = JSON.stringify(body);
      }
    } catch {
      /* keep default */
    }
    const err = new Error(detail) as ApiError;
    err.status = res.status;
    err.detail = detail;
    throw err;
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

// ---------------------------------------------------------------------------
// Typed endpoints (mirrors apps/*/urls.py + serializers)
// ---------------------------------------------------------------------------

export interface TokenPair {
  access: string;
  refresh: string;
}

export interface AuthUser {
  id: number;
  email: string;
  role: 'student' | 'teacher' | 'admin' | 'parent';
  full_name: string;
  is_active: boolean;
  first_name?: string;
  last_name?: string;
  language?: string;
  is_staff?: boolean;
  is_superuser?: boolean;
  is_platform_admin?: boolean;
}

/** Platform admin = superuser or role==admin (mirrors apps/accounts/access.py). */
export function isPlatformAdmin(u: AuthUser | null | undefined): boolean {
  if (!u) return false;
  return u.is_platform_admin === true || u.is_superuser === true || u.role === 'admin';
}

/** School/teacher area access (mirrors webapi IsTeacherOrAdmin: teacher/staff/platform-admin). */
export function canTeach(u: AuthUser | null | undefined): boolean {
  if (!u) return false;
  return u.role === 'teacher' || u.is_staff === true || isPlatformAdmin(u);
}

/** Essay review access (mirrors essays teacher_required: teacher/platform-admin only). */
export function canReviewEssays(u: AuthUser | null | undefined): boolean {
  if (!u) return false;
  return u.role === 'teacher' || isPlatformAdmin(u);
}

/** Parent portal access (mirrors school parent_overview_view). */
export function canViewParent(u: AuthUser | null | undefined): boolean {
  if (!u) return false;
  return u.role === 'parent' || isPlatformAdmin(u);
}

/**
 * Backend user shapes differ per endpoint:
 * - POST /api/auth/login/      → { id, email, role, full_name, is_active }
 * - POST /api/auth/register/   → UserProfileSerializer (first/last_name, no full_name)
 * - GET  /api/auth/me/         → UserProfileSerializer (first/last_name, no full_name)
 * Normalize every shape into AuthUser so consumers (Layout avatar, guards)
 * never crash on a missing full_name.
 */
export function normalizeUser(raw: Record<string, unknown>): AuthUser {
  const first = typeof raw.first_name === 'string' ? raw.first_name : '';
  const last = typeof raw.last_name === 'string' ? raw.last_name : '';
  const full =
    (typeof raw.full_name === 'string' && raw.full_name.trim()) ||
    `${first} ${last}`.trim() ||
    (typeof raw.email === 'string' ? raw.email : '');
  return {
    id: Number(raw.id),
    email: typeof raw.email === 'string' ? raw.email : '',
    role: (raw.role as AuthUser['role']) ?? 'student',
    full_name: full,
    is_active: typeof raw.is_active === 'boolean' ? raw.is_active : true,
    ...(first ? { first_name: first } : {}),
    ...(last ? { last_name: last } : {}),
    ...(typeof raw.language === 'string' ? { language: raw.language } : {}),
    ...(typeof raw.is_staff === 'boolean' ? { is_staff: raw.is_staff } : {}),
    ...(typeof raw.is_superuser === 'boolean' ? { is_superuser: raw.is_superuser } : {}),
    ...(typeof raw.is_platform_admin === 'boolean'
      ? { is_platform_admin: raw.is_platform_admin }
      : {}),
  };
}

/** Turn a DRF error body into a human-readable message (field errors joined). */
function parseErrorBody(body: unknown, fallback: string): string {
  if (typeof body === 'object' && body !== null) {
    const o = body as Record<string, unknown>;
    if (typeof o.detail === 'string' && o.detail) return o.detail;
    const parts: string[] = [];
    for (const [key, value] of Object.entries(o)) {
      if (Array.isArray(value)) {
        parts.push(key === 'non_field_errors' ? value.join(' ') : `${key}: ${value.join(' ')}`);
      } else if (typeof value === 'string') {
        parts.push(key === 'non_field_errors' ? value : `${key}: ${value}`);
      }
    }
    if (parts.length > 0) return parts.join(' ');
  }
  return fallback;
}

async function throwForResponse(res: Response, fallback: string): Promise<never> {
  let detail = fallback;
  try {
    detail = parseErrorBody(await res.json(), fallback);
  } catch {
    /* keep fallback */
  }
  throw new Error(detail);
}

export async function register(payload: {
  email: string;
  password: string;
  password_confirm: string;
  first_name: string;
  last_name: string;
}): Promise<{ user: AuthUser; tokens: TokenPair }> {
  const res = await fetch(`${API_BASE}/api/auth/register/`, {
    method: 'POST',
    credentials: 'omit',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) await throwForResponse(res, 'Registration failed — check the form.');
  const data = (await res.json()) as { user: Record<string, unknown>; tokens: TokenPair };
  setTokens(data.tokens.access, data.tokens.refresh);
  return { user: normalizeUser(data.user), tokens: data.tokens };
}

export async function login(
  email: string,
  password: string,
): Promise<{ user: AuthUser; tokens: TokenPair }> {
  const res = await fetch(`${API_BASE}/api/auth/login/`, {
    method: 'POST',
    credentials: 'omit',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) await throwForResponse(res, 'Invalid email or password.');
  const data = (await res.json()) as { user: Record<string, unknown>; tokens: TokenPair };
  setTokens(data.tokens.access, data.tokens.refresh);
  return { user: normalizeUser(data.user), tokens: data.tokens };
}

export async function logout(): Promise<void> {
  let { access, refresh } = getTokens();
  try {
    // If the access token expired but the refresh token is still valid,
    // rotate once so the server can actually blacklist the refresh token
    // (otherwise it would stay usable for its full 7d lifetime).
    if (!access && refresh) {
      try {
        access = await refreshTokens();
        refresh = getTokens().refresh;
      } catch {
        /* fall through — still clear everything client-side */
      }
    }
    // Close the Django session too (arena WS + session JSON use the cookie;
    // JWT blacklist alone would leave it authenticated).
    try {
      const headers: Record<string, string> = {};
      if (access) headers.Authorization = `Bearer ${access}`;
      const csrf = getCookie('csrftoken');
      if (csrf) headers['X-CSRFToken'] = csrf;
      await fetch(`${API_BASE}/api/auth/session/logout/`, {
        method: 'POST',
        credentials: 'include',
        headers,
      });
    } catch {
      /* best-effort */
    }
    if (access && refresh) {
      await fetch(`${API_BASE}/api/auth/logout/`, {
        method: 'POST',
        credentials: 'omit',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${access}`,
        },
        body: JSON.stringify({ refresh }),
      });
    }
  } finally {
    clearTokens();
    sessionReady = false;
  }
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface TestSummary {
  id: number;
  title: string;
  // List serializer fields vary — keep open for backend evolution.
  [key: string]: unknown;
}

export interface Attempt {
  id: number;
  status: string;
  [key: string]: unknown;
}

export const Auth = {
  me: async () => normalizeUser((await api<Record<string, unknown>>('/api/auth/me/'))),
  requestPasswordReset: async (email: string) => {
    const res = await fetch(`${API_BASE}/api/auth/password-reset/`, {
      method: 'POST',
      credentials: 'omit',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email }),
    });
    if (!res.ok) throw new Error(`Request failed (${res.status})`);
  },
  confirmPasswordReset: async (payload: {
    uid: string;
    token: string;
    new_password1: string;
    new_password2: string;
  }) => {
    const res = await fetch(`${API_BASE}/api/auth/password-reset/confirm/`, {
      method: 'POST',
      credentials: 'omit',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) await throwForResponse(res, 'Reset failed.');
  },
};

/**
 * Authenticated binary download (e.g. certificate PDFs) with the same
 * JWT refresh-and-retry semantics as api(). A plain <a href> cannot send
 * the Bearer header, so binary endpoints need this instead of downloadUrl
 * links whenever the user has a JWT session but no Django session cookie.
 */
export async function apiBlob(path: string, init: RequestInit = {}): Promise<Blob> {
  const doFetch = async (access: string | null): Promise<Response> => {
    const headers = new Headers(init.headers);
    if (access) headers.set('Authorization', `Bearer ${access}`);
    return fetch(`${API_BASE}${path}`, { ...init, headers });
  };

  let res = await doFetch(getTokens().access);
  if (res.status === 401 && getTokens().refresh) {
    try {
      const access = await refreshTokens();
      res = await doFetch(access);
    } catch (e) {
      if (e instanceof AuthExpiredError) throw e;
      throw e;
    }
  }
  if (res.status === 401) {
    clearTokens();
    throw new AuthExpiredError();
  }
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      detail = parseErrorBody(await res.json(), detail);
    } catch {
      /* keep default (probably a binary error page) */
    }
    const err = new Error(detail) as ApiError;
    err.status = res.status;
    err.detail = detail;
    throw err;
  }
  return res.blob();
}

export const Tests = {
  list: () => api<Paginated<TestSummary>>('/api/tests/'),
  detail: (id: string) => api<Record<string, unknown>>(`/api/tests/${id}/`),
  start: (id: string) =>
    api<Attempt | { attempt_id: number }>(`/api/tests/${id}/start/`, {
      method: 'POST',
    }),
  attempt: (id: string) => api<Attempt>(`/api/tests/attempts/${id}/`),
  saveAnswer: (
    attemptId: string,
    payload: { question_id: number; choice_ids?: number[]; text_answer?: string },
  ) =>
    api<unknown>(`/api/tests/attempts/${attemptId}/save-answer/`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  submit: (attemptId: string) =>
    api<unknown>(`/api/tests/attempts/${attemptId}/submit/`, {
      method: 'POST',
    }),
};

export const Results = {
  mine: () => api<Paginated<Record<string, unknown>>>('/api/results/my-results/'),
  stats: () => api<Record<string, unknown>>('/api/results/stats/'),
  detail: (id: string) =>
    api<Record<string, unknown>>(`/api/results/${id}/detail/`),
};

export const Certificates = {
  mine: () =>
    api<Paginated<Record<string, unknown>>>('/api/certificates/my-certificates/'),
  verify: (number: string) =>
    api<Record<string, unknown>>(`/api/certificates/verify/${number}/`),
  downloadUrl: (id: string | number) =>
    `${API_BASE}/api/certificates/${id}/download/`,
};

// ---------------------------------------------------------------------------
// Web Push (apps/notifications push_* views, JWT via api()).
// Opt-in: call Push.subscribe() from a user gesture after Notification
// permission is granted. The service worker (/sw.js) shows incoming pushes.
// ---------------------------------------------------------------------------

function urlBase64ToUint8Array(base64: string): Uint8Array {
  const padding = '='.repeat((4 - (base64.length % 4)) % 4);
  const raw = window.atob((base64 + padding).replace(/-/g, '+').replace(/_/g, '/'));
  return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)));
}

export const Push = {
  supported: () =>
    'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window,
  vapidKey: () =>
    api<{ public_key: string }>('/api/notifications/push/vapid-key/'),
  subscribe: async (): Promise<boolean> => {
    if (!Push.supported()) return false;
    const permission = await Notification.requestPermission();
    if (permission !== 'granted') return false;
    const reg = await navigator.serviceWorker.ready;
    const existing = await reg.pushManager.getSubscription();
    if (existing) return true;
    const { public_key } = await Push.vapidKey();
    if (!public_key) return false;
    const sub = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(public_key).buffer as ArrayBuffer,
    });
    const keys = sub.toJSON().keys ?? {};
    await api('/api/notifications/push/subscribe/', {
      method: 'POST',
      body: JSON.stringify({
        endpoint: sub.endpoint,
        p256dh: keys.p256dh ?? '',
        auth: keys.auth ?? '',
      }),
    });
    return true;
  },
  unsubscribe: async (): Promise<void> => {
    if (!Push.supported()) return;
    const reg = await navigator.serviceWorker.ready;
    const sub = await reg.pushManager.getSubscription();
    const endpoint = sub?.endpoint ?? '';
    if (sub) await sub.unsubscribe();
    await api('/api/notifications/push/unsubscribe/', {
      method: 'POST',
      body: JSON.stringify({ endpoint }),
    });
  },
};

// ---------------------------------------------------------------------------
// Django session bridge (for WS arena + session-only JSON endpoints).
// The WS consumer uses AuthMiddlewareStack (session cookie only — JWT in a
// header cannot authenticate a WebSocket). After JWT login we ALSO establish
// a Django session via the JSON bridge POST /api/auth/session/ same-origin
// (Vite proxy / nginx forward cookies). Non-blocking: JWT flows work
// without it; arena/session features degrade gracefully.
// ---------------------------------------------------------------------------

export function getCookie(name: string): string | null {
  const m = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return m ? decodeURIComponent(m[1]) : null;
}

let sessionReady = false;
let sessionAttempt: Promise<boolean> | null = null;

/** Probe whether the Django session cookie is currently valid. */
async function probeSession(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/api/auth/session/status/`, {
      credentials: 'include',
    });
    if (!res.ok) return false;
    const data = (await res.json()) as { authenticated?: boolean };
    return data.authenticated === true;
  } catch {
    return false;
  }
}

/** Best-effort Django session login. Returns true when session is usable. */
export function ensureSession(email: string, password: string): Promise<boolean> {
  if (sessionReady) return Promise.resolve(true);
  if (sessionAttempt) return sessionAttempt;
  sessionAttempt = (async () => {
    try {
      // Probe-first: the session cookie may already be valid (e.g. after a
      // page reload where the in-memory password cache is gone).
      if (await probeSession()) {
        sessionReady = true;
        return true;
      }
      if (!password) return false;
      const res = await fetch(`${API_BASE}/api/auth/session/`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      sessionReady = res.ok;
      return sessionReady;
    } catch {
      return false;
    } finally {
      sessionAttempt = null;
    }
  })();
  return sessionAttempt;
}

/** Same-origin session-authenticated fetch (cookies incl. CSRF for POST). */
export async function sessionApi<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  const csrf = getCookie('csrftoken');
  if (csrf && init.method && init.method.toUpperCase() !== 'GET') {
    headers.set('X-CSRFToken', csrf);
  }
  let res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
    credentials: 'include',
  });
  if (res.status === 401) {
    try {
      const ok = await probeSession();
      if (ok) {
        res = await fetch(`${API_BASE}${path}`, {
          ...init,
          headers,
          credentials: 'include',
        });
        if (res.ok) return (await res.json()) as T;
      }
    } catch (e) {
      if (e instanceof AuthExpiredError) throw e;
    }
    throw new AuthExpiredError();
  }
  if (!res.ok) throw new Error(`Request failed (${res.status})`);
  return (await res.json()) as T;
}

/** WebSocket URL for the arena (same host, ws/wss matching page protocol). */
export function arenaSocketUrl(roomCode?: string): string {
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
  const base = `${proto}://${window.location.host}/ws/arena/`;
  return roomCode ? `${base}${roomCode}/` : base;
}

export interface TelegramAuthStart {
  token: string;
  deep_link: string;
  expires_in: number;
}

export type TelegramAuthStatus =
  | { status: 'pending' }
  | { status: 'verified'; user_id: number; user_name: string; login_url: string }
  | { status: 'expired'; error?: string }
  | { status: 'invalid' | 'throttled'; error?: string };

export interface TelegramAuthLogin {
  status: string;
  redirect: string;
  user_name: string;
  user: Record<string, unknown>;
  tokens: TokenPair;
}

/**
 * Web login via Telegram bot (mirrors apps/notifications/telegram_auth.py).
 * Session-cookie bound (same session must start → poll → login), so every
 * call uses credentials:include. Successful logins return a JWT pair that
 * the SPA adopts exactly like an email/password login (the Django session
 * login in the same response additionally powers arena WS + session APIs).
 */
export const TelegramAuth = {
  start: () =>
    sessionApi<TelegramAuthStart>('/api/notifications/telegram/auth/start/', {
      method: 'POST',
    }),
  status: (token: string) =>
    sessionApi<TelegramAuthStatus>(
      `/api/notifications/telegram/auth/${encodeURIComponent(token)}/status/`,
    ),
  loginWithToken: (token: string) =>
    sessionApi<TelegramAuthLogin>(
      `/api/notifications/telegram/auth/${encodeURIComponent(token)}/login/`,
      { method: 'POST' },
    ),
  loginWithCode: async (code: string) => {
    // Same-origin session POST: Django CSRF applies. The cookie is planted
    // by telegram_auth_start (get_token) or any earlier session endpoint.
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    const csrf = getCookie('csrftoken');
    if (csrf) headers['X-CSRFToken'] = csrf;
    const res = await fetch(`${API_BASE}/api/notifications/telegram/auth/code/login/`, {
      method: 'POST',
      credentials: 'include',
      headers,
      body: JSON.stringify({ code }),
    });
    if (!res.ok) await throwForResponse(res, 'Kod noto‘g‘ri yoki eskirgan.');
    return (await res.json()) as TelegramAuthLogin;
  },
};

// ---------------------------------------------------------------------------
// React SPA API (/api/v1/ — apps/webapi, JWT via api())
// ---------------------------------------------------------------------------

export const Games = {
  hub: () => api<{
    games: Record<string, unknown>[];
    scores: Record<string, unknown>[];
    stats: { total_xp: number; total_coins: number };
    recent_badges: { name: string; emoji: string }[];
    leaderboard: Record<string, unknown>[];
  }>('/api/v1/games/'),
  leaderboard: () => api<{ leaderboard: Record<string, unknown>[]; my_stats: unknown }>('/api/v1/games/leaderboard/'),
  play: (slug: string, level?: number) =>
    api<{
      game: Record<string, unknown>;
      level: { id: number; title: string; difficulty: number; hint: string; time_limit_seconds: number };
      levels: { id: number; title: string; difficulty: number }[];
      content: Record<string, unknown>;
      my_score: Record<string, unknown> | null;
    }>(`/api/v1/games/${slug}/play/${level ? `?level=${level}` : ''}`),
  check: (slug: string, payload: Record<string, unknown>) =>
    api<{
      is_correct: boolean;
      combo: number;
      answer: Record<string, unknown>;
      xp_earned: number;
      coins_earned: number;
      total_xp: number;
      total_coins: number;
      streak: number;
      new_badges: { name: string; emoji: string }[];
    }>(`/api/v1/games/${slug}/check/`, { method: 'POST', body: JSON.stringify(payload) }),
};

export const Panel = {
  dashboard: () => api<Record<string, unknown>>('/api/v1/panel/dashboard/'),
  tests: (q = '', status = '') =>
    api<{ results: Record<string, unknown>[]; statuses: { value: string; label: string }[] }>(
      `/api/v1/panel/tests/?q=${encodeURIComponent(q)}&status=${encodeURIComponent(status)}`,
    ),
  createTest: (payload: Record<string, unknown>) =>
    api<Record<string, unknown>>('/api/v1/panel/tests/', { method: 'POST', body: JSON.stringify(payload) }),
  updateTest: (id: number | string, payload: Record<string, unknown>) =>
    api<Record<string, unknown>>(`/api/v1/panel/tests/${id}/`, { method: 'PATCH', body: JSON.stringify(payload) }),
  deleteTest: (id: number | string) =>
    api<unknown>(`/api/v1/panel/tests/${id}/`, { method: 'DELETE' }),
  setStatus: (id: number | string, status: string) =>
    api<Record<string, unknown>>(`/api/v1/panel/tests/${id}/status/`, {
      method: 'POST',
      body: JSON.stringify({ status }),
    }),
  questions: (testId: number | string) =>
    api<{ test: Record<string, unknown>; results: Record<string, unknown>[] }>(
      `/api/v1/panel/tests/${testId}/questions/`,
    ),
  createQuestion: (testId: number | string, payload: Record<string, unknown>) =>
    api<Record<string, unknown>>(`/api/v1/panel/tests/${testId}/questions/`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  updateQuestion: (testId: number | string, qid: number | string, payload: Record<string, unknown>) =>
    api<Record<string, unknown>>(`/api/v1/panel/tests/${testId}/questions/${qid}/`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),
  deleteQuestion: (testId: number | string, qid: number | string) =>
    api<unknown>(`/api/v1/panel/tests/${testId}/questions/${qid}/`, { method: 'DELETE' }),
  topics: (q = '', category = '') =>
    api<{ results: Record<string, unknown>[]; categories: { value: string; label: string }[] }>(
      `/api/v1/panel/topics/?q=${encodeURIComponent(q)}&category=${encodeURIComponent(category)}`,
    ),
  createTopic: (payload: Record<string, unknown>) =>
    api<Record<string, unknown>>('/api/v1/panel/topics/', { method: 'POST', body: JSON.stringify(payload) }),
  updateTopic: (id: number | string, payload: Record<string, unknown>) =>
    api<Record<string, unknown>>(`/api/v1/panel/topics/${id}/`, { method: 'PATCH', body: JSON.stringify(payload) }),
  deleteTopic: (id: number | string) =>
    api<unknown>(`/api/v1/panel/topics/${id}/`, { method: 'DELETE' }),
  users: (params: Record<string, string> = {}) =>
    api<{ results: Record<string, unknown>[]; roles: { value: string; label: string }[] }>(
      `/api/v1/panel/users/?${new URLSearchParams(params).toString()}`,
    ),
  setRole: (id: number | string, role: string) =>
    api<Record<string, unknown>>(`/api/v1/panel/users/${id}/role/`, {
      method: 'POST',
      body: JSON.stringify({ role }),
    }),
  toggleBlock: (id: number | string) =>
    api<Record<string, unknown>>(`/api/v1/panel/users/${id}/block/`, { method: 'POST' }),
};

export const Billing = {
  plans: () =>
    api<{ results: Record<string, unknown>[]; my_plan_id: number | null }>('/api/v1/billing/plans/'),
  my: () =>
    api<{ subscription: Record<string, unknown> | null; history: Record<string, unknown>[] }>(
      '/api/v1/billing/my/',
    ),
  subscribeInfo: (planId: number | string) =>
    api<Record<string, unknown>>(`/api/v1/billing/subscribe/${planId}/`),
  cancel: () => api<Record<string, unknown>>('/api/v1/billing/cancel/', { method: 'POST' }),
  status: () => sessionApi<Record<string, unknown>>('/subscribe/api/status/'),
};

export const School = {
  groups: () => api<Record<string, unknown>[]>('/api/v1/school/groups/'),
  createGroup: (payload: { name: string; description?: string }) =>
    api<Record<string, unknown>>('/api/v1/school/groups/', { method: 'POST', body: JSON.stringify(payload) }),
  updateGroup: (id: number | string, payload: Record<string, unknown>) =>
    api<Record<string, unknown>>(`/api/v1/school/groups/${id}/`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),
  deleteGroup: (id: number | string) =>
    api<unknown>(`/api/v1/school/groups/${id}/`, { method: 'DELETE' }),
  members: (id: number | string, payload: { add?: number[]; remove?: number[] }) =>
    api<Record<string, unknown>>(`/api/v1/school/groups/${id}/members/`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  studentSearch: (q: string) =>
    api<Record<string, unknown>[]>(`/api/v1/school/students/?q=${encodeURIComponent(q)}`),
  parent: () => api<{ children: Record<string, unknown>[] }>('/api/v1/school/parent/'),
  teacher: () => api<Record<string, unknown>>('/api/v1/school/teacher/'),
  analytics: (days = 14) =>
    api<{ labels: string[]; attempts: number[]; avg_percentage: number[]; totals: Record<string, number> }>(
      `/api/v1/school/analytics/?days=${days}`,
    ),
  essayLeaderboard: () =>
    api<{ podium: Record<string, unknown>[]; rest: Record<string, unknown>[]; total_essays: number; total_students: number }>(
      '/api/v1/school/essay-leaderboard/',
    ),
  publicStats: () =>
    api<{
      totals: { tests: number; students: number; essays_graded: number };
      daily: { labels: string[]; attempts: number[]; avg: number[] };
    }>('/api/v1/school/public-stats/'),
  importStudents: (file: File) => {
    const fd = new FormData();
    fd.append('csv_file', file);
    return api<{ created: number; skipped: number; errors: unknown[] }>('/api/v1/school/import-students/', {
      method: 'POST',
      body: fd,
    });
  },
  importTestCourses: () =>
    api<{ courses: { id: number; title: string }[] }>('/api/v1/school/import-test/'),
  importTest: (fd: FormData) =>
    api<Record<string, unknown>>('/api/v1/school/import-test/', { method: 'POST', body: fd }),
};

// ---------------------------------------------------------------------------
// Essays + arena lobby via the TMA JSON API (JWT, generic — not Telegram-only)
// ---------------------------------------------------------------------------

export const Essays = {
  topics: () => api<{ topics?: unknown[] } & Record<string, unknown>>('/tma/api/essays/topics/'),
  submissions: () => api<Record<string, unknown>>('/tma/api/essays/'),
  start: (topicId: number | string, password = '') =>
    api<Record<string, unknown>>(`/tma/api/essays/${topicId}/start/`, {
      method: 'POST',
      body: JSON.stringify(password ? { password } : {}),
    }),
  submit: (submissionId: number | string, essay_text: string) =>
    api<Record<string, unknown>>(`/tma/api/essays/${submissionId}/submit/`, {
      method: 'POST',
      body: JSON.stringify({ essay_text }),
    }),
  result: (submissionId: number | string) =>
    api<Record<string, unknown>>(`/tma/api/essays/${submissionId}/result/`),
  status: (submissionId: number | string) =>
    sessionApi<Record<string, unknown>>(`/essays/api/${submissionId}/status/`),
  improve: (submissionId: number | string) =>
    sessionApi<Record<string, unknown>>(`/essays/result/${submissionId}/improve/`, { method: 'POST' }),
};

export interface TeacherEssayCard {
  id: number;
  student: string;
  student_email: string;
  topic: string | null;
  topic_id: number | null;
  total_score: number;
  max_score: number;
  word_count: number;
  status: string;
  teacher_review_requested: boolean;
  teacher_review_reason: string;
  submitted_at: string | null;
}

export interface TeacherEssayDetail {
  submission: TeacherEssayCard & { essay_text: string; summary: string };
  ai_criteria: { criterion_id: number; name: string; score: number; reason: string }[];
  criterion_names: Record<string, string>;
  existing_review: {
    criteria_scores: Record<string, number>;
    final_score: number;
    teacher_comments: string;
    reviewed_at: string;
  } | null;
}

// Teacher essay review (/api/v1/essays/teacher/* — apps/webapi/views_essays.py, JWT).
export const TeacherEssays = {
  queue: () =>
    api<{
      student_requested: TeacherEssayCard[];
      pending: TeacherEssayCard[];
      reviewed: {
        submission_id: number;
        student: string;
        topic: string | null;
        final_score: number;
        reviewed_at: string;
      }[];
    }>('/api/v1/essays/teacher/queue/'),
  detail: (id: number | string) =>
    api<TeacherEssayDetail>(`/api/v1/essays/teacher/${id}/`),
  submitReview: (
    id: number | string,
    payload: { criteria_scores: Record<number, number>; teacher_comments: string },
  ) =>
    api<{ ok: boolean; final_score: number; reviewed_at: string }>(
      `/api/v1/essays/teacher/${id}/review/`,
      { method: 'POST', body: JSON.stringify(payload) },
    ),
};

export const ArenaLobby = {
  // JWT summary (stats + leaderboard + invites) — works without session.
  summary: () => api<Record<string, unknown>>('/tma/api/arena/'),
  // Session lobby endpoints (need ensureSession first).
  leaderboard: () => sessionApi<Record<string, unknown>>('/arena/api/leaderboard/'),
  stats: () => sessionApi<Record<string, unknown>>('/arena/api/stats/'),
  invites: () => sessionApi<Record<string, unknown>>('/arena/api/invites/'),
  createRoom: () => sessionApi<{ room_code: string; url?: string }>('/arena/api/rooms/create/', { method: 'POST' }),
  joinRoom: (code: string) =>
    sessionApi<{ room_code: string; url?: string }>('/arena/api/rooms/join/', {
      method: 'POST',
      body: JSON.stringify({ code }),
    }),
  queue: () => sessionApi<Record<string, unknown>>('/arena/api/queue/', { method: 'POST' }),
};
