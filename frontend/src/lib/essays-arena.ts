/**
 * Essays + Arena domain helpers (stream 3 of 5).
 *
 * Pure, UI-agnostic helpers shared by the essay/arena pages, plus thin
 * session-form bridges for the session-only HTML-partial endpoints
 * (POST /essays/api/autosave/, POST /essays/<id>/request-review/).
 * JWT JSON endpoints stay in lib/api.ts (untouched by this stream).
 */

const SESSION_BASE = import.meta.env.VITE_API_URL ?? '';

// ---------------------------------------------------------------------------
// Essay word counting — port of apps.essays.services.WordCounter.
// Only tokens containing a Latin/Cyrillic letter count (pure punctuation
// and numbers are ignored), matching the server-side min/max validation.
// ---------------------------------------------------------------------------

export function countEssayWords(text: string): number {
  if (!text || !text.trim()) return 0;
  const normalized = text.trim().replace(/\s+/g, ' ');
  let n = 0;
  for (const w of normalized.split(' ')) {
    if (w && /[a-zA-Z\u0410-\u044F\u0401\u0451]/.test(w)) n += 1;
  }
  return n;
}

export type WordZone = 'under' | 'ok' | 'over';

export function wordZone(count: number, min: number, max: number): WordZone {
  if (count < min) return 'under';
  if (max > 0 && count > max) return 'over';
  return 'ok';
}

// ---------------------------------------------------------------------------
// Essay grading statuses (apps.essays.models.EssaySubmission.Status).
// The TMA result endpoint mirrors the DB status verbatim.
// ---------------------------------------------------------------------------

/** Fully graded — safe to show scores + improved version + review request. */
export const ESSAY_DONE = new Set(['graded', 'ai_evaluated', 'teacher_reviewed']);

/** Nothing left to poll (graded states + waiting-on-teacher + error). */
export const ESSAY_TERMINAL = new Set([
  'graded',
  'ai_evaluated',
  'teacher_reviewed',
  'pending_teacher',
  'error',
]);

export function isEssayDone(status: string): boolean {
  return ESSAY_DONE.has(status);
}

export function isEssayTerminal(status: string): boolean {
  return ESSAY_TERMINAL.has(status);
}

// ---------------------------------------------------------------------------
// Arena scores — the WS consumer sends scores as a LIST
//   [{user_id, name, score, correct, answered, streak, is_bot,
//     xp_earned?, coins_earned?, rating_change?}]
// (see services.get_scores / _duel_summary). Older clients treated it as a
// {userId: score} map — accept both shapes.
// ---------------------------------------------------------------------------

export interface ArenaScoreRow {
  user_id: number;
  name: string;
  score: number;
  correct?: number;
  answered?: number;
  streak?: number;
  is_bot?: boolean;
  xp_earned?: number;
  coins_earned?: number;
  rating_change?: number;
}

function toRow(raw: Record<string, unknown>): ArenaScoreRow {
  return {
    user_id: Number(raw.user_id ?? raw.id ?? 0),
    name: String(raw.name ?? ''),
    score: Number(raw.score ?? 0) || 0,
    correct: raw.correct !== undefined ? Number(raw.correct) || 0 : undefined,
    answered: raw.answered !== undefined ? Number(raw.answered) || 0 : undefined,
    streak: raw.streak !== undefined ? Number(raw.streak) || 0 : undefined,
    is_bot: raw.is_bot === true,
    xp_earned: raw.xp_earned !== undefined ? Number(raw.xp_earned) || 0 : undefined,
    coins_earned:
      raw.coins_earned !== undefined ? Number(raw.coins_earned) || 0 : undefined,
    rating_change:
      raw.rating_change !== undefined ? Number(raw.rating_change) || 0 : undefined,
  };
}

export function normalizeArenaScores(input: unknown): ArenaScoreRow[] {
  if (Array.isArray(input)) {
    return (input as Record<string, unknown>[]).map(toRow);
  }
  if (input && typeof input === 'object') {
    // Legacy map shape: {"12": 30, "15": 22}
    return Object.entries(input as Record<string, unknown>).map(([k, v]) =>
      toRow({ user_id: Number(k), name: '', score: Number(v) || 0 }),
    );
  }
  return [];
}

