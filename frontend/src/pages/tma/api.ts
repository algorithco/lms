/**
 * TMA JSON client — mirrors apps/telegram_app (views.py + test_api.py).
 * Auth: JWT Bearer via the shared api() (auto refresh). All responses are
 * raw shapes (JsonResponse / DRF Response without envelope).
 */
import { api } from '../../lib/api';

export interface TmaTestSummary {
  id: number;
  title: string;
  description?: string;
  course?: string;
  time_limit_minutes: number;
  total_questions: number;
  difficulty: string;
}

export interface TmaChoice {
  id: number;
  text: string;
}

export interface TmaQuestion {
  id: number;
  text: string;
  question_type: string;
  points?: number;
  position?: number;
  choices: TmaChoice[];
  selected_choice_ids: number[];
  text_answer: string;
}

export interface TmaTestStart {
  attempt_id: number;
  test_title: string;
  test_description?: string;
  time_limit_minutes: number;
  total_questions: number;
  started_at?: string | null;
  remaining_seconds: number;
  questions: TmaQuestion[];
}

export type TmaAnswerValue = number[] | { choice_ids: number[]; text_answer: string };

export interface TmaSubmitResult {
  success?: boolean;
  result_id?: number;
  percentage?: number;
  is_passed?: boolean;
  correct_answers?: number;
  total_questions?: number;
  score?: string;
  max_score?: string;
  error?: string;
  time_expired?: boolean;
}

export interface TmaAttemptResult extends TmaSubmitResult {
  test_title?: string;
  time_taken_seconds?: number;
}

export interface TmaResultItem {
  id?: number;
  test_title: string;
  course_title?: string;
  percentage: number;
  is_passed: boolean;
  correct_answers: number;
  total_questions: number;
  calculated_at?: string | null;
}

export interface TmaProfile {
  user: { id: number; email: string; full_name: string; role: string };
  stats: {
    tests_taken: number;
    tests_passed: number;
    certificates: number;
    total_xp: number;
    essays_written: number;
  };
}

export interface TmaEssayTopic {
  id: number;
  title: string;
  description?: string;
  word_limit_min: number;
  word_limit_max: number;
  time_limit_minutes: number;
  has_password: boolean;
  user_status: { submission_id: number; status: string; total_score: number | null } | null;
}

export interface TmaEssayStart {
  submission_id: number;
  topic: {
    id: number;
    title: string;
    description?: string;
    word_limit_min: number;
    word_limit_max: number;
    time_limit_minutes: number;
  };
  remaining_seconds: number;
  essay_text: string;
  word_count: number;
  has_password: boolean;
}

export interface TmaEssayCriterion {
  id: number;
  name: string;
  score: number;
  max_score?: number;
  reason?: string;
  errors?: string[];
}

export interface TmaEssayResult {
  id: number;
  topic_title: string;
  status: string;
  total_score: number | null;
  max_score?: number;
  converted_score?: number | null;
  score_percentage?: number | null;
  summary?: string;
  word_count?: number;
  is_off_topic?: boolean;
  graded_at?: string | null;
  final_score?: number | null;
  criteria: TmaEssayCriterion[];
  poll_after?: number;
}

/** Extract a human message from api() failures ({error} or {detail} bodies). */
export function tmaErrorMessage(err: unknown, fallback: string): string {
  if (err instanceof Error && err.message) {
    const msg = err.message;
    if (msg.startsWith('{')) {
      try {
        const body = JSON.parse(msg) as { error?: unknown; detail?: unknown };
        if (typeof body.error === 'string' && body.error) return body.error;
        if (typeof body.detail === 'string' && body.detail) return body.detail;
      } catch {
        /* fall through to fallback */
      }
    } else if (!msg.startsWith('Request failed')) {
      return msg;
    }
  }
  return fallback;
}

export const TmaApi = {
  profile: () => api<TmaProfile>('/tma/api/profile/'),
  tests: () => api<{ tests: TmaTestSummary[] }>('/tma/api/tests/'),
  results: () => api<{ results: TmaResultItem[] }>('/tma/api/results/'),
  startTest: (testId: number) =>
    api<TmaTestStart>(`/tma/api/tests/${testId}/start/`, { method: 'POST', body: '{}' }),
  submitTest: (testId: number, attemptId: number, answers: Record<number, TmaAnswerValue>) =>
    api<TmaSubmitResult>(`/tma/api/tests/${testId}/submit/`, {
      method: 'POST',
      body: JSON.stringify({ attempt_id: attemptId, answers }),
    }),
  attemptResult: (attemptId: number) =>
    api<TmaAttemptResult>(`/tma/api/attempts/${attemptId}/result/`),
  essayTopics: () => api<{ topics: TmaEssayTopic[] }>('/tma/api/essays/topics/'),
  essayStart: (topicId: number, password?: string) =>
    api<TmaEssayStart>(`/tma/api/essays/${topicId}/start/`, {
      method: 'POST',
      body: JSON.stringify(password ? { password } : {}),
    }),
  essaySubmit: (submissionId: number, essayText: string) =>
    api<{ status: string; submission_id: number; poll_after?: number; result_url?: string }>(
      `/tma/api/essays/${submissionId}/submit/`,
      { method: 'POST', body: JSON.stringify({ essay_text: essayText }) },
    ),
  essayResult: (submissionId: number) =>
    api<TmaEssayResult>(`/tma/api/essays/${submissionId}/result/`),
};
