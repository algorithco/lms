import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { useLang } from '../../i18n/LangContext';
import { Tests as TestsApi } from '../../lib/api';
import CefrResultSummary, { type CefrSummary } from './CefrResultSummary';
import IeltsResultSummary, { type IeltsSummary } from './IeltsResultSummary';

/* ------------------------------------------------------------------ types */

interface CdChoice { id: number; text: string; position: number }
interface CdQuestion {
  id: number;
  text: string;
  question_type: string;
  section_id: number | null;
  group_id: number | null;
  config: {
    number?: number;
    min_words?: number;
    max_words?: number;
    target_words?: number;
    prep_seconds?: number;
    answer_seconds?: number;
    for?: string[];
    against?: string[];
  };
  choices: CdChoice[];
  selected_choice_ids?: number[];
  text_answer?: string;
  written_text?: string;
}
interface CdGroup {
  id: number;
  title: string;
  instructions: string;
  answer_rule: string;
  passage_id: number | null;
  image_url: string;
  options_label: string;
  each_option_once: boolean;
}
interface CdPart { id: number; number: string; title: string; instructions: string; audio_url: string; groups: CdGroup[] }
interface CdSection { section_id: number; code: string; name: string; duration_minutes: number; parts: CdPart[] }
export interface CdAttempt {
  id: number;
  test_title: string;
  is_preview?: boolean;
  is_trial?: boolean;
  remaining_seconds: number | null;
  structure: CdSection[];
  questions: CdQuestion[];
  passages?: { id: number; title: string; content: string }[];
}

interface Answer { choice?: number; text?: string; written?: string }

const LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
const SELECT_TYPES = new Set(['MATCHING', 'MAP_LABELING', 'HEADING_MATCHING']);
const GAP_RE = /\(\d+\)\s*_{2,}/;

const isAnswered = (a?: Answer) =>
  !!a && (a.choice != null || !!a.text?.trim() || !!a.written?.trim());

const wordCount = (text = '') => text.trim().split(/\s+/).filter(Boolean).length;

const fmt = (secs: number) => {
  const s = Math.max(0, Math.floor(secs));
  return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;
};

/** Section deadline survives reloads: first visit fixes it in sessionStorage. */
function sectionDeadline(attemptId: number, section: CdSection): number | null {
  if (!section.duration_minutes) return null;
  const key = `cd-exam:${attemptId}:${section.section_id}`;
  try {
    const saved = Number(sessionStorage.getItem(key));
    if (saved) return saved;
    const deadline = Date.now() + section.duration_minutes * 60_000;
    sessionStorage.setItem(key, String(deadline));
    return deadline;
  } catch {
    return Date.now() + section.duration_minutes * 60_000;
  }
}

/* -------------------------------------------------------------- component */

/**
 * Computer-delivered exam driven entirely by the attempt API:
 * section → part → group → question. Answer keys never reach the client;
 * every change is saved to the backend, which does all checking.
 */
