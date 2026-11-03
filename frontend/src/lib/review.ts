/** Shape of one entry of `question_details` in GET /api/results/<id>/detail/ (answers released). */
export type ReviewStatus = 'correct' | 'wrong' | 'blank' | 'hidden' | 'written';

export interface ReviewChoice {
  id: number;
  text: string;
  letter?: string;
}

export interface ReviewHint {
  code: 'unanswered' | 'near_typo' | 'near_form' | 'near_case' | 'word_limit' | 'not_in_text';
  limit?: number;
}

export interface ReviewQuestion {
  question_id: number;
  number: number | null;
  number_key?: string;
  section_code: string;
  section_name?: string;
  part_id?: number | null;
  part_number?: string;
  part_title?: string;
  group_title?: string;
  question_text: string;
  question_type: string;
  status?: ReviewStatus;
  is_correct: boolean | null;
  correct_choices: ReviewChoice[];
  selected_choices: ReviewChoice[];
  correct_text?: string;
  student_answer_text?: string;
  hint?: ReviewHint | null;
  explanation?: string;
  evidence?: string;
  explanation_status?: string;
  can_ai_explain?: boolean;
}

/** Choice questions where the option letter is part of the answer ("B: It starts at 9 a.m."). */
const LETTERED = new Set([
  'MULTIPLE_CHOICE',
  'MATCHING',
  'HEADING_MATCHING',
  'MAP_LABELING',
  'single',
  'multiple',
  'matching',
]);

/** Objective questions only: written and speaking tasks are not part of the per-question review. */
export const isReviewable = (q: ReviewQuestion): boolean =>
  q.question_type !== 'written' && q.question_type !== 'SPEAKING_PROMPT';

export function statusOf(q: ReviewQuestion): ReviewStatus {
  if (q.status) return q.status;
  if (q.is_correct === true) return 'correct';
  if (q.is_correct === false) return 'wrong';
  return (q.selected_choices?.length || (q.student_answer_text || '').trim()) ? 'hidden' : 'blank';
}

function format(q: ReviewQuestion, choices: ReviewChoice[], fallback: string): string {
  const lettered = LETTERED.has(q.question_type);
  const parts = choices
    .filter((c) => c.text)
    .map((c) => (lettered && c.letter ? `${c.letter}: ${c.text}` : c.text));
  return parts.join(', ') || fallback.trim();
}

export const givenAnswer = (q: ReviewQuestion): string =>
  format(q, q.selected_choices ?? [], q.student_answer_text ?? '');

export const correctAnswer = (q: ReviewQuestion): string =>
  format(q, q.correct_choices ?? [], q.correct_text ?? '');

export interface ReviewGroup {
  key: string;
  sectionCode: string;
  sectionName: string;
  partNumber: string;
  partTitle: string;
  items: ReviewQuestion[];
  correct: number;
}

/** Group by section and part, in the order the questions arrive. No section → one flat group. */
export function groupQuestions(questions: ReviewQuestion[]): ReviewGroup[] {
  const map = new Map<string, ReviewGroup>();
  for (const q of questions) {
    const key = `${q.section_code || ''}|${q.part_id ?? ''}`;
    let g = map.get(key);
    if (!g) {
      g = {
        key,
        sectionCode: q.section_code || '',
        sectionName: q.section_name || '',
        partNumber: q.part_number || '',
        partTitle: q.part_title || '',
        items: [],
        correct: 0,
      };
      map.set(key, g);
    }
    g.items.push(q);
    if (statusOf(q) === 'correct') g.correct += 1;
  }
  return [...map.values()];
}
