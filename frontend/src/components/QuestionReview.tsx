import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Check, ChevronDown, Minus, Sparkles, X } from 'lucide-react';
import { useLang } from '../i18n/LangContext';
import { Tests as TestsApi, type ApiError } from '../lib/api';
import {
  correctAnswer,
  givenAnswer,
  groupQuestions,
  isReviewable,
  statusOf,
  type ReviewGroup,
  type ReviewQuestion,
} from '../lib/review';

type Filter = 'all' | 'wrong' | 'blank';

interface ExplainState {
  loading?: boolean;
  text?: string;
  message?: string;
  upgrade?: boolean;
}

interface Props {
  questions: ReviewQuestion[];
  /** Result id: needed for the on-demand AI explanation. */
  resultId: number;
  /** Renders a per-question "Problem with this question?" control. */
  renderIssue?: (q: ReviewQuestion) => React.ReactNode;
}

const StatusIcon = ({ status }: { status: string }) =>
  status === 'correct' ? (
    <Check size={14} aria-hidden="true" />
  ) : status === 'wrong' ? (
    <X size={14} aria-hidden="true" />
  ) : (
    <Minus size={14} aria-hidden="true" />
  );

const anchorOf = (key: string) => `rv-g-${key.replace(/\W+/g, '_')}`;

/**
 * Per-question review of a finished attempt: what you answered, the right answer,
 * and — for mistakes — why (deterministic hint, stored explanation and evidence,
 * and an on-demand AI explanation for paid plans).
 */
