/**
 * School domain helpers (Teacher / Groups / Parent / Imports).
 *
 * The typed `School` client in lib/api.ts covers most of
 * apps/webapi/views_school.py. The helpers below fill the remaining gaps
 * via the generic api<T>() — group detail GET, parent overview for a given
 * user_id (platform admin), plus shared types, CSV sample templates and
 * per-row error normalisation. No other stream files are touched.
 */
import { api } from './api';

export interface GroupMember {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  full_name: string;
}

export interface SchoolGroup {
  id: number;
  name: string;
  description: string;
  teacher: number;
  teacher_name: string;
  student_count: number;
  students: GroupMember[];
  created_at: string;
}

export interface RecentResult {
  student: string;
  test: string;
  percentage: number;
  is_passed: boolean;
  date: string;
}

export interface TeacherOverview {
  groups: SchoolGroup[];
  student_count: number;
  published_tests: number;
  active_topics: number;
  recent_results: RecentResult[];
}

export interface AnalyticsTotals {
  attempts: number;
  passed: number;
}

export interface AnalyticsData {
  labels: string[];
  attempts: number[];
  avg_percentage: number[];
  totals: AnalyticsTotals;
}

export interface ChildResult {
  test: string;
  percentage: number;
  is_passed: boolean;
  date: string;
}

export interface ParentChild {
  id: number;
  name: string;
  email: string;
  relationship: string;
  is_approved: boolean;
  results: ChildResult[];
}

export interface ParentOverview {
  children: ParentChild[];
}

/** Per-row import error — services return {row, error} objects. */
export interface ImportRowError {
  row: number | string;
  message: string;
}

export interface StudentImportResult {
  created: number;
  skipped: number;
  errors: ImportRowError[];
}

export interface TestImportCourse {
  id: number;
  title: string;
}

export interface TestImportResult {
  success: boolean;
  test_id: number | null;
  questions_created: number;
  errors: ImportRowError[];
}

/** Leaderboard entry from /api/v1/school/essay-leaderboard/. */
export interface EssayBoardEntry {
  rank: number;
  name: string;
  student_id: number;
  best_score: number;
  converted_score: number;
  essay_count: number;
  avg_score: number;
}

export interface EssayBoard {
  podium: EssayBoardEntry[];
  rest: EssayBoardEntry[];
  total_essays: number;
  total_students: number;
}

/** GET /api/v1/school/groups/<id>/ — the typed client only has PATCH/DELETE. */
export function getGroupDetail(id: number | string): Promise<SchoolGroup> {
  return api<SchoolGroup>(`/api/v1/school/groups/${id}/`);
}

/**
 * GET /api/v1/school/parent/ — optional user_id lets a platform admin
 * inspect another parent's overview (backend supports ?user_id= for admins).
 */
export function parentOverview(userId?: number | string): Promise<ParentOverview> {
  const qs = userId ? `?user_id=${encodeURIComponent(String(userId))}` : '';
  return api<ParentOverview>(`/api/v1/school/parent/${qs}`);
}

/** Normalise per-row errors: [{row, error}] objects or plain strings. */
export function normaliseRowErrors(input: unknown): ImportRowError[] {
  if (!Array.isArray(input)) return [];
  return input.map((e, i) => {
    if (typeof e === 'object' && e !== null) {
      const r = e as Record<string, unknown>;
      return {
        row: (r.row as number | string) ?? i + 1,
        message: String(r.error ?? r.message ?? JSON.stringify(e)),
      };
    }
    return { row: i + 1, message: String(e) };
  });
}

export function errMessage(e: unknown): string {
  return e instanceof Error ? e.message : 'Failed.';
}

/** Trigger a client-side download (used for sample CSV templates). */
export function downloadCsv(filename: string, content: string): void {
  const blob = new Blob([content], { type: 'text/csv;charset=utf-8' });
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}

/** Mirrors templates/web/csv_import.html downloadTemplate(). */
export const STUDENT_CSV_SAMPLE =
  'email,first_name,last_name,phone\n' +
  'ali@example.com,Ali,Valiyev,+998901234567\n' +
  'vali@example.com,Vali,Hasanov,+998907654321\n';

/** Mirrors templates/web/bulk_test_import.html downloadTemplate(). */
export const TEST_CSV_SAMPLE =
  'question,choice_a,choice_b,choice_c,choice_d,correct,points,explanation\n' +
  '"2+2=?",A.3,B.4,C.5,D.6,B,1,"Oddiy qo\'shish"\n' +
  '"3+5=?",A.6,B.7,C.8,D.9,C,1,""\n' +
  '"Poytaxt Toshkentmi?",A.Ha,B.Yo\'q,,,A,1,""\n';

/** Client-side mirror of the backend _csv_guard (5 MB, .csv). */
export function guardCsv(file: File | null): string | null {
  if (!file) return 'CSV faylni tanlang.';
  if (!file.name.toLowerCase().endsWith('.csv')) return 'Faqat CSV fayllar qabul qilinadi.';
  if (file.size > 5 * 1024 * 1024) return 'CSV fayl hajmi 5 MB dan oshmasligi kerak.';
  return null;
}
