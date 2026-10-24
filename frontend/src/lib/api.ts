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

api.get = <T>(path: string, init?: RequestInit): Promise<T> =>
  api<T>(path, { ...init, method: 'GET' });

api.post = <T>(path: string, body?: unknown, init?: RequestInit): Promise<T> =>
  api<T>(path, {
    ...init,
    method: 'POST',
    body: body instanceof FormData ? body : body !== undefined ? JSON.stringify(body) : undefined,
    headers:
      body instanceof FormData
        ? init?.headers
        : { 'Content-Type': 'application/json', ...(init?.headers || {}) },
  });

api.patch = <T>(path: string, body?: unknown, init?: RequestInit): Promise<T> =>
  api<T>(path, {
    ...init,
    method: 'PATCH',
    body: body !== undefined ? JSON.stringify(body) : undefined,
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
  });

api.delete = <T>(path: string, init?: RequestInit): Promise<T> =>
  api<T>(path, { ...init, method: 'DELETE' });

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
  role: 'student' | 'teacher' | 'admin' | 'parent' | 'center_admin';
  full_name: string;
  is_active: boolean;
  first_name?: string;
  last_name?: string;
  language?: string;
  is_staff?: boolean;
  is_superuser?: boolean;
  is_platform_admin?: boolean;
  avatar?: string;
  active_subject?: 'uzbek' | 'english';
  exam_target?: 'national_certificate' | 'attestation' | 'ielts' | 'multilevel' | 'undecided';
  target_timeline_months?: number;
  target_grade?: string;
  placement_score?: number | string | null;
  onboarding_completed?: boolean;
  daily_plan_summary?: Record<string, unknown>;
  telegram_chat_id?: number | null;
  telegram_identity_verified_at?: string | null;
}

/** Platform admin = active + (superuser or role==admin) (mirrors apps/accounts/access.py). */
export function isPlatformAdmin(u: AuthUser | null | undefined): boolean {
  if (!u || u.is_active === false) return false;
  return u.is_platform_admin === true || u.is_superuser === true || u.role === 'admin';
}

