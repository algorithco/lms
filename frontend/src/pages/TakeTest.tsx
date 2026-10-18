import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ChevronLeft,
  ChevronRight,
  Check,
  FileText,
  LayoutGrid,
  Keyboard,
} from 'lucide-react';
import { useLang } from '../i18n/LangContext';
import { Tests as TestsApi } from '../lib/api';
import {
  GapFillInput,
  MatchingInput,
  PassageCard,
  SectionNav,
  WrittenInput,
} from '../components/ExamQuestions';
import {
  clearDraft,
  formatClock,
  loadDraft,
  num,
  storeDraft,
  type DraftMap,
} from '../lib/testing';
import { ClockIcon } from '../components/icons';
import TiltCard from '../components/TiltCard';
import confetti from 'canvas-confetti';

interface Choice {
  id: number;
  text: string;
}

interface GapDef {
  position: number;
}

interface MatchingPromptDef {
  id: number;
  text: string;
  position: number;
}

interface MatchingOptionDef {
  id: number;
  text: string;
}

interface PassageDef {
  id: number;
  title: string;
  content: string;
  source?: string;
  order: number;
}

interface SectionDef {
  id: number;
  name: string;
  code: string;
  order: number;
  duration_minutes: number;
  weight: string;
}

interface SectionProgressDef {
  section_id: number;
  remaining_seconds: number | null;
  is_expired: boolean;
  completed: boolean;
}

type QuestionType =
  | 'single'
  | 'multiple'
  | 'text'
  | 'gap_fill'
  | 'matching'
  | 'written';

interface Question {
  id: number;
  text: string;
  passage: PassageDef | null;
  question_type: QuestionType;
  points: number;
  position: number;
  section_id: number | null;
  choices: Choice[];
  selected_choice_ids: number[];
  /** REST AttemptDetailSerializer currently omits text answers — drafts fill the gap. */
  text_answer?: string;
  gaps?: GapDef[];
  prompts?: MatchingPromptDef[];
  matching_options?: MatchingOptionDef[];
  written?: { min_words: number; max_words: number };
  gap_answers?: Record<string, string>;
  matching?: Record<string, number | null>;
  written_text?: string;
  written_word_count?: number;
}

interface AttemptDetail {
  id: number;
  test: number;
  test_title: string;
  status: string;
  remaining_seconds: number | null;
  questions: Question[];
  answered_count: number;
  sections?: SectionDef[];
  passages?: PassageDef[];
  section_progress?: SectionProgressDef[];
}

interface SubmitResult {
  attempt_id: number;
  total_questions: number;
  correct_answers: number;
  wrong_answers: number;
  unanswered: number;
  score: string | number;
  max_score: string | number;
  percentage: string | number;
  is_passed: boolean;
  time_taken_seconds: number;
  grading_status?: string;
  certificate_status?: string;
  scoring_version?: string;
  objective_score?: string | number;
  writing_score?: string | number;
  pending_written_count?: number;
}

interface AnswerEntry {
  choices: number[];
  text: string;
  gaps: Record<string, string>;
  matching: Record<string, number | null>;
  written: string;
}

type Answers = Record<number, AnswerEntry>;

const emptyEntry = (): AnswerEntry => ({
  choices: [],
  text: '',
  gaps: {},
  matching: {},
  written: '',
});

const TEXT_DEBOUNCE_MS = 400;

function qtypeLabel(qtype: string, t: (k: string) => string): string {
  if (qtype === 'single') return t('take_single');
  if (qtype === 'multiple') return t('take_multiple');
  if (qtype === 'gap_fill') return t('take_gap_fill');
  if (qtype === 'matching') return t('take_matching');
  if (qtype === 'written') return t('take_written');
  return t('take_text');
}

function entryHasContent(q: Question, a: AnswerEntry): boolean {
  if (q.question_type === 'gap_fill') return Object.keys(a.gaps).length > 0;
  if (q.question_type === 'matching') return Object.keys(a.matching).length > 0;
  if (q.question_type === 'written') return a.written.trim().length > 0;
  if (q.question_type === 'text') return a.text.trim().length > 0;
  return a.choices.length > 0;
}

function parseTwoPartAnswer(text: string): { a: string; b: string } {
  if (!text) return { a: '', b: '' };
  try {
    const obj = JSON.parse(text);
    if (obj && typeof obj === 'object') {
      return { a: String(obj.a || ''), b: String(obj.b || '') };
    }
  } catch {
    // plain string format
  }
  const match = text.match(/a\)\s*(.*?)(?:\s*;?\s*b\)\s*(.*)|$)/is);
  if (match) {
    const aVal = (match[1] || '').replace(/;\s*$/, '').trim();
    const bVal = (match[2] || '').trim();
    if (aVal || bVal || text.includes('a)')) {
      return { a: aVal, b: bVal };
    }
  }
  const parts = text.split(/[\n;]/);
  if (parts.length >= 2) {
    return {
      a: parts[0].trim(),
      b: parts.slice(1).join('; ').trim(),
    };
  }
  return { a: text.trim(), b: '' };
}

function formatTwoPartAnswer(valA: string, valB: string): string {
  const cleanA = valA.trim();
  const cleanB = valB.trim();
  if (!cleanA && !cleanB) return '';
  if (cleanA && cleanB) return `a) ${cleanA}; b) ${cleanB}`;
  if (cleanA) return `a) ${cleanA}`;
  return `b) ${cleanB}`;
}

