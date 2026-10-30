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
  subject?: 'uzbek' | 'english' | string;
  audio_url?: string;
  is_strict_mode?: boolean;
  category_slug?: string;
  category_name?: string;
  mock_code?: string;
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
  certificate_status?: string;
  grading_status?: string;
  time_taken_seconds?: number;
  calculated_at?: string;
  rasch_score?: string | number;
  max_rasch_score?: string | number;
  rasch_grade?: string;
  rasch_explanation?: string;
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
export function listTestsPage(page = 1, subject?: string): Promise<Paginated<TestListItem>> {
  const query = subject ? `&subject=${encodeURIComponent(subject)}` : '';
  return api<Paginated<TestListItem>>(`/api/tests/?page=${page}${query}`);
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
  const n = Number(v);
  return Number.isFinite(n) ? (n as number) : fallback;
}

export interface ConvertedChoice {
  code: string;
  text: string;
}

export interface ConvertedQuestion {
  order: number;
  text: string;
  choices: ConvertedChoice[];
  correct_answer: string;
  explanation?: string;
  question_type?: string;
}

export interface ConvertedTestResult {
  test_title: string;
  reading_passage?: string;
  subject: string;
  questions_count: number;
  questions: ConvertedQuestion[];
}

export const TestsApi = {
  list(params: {
    page?: number;
    course?: number;
    search?: string;
    subject?: string;
    category?: string;
  } = {}): Promise<Paginated<TestListItem>> {
    const q = new URLSearchParams();
    if (params.page) q.set('page', String(params.page));
    if (params.course) q.set('course', String(params.course));
    if (params.search) q.set('search', params.search);
    if (params.subject) q.set('subject', params.subject);
    if (params.category) q.set('category', params.category);
    const qs = q.toString();
    return api<Paginated<TestListItem>>(`/api/tests/${qs ? `?${qs}` : ''}`);
  },

  detail(id: number | string): Promise<TestListItem> {
    return api<TestListItem>(`/api/tests/${id}/`);
  },

  start(id: number | string, isStrict = false): Promise<unknown> {
    return api(`/api/tests/${id}/start/`, {
      method: 'POST',
      body: JSON.stringify({ is_strict_mode: isStrict }),
    });
  },

  saveAnswer(
    attemptId: string,
    payload: {
      question_id: number;
      choice_ids?: number[];
      text_answer?: string;
      gap_answers?: Record<string, string>;
      matching?: Record<string, number | null>;
      written_text?: string;
    },
  ): Promise<unknown> {
    return api(`/api/tests/attempts/${attemptId}/answer/`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  submit(attemptId: string): Promise<unknown> {
    return api(`/api/tests/attempts/${attemptId}/submit/`, { method: 'POST' });
  },

  results(page = 1): Promise<Paginated<ResultListItem>> {
    return api<Paginated<ResultListItem>>(`/api/results/my/?page=${page}`);
  },

  resultDetail(id: number | string): Promise<ResultListItem> {
    return api<ResultListItem>(`/api/results/${id}/`);
  },

  certificates(): Promise<CertListItem[]> {
    return api<CertListItem[]>('/api/certificates/my/');
  },

  aiConvertDocument(formData: FormData): Promise<{ success: boolean; data: ConvertedTestResult }> {
    return api<{ success: boolean; data: ConvertedTestResult }>('/api/v1/tests/ai-convert-document/', {
      method: 'POST',
      body: formData,
    });
  },

  aiSaveConverted(payload: {
    test_title: string;
    subject: string;
    time_limit_minutes: number;
    reading_passage?: string;
    questions: ConvertedQuestion[];
  }): Promise<{ success: boolean; test_id: number; mock_code: string; title: string; questions_count: number; message: string }> {
    return api('/api/v1/tests/ai-save-converted/', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  generateRetest(attemptId: number | string): Promise<{
    has_mistakes: boolean;
    retest_test_id?: number;
    attempt_id?: number;
    total_questions?: number;
    weak_topics?: string[];
    message?: string;
  }> {
    return api(`/api/v1/tests/attempts/${attemptId}/generate-retest/`, {
      method: 'POST',
    });
  },

  getMistakeVault(): Promise<{
    unresolved_count: number;
    mastered_count: number;
    weak_topics: { topic: string; error_count: number }[];
    recent_mistakes: {
      question_id: number;
      question_text: string;
      topic: string;
      test_title: string;
      correct_answer: string;
      explanation: string;
      date: string;
    }[];
  }> {
    return api('/api/v1/tests/mistake-vault/');
  },
};

/** Storage draft key for network-failure resume of an attempt. */
export function draftKey(attemptId: string): string {
  return `take-draft-${attemptId}`;
}

export type DraftMap = Record<
  number,
  {
    choices: number[];
    text: string;
    gaps?: Record<string, string>;
    matching?: Record<string, number | null>;
    written?: string;
    flagged?: boolean;
    highlighterText?: string;
    updatedAt: number;
  }
>;

export function loadDraft(attemptId: string): DraftMap {
  try {
    const raw =
      localStorage.getItem(draftKey(attemptId)) ||
      sessionStorage.getItem(draftKey(attemptId));
    if (!raw) return {};
    const parsed = JSON.parse(raw) as DraftMap;
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch {
    return {};
  }
}

export function storeDraft(attemptId: string, draft: DraftMap): void {
  const json = JSON.stringify(draft);
  try {
    localStorage.setItem(draftKey(attemptId), json);
  } catch {
    try {
      sessionStorage.setItem(draftKey(attemptId), json);
    } catch {
      /* storage full / private mode — non-fatal */
    }
  }
}

export function clearDraft(attemptId: string): void {
  try {
    localStorage.removeItem(draftKey(attemptId));
    sessionStorage.removeItem(draftKey(attemptId));
  } catch {
    /* ignore */
  }
}