/** Where to land after sign-in: admins get the control panel, everyone else the student dashboard. */
export function landingFor(u: AuthUser | null | undefined): string {
  return isPlatformAdmin(u) ? '/panel' : '/dashboard';
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

/** Cleanly format and auto-capitalize user display names (e.g. "komiljon roziyev" -> "Komiljon Roziyev"). */
export function formatDisplayName(name?: string | null, email?: string | null): string {
  const raw = (name || email?.split('@')[0] || '').trim();
  if (!raw) return 'Foydalanuvchi';
  return raw
    .split(/\s+/)
    .map((w) => (w ? w.charAt(0).toUpperCase() + w.slice(1).toLowerCase() : ''))
    .join(' ');
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
  const active_subject =
    raw.active_subject === 'english' || raw.active_subject === 'uzbek'
      ? (raw.active_subject as 'uzbek' | 'english')
      : 'uzbek';
  return {
    id: Number(raw.id),
    email: typeof raw.email === 'string' ? raw.email : '',
    role: (raw.role as AuthUser['role']) ?? 'student',
    full_name: full,
    is_active: typeof raw.is_active === 'boolean' ? raw.is_active : true,
    active_subject,
    ...(first ? { first_name: first } : {}),
    ...(last ? { last_name: last } : {}),
    ...(typeof raw.language === 'string' ? { language: raw.language } : {}),
    ...(typeof raw.is_staff === 'boolean' ? { is_staff: raw.is_staff } : {}),
    ...(typeof raw.is_superuser === 'boolean' ? { is_superuser: raw.is_superuser } : {}),
    ...(typeof raw.is_platform_admin === 'boolean'
      ? { is_platform_admin: raw.is_platform_admin }
      : {}),
    ...(typeof raw.avatar === 'string' && raw.avatar ? { avatar: raw.avatar } : {}),
    ...(typeof raw.picture === 'string' && raw.picture ? { avatar: raw.picture } : {}),
    exam_target: (raw.exam_target as AuthUser['exam_target']) ?? 'undecided',
    target_timeline_months: typeof raw.target_timeline_months === 'number' ? raw.target_timeline_months : 3,
    target_grade: typeof raw.target_grade === 'string' ? raw.target_grade : 'A',
    placement_score: raw.placement_score !== undefined ? (raw.placement_score as number) : null,
    onboarding_completed: typeof raw.onboarding_completed === 'boolean' ? raw.onboarding_completed : false,
    daily_plan_summary:
      typeof raw.daily_plan_summary === 'object' && raw.daily_plan_summary
        ? (raw.daily_plan_summary as Record<string, unknown>)
        : {},
    telegram_chat_id: typeof raw.telegram_chat_id === 'number' ? raw.telegram_chat_id : null,
    telegram_identity_verified_at:
      typeof raw.telegram_identity_verified_at === 'string' ? raw.telegram_identity_verified_at : null,
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
  role?: string;
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

export interface SubjectItem {
  slug: 'uzbek' | 'english';
  name: string;
  description: string;
  icon: string;
  is_active: boolean;
}

export const ProfileApi = {
  subjects: () => api<SubjectItem[]>('/api/v1/subjects/'),
  switchSubject: (subject: 'uzbek' | 'english', exam_target?: string) =>
    api<{
      ok: boolean;
      active_subject: 'uzbek' | 'english';
      exam_target: 'national_certificate' | 'attestation' | 'ielts' | 'multilevel' | 'undecided';
      target_grade: string;
      daily_plan_summary: Record<string, unknown>;
    }>('/api/v1/profile/switch-subject/', {
      method: 'POST',
      body: JSON.stringify({ subject, exam_target }),
    }),
  linkTelegram: (telegram_chat_id: number) =>
    api<{ ok: boolean; telegram_chat_id: number; message: string }>('/api/v1/accounts/link-telegram/', {
      method: 'POST',
      body: JSON.stringify({ telegram_chat_id }),
    }),
};

export const Tests = {
  list: (params?: { subject?: string; category?: string }) => {
    const qs = new URLSearchParams();
    if (params?.subject) qs.set('subject', params.subject);
    if (params?.category) qs.set('category', params.category);
    const query = qs.toString() ? `?${qs.toString()}` : '';
    return api<Paginated<TestSummary>>(`/api/tests/${query}`);
  },
  detail: (id: string) => api<Record<string, unknown>>(`/api/tests/${id}/`),
  start: (id: string, mode: 'strict' | 'practice' = 'strict') =>
    api<Attempt | { attempt_id: number }>(`/api/tests/${id}/start/`, {
      method: 'POST',
      body: JSON.stringify({ mode }),
    }),
  attempt: (id: string) => api<Attempt>(`/api/tests/attempts/${id}/`),
  saveAnswer: (
    attemptId: string,
    payload: {
      question_id: number;
      choice_ids?: number[];
      text_answer?: string;
      gap_answers?: Record<string, string>;
      matching?: Record<string, number | null>;
      written_text?: string;
      test_id?: number | string;
      selected_option_id?: number | null;
      selected_choice_id?: number | null;
    },
  ) =>
    api<unknown>(`/api/tests/attempts/${attemptId}/save-answer/`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  submit: (attemptId: string) =>
    api<unknown>(`/api/tests/attempts/${attemptId}/submit/`, {
      method: 'POST',
    }),
  finalize: (attemptId: string) =>
    api<unknown>(`/api/tests/attempts/${attemptId}/finalize/`, {
      method: 'POST',
    }),
  reportViolation: (attemptId: string | number, type = 'tab_switch') =>
    api<{
      attempt_id: number;
      violation_count: number;
      max_violations: number;
      cheating_detected: boolean;
      terminated: boolean;
      status: string;
      result_id?: number | null;
      message: string;
    }>(`/api/tests/attempts/${attemptId}/report-violation/`, {
      method: 'POST',
      body: JSON.stringify({ type }),
    }),
  explainMistake: (questionId: number, selectedChoiceId?: number, attemptId?: number) =>
    api<Record<string, unknown>>(`/api/tests/questions/${questionId}/explain-mistake/`, {
      method: 'POST',
      body: JSON.stringify({
        selected_choice_id: selectedChoiceId,
        attempt_id: attemptId,
      }),
    }),
  evaluateWriting: (payload: { essay_text: string; topic_title?: string; exam_type?: string; task_type?: string }) =>
    api<Record<string, unknown>>(`/api/tests/writing/evaluate/`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  certificateCard: (attemptId: string | number) =>
    api<Record<string, unknown>>(`/api/tests/attempts/${attemptId}/certificate-card/`),
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

export interface MockTestCreateResponse {
  ok: boolean;
  test_id: number;
  mock_code: string;
  title: string;
  questions_count: number;
  time_limit: number;
  passing_score: number;
}

export interface MockTestJoinResponse {
  ok?: boolean;
  success?: boolean;
  message?: string;
  test_id?: number;
  test?: {
    id: number;
    title: string;
    mock_code: string;
    time_limit: number;
    questions_count: number;
  };
  attempt_id: number;
}

export interface MockLeaderboardResponse {
  test_id: number;
  title: string;
  mock_code: string;
  total_participants: number;
  bmb_summary: Record<string, number>;
  leaderboard: Array<{
    rank: number;
    student_name: string;
    score: number;
    max_score: number;
    percentage: number;
    bmb_grade: string;
    bmb_title: string;
    passed: boolean;
    date: string;
  }>;
}

export const MockTests = {
  create: (payload: { title?: string; keys: string; time_limit?: number; passing_score?: number }) =>
    api<MockTestCreateResponse>('/api/tests/mock/create/', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  join: (mock_code: string) => {
    const clean = (mock_code || '').trim();
    return api<MockTestJoinResponse>('/api/tests/mock/join/', {
      method: 'POST',
      body: JSON.stringify({ code: clean, mock_code: clean, auto_start: true }),
    });
  },
  leaderboard: (testId: number | string) =>
    api<MockLeaderboardResponse>(`/api/tests/mock/${testId}/leaderboard/`),
};

export interface WeakTopicItem {
  topic: string;
  category: string;
  incorrect_count: number;
  severity: 'high' | 'medium' | 'low';
  recommendation: string;
}

export interface ResultDiagnosticsResponse {
  result_id: number;
  score: number;
  max_score: number;
  percentage: number;
  bmb_grade: string;
  bmb_title: string;
  total_questions: number;
  incorrect_count: number;
  weak_topics: WeakTopicItem[];
  general_advice: string;
}

export interface QuestionMistakeExplanation {
  ok: boolean;
  question_id: number;
  question_text: string;
  selected_choice: string | null;
  correct_choice: string;
  why_wrong: string;
  correct_rule: string;
  memory_tip: string;
}

export const AiTutor = {
  getDiagnostics: (resultId: number | string) =>
    api<ResultDiagnosticsResponse>(`/api/tests/results/${resultId}/diagnostics/`),
  explainMistake: (
    questionId: number | string,
    payload: { selected_choice_id?: number | null; attempt_id?: number | null } = {},
  ) =>
    api<QuestionMistakeExplanation>(
      `/api/tests/questions/${questionId}/explain-mistake/`,
      {
        method: 'POST',
        body: JSON.stringify(payload),
      },
    ),
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

/** Best-effort Django session login (no-op now that WS and APIs use JWT). */
export function ensureSession(_email?: string, _password?: string): Promise<boolean> {
  return Promise.resolve(true);
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
  if (!res.ok) await throwForResponse(res, `Request failed (${res.status})`);
  return (await res.json()) as T;
}

/** WebSocket URL for the arena (same host, ws/wss matching page protocol). */
export function arenaSocketUrl(roomCode?: string): string {
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
  const base = `${proto}://${window.location.host}/ws/arena/`;
  const url = roomCode ? `${base}${roomCode}/` : base;
  const token = getTokens().access;
  return token ? `${url}?token=${encodeURIComponent(token)}` : url;
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
  loginWithWidget: async (data: Record<string, unknown>) => {
    const res = await fetch(`${API_BASE}/api/auth/telegram/widget/`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) await throwForResponse(res, 'Telegram orqali kirishda xatolik yuz berdi.');
    return (await res.json()) as TelegramAuthLogin;
  },
  loginWithInitData: async (initData: string) => {
    const res = await fetch(`${API_BASE}/tma/api/auth/`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ init_data: initData }),
    });
    if (!res.ok) await throwForResponse(res, 'Telegram WebApp avtorizatsiyasida xatolik.');
    return (await res.json()) as TelegramAuthLogin;
  },
};

export interface GoogleAuthVerifyResponse {
  status: string;
  redirect: string;
  user: Record<string, unknown>;
  tokens: TokenPair;
}

export interface SessionStatusResponse {
  authenticated: boolean;
  user: Record<string, unknown> | null;
  tokens: TokenPair | null;
}

export const GoogleAuth = {
  startUrl: `${API_BASE}/api/v1/auth/google/`,
  getConfig: async () => {
    try {
      const res = await fetch(`${API_BASE}/api/v1/auth/google/config/`);
      if (!res.ok) return { client_id: '', enabled: false };
      return (await res.json()) as { client_id: string; enabled: boolean };
    } catch {
      return { client_id: '', enabled: false };
    }
  },
  verify: async (credential: string) => {
    const res = await fetch(`${API_BASE}/api/v1/auth/google/`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ credential }),
    });
    if (!res.ok) await throwForResponse(res, 'Google orqali kirishda xatolik yuz berdi.');
    return (await res.json()) as GoogleAuthVerifyResponse;
  },
};

export const SessionAuth = {
  status: async () => {
    try {
      const res = await fetch(`${API_BASE}/api/auth/session/status/`, {
        method: 'GET',
        credentials: 'include',
      });
      if (!res.ok) return { authenticated: false, user: null, tokens: null } as SessionStatusResponse;
      return (await res.json()) as SessionStatusResponse;
    } catch {
      return { authenticated: false, user: null, tokens: null } as SessionStatusResponse;
    }
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

export interface CohortAnalyticsResponse {
  total_onboarded: number;
  segmentation: {
    national_certificate: { count: number; percentage: number; label: string };
    attestation: { count: number; percentage: number; label: string };
    undecided: { count: number; percentage: number; label: string };
  };
  avg_placement_score: number;
  timeline_breakdown: {
    months_1: { count: number; label: string };
    months_3: { count: number; label: string };
    months_6: { count: number; label: string };
  };
}

export interface PanelDashboardResponse {
  tests: { total: number; published: number; draft: number; archived: number };
  questions: number;
  essay_topics: number;
  users: { total: number; active: number; blocked: number };
  new_users_today: number;
  attempts: { total: number; today: number };
  essays: { total: number; pending_ai: number; awaiting_review: number };
  pending_payments: number;
  active_subscriptions: number;
  role_breakdown: { key: string; count: number }[];
  recent_tests: Record<string, unknown>[];
  recent_topics: Record<string, unknown>[];
  cohort_analytics?: CohortAnalyticsResponse;
}

export interface PlacementQuestion {
  id: number;
  text: string;
  passage?: string;
  choices: Array<{ id: number; text: string }>;
}

export interface PlacementQuizResponse {
  ok: boolean;
  target: string;
  time_limit_seconds: number;
  total_questions: number;
  questions: PlacementQuestion[];
}

export interface PlacementSubmitPayload {
  target: string;
  target_timeline_months: number;
  target_grade: string;
  answers: Array<{ question_id: number; selected_choice_id: number }>;
}

export interface PlacementSubmitResponse {
  ok: boolean;
  score: number;
  total: number;
  percentage: number;
  initial_level: string;
  target: string;
  target_timeline_months: number;
  target_grade: string;
  daily_plan: {
    schedule_label?: string;
    tests_per_day?: number;
    essays_per_week?: number;
    daily_minutes?: number;
    focus_areas?: string[];
    recommended_actions?: Array<{ title: string; badge: string; link: string }>;
    advice?: string;
  };
  onboarding_completed: boolean;
  message?: string;
}

export const PlacementQuiz = {
  get: (target = 'national_certificate') =>
    api<PlacementQuizResponse>(`/api/v1/tests/placement-quiz/?target=${encodeURIComponent(target)}`),
  submit: (payload: PlacementSubmitPayload) =>
    api<PlacementSubmitResponse>('/api/v1/tests/placement-quiz/submit/', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
};

export const Panel = {
  dashboard: () => api<PanelDashboardResponse>('/api/v1/panel/dashboard/'),
  cohorts: () => api<CohortAnalyticsResponse>('/api/v1/panel/analytics/cohorts/'),
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
  groups: () => api<{ results: PanelGroupItem[] }>('/api/v1/panel/groups/'),
  createGroup: (payload: { name: string; subject: string; teacher_id: number; monthly_fee?: number }) =>
    api<PanelGroupItem & { message?: string }>('/api/v1/panel/groups/', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  teachers: () => api<{ results: PanelTeacherItem[] }>('/api/v1/panel/teachers/'),
  attendance: () => api<{ results: PanelAttendanceItem[] }>('/api/v1/panel/attendance/'),
  exportAttendanceUrl: '/api/v1/panel/attendance/export/',
};

export interface PanelGroupItem {
  id: number;
  name: string;
  subject: 'uzbek' | 'english';
  subject_display: string;
  teacher_id: number;
  teacher_name: string;
  teacher_email: string;
  student_count: number;
  invite_code: string;
  monthly_fee: number;
  created_at: string;
}

export interface PanelTeacherItem {
  id: number;
  full_name: string;
  email: string;
  role: string;
}

export interface PanelAttendanceSessionItem {
  id: number;
  lesson_date: string;
  status: string;
  present: number;
  late: number;
  absent: number;
}

export interface PanelAttendanceItem {
  group_id: number;
  group_name: string;
  subject: string;
  subject_display: string;
  teacher_name: string;
  student_count: number;
  total_sessions: number;
  present_count: number;
  late_count: number;
  absent_count: number;
  attendance_rate: number;
  recent_sessions: PanelAttendanceSessionItem[];
}

/**
 * One commercial quota bucket from GET /api/v1/billing/entitlement/.
 * `unlimited: true` means the plan does not meter this operation, so both
 * `limit` and `remaining` are null. A null `limit` with `unlimited: false`
 * means "not configured by an administrator" — which is NOT the same as zero
 * remaining, so it must never be rendered as 0.
 */
export interface UsageBucket {
  unlimited: boolean;
  limit: number | null;
  used: number;
  remaining: number | null;
}

/**
 * Effective entitlement + remaining allowances for the signed-in student.
 * `source` is the precedence chain that produced the entitlement:
 * override → sponsored → subscription → default.
 */
export interface BillingEntitlement {
  source: 'override' | 'sponsored' | 'subscription' | 'default' | string;
  plan_type: string | null;
  plan_name: string;
  is_sponsored: boolean;
  is_paid: boolean;
  expires_at: string | null;
  period_start: string;
  period_end: string;
  image_essay: UsageBucket;
  text_essay: UsageBucket;
  test: UsageBucket;
  text_cooldown_seconds: number;
  text_cooldown_until: string | null;
  can_submit_image_essay: boolean;
  can_submit_text_essay: boolean;
  can_start_test: boolean;
}

/** Plan shape returned by /api/v1/billing/plans/ (mirrors SubscriptionPlanSerializer). */
export interface BillingPlan {
  id: number;
  name: string;
  plan_type: string;
  description?: string;
  price_monthly?: number | string;
  price_yearly?: number | string;
  max_tests_per_day?: number;
  max_essays_per_week?: number;
  unlimited_tests?: boolean;
  unlimited_essays?: boolean;
  detailed_analytics?: boolean;
  pdf_certificate?: boolean;
  priority_support?: boolean;
  /** Canonical plan code (aliases plan_type on the backend). */
  code?: string;
  price_uzs?: number;
  display_order?: number;
  duration_days?: number;
  /** Whole Stars charged inside Telegram; null = not sold through Telegram. */
  telegram_stars_price?: number | null;
  image_essay_weekly_limit?: number | null;
  text_essay_weekly_limit?: number | null;
  text_essay_cooldown_hours?: number | null;
  test_limit?: number | null;
  is_unlimited_image_essays?: boolean;
  is_unlimited_text_essays?: boolean;
  is_unlimited_tests?: boolean;
  is_public?: boolean;
}

export const Billing = {
  plans: () =>
    api<{ results: BillingPlan[]; my_plan_id: number | null }>('/api/v1/billing/plans/'),
  my: () =>
    api<{ subscription: Record<string, unknown> | null; history: Record<string, unknown>[] }>(
      '/api/v1/billing/my/',
    ),
  subscribeInfo: (planId: number | string) =>
    api<Record<string, unknown>>(`/api/v1/billing/subscribe/${planId}/`),
  cancel: () => api<Record<string, unknown>>('/api/v1/billing/cancel/', { method: 'POST' }),
  status: () => sessionApi<Record<string, unknown>>('/subscribe/api/status/'),
  /** Server-calculated plan + remaining usage for the current student. */
  entitlement: () => api<BillingEntitlement>('/api/v1/billing/entitlement/'),
};

export interface PlanInfoItem {
  name: string;
  price: number;
  label: string;
}

export interface CardInfoResponse {
  card_number: string;
  card_holder: string;
  starter_price: number;
  pro_price?: number;
  premium_price: number;
  plans?: {
    starter: PlanInfoItem;
    pro: PlanInfoItem;
    premium: PlanInfoItem;
  };
}

export interface PaymentReceiptItem {
  id: number;
  plan: 'starter' | 'pro' | 'premium';
  amount: number | string;
  receipt_image: string;
  receipt_image_url: string;
  status: 'pending' | 'approved' | 'rejected';
  source: 'web' | 'bot';
  admin_note: string | null;
  created_at: string;
  updated_at: string;
}

export const PaymentsApi = {
  cardInfo: () => api<CardInfoResponse>('/api/v1/payments/card-info/'),
  uploadReceipt: (plan: 'starter' | 'pro' | 'premium', file: File, amount?: number) => {
    const fd = new FormData();
    fd.append('plan', plan);
    fd.append('receipt_image', file);
    if (amount) fd.append('amount', String(amount));
    return api<PaymentReceiptItem>('/api/v1/payments/receipts/', {
      method: 'POST',
      body: fd,
    });
  },
  myReceipts: () => api<{ results: PaymentReceiptItem[] }>('/api/v1/payments/my-receipts/'),
  verifyReceipt: (plan: 'starter' | 'pro' | 'premium', file: File) => {
    const fd = new FormData();
    fd.append('plan_type', plan);
    fd.append('receipt_image', file);
    return api<{
      success: boolean;
      message: string;
      is_banned?: boolean;
      plan_type?: string;
      amount?: number;
      transaction_id?: string;
    }>('/api/v1/subscriptions/verify-receipt/', {
      method: 'POST',
      body: fd,
    });
  },
};

/**
 * Attendance + group essay reporting (apps/attendance, apps/essays/group_reports).
 *
 * Status vocabulary is fixed: `present` / `absent` / `late` / `excused` — the
 * Uzbek labels are Keldi / Kelmadi / Kechikdi / Sababli.
 */
export type AttendanceStatus = 'present' | 'absent' | 'late' | 'excused';

export interface AttendanceRosterRow {
  student_id: number;
  name: string;
  record_id: number | null;
  /** `null` means the teacher has not marked this student yet. */
  status: AttendanceStatus | null;
  status_label: string;
  late_minutes: number;
  note: string;
  marked: boolean;
}

export interface AttendanceSessionSummary {
  session_id: number;
  group_id: number;
  group_name: string;
  lesson_date: string;
  time_label: string;
  status: 'draft' | 'finalized' | 'cancelled' | string;
  status_label: string;
  roster_size: number;
  marked: number;
  unmarked: number;
  present: number;
  late: number;
  absent: number;
  excused: number;
  attended: number;
}

export interface AttendanceSessionDetail extends AttendanceSessionSummary {
  roster: AttendanceRosterRow[];
}

export interface AttendanceReport {
  group_id?: number;
  group_name: string;
  start?: string;
  end?: string;
  roster_size: number;
  sessions_total: number;
  finalized_sessions: number;
  /** Unfinished registers are reported separately and never counted as absent. */
  pending_sessions: number;
  present: number;
  late: number;
  absent: number;
  excused: number;
  unexcused_absent: number;
  attended: number;
  marked_records: number;
  /** `null` when nothing has been marked yet — not the same as 0%. */
  attendance_percentage: number | null;
  daily?: AttendanceDailyRow[];
  groups?: AttendanceGroupRow[];
}

export interface AttendanceDailyRow {
  date: string;
  present: number;
  late: number;
  absent: number;
  excused: number;
  attendance_percentage: number | null;
}

export interface AttendanceGroupRow {
  group_id: number;
  group_name: string;
  roster_size: number;
  finalized_sessions: number;
  pending_sessions: number;
  attendance_percentage: number | null;
  absent: number;
  late: number;
  excused: number;
}

export interface StudentAttendanceRecord {
  date: string;
  time: string;
  group: string;
  status: AttendanceStatus;
  status_label: string;
  late_minutes: number;
  note: string;
}

export interface StudentAttendance {
  student_id: number;
  name: string;
  present: number;
  late: number;
  absent: number;
  excused: number;
  unexcused_absent: number;
  attended: number;
  marked_records: number;
  attendance_percentage: number | null;
  recent: StudentAttendanceRecord[];
}

/** A single row from `GET school/essay-results/`. */
export interface GroupEssayResultRow {
  submission_id: number;
  student_id: number;
  student_name: string;
  topic_title: string;
  submitted_at: string | null;
  source: string;
  source_label: string;
  status: string;
  status_label: string;
  is_graded: boolean;
  is_pending: boolean;
  is_failed: boolean;
  /** Raw AI total. Distinct from `final_score` (teacher-adjusted). */
  ai_total_score: number | null;
  max_score: number;
  final_score: number | null;
  effective_score: number | null;
  /** Practice-scale conversion only — never an official Rasch result. */
  converted_practice_score: number | null;
  is_off_topic: boolean;
  teacher_review_required: boolean;
  result_url: string;
}

export interface GroupEssayResults {
  group_id: number;
  group_name: string;
  total: number;
  shown: number;
  limit: number;
  offset: number;
  graded: number;
  pending: number;
  failed: number;
  average_ai_score: number | null;
  results: GroupEssayResultRow[];
}

export interface GroupEssaySummaryRow {
  group_id: number;
  group_name: string;
  roster_size: number;
  graded: number;
  pending: number;
  failed: number;
  average_ai_score: number | null;
}

export interface GroupEssaySummary {
  days: number;
  groups: GroupEssaySummaryRow[];
}

/**
 * Extract the structured body of a failed request.
 *
 * `api()` throws an `ApiError` whose `detail` is the JSON body stringified
 * when the response has no `detail` key — which is exactly the shape the
 * attendance finalize endpoint uses for its 409 (`{ok: false, reason:
 * "unmarked_students", unmarked: [...]}`). Returns `null` when the body is not
 * parsed JSON, so callers can fall back to the plain message.
 */
export function apiErrorBody(e: unknown): Record<string, unknown> | null {
  const raw = (e as { detail?: unknown })?.detail;
  if (typeof raw !== 'string') return null;
  try {
    const parsed = JSON.parse(raw) as unknown;
    return typeof parsed === 'object' && parsed !== null
      ? (parsed as Record<string, unknown>)
      : null;
  } catch {
    return null;
  }
}

export interface WeeklyReportRow {
  id: number;
  group_id?: number;
  group_name?: string;
  student_id?: number;
  student_name?: string;
  period_label: string;
  version: number;
  generated_at: string;
  text: string;
  summary: Record<string, unknown>;
}

export interface TuitionInvoice {
  id: number;
  student_id: number;
  student_name: string;
  period_label: string;
  course: string | null;
  amount_due_uzs: number;
  paid_amount_uzs: number;
  pending_amount_uzs: number;
  balance_uzs: number;
  due_date: string;
  grace_until?: string | null;
  status: string;
  status_label: string;
  awaiting_confirmation: boolean;
  payment_instructions: string;
}

export interface TuitionOverview {
  student_id: number;
  student_name: string;
  outstanding_uzs: number;
  confirmed_paid_uzs: number;
  invoices: TuitionInvoice[];
  payments: Array<Record<string, unknown>>;
  accepted_methods: Array<{ value: string; label: string }>;
}

export interface GroupStudentAnalytics {
  student_id: number;
  student_name: string;
  email: string;
  tests_count: number;
  avg_test_percentage: number;
  latest_test_grade: string;
  essays_count: number;
  avg_essay_score: number;
  tuition_status?: string;
  tuition_label?: string;
  last_active: string | null;
}

export interface GroupFullAnalyticsResponse {
  group: {
    id: number;
    name: string;
    invite_code: string;
    teacher_name: string;
    total_students: number;
  };
  summary: {
    total_tests_taken: number;
    total_essays_submitted: number;
    average_test_score: number;
    average_test_percentage: number;
    average_essay_score: number;
    bmb_distribution: Record<string, number>;
  };
  students: GroupStudentAnalytics[];
}

export const School = {
  notificationPreferences: (payload?: Record<string, boolean>) =>
    api<Record<string, boolean>>('/api/v1/school/notification-preferences/', {
      method: payload ? 'PATCH' : 'GET',
      ...(payload ? { body: JSON.stringify(payload) } : {}),
    }),
  weeklyReports: () =>
    api<{ count: number; results: WeeklyReportRow[] }>('/api/v1/school/weekly-reports/'),
  myWeeklyReports: () =>
    api<{ count: number; results: WeeklyReportRow[] }>('/api/v1/billing/weekly-reports/'),
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
  groupAnalytics: (groupId: number | string) =>
    api<GroupFullAnalyticsResponse>(`/api/v1/school/groups/${groupId}/analytics/`),
  joinGroup: (invite_code: string) =>
    api<{ ok: boolean; message: string; group: { id: number; name: string; teacher_name: string } }>(
      '/api/v1/school/groups/join/',
      { method: 'POST', body: JSON.stringify({ invite_code }) },
    ),
  exportExcelUrl: (groupId: number | string) =>
    `${API_BASE}/api/v1/school/groups/${groupId}/export/excel/`,
  exportPdfUrl: (groupId: number | string) =>
    `${API_BASE}/api/v1/school/groups/${groupId}/export/pdf/`,

  // -- Attendance ----------------------------------------------------------
  attendanceQuickMark: (payload: {
    group_id: number | string;
    student_id: number | string;
    status: 'present' | 'late' | 'absent' | 'excused';
    lesson_date?: string;
    late_minutes?: number;
    note?: string;
  }) =>
    api<{
      ok: boolean;
      session_id: number;
      lesson_date: string;
      applied: number;
      parent_alert_scheduled: boolean;
      parent_alert_scheduled_in_minutes: number;
      summary: AttendanceSessionSummary;
      roster: AttendanceRosterRow[];
    }>('/api/v1/school/attendance/quick-mark/', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  attendanceSessions: (params: {
    group_id: number | string;
    start?: string;
    end?: string;
  }) => {
    const qs = new URLSearchParams({ group_id: String(params.group_id) });
    if (params.start) qs.set('start', params.start);
    if (params.end) qs.set('end', params.end);
    return api<AttendanceSessionSummary[]>(
      `/api/v1/school/attendance/sessions/?${qs.toString()}`,
    );
  },
  attendanceSession: (sessionId: number | string) =>
    api<AttendanceSessionDetail>(`/api/v1/school/attendance/sessions/${sessionId}/`),
  /**
   * Create or resolve the register for a group/date/period. The backend is
   * idempotent per (group, lesson_date, start_time), so posting twice returns
   * the existing session instead of creating a second register.
   */
  attendanceOpenSession: (payload: {
    group_id: number | string;
    lesson_date?: string;
    start_time?: string;
    end_time?: string;
    title?: string;
  }) =>
    api<AttendanceSessionDetail>('/api/v1/school/attendance/sessions/', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  attendanceMark: (
    sessionId: number | string,
    marks: Array<{
      student_id: number;
      status: AttendanceStatus;
      late_minutes?: number;
      note?: string;
    }>,
    reason = '',
  ) =>
    api<AttendanceSessionDetail>(`/api/v1/school/attendance/sessions/${sessionId}/mark/`, {
      method: 'POST',
      body: JSON.stringify({ marks, reason }),
    }),
  attendanceMarkAllPresent: (sessionId: number | string) =>
    api<AttendanceSessionDetail>(
      `/api/v1/school/attendance/sessions/${sessionId}/mark-all-present/`,
      { method: 'POST' },
    ),
  /**
   * Finalize a register. Throws with status 409 while students are unmarked;
   * the caller must confirm explicitly, then retry with
   * `mark_unmarked_as_absent: true`. Unmarked students are NEVER marked absent
   * implicitly.
   */
  attendanceFinalize: (
    sessionId: number | string,
    markUnmarkedAsAbsent = false,
  ) =>
    api<AttendanceSessionSummary>(
      `/api/v1/school/attendance/sessions/${sessionId}/finalize/`,
      {
        method: 'POST',
        body: JSON.stringify({ mark_unmarked_as_absent: markUnmarkedAsAbsent }),
      },
    ),
  attendanceReport: (params: {
    group_id: number | string;
    start?: string;
    end?: string;
    daily?: boolean;
  }) => {
    const qs = new URLSearchParams({ group_id: String(params.group_id) });
    if (params.start) qs.set('start', params.start);
    if (params.end) qs.set('end', params.end);
    if (params.daily) qs.set('daily', 'true');
    return api<AttendanceReport>(`/api/v1/school/attendance/report/?${qs.toString()}`);
  },
  attendanceOverview: () =>
    api<AttendanceReport>('/api/v1/school/attendance/report/?overview=true'),
  /**
   * One student's attendance history — teacher/admin only.
   * A parent must use parentAttendance() below: this endpoint refuses them.
   */
  studentAttendance: (studentId: number | string) =>
    api<StudentAttendance>(`/api/v1/school/attendance/students/${studentId}/`),
  /** Attendance for every child this parent is approved for, in one call. */
  parentAttendance: () =>
    api<{ children: (StudentAttendance & { relationship?: string })[] }>(
      '/api/v1/school/parent/attendance/',
    ),

  // -- Group essay results -------------------------------------------------
  groupEssayResults: (params: {
    group_id: number | string;
    student_id?: number | string;
    start?: string;
    end?: string;
    state?: 'graded' | 'pending' | 'failed';
    source?: string;
    review_required?: boolean;
    limit?: number;
    offset?: number;
  }) => {
    const qs = new URLSearchParams({ group_id: String(params.group_id) });
    if (params.student_id) qs.set('student_id', String(params.student_id));
    if (params.start) qs.set('start', params.start);
    if (params.end) qs.set('end', params.end);
    if (params.state) qs.set('state', params.state);
    if (params.source) qs.set('source', params.source);
    if (params.review_required) qs.set('review_required', 'true');
    if (params.limit !== undefined) qs.set('limit', String(params.limit));
    if (params.offset !== undefined) qs.set('offset', String(params.offset));
    return api<GroupEssayResults>(`/api/v1/school/essay-results/?${qs.toString()}`);
  },
  groupEssaySummary: (days = 30) =>
    api<GroupEssaySummary>(`/api/v1/school/essay-summary/?overview=true&days=${days}`),
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
  /** The same canonical admin course list, named for the tuition policy scope. */
  courses: () =>
    api<{ courses: { id: number; title: string }[] }>('/api/v1/school/import-test/'),
  importTest: (fd: FormData) =>
    api<Record<string, unknown>>('/api/v1/school/import-test/', { method: 'POST', body: fd }),
};

/**
 * The per-policy reminder ladder of the tuition reminder job
 * (`CourseBillingPolicy.reminder_policy`). Day offsets are relative to the due
 * date; quiet hours are whole hours in the reporting timezone. An absent or
 * empty ladder means "never remind automatically".
 */
export interface TuitionReminderPolicy {
  before?: number[];
  due?: number[];
  overdue?: number[];
  quiet_start?: number;
  quiet_end?: number;
}

/** Mirrors CourseBillingPolicySerializer (apps/webapi/serializers.py). */
export interface TuitionPolicy {
  id: number;
  name: string;
  course: number | null;
  group: number | null;
  amount_uzs: number;
  billing_frequency: string;
  due_day: number;
  grace_days: number;
  mid_month_policy: string;
  installment_allowed: boolean;
  installments: number;
  effective_from: string;
  effective_until: string | null;
  payment_instructions: string;
  accepted_methods: string[];
  reminder_policy: TuitionReminderPolicy;
  is_active: boolean;
}

/** One row of GET /api/v1/school/tuition/payments/ (the confirmation queue). */
export interface TuitionPaymentRow {
  id: number;
  invoice_id: number | null;
  student_id: number;
  student_name: string;
  invoice_period: string | null;
  amount_uzs: number;
  method: string;
  method_label: string;
  reference: string;
  status: string;
  status_label: string;
  verified_at: string | null;
  created_at: string;
}

/** One append-only correction record from GET /school/tuition/audit/. */
export interface TuitionAuditRow {
  id: number;
  action: string;
  action_label: string;
  actor_id: number | null;
  actor_name: string | null;
  field: string;
  old_value: string;
  new_value: string;
  reason: string;
  created_at: string;
}

export const Tuition = {
  mine: () => api<TuitionOverview>('/api/v1/billing/tuition/'),
  children: () =>
    api<{ children: Array<TuitionOverview & { invoice_rows?: TuitionInvoice[] }> }>(
      '/api/v1/billing/tuition/children/',
    ),
  submitPayment: (payload: {
    invoice_id: number;
    amount: number;
    method: string;
    reference?: string;
  }) =>
    api<{ payment: Record<string, unknown>; invoice: TuitionInvoice }>(
      '/api/v1/billing/tuition/payments/',
      { method: 'POST', body: JSON.stringify(payload) },
    ),
};

/**
 * Staff-side course tuition (`/api/v1/school/tuition/...`).
 *
 * Every call here is gated on the backend by `tuition.view_courseinvoice` /
 * `tuition.change_courseinvoice` (a platform admin holds both). The panel page
 * that uses this client is mounted behind AdminRoute, so the client never has
 * to guess whether the caller may see money — the server answers 403 instead.
 */
export const TuitionAdmin = {
  policies: (params: { active?: boolean } = {}) =>
    api<{ count: number; results: TuitionPolicy[] }>(
      `/api/v1/school/tuition/policies/${params.active ? '?active=1' : ''}`,
    ),
  createPolicy: (payload: Partial<TuitionPolicy>) =>
    api<TuitionPolicy>('/api/v1/school/tuition/policies/create/', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  updatePolicy: (id: number | string, payload: Partial<TuitionPolicy>) =>
    api<TuitionPolicy>(`/api/v1/school/tuition/policies/${id}/`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    }),
  invoices: (params: Record<string, string> = {}) => {
    const qs = new URLSearchParams(params).toString();
    return api<{ count: number; results: TuitionInvoice[] }>(
      `/api/v1/school/tuition/invoices/${qs ? `?${qs}` : ''}`,
    );
  },
  studentTuition: (studentId: number | string) =>
    api<TuitionOverview>(`/api/v1/school/tuition/students/${studentId}/`),
  setInvoiceDueDate: (
    id: number | string,
    payload: { due_date: string; grace_until?: string | null },
  ) =>
    api<{ invoice: TuitionInvoice }>(`/api/v1/school/tuition/invoices/${id}/due-date/`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  /** Record an offline payment the operator has already seen the evidence for. */
  recordInvoicePayment: (
    id: number | string,
    payload: { amount: number; method?: string; reference?: string; reason: string },
  ) =>
    api<{ payment: Record<string, unknown>; invoice: TuitionInvoice }>(
      `/api/v1/school/tuition/invoices/${id}/payments/record/`,
      { method: 'POST', body: JSON.stringify(payload) },
    ),
  adjustInvoice: (id: number | string, payload: { amount: number; reason: string }) =>
    api<{ invoice: TuitionInvoice }>(`/api/v1/school/tuition/invoices/${id}/adjust/`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  waiveInvoice: (id: number | string, reason: string) =>
    api<{ invoice: TuitionInvoice }>(`/api/v1/school/tuition/invoices/${id}/waive/`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    }),
  paymentQueue: (status = '') => {
    const qs = status ? `?status=${encodeURIComponent(status)}` : '';
    return api<{ count: number; results: TuitionPaymentRow[] }>(
      `/api/v1/school/tuition/payments/${qs}`,
    );
  },
  verifyPayment: (id: number | string, reason: string) =>
    api<{ payment: TuitionPaymentRow; invoice: TuitionInvoice | null }>(
      `/api/v1/school/tuition/payments/${id}/verify/`,
      { method: 'POST', body: JSON.stringify({ reason }) },
    ),
  rejectPayment: (id: number | string, reason: string) =>
    api<{ payment: TuitionPaymentRow; invoice: TuitionInvoice | null }>(
      `/api/v1/school/tuition/payments/${id}/reject/`,
      { method: 'POST', body: JSON.stringify({ reason }) },
    ),
  audit: (params: Record<string, string> = {}) => {
    const qs = new URLSearchParams(params).toString();
    return api<{ count: number; results: TuitionAuditRow[] }>(
      `/api/v1/school/tuition/audit/${qs ? `?${qs}` : ''}`,
    );
  },
};

// ---------------------------------------------------------------------------
// Essays + arena lobby via the TMA JSON API (JWT, generic — not Telegram-only)
// ---------------------------------------------------------------------------

/**
 * Grading provenance the backend reports for the student's OWN essay.
 * `cached: true` means the grade is a shared, previously validated AI
 * evaluation that was reused. It never identifies another account, and
 * `grading_source: 'mock'` means the AI was not actually called (test mode),
 * so the score must be presented as unverified.
 */
export interface EssayGradingProvenance {
  grading_source?: 'ai' | 'cache' | 'mock' | string;
  cached?: boolean;
}

export interface IeltsCriterionScore {
  band: number;
  criterion_name: string;
  feedback: string;
}

export interface IeltsGradePayload {
  task_type: 'task1' | 'task2';
  prompt: string;
  essay_text: string;
}

export interface IeltsGradeResponse {
  task_type: string;
  word_count: number;
  min_words: number;
  overall_band: number;
  cefr_level: string;
  criteria: Record<string, IeltsCriterionScore>;
  general_feedback: string;
  model_band9_rewrite: string;
  submission_id?: number | null;
}

export const Essays = {
  topics: (params?: { subject?: string; category?: string }) => {
    const qs = new URLSearchParams();
    if (params?.subject) qs.set('subject', params.subject);
    if (params?.category) qs.set('category', params.category);
    const query = qs.toString() ? `?${qs.toString()}` : '';
    return api<{ topics?: unknown[] } & Record<string, unknown>>(`/tma/api/essays/topics/${query}`);
  },
  submissions: (params?: { subject?: string }) => {
    const qs = new URLSearchParams();
    if (params?.subject) qs.set('subject', params.subject);
    const query = qs.toString() ? `?${qs.toString()}` : '';
    return api<Record<string, unknown>>(`/tma/api/essays/${query}`);
  },
  start: (topicId: number | string, password = '') =>
    api<Record<string, unknown>>(`/tma/api/essays/${topicId}/start/`, {
      method: 'POST',
      body: JSON.stringify(password ? { password } : {}),
    }),
  submit: (submissionId: number | string, essay_text: string, autoSubmit = false) =>
    api<Record<string, unknown>>(`/tma/api/essays/${submissionId}/submit/`, {
      method: 'POST',
      body: JSON.stringify({ essay_text, ...(autoSubmit ? { auto_submit: true } : {}) }),
    }),
  result: (submissionId: number | string) =>
    api<EssayGradingProvenance & Record<string, unknown>>(
      `/tma/api/essays/${submissionId}/result/`,
    ),
  status: (submissionId: number | string) =>
    api<EssayGradingProvenance & Record<string, unknown>>(
      `/essays/api/${submissionId}/status/`,
    ),
  improve: (submissionId: number | string) =>
    api<{ ok: boolean; content?: string; error?: string; word_count?: number }>(
      `/api/v1/essays/${submissionId}/improve/`,
      { method: 'POST' },
    ),
  requestReview: (submissionId: number | string, reason?: string) =>
    api<{ ok: boolean; error?: string; submission_id?: number; status?: string }>(
      `/api/v1/essays/${submissionId}/request-review/`,
      {
        method: 'POST',
        body: JSON.stringify({ reason: reason || '' }),
      },
    ),
  ieltsGrade: (payload: IeltsGradePayload) =>
    api<IeltsGradeResponse>('/api/v1/essays/ielts/grade/', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
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
  // Platform-admin only: edit the whole essay text (word_count recomputed).
  updateText: (id: number | string, essay_text: string) =>
    api<TeacherEssayCard & { essay_text: string }>(`/api/v1/essays/teacher/${id}/edit/`, {
      method: 'PATCH',
      body: JSON.stringify({ essay_text }),
    }),
};

export const ArenaLobby = {
  // JWT summary (stats + leaderboard + invites) — works without session.
  summary: () => api<Record<string, unknown>>('/tma/api/arena/'),
  // Arena endpoints with DRF JWT Bearer authentication.
  leaderboard: () => api<Record<string, unknown>>('/arena/api/leaderboard/'),
  stats: () => api<Record<string, unknown>>('/arena/api/stats/'),
  invites: () => api<Record<string, unknown>>('/arena/api/invites/'),
  createRoom: () => api<{ room_code: string; url?: string }>('/arena/api/rooms/create/', { method: 'POST' }),
  joinRoom: (code: string) =>
    api<{ room_code: string; url?: string }>('/arena/api/rooms/join/', {
      method: 'POST',
      body: JSON.stringify({ code }),
    }),
  queue: () => api<Record<string, unknown>>('/arena/api/queue/', { method: 'POST' }),
};

// -- OMR Answer Sheet Scanner -----------------------------------------------
export interface OmrScanBreakdown {
  question_number: number;
  question_text: string;
  selected_answer: string;
  correct_answer: string;
  is_correct: boolean;
  is_blank: boolean;
  points: number;
  max_points: number;
}

export interface OmrScanResponse {
  ok: boolean;
  test_id: number;
  test_title: string;
  mock_code: string;
  subject: string;
  total_questions: number;
  correct_count: number;
  incorrect_count: number;
  blank_count: number;
  total_score: number;
  max_score: number;
  percentage: number;
  grade: string;
  is_passed: boolean;
  pass_percentage: number;
  attempt_id?: number | null;
  xp_earned?: number;
  breakdown: OmrScanBreakdown[];
  error?: string;
}

export const OmrApi = {
  scan: (formData: FormData) =>
    api<OmrScanResponse>('/api/v1/tests/scan-omr/', {
      method: 'POST',
      body: formData,
    }),
};

// -- AI Speaking Simulator --------------------------------------------------
export interface SpeakingTopicItem {
  id: number;
  title: string;
  subject: string;
  part: 'part1' | 'part2' | 'part3' | 'multilevel';
  part_label: string;
  prompt: string;
  bullet_points: string[];
  follow_up_questions?: string[];
  prep_time_seconds: number;
  speak_time_seconds: number;
  difficulty: string;
  difficulty_label: string;
}

export interface SpeakingSubmissionDetail {
  id: number;
  topic_id: number;
  topic_title: string;
  part: string;
  part_label: string;
  audio_url?: string | null;
  duration_seconds: number;
  transcript: string;
  fluency_score: number;
  lexical_score: number;
  grammar_score: number;
  pronunciation_score: number;
  overall_band: number;
  feedback: {
    summary?: string;
    fluency_feedback?: string;
    lexical_feedback?: string;
    grammar_feedback?: string;
    pronunciation_feedback?: string;
    vocabulary_suggestions?: { original: string; improved: string; explanation: string }[];
    grammar_corrections?: { incorrect: string; corrected: string; rule: string }[];
  };
  status: string;
  created_at: string;
}

export const SpeakingApi = {
  topics: (params?: { part?: string }) => {
    const qs = new URLSearchParams();
    if (params?.part) qs.set('part', params.part);
    const q = qs.toString() ? `?${qs.toString()}` : '';
    return api<{ count: number; results: SpeakingTopicItem[] }>(`/api/v1/speaking/topics/${q}`);
  },
  topic: (id: number | string) => api<SpeakingTopicItem>(`/api/v1/speaking/topics/${id}/`),
  submit: (formData: FormData) =>
    api<{ ok: boolean; submission: SpeakingSubmissionDetail }>('/api/v1/speaking/submit/', {
      method: 'POST',
      body: formData,
    }),
  submission: (id: number | string) => api<SpeakingSubmissionDetail>(`/api/v1/speaking/submissions/${id}/`),
  mySubmissions: () => api<{ count: number; results: SpeakingSubmissionDetail[] }>('/api/v1/speaking/my-submissions/'),
};

// -- Gamification & Streak --------------------------------------------------
export interface StreakInfoResponse {
  current_streak: number;
  longest_streak: number;
  is_active_today: boolean;
  streak_freeze_count: number;
  xp_points: number;
  weekly_xp: number;
  weekly_league: 'bronze' | 'silver' | 'gold' | 'diamond';
  daily_goal_completed: boolean;
}

export interface LeagueParticipant {
  rank: number;
  user_id: number;
  name: string;
  avatar_url?: string | null;
  weekly_xp: number;
  is_current_user: boolean;
  tier_badge: string;
}

export interface LeagueLeaderboardResponse {
  league: string;
  league_title: string;
  user_rank?: number | null;
  participants: LeagueParticipant[];
  resets_in_hours: number;
}

export const GamificationApi = {
  streak: () => api<StreakInfoResponse>('/api/v1/gamification/streak/'),
  league: () => api<LeagueLeaderboardResponse>('/api/v1/gamification/league/'),
};

// -- White-Label B2B Branding -----------------------------------------------
export interface BrandingInfoResponse {
  success: boolean;
  center_name: string;
  header_title: string;
  brand_color: string;
  center_logo_url?: string | null;
  stamp_signature_url?: string | null;
}

export const WhiteLabelApi = {
  get: () => api<BrandingInfoResponse>('/api/v1/organizations/branding/'),
  update: (formData: FormData) =>
    api<BrandingInfoResponse>('/api/v1/organizations/branding/', {
      method: 'POST',
      body: formData,
    }),
  monthlyReportPdfUrl: (groupId: number | string) =>
    `${API_BASE}/api/v1/school/groups/${groupId}/export/monthly-report-pdf/`,
};

export const apiFetch = api;
