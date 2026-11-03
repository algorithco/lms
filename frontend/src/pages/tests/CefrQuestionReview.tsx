import { useLang } from '../../i18n/LangContext';

/** The slice of a result's question_details this review needs. */
export interface CefrReviewQuestion {
  question_id: number;
  number: number | null;
  number_key: string;
  section_code: string;
  is_correct: boolean | null;
  selected_choices: { id: number; text: string }[];
  correct_choices: { id: number; text: string }[];
  student_answer_text?: string;
}

const SECTIONS = ['LISTENING', 'READING'] as const;

/**
 * Per-question review for a CEFR Multi-level attempt: Listening and Reading
 * numbered 1–35 each, like the paper sheet. Writing and Speaking are not
 * questions here — their state is in CefrResultSummary.
 */
export default function CefrQuestionReview({ questions }: { questions: CefrReviewQuestion[] }) {
  const { t } = useLang();
  const answerText = (q: CefrReviewQuestion) =>
    q.selected_choices.map((c) => c.text).filter(Boolean).join(', ') || (q.student_answer_text || '').trim();

  return (
    <div className="card cefr-review">
      <h3>{t('cefr_review_title')}</h3>
      {SECTIONS.map((code) => {
        const items = questions.filter((q) => q.section_code === code && q.number != null);
        if (!items.length) return null;
        const right = items.filter((q) => q.is_correct === true).length;
        return (
          <section key={code}>
            <h4>
              {t(`omr_section_${code}`, code)} <span className="muted small">· {right}/{items.length}</span>
            </h4>
            <ol className="cefr-review-grid">
              {items.map((q) => {
                const given = answerText(q);
                const state = !given ? 'blank' : q.is_correct === true ? 'right' : q.is_correct === false ? 'wrong' : 'hidden';
                const correct = q.correct_choices.map((c) => c.text).filter(Boolean).join(', ');
                return (
                  <li key={q.question_id} className={`cefr-review-item ${state}`}>
                    <span className="cefr-review-num">{q.number}</span>
                    <span className="cefr-review-answer">
                      {given || t('cefr_review_blank')}
                      {state === 'wrong' && correct && (
                        <span className="muted small"> · {t('cefr_review_correct')}: {correct}</span>
                      )}
                    </span>
                  </li>
                );
              })}
            </ol>
          </section>
        );
      })}
    </div>
  );
}