export default function TakeTest() {
  const { attemptId = '' } = useParams();
  const navigate = useNavigate();
  const { t } = useLang();
  const [attempt, setAttempt] = useState<AttemptDetail | null>(null);
  const [answers, setAnswers] = useState<Answers>({});
  const [saved, setSaved] = useState<Record<number, boolean>>({});
  const [failed, setFailed] = useState<Record<number, string>>({});
  const [remaining, setRemaining] = useState<number | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [result, setResult] = useState<SubmitResult | null>(null);
  const [savingAll, setSavingAll] = useState(false);
  const [singleMode, setSingleMode] = useState(true);
  const [currentQIndex, setCurrentQIndex] = useState(0);
  const timers = useRef<Record<number, ReturnType<typeof setTimeout>>>({});
  const submittedRef = useRef(false);
  const [isMobile, setIsMobile] = useState<boolean>(
    typeof window !== 'undefined' ? window.innerWidth < 768 : false
  );

  useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const load = useCallback(async () => {
    setLoadError(null);
    try {
      const a = (await TestsApi.attempt(attemptId)) as unknown as AttemptDetail;
      setAttempt(a);
      setRemaining(a.remaining_seconds);
      const draft = loadDraft(attemptId);
      setAnswers((prev) => {
        if (Object.keys(prev).length > 0) return prev;
        const init: Answers = {};
        for (const q of a.questions ?? []) {
          const d: DraftMap[number] | undefined = draft[q.id];
          init[q.id] = {
            choices: d ? [...d.choices] : [...(q.selected_choice_ids ?? [])],
            // Server does not return text answers on the attempt endpoint,
            // so a local draft is the only resume source for text questions.
            text: d ? d.text : String(q.text_answer ?? ''),
            gaps: d?.gaps ?? { ...(q.gap_answers ?? {}) },
            matching: d?.matching ?? { ...(q.matching ?? {}) },
            written: d?.written ?? String(q.written_text ?? ''),
          };
        }
        return init;
      });
      setSaved((prev) => {
        if (Object.keys(prev).length > 0) return prev;
        const s: Record<number, boolean> = {};
        for (const q of a.questions ?? []) {
          s[q.id] =
            (q.selected_choice_ids ?? []).length > 0 ||
            Boolean(q.text_answer) ||
            Object.keys(q.gap_answers ?? {}).length > 0 ||
            Object.keys(q.matching ?? {}).length > 0 ||
            Boolean(q.written_text);
        }
        return s;
      });
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : t('err_retry_js'));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [attemptId]);

  useEffect(() => {
    load();
    return () => {
      for (const id of Object.values(timers.current)) clearTimeout(id);
      timers.current = {};
    };
  }, [load]);

  const persist = useCallback(
    (next: Answers) => {
      const draft: DraftMap = {};
      for (const [qid, a] of Object.entries(next)) {
        draft[Number(qid)] = {
          choices: a.choices,
          text: a.text,
          gaps: a.gaps,
          matching: a.matching,
          written: a.written,
          updatedAt: Date.now(),
        };
      }
      storeDraft(attemptId, draft);
    },
    [attemptId],
  );

  // Countdown — backend auto-timeouts on expiry (AttemptDetailView +
  // SaveAnswerService), so at zero we auto-submit once.
  useEffect(() => {
    if (remaining === null || remaining <= 0) return;
    const id = setInterval(() => setRemaining((r) => (r !== null ? r - 1 : r)), 1000);
    return () => clearInterval(id);
  }, [remaining]);

  const doSubmit = useCallback(
    async (auto = false) => {
      if (submittedRef.current || submitting) return;
      submittedRef.current = true;
      setSubmitting(true);
      setErr(null);
      try {
        // Flush unsaved answers first (best effort, incl. retries).
        for (const q of attempt?.questions ?? []) {
          const a = answers[q.id];
          if (!a) continue;
          const dirty = !saved[q.id] || failed[q.id];
          if (dirty && entryHasContent(q, a)) {
            await TestsApi.saveAnswer(attemptId, {
              question_id: q.id,
              choice_ids: a.choices,
              text_answer: a.text,
              gap_answers: a.gaps,
              matching: a.matching,
              written_text: a.written || undefined,
            }).catch(() => undefined);
          }
        }
        const out = (await TestsApi.submit(attemptId)) as unknown as {
          result?: SubmitResult;
        } & SubmitResult;
        const r: SubmitResult = (out.result ?? out) as SubmitResult;
        setResult(r);
        clearDraft(attemptId);
        if (r.is_passed) {
          try {
            confetti({
              particleCount: 80,
              spread: 70,
              origin: { y: 0.6 },
              colors: ['#10B981', '#34D399', '#F59E0B', '#FBBF24'],
            });
          } catch {
            /* ignore */
          }
        }
      } catch (e) {
        submittedRef.current = false;
        setErr(
          (e instanceof Error ? e.message : t('err_retry_js')) +
            (auto ? ` (${t('take_auto_submit')})` : ''),
        );
        setSubmitting(false);
      }
    },
    [attempt, answers, saved, failed, attemptId, submitting, t],
  );

  useEffect(() => {
    if (remaining === 0 && attempt && !result) {
      doSubmit(true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [remaining]);

  const save = useCallback(
    async (q: Question, a?: AnswerEntry) => {
      const cur = a ?? answers[q.id] ?? emptyEntry();
      // Empty answers cannot be saved for choice questions (backend requires
      // ≥1 choice); other types skip the round-trip when untouched.
      if (!entryHasContent(q, cur)) {
        setSaved((s) => ({ ...s, [q.id]: false }));
        return;
      }

      let lastErr: unknown = null;
      // 3 martagacha avtomatik qayta urinish (retry)
      for (let attemptNum = 1; attemptNum <= 3; attemptNum++) {
        try {
          const payload = {
            test_id: attempt?.test,
            question_id: q.id,
            choice_ids: cur.choices,
            selected_option_id: cur.choices.length === 1 ? cur.choices[0] : undefined,
            selected_choice_id: cur.choices.length === 1 ? cur.choices[0] : undefined,
            text_answer: cur.text,
            gap_answers: cur.gaps,
            matching: cur.matching,
            written_text: q.question_type === 'written' ? cur.written : undefined,
          };
          const res = (await TestsApi.saveAnswer(attemptId, payload)) as unknown as {
            remaining_seconds?: number | null;
          };
          setSaved((s) => ({ ...s, [q.id]: true }));
          setFailed((f) => {
            if (!(q.id in f)) return f;
            const next = { ...f };
            delete next[q.id];
            return next;
          });
          if (typeof res?.remaining_seconds === 'number') {
            setRemaining(res.remaining_seconds);
          }
          return; // Success!
        } catch (e) {
          lastErr = e;
          if (attemptNum < 3) {
            await new Promise((resolve) => setTimeout(resolve, attemptNum * 350));
          }
        }
      }

      setSaved((s) => ({ ...s, [q.id]: false }));
      setFailed((f) => ({
        ...f,
        [q.id]: lastErr instanceof Error ? lastErr.message : t('take_save_failed'),
      }));
    },
    [answers, attempt, attemptId, t],
  );

  const saveDebounced = useCallback(
    (q: Question, next: AnswerEntry) => {
      if (timers.current[q.id]) clearTimeout(timers.current[q.id]);
      timers.current[q.id] = setTimeout(() => {
        save(q, next);
      }, TEXT_DEBOUNCE_MS);
    },
    [save],
  );

  const pick = useCallback(
    (q: Question, choiceId: number) => {
      const cur = answers[q.id] ?? emptyEntry();
      const has = cur.choices.includes(choiceId);
      const chosen =
        q.question_type === 'multiple'
          ? has
            ? cur.choices.filter((c) => c !== choiceId)
            : [...cur.choices, choiceId]
          : [choiceId];
      const nextEntry: AnswerEntry = { ...cur, choices: chosen };
      setAnswers((prev) => {
        const next = { ...prev, [q.id]: nextEntry };
        persist(next);
        return next;
      });
      setSaved((s) => ({ ...s, [q.id]: false }));
      save(q, nextEntry);
    },
    [answers, persist, save],
  );

  // Fast CBT hotkeys: Arrow keys to navigate, A/B/C/D or 1/2/3/4 to pick choices
  useEffect(() => {
    if (!singleMode || !attempt?.questions?.length || submitting || confirmOpen || result) {
      return;
    }

    const handleKeyDown = (e: KeyboardEvent) => {
      const activeEl = document.activeElement as HTMLElement | null;
      const tag = activeEl?.tagName?.toLowerCase();
      if (tag === 'input' || tag === 'textarea' || activeEl?.isContentEditable) {
        return;
      }

      if (e.key === 'ArrowLeft') {
        e.preventDefault();
        setCurrentQIndex((idx) => Math.max(0, idx - 1));
      } else if (e.key === 'ArrowRight') {
        e.preventDefault();
        setCurrentQIndex((idx) => Math.min(attempt.questions.length - 1, idx + 1));
      } else if (['1', '2', '3', '4', '5', 'a', 'b', 'c', 'd', 'e', 'A', 'B', 'C', 'D', 'E'].includes(e.key)) {
        const q = attempt.questions[currentQIndex];
        if (q && (q.question_type === 'single' || q.question_type === 'multiple')) {
          let cIdx = -1;
          const k = e.key.toLowerCase();
          if (k === '1' || k === 'a') cIdx = 0;
          else if (k === '2' || k === 'b') cIdx = 1;
          else if (k === '3' || k === 'c') cIdx = 2;
          else if (k === '4' || k === 'd') cIdx = 3;
          else if (k === '5' || k === 'e') cIdx = 4;

          if (cIdx >= 0 && cIdx < q.choices.length) {
            e.preventDefault();
            pick(q, q.choices[cIdx].id);
          }
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [singleMode, attempt, currentQIndex, submitting, confirmOpen, result, pick]);

  const editText = (q: Question, text: string) => {
    const cur = answers[q.id] ?? emptyEntry();
    const nextEntry: AnswerEntry = { ...cur, choices: [], text };
    setAnswers((prev) => {
      const next = { ...prev, [q.id]: nextEntry };
      persist(next);
      return next;
    });
    setSaved((s) => ({ ...s, [q.id]: false }));
    // Debounced autosave for text (400ms)
    saveDebounced(q, nextEntry);
  };

  const editGap = (q: Question, position: number, value: string) => {
    const cur = answers[q.id] ?? emptyEntry();
    const gaps = { ...cur.gaps, [String(position)]: value };
    const nextEntry: AnswerEntry = { ...cur, gaps };
    setAnswers((prev) => {
      const next = { ...prev, [q.id]: nextEntry };
      persist(next);
      return next;
    });
    setSaved((s) => ({ ...s, [q.id]: false }));
    saveDebounced(q, nextEntry);
  };

  const editMatching = (q: Question, promptId: number, optionId: number | null) => {
    const cur = answers[q.id] ?? emptyEntry();
    const matching = { ...cur.matching, [String(promptId)]: optionId };
    const nextEntry: AnswerEntry = { ...cur, matching };
    setAnswers((prev) => {
      const next = { ...prev, [q.id]: nextEntry };
      persist(next);
      return next;
    });
    setSaved((s) => ({ ...s, [q.id]: false }));
    save(q, nextEntry);
  };

  const editWritten = (q: Question, written: string) => {
    const cur = answers[q.id] ?? emptyEntry();
    const nextEntry: AnswerEntry = { ...cur, written };
    setAnswers((prev) => {
      const next = { ...prev, [q.id]: nextEntry };
      persist(next);
      return next;
    });
    setSaved((s) => ({ ...s, [q.id]: false }));
    saveDebounced(q, nextEntry);
  };

  const retryFailed = async () => {
    setSavingAll(true);
    try {
      for (const q of attempt?.questions ?? []) {
        if (failed[q.id]) {
          const a = answers[q.id];
          if (a) await save(q, a);
        }
      }
    } finally {
      setSavingAll(false);
    }
  };

  if (loadError && !attempt) {
    return (
      <div>
        <h1>{t('take_title')}</h1>
        <p className="error">{loadError}</p>
        <div className="toolbar">
          <button className="btn primary" onClick={load}>
            {t('essay_error_retry')}
          </button>
          <Link className="btn ghost" to="/tests">
            {t('back')}
          </Link>
        </div>
      </div>
    );
  }
  if (!attempt) return <p className="muted">{t('loading')}</p>;

  const finished =
    attempt.status === 'completed' ||
    attempt.status === 'timeout' ||
    attempt.status === 'cancelled' ||
    attempt.status === 'pending_grading';

  const answeredCount = attempt.questions.filter((q) => {
    const a = answers[q.id];
    if (!a) return false;
    return entryHasContent(q, a);
  }).length;
  const unanswered = attempt.questions.length - answeredCount;
  const failedCount = Object.keys(failed).length;
  const timerClass =
    remaining === null ? '' : remaining <= 60 ? ' low' : '';

  const sections = attempt.sections ?? [];
  const sectionCounts: Record<number, { answered: number; total: number }> = {};
  for (const q of attempt.questions) {
    if (q.section_id == null) continue;
    const c = sectionCounts[q.section_id] ?? { answered: 0, total: 0 };
    c.total += 1;
    const a = answers[q.id];
    if (a && entryHasContent(q, a)) c.answered += 1;
    sectionCounts[q.section_id] = c;
  }

  // Group consecutive questions sharing one passage: the passage renders once.
  interface Block {
    passage: PassageDef | null;
    sectionId: number | null;
    questions: { q: Question; index: number }[];
  }
  const blocks: Block[] = [];
  attempt.questions.forEach((q, i) => {
    const passage = q.passage ?? null;
    const last = blocks[blocks.length - 1];
    if (last && last.passage && passage && last.passage.id === passage.id) {
      last.questions.push({ q, index: i });
    } else {
      blocks.push({ passage, sectionId: q.section_id, questions: [{ q, index: i }] });
    }
  });

  const safeQIndex = Math.min(
    Math.max(0, currentQIndex),
    Math.max(0, attempt.questions.length - 1),
  );
  const currentQuestion = attempt.questions[safeQIndex];

  const renderQuestionCard = (q: Question, i: number, isSingleView: boolean) => {
    const a = answers[q.id] ?? emptyEntry();
    const hasAnswer = entryHasContent(q, a);
    return (
      <TiltCard
        key={q.id}
        glare={false}
        maxTilt={isSingleView ? 2 : 3}
        scale={isSingleView ? 1 : 1.005}
        style={{ borderRadius: 'var(--radius)', marginBottom: isSingleView ? 0 : 12 }}
      >
        <div
          id={`question-${q.id}`}
          className={`card take-test-card${isSingleView ? ' single-view' : ''}`}
          style={{
            height: '100%',
            margin: 0,
            paddingBottom: isSingleView && isMobile ? '140px' : undefined,
          }}
        >
          {q.section_id != null && (
            <span id={`section-${q.section_id}`} style={{ scrollMarginTop: 80 }} />
          )}
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              marginBottom: 10,
              flexWrap: 'wrap',
              gap: 8,
            }}
          >
            <p className="muted small" style={{ margin: 0 }}>
              {t('th_questions')} {i + 1}/{attempt.questions.length} · {q.points}{' '}
              {t('points')} · {qtypeLabel(q.question_type, t)}
            </p>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              {saved[q.id] && !failed[q.id] && hasAnswer && (
                <span className="badge green" style={{ fontSize: '0.72rem' }}>
                  ✓ {t('essay_js_saved')}
                </span>
              )}
              {failed[q.id] && (
                <span className="badge rose" style={{ fontSize: '0.72rem' }}>
                  {t('essay_error') || 'Xatolik'}
                </span>
              )}
            </div>
          </div>

          <p style={{ fontWeight: 700, fontSize: isSingleView ? '1.12rem' : '1rem', lineHeight: 1.55, whiteSpace: 'pre-line' }}>
            {q.text}
          </p>

          {q.question_type === 'text' ? (
            (() => {
              const isTwoPart =
                (q.text.includes('a)') && q.text.includes('b)')) ||
                (q.position >= 40 && q.position <= 44);
              if (isTwoPart) {
                const twoPart = parseTwoPartAnswer(a.text);
                return (
                  <div style={{ display: 'grid', gap: 12, marginTop: 12 }}>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                      <label style={{ fontSize: '0.85rem', fontWeight: 700, color: '#f59e0b' }}>
                        {t('two_part_label_a')}
                      </label>
                      <input
                        type="text"
                        disabled={finished || submitting}
                        value={twoPart.a}
                        onChange={(e) => {
                          const next = formatTwoPartAnswer(e.target.value, twoPart.b);
                          editText(q, next);
                        }}
                        onBlur={() => {
                          if (timers.current[q.id]) clearTimeout(timers.current[q.id]);
                          const cur = answers[q.id] ?? emptyEntry();
                          if (cur.text.trim()) save(q, cur);
                        }}
                        placeholder={t('two_part_placeholder_a')}
                        style={{
                          padding: '10px 14px',
                          borderRadius: 8,
                          border: '1px solid var(--border)',
                          background: 'var(--card)',
                          color: 'var(--ink)',
                          fontSize: '0.95rem',
                        }}
                      />
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                      <label style={{ fontSize: '0.85rem', fontWeight: 700, color: '#f59e0b' }}>
                        {t('two_part_label_b')}
                      </label>
                      <input
                        type="text"
                        disabled={finished || submitting}
                        value={twoPart.b}
                        onChange={(e) => {
                          const next = formatTwoPartAnswer(twoPart.a, e.target.value);
                          editText(q, next);
                        }}
                        onBlur={() => {
                          if (timers.current[q.id]) clearTimeout(timers.current[q.id]);
                          const cur = answers[q.id] ?? emptyEntry();
                          if (cur.text.trim()) save(q, cur);
                        }}
                        placeholder={t('two_part_placeholder_b')}
                        style={{
                          padding: '10px 14px',
                          borderRadius: 8,
                          border: '1px solid var(--border)',
                          background: 'var(--card)',
                          color: 'var(--ink)',
                          fontSize: '0.95rem',
                        }}
                      />
                    </div>
                  </div>
                );
              }
              return (
                <textarea
                  rows={isSingleView ? 4 : 3}
                  value={a.text}
                  disabled={finished || submitting}
                  onChange={(e) => editText(q, e.target.value)}
                  onBlur={() => {
                    if (timers.current[q.id]) clearTimeout(timers.current[q.id]);
                    const cur = answers[q.id] ?? emptyEntry();
                    if (cur.text.trim()) save(q, cur);
                  }}
                  placeholder={t('take_text_ph')}
                  style={{ width: '100%', marginTop: 8 }}
                />
              );
            })()
          ) : q.question_type === 'gap_fill' ? (
            <GapFillInput
              text={q.text}
              gaps={q.gaps ?? []}
              values={a.gaps}
              disabled={finished || submitting}
              onChange={(pos, value) => editGap(q, pos, value)}
            />
          ) : q.question_type === 'matching' ? (
            <MatchingInput
              prompts={q.prompts ?? []}
              options={q.matching_options ?? []}
              values={a.matching}
              disabled={finished || submitting}
              onChange={(pid, oid) => editMatching(q, pid, oid)}
            />
          ) : q.question_type === 'written' ? (
            <WrittenInput
              value={a.written}
              minWords={q.written?.min_words ?? 0}
              maxWords={q.written?.max_words ?? 0}
              disabled={finished || submitting}
              placeholder={t('take_written_ph')}
              onChange={(value) => editWritten(q, value)}
              onBlur={() => {
                if (timers.current[q.id]) clearTimeout(timers.current[q.id]);
                const cur = answers[q.id] ?? emptyEntry();
                if (cur.written.trim()) save(q, cur);
              }}
            />
          ) : (
            <div style={{ marginTop: 10 }}>
              {/* Quick selector pill bar for matching or multi-choice items (Q33-Q35) */}
              {q.choices.length >= 4 && (
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 6,
                    marginBottom: 10,
                    flexWrap: 'wrap',
                  }}
                >
                  <span className="small muted" style={{ marginRight: 4, fontWeight: 600 }}>
                    {t('matching_pick_option')}:
                  </span>
                  {q.choices.map((c, ci) => {
                    const on = a.choices.includes(c.id);
                    const letter = String.fromCharCode(65 + ci);
                    return (
                      <button
                        key={`pill-${c.id}`}
                        type="button"
                        disabled={finished || submitting}
                        onClick={() => pick(q, c.id)}
                        className={`btn sm ${on ? 'primary' : 'ghost'}`}
                        style={{
                          minWidth: 36,
                          height: 32,
                          padding: 0,
                          fontWeight: 800,
                          borderRadius: 8,
                          borderColor: on ? '#f59e0b' : 'var(--border)',
                          background: on ? '#f59e0b' : 'rgba(255, 255, 255, 0.04)',
                          color: on ? '#111' : 'var(--ink)',
                          boxShadow: on ? '0 0 10px rgba(245, 158, 11, 0.3)' : undefined,
                        }}
                      >
                        {letter}
                      </button>
                    );
                  })}
                </div>
              )}

              <div
                className="take-test-choices"
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 10,
                  paddingBottom: isSingleView && isMobile ? '140px' : undefined,
                }}
              >
                {q.choices.map((c, ci) => {
                  const on = a.choices.includes(c.id);
                  const letter = String.fromCharCode(65 + ci);
                  return (
                    <button
                      key={c.id}
                      type="button"
                      disabled={finished || submitting}
                      className={`quiz-opt${on ? ' picked' : ''}`}
                      aria-pressed={on}
                      onClick={() => pick(q, c.id)}
                      style={{
                        minHeight: 48,
                        padding: '14px 16px',
                        display: 'flex',
                        alignItems: 'center',
                        gap: 12,
                        width: '100%',
                        textAlign: 'left',
                        transition: 'all 0.15s ease',
                        boxShadow: on ? '0 0 10px rgba(245, 158, 11, 0.2)' : undefined,
                      }}
                    >
                      <span
                        className="quiz-key"
                        style={on ? { background: '#f59e0b', color: '#111' } : {}}
                      >
                        {on ? '✓' : letter}
                      </span>
                      <span style={{ fontWeight: on ? 600 : 400, flex: 1, wordBreak: 'break-word' }}>
                        {c.text}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {failed[q.id] && (
            <div style={{ marginTop: 8 }}>
              <span className="error small">
                {failed[q.id]}{' '}
                <button className="btn sm ghost" onClick={() => a && save(q, a)}>
                  {t('essay_error_retry')}
                </button>
              </span>
            </div>
          )}

          {!isSingleView && entryHasContent(q, a) && (
            <div style={{ marginTop: 8 }} className="toolbar">
              <button
                className="btn sm ghost"
                disabled={finished || submitting}
                onClick={() => save(q, a)}
              >
                {saved[q.id] && !failed[q.id]
                  ? `✓ ${t('essay_js_saved')}`
                  : t('save')}
              </button>
            </div>
          )}

          {isSingleView && (
            <div className="single-q-actions">
              <button
                type="button"
                className="btn ghost nav-prev-btn"
                disabled={i === 0 || finished || submitting}
                onClick={() => {
                  setCurrentQIndex((prev) => Math.max(0, prev - 1));
                  window.scrollTo({ top: 0, behavior: 'smooth' });
                }}
                style={{ display: 'inline-flex', alignItems: 'center', gap: 6, minHeight: 44 }}
              >
                <ChevronLeft size={18} /> {t('take_prev_q') || 'Oldingi'}
              </button>

              <span className="muted small q-counter-text" style={{ fontWeight: 700, fontSize: '0.9rem' }}>
                {i + 1} / {attempt.questions.length}
              </span>

              {i < attempt.questions.length - 1 ? (
                <button
                  type="button"
                  className="btn primary nav-next-btn"
                  disabled={finished || submitting}
                  onClick={() => {
                    setCurrentQIndex((prev) => Math.min(attempt.questions.length - 1, prev + 1));
                    window.scrollTo({ top: 0, behavior: 'smooth' });
                  }}
                  style={{ display: 'inline-flex', alignItems: 'center', gap: 6, minHeight: 44 }}
                >
                  {t('take_next_q') || 'Keyingi'} <ChevronRight size={18} />
                </button>
              ) : (
                <button
                  type="button"
                  className="btn primary nav-finish-btn"
                  disabled={finished || submitting}
                  onClick={() => setConfirmOpen(true)}
                  style={{ display: 'inline-flex', alignItems: 'center', gap: 6, minHeight: 44, background: '#10b981', borderColor: '#10b981' }}
                >
                  <Check size={18} /> {t('take_finish')}
                </button>
              )}
            </div>
          )}
        </div>
      </TiltCard>
    );
  };

  return (
    <div className="take-test-page-container">
      <p className="muted small">
        <Link to="/tests">← {t('tests')}</Link>
      </p>
      <h1>{attempt.test_title}</h1>
      {err && <p className="error">{err}</p>}

      {finished && !result && (
        <div className="card">
          <p className="muted">{t('take_already_finished')}</p>
          <Link className="btn primary" to="/results">
            {t('my_results')}
          </Link>
        </div>
      )}

      {failedCount > 0 && (
        <p className="error">
          {t('take_save_failed')} ({failedCount}){' '}
          <button className="btn sm" onClick={retryFailed} disabled={savingAll}>
            {savingAll ? t('loading') : t('essay_error_retry')}
          </button>
        </p>
      )}

      {/* Sticky Top Bar with 180 min Timer & Progress */}
      <div className="take-test-sticky-top">
        <div className="toolbar" style={{ justifyContent: 'space-between', margin: 0 }}>
          {remaining !== null && (
            <span className={`timer${timerClass}`}>
              <ClockIcon size={16} className="ico" /> {formatClock(remaining)}
            </span>
          )}
          <span className="badge" style={{ fontWeight: 700 }}>
            {answeredCount}/{attempt.questions.length} ✓
          </span>
          {attempt.status === 'timeout' && (
            <span className="badge rose">{t('take_time_up')}</span>
          )}
        </div>
        <div className="progress" style={{ marginTop: 6, marginBottom: 0 }}>
          <div
            style={{
              width: `${(answeredCount / Math.max(attempt.questions.length, 1)) * 100}%`,
            }}
          />
        </div>
      </div>

      {/* Mode switch, hotkey hints, quick finish button */}
      <div className="test-top-bar">
        <div className="test-mode-switch" role="tablist">
          <button
            type="button"
            className={`test-mode-btn${singleMode ? ' active' : ''}`}
            onClick={() => setSingleMode(true)}
          >
            <FileText size={14} /> {t('take_single_mode') || '1 tadan ishlash'}
          </button>
          <button
            type="button"
            className={`test-mode-btn${!singleMode ? ' active' : ''}`}
            onClick={() => setSingleMode(false)}
          >
            <LayoutGrid size={14} /> {t('take_all_mode') || 'Barcha savollar'}
          </button>
        </div>

        {singleMode && (
          <div className="hotkey-hint-pill">
            <Keyboard size={13} style={{ color: '#f59e0b' }} />
            <span>
              <kbd className="hotkey-kbd">←</kbd> <kbd className="hotkey-kbd">→</kbd> {t('hotkey_questions')} ·{' '}
              <kbd className="hotkey-kbd">A</kbd> <kbd className="hotkey-kbd">B</kbd>{' '}
              <kbd className="hotkey-kbd">C</kbd> <kbd className="hotkey-kbd">D</kbd> {t('hotkey_select')}
            </span>
          </div>
        )}

        {!finished && !result && (
          <button
            type="button"
            className="btn sm"
            style={{ borderColor: 'rgba(239, 68, 68, 0.4)', color: '#f87171' }}
            disabled={submitting}
            onClick={() => setConfirmOpen(true)}
          >
            {submitting ? t('loading') : t('take_finish')}
          </button>
        )}
      </div>

      {/* Interactive Question Palette */}
      <div className="q-palette-container">
        <div className="q-palette-header">
          <span style={{ fontWeight: 700, color: 'var(--ink)' }}>
            {t('questions')}: {safeQIndex + 1} / {attempt.questions.length}
          </span>
          <span>
            <span style={{ color: '#86efac', fontWeight: 700 }}>✓ {answeredCount}</span>{' '}
            {t('take_answered_stat') || 'ta belgilandi'} ·{' '}
            <span style={{ color: '#fca5a5', fontWeight: 700 }}>{unanswered}</span>{' '}
            {t('take_left_stat') || 'ta qoldi'}
          </span>
        </div>
        <div className="q-palette-grid">
          {attempt.questions.map((q, i) => {
            const a = answers[q.id];
            const done = Boolean(a && entryHasContent(q, a));
            const isActive = singleMode && safeQIndex === i;
            return (
              <button
                type="button"
                key={q.id}
                onClick={() => {
                  setCurrentQIndex(i);
                  if (!singleMode) {
                    const el = document.getElementById(`question-${q.id}`);
                    el?.scrollIntoView({ behavior: 'smooth', block: 'start' });
                  }
                }}
                className={`q-palette-badge${isActive ? ' active' : ''}${done ? ' done' : ''}${failed[q.id] ? ' rose' : ''}`}
                title={`Savol ${i + 1}`}
                aria-current={isActive ? 'true' : undefined}
              >
                {i + 1}
              </button>
            );
          })}
        </div>
      </div>

      <SectionNav
        sections={sections}
        progress={attempt.section_progress ?? []}
        counts={sectionCounts}
        activeSectionId={singleMode ? currentQuestion?.section_id : null}
        onSelectSection={(sectionId) => {
          const idx = attempt.questions.findIndex((q) => q.section_id === sectionId);
          if (idx !== -1) {
            setCurrentQIndex(idx);
            if (!singleMode) {
              const el = document.getElementById(`section-${sectionId}`);
              el?.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
          }
        }}
      />

      {/* Questions Render: Single Question or All Blocks */}
      {singleMode && currentQuestion ? (
        <AnimatePresence mode="wait">
          <motion.div
            key={currentQuestion.id}
            initial={{ opacity: 0, x: 12 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -12 }}
            transition={{ duration: 0.15 }}
          >
            {currentQuestion.passage ? (
              <div className="single-q-split has-passage">
                <PassageCard passage={currentQuestion.passage} />
                <div>{renderQuestionCard(currentQuestion, safeQIndex, true)}</div>
              </div>
            ) : (
              <div>{renderQuestionCard(currentQuestion, safeQIndex, true)}</div>
            )}
          </motion.div>
        </AnimatePresence>
      ) : (
        <>
          {blocks.map((block, bi) => (
            <div key={bi}>
              {block.passage && <PassageCard passage={block.passage} />}
              {block.questions.map(({ q, index: i }) => renderQuestionCard(q, i, false))}
            </div>
          ))}
          {!finished && !result && (
            <button
              className="btn primary"
              disabled={submitting}
              onClick={() => setConfirmOpen(true)}
              style={{ marginTop: 16 }}
            >
              {submitting ? t('loading') : t('take_finish')}
            </button>
          )}
        </>
      )}

      {confirmOpen && !result && (
        <div className="card" role="dialog" aria-modal="true" style={{ marginTop: 16 }}>
          <h3>{t('take_confirm_title')}</h3>

          {attempt.questions.some(
            (q) => q.question_type === 'written' && (!answers[q.id]?.written || !answers[q.id].written.trim())
          ) && (
            <div
              style={{
                padding: '12px 16px',
                borderRadius: 10,
                background: 'rgba(239, 68, 68, 0.12)',
                border: '1px solid rgba(239, 68, 68, 0.4)',
                color: '#ef4444',
                marginTop: 10,
                marginBottom: 12,
              }}
            >
              <strong style={{ display: 'block', fontSize: '0.95rem', marginBottom: 4 }}>
                ⚠️ {t('essay_empty_warning_title')}
              </strong>
              <span style={{ fontSize: '0.86rem', lineHeight: 1.5, display: 'block' }}>
                {t('essay_empty_warning_body')}
              </span>
            </div>
          )}

          <p className="muted">
            {unanswered === 0
              ? t('take_confirm_all')
              : `${answeredCount}/${attempt.questions.length} · ${t('take_confirm_left')}: ${unanswered}`}
          </p>
          <div className="toolbar">
            {attempt.questions.map((q, i) => {
              const a = answers[q.id];
              const done = Boolean(a && entryHasContent(q, a));
              return (
                <span key={q.id} className={`badge${done ? ' green' : ' rose'}`}>
                  {i + 1}
                </span>
              );
            })}
          </div>
          <div className="toolbar" style={{ marginTop: 12 }}>
            <button className="btn ghost" onClick={() => setConfirmOpen(false)}>
              {t('cancel')}
            </button>
            <button
              className="btn primary"
              disabled={submitting}
              onClick={() => {
                setConfirmOpen(false);
                doSubmit(false);
              }}
            >
              {submitting ? t('loading') : t('confirm')}
            </button>
          </div>
        </div>
      )}

      {result && (
        <div className="card" style={{ marginTop: 16 }}>
          {result.grading_status === 'pending_grading' ? (
            <>
              <h2>{t('take_pending_title')}</h2>
              <p className="muted">{t('take_pending_msg')}</p>
              <p className="stat-value">{num(result.objective_score, 0)}</p>
              <p className="muted small">
                {t('take_objective_done')} · {t('take_writing_pending')}
              </p>
              <div className="toolbar" style={{ marginTop: 12 }}>
                <button
                  className="btn primary"
                  disabled={submitting}
                  onClick={async () => {
                    setSubmitting(true);
                    setErr(null);
                    try {
                      const out = (await TestsApi.finalize(attemptId)) as unknown as {
                        result?: SubmitResult;
                        status?: string;
                        detail?: string;
                      } & SubmitResult;
                      if (out && typeof out === 'object' && 'result' in out && out.result) {
                        setResult(out.result as SubmitResult);
                      } else {
                        // 202: writing still grading — keep pending state.
                        setErr(
                          (out as { detail?: string }).detail ?? t('take_pending_msg'),
                        );
                      }
                    } catch (e) {
                      setErr(e instanceof Error ? e.message : t('take_pending_msg'));
                    } finally {
                      setSubmitting(false);
                    }
                  }}
                >
                  {t('take_finalize')}
                </button>
                <button className="btn ghost" onClick={() => navigate('/results')}>
                  {t('take_view_results')}
                </button>
              </div>
            </>
          ) : result.certificate_status === 'rules_unverified' ? (
            <>
              <h2>{t('take_rules_unverified_title')}</h2>
              <p className="muted">{t('take_rules_unverified_msg')}</p>
              <p className="stat-value">{num(result.percentage, 0)}%</p>
              <p className="badge blue">{t('raw_score_not_official')}</p>
            </>
          ) : (
            <>
              <h2>{result.is_passed ? t('rd_passed_msg') : t('rd_failed_msg')}</h2>
              <p className="stat-value">{num(result.percentage, 0)}%</p>
            </>
          )}
          {result.grading_status !== 'pending_grading' && (
            <>
          <div className="toolbar">
            <span className="badge green">
              {t('rd_correct')}: {result.correct_answers}
            </span>
            <span className="badge rose">
              {t('rd_wrong')}: {result.wrong_answers}
            </span>
            <span className="badge">
              {t('rd_unanswered')}: {result.unanswered}
            </span>
            <span className="badge blue">
              {t('rd_time_spent')}: {formatClock(num(result.time_taken_seconds, 0))}
            </span>
          </div>
          <div className="toolbar" style={{ marginTop: 12 }}>
            <button className="btn primary" onClick={() => navigate('/results')}>
              {t('take_view_results')}
            </button>
            {result.is_passed &&
              result.certificate_status !== 'rules_unverified' &&
              result.certificate_status !== 'pending_writing' && (
                <button className="btn" onClick={() => navigate('/certificates')}>
                  {t('my_certificates')}
                </button>
              )}
          </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
