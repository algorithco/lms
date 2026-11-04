/** Essay helpers shared by the studio, my-essays list and the dashboard. */

export type EssayKind = 'ona_tili' | 'adabiyot' | 'ielts_task1' | 'ielts_task2' | 'multilevel';
export type EssayState = 'draft' | 'pending' | 'teacher' | 'graded' | 'error';

/** Which rubric the topic (or submission) belongs to; decides labels and scales. */
export function essayKind(x: { category?: string; rubric_type?: string; subject?: string }): EssayKind {
  const cat = (x.category || '').toLowerCase();
  const rubric = (x.rubric_type || '').toLowerCase();
  if (cat === 'ielts_task1' || rubric === 'ielts_task1') return 'ielts_task1';
  if (cat === 'ielts_task2' || rubric === 'ielts_task2') return 'ielts_task2';
  if (cat === 'multilevel') return 'multilevel';
  if (cat === 'adabiyot') return 'adabiyot';
  return 'ona_tili';
}

/** Raw server status → the five states shown to students (never the raw English word). */
export function essayStatus(raw: string): EssayState {
  switch (raw) {
    case 'draft':
      return 'draft';
    case 'pending_teacher':
      return 'teacher';
    case 'graded':
    case 'ai_evaluated':
    case 'teacher_reviewed':
      return 'graded';
    case 'error':
      return 'error';
    default:
      return 'pending';
  }
}

/** Score exactly as the server stored it: an IELTS band, or points out of the maximum. */
export function scoreLabel(
  s: { overall_band?: number | null; total_score?: number | null; max_score?: number | null },
  t: (key: string) => string,
): string {
  if (s.overall_band != null) return `${t('es_band')} ${Number(s.overall_band).toFixed(1)}`;
  if (s.total_score == null) return '';
  return s.max_score ? `${Number(s.total_score)}/${s.max_score}` : String(Number(s.total_score));
}