export function arenaRowOf(
  rows: ArenaScoreRow[],
  userId: number | null,
): ArenaScoreRow | undefined {
  if (userId === null) return undefined;
  return rows.find((r) => r.user_id === userId);
}

export function arenaScoreOf(rows: ArenaScoreRow[], userId: number | null): number {
  return arenaRowOf(rows, userId)?.score ?? 0;
}

export function arenaOpponentRows(
  rows: ArenaScoreRow[],
  userId: number | null,
): ArenaScoreRow[] {
  return rows.filter((r) => r.user_id !== userId);
}

// ---------------------------------------------------------------------------
// Local draft persistence (per-topic). The server autosave endpoint is
// session-only and returns HTML partials, so the SPA keeps the draft in
// localStorage (always) and best-effort POSTs it to the server (session).
// ---------------------------------------------------------------------------

const draftKey = (topicId: number | string) => `essay_draft_topic_${topicId}`;

export function loadLocalDraft(topicId: number | string): string | null {
  try {
    return localStorage.getItem(draftKey(topicId));
  } catch {
    return null;
  }
}

export function saveLocalDraft(topicId: number | string, text: string): void {
  try {
    if (text) localStorage.setItem(draftKey(topicId), text);
    else localStorage.removeItem(draftKey(topicId));
  } catch {
    /* quota / private mode — server autosave is the fallback */
  }
}

export function clearLocalDraft(topicId: number | string): void {
  try {
    localStorage.removeItem(draftKey(topicId));
  } catch {
    /* ignore */
  }
}

// ---------------------------------------------------------------------------
// Session form bridge (same-origin cookies + CSRF). Used ONLY for the
// session-only HTML-partial essay endpoints that have no JWT JSON
// equivalent: POST /essays/api/autosave/ and
// POST /essays/<submission_id>/request-review/.
// ---------------------------------------------------------------------------

function getCookie(name: string): string | null {
  const m = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return m ? decodeURIComponent(m[1]) : null;
}

export interface SessionFormResult {
  ok: boolean;
  status: number;
  text: string;
}

export async function sessionPostForm(
  path: string,
  params: Record<string, string>,
): Promise<SessionFormResult> {
  const csrf = getCookie('csrftoken') ?? '';
  const res = await fetch(`${SESSION_BASE}${path}`, {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
      'X-CSRFToken': csrf,
    },
    body: new URLSearchParams(params).toString(),
  });
  const text = await res.text().catch(() => '');
  return { ok: res.ok, status: res.status, text };
}

/**
 * Best-effort server autosave. The endpoint answers with an HTML partial
 * (word_counter_partial.html, or autosave_result_partial.html containing
 * `auto-submit-notice` when the timer already expired server-side).
 * A login page (password input) in the response means there is no Django
 * session — the caller should fall back to the local draft.
 */
export async function autosaveEssay(
  submissionId: number | string,
  essayText: string,
): Promise<{ saved: boolean; autoSubmitted: boolean }> {
  try {
    const r = await sessionPostForm('/essays/api/autosave/', {
      submission_id: String(submissionId),
      essay_text: essayText,
    });
    if (!r.ok) return { saved: false, autoSubmitted: false };
    if (r.text.includes('auto-submit-notice')) {
      return { saved: true, autoSubmitted: true };
    }
    if (/<input[^>]*password/i.test(r.text)) {
      return { saved: false, autoSubmitted: false };
    }
    return { saved: true, autoSubmitted: false };
  } catch {
    return { saved: false, autoSubmitted: false };
  }
}

/**
 * Student request for teacher review. The view always answers HTTP 200 with
 * an HTML partial (review_request_partial.html); the error variant contains
 * ❌ while the success variant contains ✅ — used here to detect failure.
 * Fragile by nature; a JSON endpoint would be preferable (see stream notes).
 */
export async function requestTeacherReview(
  submissionId: number | string,
  reason: string,
): Promise<{ ok: boolean }> {
  try {
    const r = await sessionPostForm(`/essays/${submissionId}/request-review/`, {
      reason,
    });
    if (!r.ok) return { ok: false };
    if (r.text.includes('\u274C')) return { ok: false };
    return { ok: true };
  } catch {
    return { ok: false };
  }
}