export default function QuestionReview({ questions, resultId, renderIssue }: Props) {
  const { t, lang } = useLang();
  const items = useMemo(() => questions.filter(isReviewable), [questions]);
  const [filter, setFilter] = useState<Filter>('all');
  const [closed, setClosed] = useState<Record<string, boolean>>({});
  const [explain, setExplain] = useState<Record<number, ExplainState>>({});
  const [socratic, setSocratic] = useState<Record<number, { loading?: boolean; text?: string; error?: string }>>({});

  const counts = useMemo(() => {
    let wrong = 0;
    let blank = 0;
    for (const q of items) {
      const s = statusOf(q);
      if (s === 'wrong') wrong += 1;
      if (s === 'blank') blank += 1;
    }
    return { all: items.length, wrong, blank };
  }, [items]);

  const fullGroups = useMemo(() => groupQuestions(items), [items]);
  const groups = useMemo<ReviewGroup[]>(() => {
    const visible = items.filter((q) => {
      const s = statusOf(q);
      return filter === 'all' || (filter === 'wrong' ? s === 'wrong' : s === 'blank');
    });
    return groupQuestions(visible);
  }, [items, filter]);
  const hasStructure = fullGroups.some((g) => g.sectionCode || g.partNumber);

  if (items.length === 0) return null;

  const groupTitle = (g: ReviewGroup) => {
    if (!g.sectionCode && !g.partNumber) return t('rv_flat_group');
    const section = g.sectionCode ? t(`omr_section_${g.sectionCode}`, g.sectionName || g.sectionCode) : '';
    const part = g.partNumber ? `${t('rv_part')} ${g.partNumber}` : '';
    return [section, part, g.partTitle].filter(Boolean).join(' · ');
  };

  const askSocratic = async (q: ReviewQuestion, userAns: string) => {
    setSocratic((prev) => ({ ...prev, [q.question_id]: { loading: true } }));
    try {
      const res = await TestsApi.socraticTutor({
        question_id: q.question_id,
        result_id: resultId,
        user_answer: userAns,
      });
      setSocratic((prev) => ({
        ...prev,
        [q.question_id]: { text: res.explanation },
      }));
    } catch (e: any) {
      setSocratic((prev) => ({
        ...prev,
        [q.question_id]: { error: e?.message || "Tushuntirish olishda xatolik yuz berdi." },
      }));
    }
  };

  const ask = async (q: ReviewQuestion) => {
    setExplain((prev) => ({ ...prev, [q.question_id]: { loading: true } }));
    try {
      const res = await TestsApi.explainResultQuestion(resultId, q.question_id, lang);
      setExplain((prev) => ({
        ...prev,
        [q.question_id]: res.text ? { text: res.text } : { message: t('rv_explain_unavailable') },
      }));
    } catch (e) {
      const err = e as ApiError;
      const state: ExplainState =
        err.code === 'paid_only'
          ? { message: t('rv_explain_paid'), upgrade: true }
          : err.code === 'limit'
            ? { message: t('rv_explain_limit') }
            : { message: t('rv_explain_failed') };
      setExplain((prev) => ({ ...prev, [q.question_id]: state }));
    }
  };

  const hintText = (q: ReviewQuestion): string => {
    if (!q.hint) return '';
    return t(`rv_hint_${q.hint.code}`).replace('{limit}', String(q.hint.limit ?? ''));
  };

  const renderCard = (q: ReviewQuestion) => {
    const status = statusOf(q);
    const given = givenAnswer(q);
    const right = correctAnswer(q);
    const missed = status === 'wrong' || status === 'blank';
    const ex = explain[q.question_id];
    const soc = socratic[q.question_id];
    const hint = hintText(q);
    const hasWhy = missed;

    return (
      <li key={q.question_id} id={`q-${q.question_id}`} className={`rv-card rv-card--${status}`}>
        <div className="rv-card__head">
          <span className="rv-num">{q.number ?? '·'}</span>
          <span className="rv-type">{t(`rv_type_${q.question_type}`, q.question_type)}</span>
          <span className={`rv-status rv-status--${status}`}>
            <StatusIcon status={status} />
            {t(`rv_status_${status}`)}
          </span>
        </div>

        {q.group_title && <p className="rv-group-title">{q.group_title}</p>}
        <p className="rv-question">{q.question_text}</p>

        {status !== 'hidden' ? (
          <dl className="rv-answers">
            <div className={`rv-answer rv-answer--given${status === 'correct' ? ' is-right' : ''}`}>
              <dt>{t('rv_your_answer')}</dt>
              <dd>{given || <span className="rv-muted">{t('rv_no_answer')}</span>}</dd>
            </div>
            {missed && (
              <div className="rv-answer rv-answer--right">
                <dt>{t('rv_correct_answer')}</dt>
                <dd>{right || '—'}</dd>
              </div>
            )}
          </dl>
        ) : (
          <p className="rv-muted">{t('rv_hidden_note')}</p>
        )}

        {hasWhy && (
          <div className="rv-why">
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8, marginBottom: 8 }}>
              <h4>{t('rv_why_title')}</h4>
              {!soc?.text && !soc?.loading && (
                <button
                  type="button"
                  onClick={() => void askSocratic(q, given)}
                  style={{
                    padding: '6px 12px',
                    borderRadius: '8px',
                    border: '1px solid rgba(200, 146, 42, 0.4)',
                    background: 'linear-gradient(135deg, rgba(200, 146, 42, 0.15), rgba(200, 146, 42, 0.05))',
                    color: '#C8922A',
                    fontWeight: 600,
                    fontSize: '12px',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '6px',
                    cursor: 'pointer',
                    transition: 'all 0.2s ease',
                  }}
                >
                  <span>🧠</span>
                  <span>Nega xato qildim? (AI)</span>
                </button>
              )}
            </div>

            {soc?.loading && (
              <div
                style={{
                  margin: '10px 0',
                  padding: '12px 16px',
                  borderRadius: '10px',
                  background: 'rgba(200, 146, 42, 0.08)',
                  backdropFilter: 'blur(8px)',
                  border: '1px solid rgba(200, 146, 42, 0.25)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '10px',
                }}
              >
                <div
                  style={{
                    width: '16px',
                    height: '16px',
                    border: '2px solid #C8922A',
                    borderTopColor: 'transparent',
                    borderRadius: '50%',
                    animation: 'spin 0.8s linear infinite',
                  }}
                />
                <span style={{ fontSize: '13px', fontWeight: 500, color: '#C8922A' }}>
                  🧠 Sokratik AI tyutor xatoingizni tahlil qilmoqda...
                </span>
              </div>
            )}

            {soc?.text && (
              <div
                style={{
                  margin: '10px 0',
                  padding: '14px 18px',
                  borderRadius: '12px',
                  background: 'rgba(255, 255, 255, 0.05)',
                  backdropFilter: 'blur(12px)',
                  WebkitBackdropFilter: 'blur(12px)',
                  border: '1px solid rgba(200, 146, 42, 0.35)',
                  boxShadow: '0 4px 20px -2px rgba(200, 146, 42, 0.12)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                  <span style={{ fontSize: '16px' }}>🧠</span>
                  <span style={{ fontSize: '12px', fontWeight: 700, color: '#C8922A', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                    Sokratik Tyutor Tahlili (DeepSeek V3)
                  </span>
                </div>
                <p style={{ margin: 0, fontSize: '13.5px', lineHeight: 1.6, color: 'inherit' }}>
                  {soc.text}
                </p>
              </div>
            )}
            {hint && <p className="rv-hint">{hint}</p>}
            {q.explanation && (
              <p className="rv-explanation">
                {q.explanation}{' '}
                {q.explanation_status === 'draft' && <span className="rv-draft">{t('rv_draft_badge')}</span>}
              </p>
            )}
            {q.evidence && (
              <blockquote className="rv-evidence">
                <span>{t('rv_evidence')}</span>
                {q.evidence}
              </blockquote>
            )}
            {ex?.text && (
              <div className="rv-ai">
                <span className="rv-ai__label">
                  <Sparkles size={13} aria-hidden="true" /> {t('rv_explain_ai_label')}
                </span>
                <p>{ex.text}</p>
              </div>
            )}
            {ex?.message && (
              <p className="rv-muted" role="status">
                {ex.message} {ex.upgrade && <Link to="/pricing">{t('rv_explain_upgrade')}</Link>}
              </p>
            )}
            {q.can_ai_explain && !ex?.text && (
              <button
                type="button"
                className="ui-btn ui-btn--sm"
                disabled={ex?.loading}
                onClick={() => void ask(q)}
              >
                <Sparkles size={14} aria-hidden="true" />
                {ex?.loading ? t('rv_explain_loading') : t('rv_explain_btn')}
              </button>
            )}
          </div>
        )}

        {renderIssue && <div className="rv-issue">{renderIssue(q)}</div>}
      </li>
    );
  };

  return (
    <section className="rv" aria-label={t('rv_title')}>
      <h3 className="rv-title">{t('rv_title')}</h3>

      {hasStructure && (
        <div className="rv-summary">
          <h4>{t('rv_by_part')}</h4>
          <ul>
            {fullGroups.map((g) => (
              <li key={g.key}>
                <a href={`#${anchorOf(g.key)}`} onClick={() => setClosed((prev) => ({ ...prev, [g.key]: false }))}>
                  <span>{groupTitle(g)}</span>
                  <b>
                    {g.correct}/{g.items.length}
                  </b>
                </a>
                <span className="rv-bar" aria-hidden="true">
                  <i style={{ width: `${(g.correct / g.items.length) * 100}%` }} />
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="rv-filters" role="group" aria-label={t('rv_title')}>
        {(['all', 'wrong', 'blank'] as Filter[]).map((f) => (
          <button
            key={f}
            type="button"
            className={`rv-chip${filter === f ? ' is-active' : ''}`}
            aria-pressed={filter === f}
            onClick={() => setFilter(f)}
          >
            {t(`rv_filter_${f}`)} <b>{counts[f]}</b>
          </button>
        ))}
      </div>

      {groups.length === 0 ? (
        <p className="rv-muted">{t('rv_empty_filter')}</p>
      ) : (
        groups.map((g) => {
          const full = fullGroups.find((x) => x.key === g.key) ?? g;
          const isClosed = closed[g.key] === true;
          return (
            <div key={g.key} className="rv-group" id={anchorOf(g.key)}>
              {(hasStructure || groups.length > 1) && (
                <button
                  type="button"
                  className="rv-group__head"
                  aria-expanded={!isClosed}
                  aria-label={`${groupTitle(g)} — ${t('rv_group_toggle')}`}
                  onClick={() => setClosed((prev) => ({ ...prev, [g.key]: !isClosed }))}
                >
                  <span>{groupTitle(g)}</span>
                  <span className="rv-group__score">
                    {full.correct}/{full.items.length}
                  </span>
                  <ChevronDown size={18} aria-hidden="true" className={isClosed ? '' : 'is-open'} />
                </button>
              )}
              {!isClosed && <ol className="rv-list">{g.items.map(renderCard)}</ol>}
            </div>
          );
        })
      )}
    </section>
  );
}
