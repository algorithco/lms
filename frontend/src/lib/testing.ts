/**
 * Student testing domain helpers (Stream 2).
 * Thin wrappers over the JWT `api()` client — no new auth logic here.
 * Backend: apps/tests, apps/results, apps/certificates (REST /api/*).
 * The legacy `quiz/` WebSocket arena (ws/quiz/arena/) is a separate
 * 1v1-duel surface and is NOT used by the solo test-taking flow.
 */
import { api, type Paginated } from './api';

export interface TestListItem {
  id: number;
  title: string;
  description?: string;
  course?: number;
  course_title?: string;
  difficulty?: string;
  time_limit_minutes?: number;
  max_attempts?: number;
  pass_percentage?: number;
  total_questions?: number;
  is_active?: boolean;
  created_at?: string;
  [key: string]: unknown;
}

export interface ResultListItem {
  id: number;
  test?: number;
  test_title?: string;
  course?: number;
  course_title?: string;
  student_name?: string;
  score?: string | number;
  max_score?: string | number;
  percentage?: string | number;
  is_passed?: boolean;
  time_taken_seconds?: number;
  calculated_at?: string;
  [key: string]: unknown;
}

export interface CertListItem {
  id: number;
  certificate_number?: string;
  course_title?: string;
  test_title?: string;
  percentage?: string | number;
  status?: string;
  issued_at?: string;
  [key: string]: unknown;
}

/** Paginated test list. Backend uses PageNumberPagination (PAGE_SIZE=20). */
export function listTestsPage(page = 1): Promise<Paginated<TestListItem>> {
  return api<Paginated<TestListItem>>(`/api/tests/?page=${page}`);
}

/** Paginated results list. */
export function listResultsPage(page = 1): Promise<Paginated<ResultListItem>> {
  return api<Paginated<ResultListItem>>(
    `/api/results/my-results/?page=${page}`,
  );
}

/** Paginated certificate list. */
export function listCertsPage(page = 1): Promise<Paginated<CertListItem>> {
  return api<Paginated<CertListItem>>(
    `/api/certificates/my-certificates/?page=${page}`,
  );
}

export function formatClock(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(totalSeconds));
  const mm = String(Math.floor(s / 60)).padStart(2, '0');
  const ss = String(s % 60).padStart(2, '0');
  return `${mm}:${ss}`;
}

export function formatDuration(totalSeconds: number | null | undefined): string {
  if (totalSeconds === null || totalSeconds === undefined) return '—';
  const s = Math.max(0, Math.floor(Number(totalSeconds) || 0));
  const m = Math.floor(s / 60);
  const rest = s % 60;
  if (m === 0) return `${rest} soniya`;
  return `${m} daqiqa ${String(rest).padStart(2, '0')} soniya`;
}

export function num(v: unknown, fallback = 0): number {
  const n = typeof v === 'string' ? parseFloat(v) : (v as number);
  return Number.isFinite(n) ? (n as number) : fallback;
}

/** sessionStorage draft key for network-failure resume of an attempt. */
export function draftKey(attemptId: string): string {
  return `take-draft-${attemptId}`;
}

export type DraftMap = Record<
  number,
  { choices: number[]; text: string; updatedAt: number }
>;

export function loadDraft(attemptId: string): DraftMap {
  try {
    const raw = sessionStorage.getItem(draftKey(attemptId));
    if (!raw) return {};
    const parsed = JSON.parse(raw) as DraftMap;
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch {
    return {};
  }
}

export function storeDraft(attemptId: string, draft: DraftMap): void {
  try {
    sessionStorage.setItem(draftKey(attemptId), JSON.stringify(draft));
  } catch {
    /* storage full / private mode — non-fatal */
  }
}

export function clearDraft(attemptId: string): void {
  try {
    sessionStorage.removeItem(draftKey(attemptId));
  } catch {
    /* ignore */
  }
}