export default function CdExamInterface({ attempt }: { attempt: CdAttempt }) {
  const { t } = useLang();
  const attemptId = String(attempt.id);

  const [answers, setAnswers] = useState<Record<number, Answer>>(() => {
    const init: Record<number, Answer> = {};
    for (const q of attempt.questions) {
      init[q.id] = {
        choice: q.selected_choice_ids?.[0],
        text: q.text_answer || '',
        written: q.written_text || '',
      };
    }
    return init;
  });
  const [sectionIdx, setSectionIdx] = useState(0);
  const [partIdx, setPartIdx] = useState<Record<number, number>>({});
  const [now, setNow] = useState(() => Date.now());
  const [saveError, setSaveError] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [result, setResult] = useState<CefrSummary | null | 'done'>(null);
  const [ielts, setIelts] = useState<IeltsSummary | null>(null);
  const textTimers = useRef<Record<number, number>>({});
  const submittedRef = useRef(false);

  const sections = attempt.structure;
  const section = sections[sectionIdx];
  const part = section.parts[partIdx[section.section_id] ?? 0];

  const questionsByGroup = useMemo(() => {
    const map: Record<number, CdQuestion[]> = {};
    for (const q of attempt.questions) if (q.group_id != null) (map[q.group_id] ??= []).push(q);
    return map;
  }, [attempt.questions]);
  const passages = useMemo(
    () => Object.fromEntries((attempt.passages || []).map((p) => [p.id, p])),
    [attempt.passages],
  );
  const sectionQuestions = useCallback(
    (s: CdSection) => s.parts.flatMap((p) => p.groups.flatMap((g) => questionsByGroup[g.id] || [])),
    [questionsByGroup],
  );

  const deadline = useMemo(() => sectionDeadline(attempt.id, section), [attempt.id, section]);
  const sectionLeft = deadline ? (deadline - now) / 1000 : null;
  const locked = sectionLeft != null && sectionLeft <= 0;
  const [examEndsAt] = useState(() =>
    attempt.remaining_seconds != null ? Date.now() + attempt.remaining_seconds * 1000 : null,
  );

  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, []);

  const submit = useCallback(async () => {
    if (submittedRef.current) return;
    submittedRef.current = true;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const submitted = (await TestsApi.submit(attemptId)) as unknown as {
        result?: { correct_answers?: number; total_questions?: number };
      };
      if (attempt.is_trial) {
        // One free part has no 0–75 estimate; its review is on /results.
        setResult('done');
        return;
      }
      try {
        const card = (await TestsApi.certificateCard(attemptId)) as unknown as CefrSummary & {
          exam_type?: string;
          overall_band?: number | null;
        };
        if (card.scale === 'cefr_multilevel') {
          setResult(card);
        } else if (/ielts/i.test(card.exam_type ?? '') && submitted?.result?.total_questions) {
          setIelts({
            correct: Number(submitted.result.correct_answers ?? 0),
            total: Number(submitted.result.total_questions),
            band: typeof card.overall_band === 'number' ? card.overall_band : null,
          });
          setResult('done');
        } else {
          setResult('done');
        }
      } catch {
        setResult('done');
      }
    } catch (e) {
      submittedRef.current = false;
      setSubmitError(e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
      setConfirming(false);
    }
  }, [attemptId, attempt.is_trial]);

  // Whole-exam time limit (enforced by the backend too).
  useEffect(() => {
    if (examEndsAt && now >= examEndsAt) void submit();
  }, [now, examEndsAt, submit]);

  const save = useCallback(
    (q: CdQuestion, a: Answer) => {
      const payload =
        q.question_type === 'written'
          ? { question_id: q.id, written_text: a.written || '' }
          : a.choice != null
            ? { question_id: q.id, choice_ids: [a.choice] }
            : { question_id: q.id, text_answer: a.text || '' };
      TestsApi.saveAnswer(attemptId, payload)
        .then(() => setSaveError(false))
        .catch(() => setSaveError(true));
    },
    [attemptId],
  );

  const update = (q: CdQuestion, patch: Answer, debounce = false) => {
    if (locked) return;
    const next = { ...answers[q.id], ...patch };
    setAnswers((prev) => ({ ...prev, [q.id]: next }));
    window.clearTimeout(textTimers.current[q.id]);
    if (debounce) textTimers.current[q.id] = window.setTimeout(() => save(q, next), 600);
    else save(q, next);
  };

  const unanswered = attempt.questions.filter(
    (q) => q.question_type !== 'SPEAKING_PROMPT' && !isAnswered(answers[q.id]),
  ).length;

  /* ---------------------------------------------------------- result view */
  if (result) {
    return (
      <div className="cefr-result-page">
        <h1>{attempt.test_title}</h1>
        {attempt.is_trial ? (
          <p className="cd-preview-badge">{t('cd_trial_badge')}</p>
        ) : (
          attempt.is_preview && <p className="cd-preview-badge">{t('cd_preview_badge')}</p>
        )}
        {result !== 'done' ? (
          <CefrResultSummary data={result} />
        ) : ielts ? (
          <IeltsResultSummary data={ielts} />
        ) : (
          <div className="card">{t(attempt.is_trial ? 'cd_trial_done' : 'cd_submitted')}</div>
        )}
        <div className="error-boundary-actions">
          <Link to="/results" className="btn">{t('my_results')}</Link>
          <Link to="/tests" className="btn primary">{t('error_boundary_back')}</Link>
        </div>
      </div>
    );
  }

  /* ------------------------------------------------------------ renderers */
  const renderQuestion = (q: CdQuestion, group: CdGroup, siblings: CdQuestion[]) => {
    const a = answers[q.id] || {};
    const num = q.config.number;
    const choices = [...q.choices].sort((x, y) => x.position - y.position);

    if (q.question_type === 'SPEAKING_PROMPT') return <SpeakingPrompt key={q.id} q={q} />;

    if (q.question_type === 'written') {
      const words = wordCount(a.written);
      const { min_words: min, max_words: max, target_words: target } = q.config;
      const range = target ? `~${target}` : min && max ? `${min}–${max}` : '';
      const outside = (min && words < min) || (max && words > max);
      return (
        <div key={q.id} className="cd-question cd-written">
          <p className="cd-prompt">{q.text}</p>
          <textarea
            value={a.written || ''}
            disabled={locked}
            onChange={(e) => update(q, { written: e.target.value }, true)}
            rows={10}
            aria-label={t('cd_writing_area')}
          />
          <p className={`cd-word-count${outside ? ' warn' : ''}`}>
            {words} {t('cd_words')}
            {range && ` · ${t('cd_word_target').replace('{range}', range)}`}
          </p>
        </div>
      );
    }

    if (q.question_type === 'INLINE_GAP_FILL') {
      const input = (
        <input
          className="cd-gap"
          value={a.text || ''}
          disabled={locked}
          onChange={(e) => update(q, { text: e.target.value }, true)}
          aria-label={`${t('cd_question')} ${num}`}
          autoComplete="off"
          spellCheck={false}
        />
      );
      const [before, after] = q.text.split(GAP_RE);
      return (
        <div key={q.id} className="cd-question cd-inline">
          <span className="cd-num">{num}</span>
          {after !== undefined ? (
            <p>{before}{input}{after}</p>
          ) : (
            <p>{q.text} {input}</p>
          )}
        </div>
      );
    }

    if (SELECT_TYPES.has(q.question_type)) {
      const taken = group.each_option_once
        ? new Set(siblings.filter((s) => s.id !== q.id).map((s) => answers[s.id]?.choice))
        : new Set<number | undefined>();
      return (
        <label key={q.id} className="cd-question cd-select">
          <span className="cd-num">{num}</span>
          <span className="cd-select-text">{q.text}</span>
          <select
            value={a.choice ?? ''}
            disabled={locked}
            onChange={(e) => update(q, { choice: e.target.value ? Number(e.target.value) : undefined, text: '' })}
          >
            <option value="">{t('cd_choose')}</option>
            {choices.map((c, i) => (
              <option key={c.id} value={c.id} disabled={taken.has(c.id)}>
                {LETTERS[i]}
              </option>
            ))}
          </select>
        </label>
      );
    }

    // MULTIPLE_CHOICE / TRUE_FALSE_NOT_GIVEN
    const tfng = q.question_type === 'TRUE_FALSE_NOT_GIVEN';
    return (
      <fieldset key={q.id} className="cd-question cd-choice">
        <legend>
          <span className="cd-num">{num}</span> {q.text}
        </legend>
        <div className={tfng ? 'cd-options inline' : 'cd-options'}>
          {choices.map((c, i) => (
            <label key={c.id} className={a.choice === c.id ? 'cd-option selected' : 'cd-option'}>
              <input
                type="radio"
                name={`q-${q.id}`}
                checked={a.choice === c.id}
                disabled={locked}
                onChange={() => update(q, { choice: c.id, text: '' })}
              />
              {!tfng && <b>{LETTERS[i]}</b>} {c.text}
            </label>
          ))}
        </div>
      </fieldset>
    );
  };

  const renderGroup = (group: CdGroup) => {
    const qs = questionsByGroup[group.id] || [];
    const shared = group.options_label && qs[0]?.choices.some((c) => c.text.length > 1) ? qs[0].choices : [];
    return (
      <section key={group.id} className="cd-group">
        {group.title && <h3>{group.title}</h3>}
        {group.instructions && <p className="cd-instructions">{group.instructions}</p>}
        {group.answer_rule && (
          <p className="cd-rule">
            {t('cd_answer_rule')}: <strong>{group.answer_rule}</strong>
          </p>
        )}
        {group.image_url && <img className="cd-image" src={group.image_url} alt={group.title || t('cd_picture')} />}
        {shared.length > 0 && (
          <div className="cd-shared-options">
            <p className="cd-options-label">{group.options_label}</p>
            <ol>
              {[...shared].sort((x, y) => x.position - y.position).map((c, i) => (
                <li key={c.id}><b>{LETTERS[i]}</b> {c.text}</li>
              ))}
            </ol>
          </div>
        )}
        <div className="cd-questions">{qs.map((q) => renderQuestion(q, group, qs))}</div>
      </section>
    );
  };

  const partPassages = [...new Set(part.groups.map((g) => g.passage_id).filter((id): id is number => id != null))]
    .map((id) => passages[id])
    .filter(Boolean);
  const nextSection = sections[sectionIdx + 1];

  /* -------------------------------------------------------------- layout */
  return (
    <div className="cd-exam">
      <header className="cd-header">
        <div className="cd-title">
          <strong>{attempt.test_title}</strong>
          {attempt.is_trial ? (
            <span className="cd-preview-badge">{t('cd_trial_badge')}</span>
          ) : (
            attempt.is_preview && <span className="cd-preview-badge">{t('cd_preview_badge')}</span>
          )}
        </div>
        <div className="cd-timers">
          {sectionLeft != null && (
            <span className={sectionLeft < 300 ? 'cd-timer warn' : 'cd-timer'}>
              {t('cd_section_time')}: {fmt(sectionLeft)}
            </span>
          )}
          <button type="button" className="btn primary sm" onClick={() => setConfirming(true)} disabled={submitting}>
            {t('cd_finish')}
          </button>
        </div>
      </header>

      <nav className="cd-section-tabs" aria-label={t('cd_sections')}>
        {sections.map((s, i) => {
          const qs = sectionQuestions(s).filter((q) => q.question_type !== 'SPEAKING_PROMPT');
          const done = qs.filter((q) => isAnswered(answers[q.id])).length;
          return (
            <button
              key={s.section_id}
              type="button"
              className={i === sectionIdx ? 'active' : ''}
              onClick={() => setSectionIdx(i)}
            >
              {s.name}
              {qs.length > 0 && <small> {done}/{qs.length}</small>}
            </button>
          );
        })}
      </nav>

      {saveError && <p className="cd-alert">{t('cd_save_error')}</p>}
      {submitError && <p className="cd-alert">{submitError}</p>}
      {locked && <p className="cd-alert">{t('cd_time_up')}</p>}

      <nav className="cd-part-tabs" aria-label={t('cd_parts')}>
        {section.parts.map((p, i) => (
          <button
            key={p.id}
            type="button"
            className={p.id === part.id ? 'active' : ''}
            onClick={() => setPartIdx((prev) => ({ ...prev, [section.section_id]: i }))}
          >
            {t('cd_part')} {p.number}
          </button>
        ))}
      </nav>

      <main className={partPassages.length ? 'cd-body with-passage' : 'cd-body'}>
        {partPassages.length > 0 && (
          <article className="cd-passage">
            {partPassages.map((p) => (
              <div key={p.id}>
                {p.title && <h2>{p.title}</h2>}
                <p>{p.content}</p>
              </div>
            ))}
          </article>
        )}
        <div className="cd-part">
          {part.title && <h2>{part.title}</h2>}
          {part.instructions && <p className="cd-instructions">{part.instructions}</p>}
          {section.code === 'LISTENING' &&
            (part.audio_url ? (
              <audio className="cd-audio" controls preload="none" src={part.audio_url} />
            ) : (
              <p className="cd-notice">{t('cd_audio_missing')}</p>
            ))}
          {section.code === 'SPEAKING' && <p className="cd-notice">{t('cd_speaking_note')}</p>}
          {part.groups.map(renderGroup)}
        </div>
      </main>

      <footer className="cd-footer">
        {nextSection && (
          <button type="button" className="btn" onClick={() => setSectionIdx(sectionIdx + 1)}>
            {t('cd_next_section')}: {nextSection.name}
          </button>
        )}
      </footer>

      {confirming && (
        <div className="cd-modal" role="dialog" aria-modal="true">
          <div className="card">
            <p>{t('cd_finish_confirm').replace('{n}', String(unanswered))}</p>
            <div className="error-boundary-actions">
              <button type="button" className="btn" onClick={() => setConfirming(false)} disabled={submitting}>
                {t('cd_cancel')}
              </button>
              <button type="button" className="btn primary" onClick={() => void submit()} disabled={submitting}>
                {submitting ? t('cd_submitting') : t('cd_finish_yes')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/** Speaking task: prompt, optional For/Against table and prep/answer timers. */
function SpeakingPrompt({ q }: { q: CdQuestion }) {
  const { t } = useLang();
  const [phase, setPhase] = useState<'idle' | 'prep' | 'speak' | 'done'>('idle');
  const [left, setLeft] = useState(0);
  const prep = q.config.prep_seconds || 0;
  const speak = q.config.answer_seconds || 0;

  useEffect(() => {
    if (phase !== 'prep' && phase !== 'speak') return;
    if (left <= 0) {
      if (phase === 'prep') {
        setPhase('speak');
        setLeft(speak);
      } else setPhase('done');
      return;
    }
    const id = window.setTimeout(() => setLeft((s) => s - 1), 1000);
    return () => window.clearTimeout(id);
  }, [phase, left, speak]);

  const start = () => {
    if (prep) {
      setPhase('prep');
      setLeft(prep);
    } else {
      setPhase('speak');
      setLeft(speak);
    }
  };

  return (
    <div className="cd-question cd-speaking">
      <p className="cd-prompt">
        <span className="cd-num">{q.config.number}</span> {q.text}
      </p>
      {(q.config.for || q.config.against) && (
        <div className="cd-for-against">
          <div>
            <b>{t('cd_for')}</b>
            <ul>{q.config.for?.map((x) => <li key={x}>{x}</li>)}</ul>
          </div>
          <div>
            <b>{t('cd_against')}</b>
            <ul>{q.config.against?.map((x) => <li key={x}>{x}</li>)}</ul>
          </div>
        </div>
      )}
      <div className="cd-speaking-timer">
        <span className="muted small">
          {prep ? `${t('cd_prep')}: ${fmt(prep)} · ` : ''}
          {t('cd_speak')}: {fmt(speak)}
        </span>
        {phase === 'idle' || phase === 'done' ? (
          <button type="button" className="btn sm" onClick={start}>
            {t('cd_start_timer')}
          </button>
        ) : (
          <strong>
            {phase === 'prep' ? t('cd_prep') : t('cd_speak')}: {fmt(left)}
          </strong>
        )}
      </div>
    </div>
  );
}
