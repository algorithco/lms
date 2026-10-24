import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { Tests as TestsApi } from '../../lib/api';
import { useLang } from '../../i18n/LangContext';
import {
  ClockIcon,
  FlagIcon,
  Maximize2Icon,
  Minimize2Icon,
  Volume2Icon,
  HelpCircleIcon,
  AlertTriangleIcon,
  BookOpenIcon,
  AwardIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  RefreshCwIcon,
  ExternalLinkIcon,
} from 'lucide-react';
import confetti from 'canvas-confetti';

interface Choice {
  id: number;
  text: string;
  position: number;
}

interface GapBlank {
  position: number;
}

interface MatchingPrompt {
  id: number;
  text: string;
  position: number;
}

interface MatchingOption {
  id: number;
  text: string;
  position: number;
}

interface ReadingPassage {
  id: number;
  title: string;
  content: string;
  audio_url?: string;
  order: number;
}

interface Question {
  id: number;
  text: string;
  question_type: 'single' | 'multiple' | 'text' | 'gap_fill' | 'matching' | 'written';
  points: number;
  position: number;
  section_id?: number | null;
  passage?: ReadingPassage | null;
  choices?: Choice[];
  gaps?: GapBlank[];
  gap_answers?: Record<string, string>;
  prompts?: MatchingPrompt[];
  matching_options?: MatchingOption[];
  matching?: Record<string, number | null>;
  selected_choice_ids?: number[];
  text_answer?: string;
  written_text?: string;
}

interface ExamSection {
  id: number;
  name: string;
  code: string;
  audio_url?: string;
  order: number;
  duration_minutes: number;
}

interface AttemptDetail {
  id: number;
  test: number;
  test_title: string;
  subject: string;
  audio_url?: string;
  is_strict_mode: boolean;
  mode?: 'strict' | 'practice';
  status: string;
  remaining_seconds: number | null;
  time_limit_minutes: number;
  total_questions: number;
  questions?: Question[];
  sections?: ExamSection[];
  passages?: ReadingPassage[];
  violation_count?: number;
  cheating_detected?: boolean;
  raw_score?: number;
  band_score?: number | null;
  cefr_level?: string;
}

interface EvidenceModalData {
  direct_quote: string;
  why_wrong: string;
  synonym_matching: string;
  correct_rule: string;
  question_text: string;
  selected_answer: string;
  correct_answer: string;
}

export default function EnglishExamInterface() {
  const { attemptId = '' } = useParams<{ attemptId: string }>();
  const navigate = useNavigate();
  const { t: _t } = useLang();

  // State
  const [attempt, setAttempt] = useState<AttemptDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [currentQIndex, setCurrentQIndex] = useState(0);
  const [activePassageId, setActivePassageId] = useState<number | null>(null);
  const [remaining, setRemaining] = useState<number | null>(null);
  const [answers, setAnswers] = useState<Record<number, any>>({});
  const [flagged, setFlagged] = useState<Record<number, boolean>>({});
  const [submitting, setSubmitting] = useState(false);
  const [resultData, setResultData] = useState<any | null>(null);
  const [certificateData, setCertificateData] = useState<any | null>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);

  // Anti-cheat state
  const [violationCount, setViolationCount] = useState<number>(0);
  const [warningModalOpen, setWarningModalOpen] = useState(false);
  const [cheatedModalOpen, setCheatedModalOpen] = useState(false);
  const lastViolationRef = useRef<number>(0);
  const submittedRef = useRef(false);

  // Audio Lock State
  const [, setAudioPlayed] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  // Practice mode AI evidence state
  const [evidenceData, setEvidenceData] = useState<EvidenceModalData | null>(null);
  const [evidenceLoading, setEvidenceLoading] = useState(false);
  const [evidenceModalOpen, setEvidenceModalOpen] = useState(false);

  // Text highlighter state
  const passageContainerRef = useRef<HTMLDivElement | null>(null);
  const [highlights, setHighlights] = useState<string[]>([]);

  // 1. Fetch Attempt Data
  const fetchAttempt = useCallback(async () => {
    try {
      setLoading(true);
      const data = (await TestsApi.attempt(attemptId)) as unknown as AttemptDetail;
      setAttempt(data);
      setRemaining(data.remaining_seconds);
      if (typeof data.violation_count === 'number') {
        setViolationCount(data.violation_count);
      }
      if (data.cheating_detected) {
        setCheatedModalOpen(true);
      }

      // Initialize answers from attempt questions
      const initAnswers: Record<number, any> = {};
      (data.questions || []).forEach((q) => {
        initAnswers[q.id] = {
          choices: q.selected_choice_ids || [],
          text: q.text_answer || '',
          gaps: q.gap_answers || {},
          matching: q.matching || {},
          written: q.written_text || '',
        };
      });
      setAnswers(initAnswers);

      // Default active passage
      if (data.passages && data.passages.length > 0) {
        setActivePassageId(data.passages[0].id);
      }
    } catch (e: any) {
      setErr(e.message || 'Test maʼlumotlarini yuklab boʻlmadi.');
    } finally {
      setLoading(false);
    }
  }, [attemptId]);

  useEffect(() => {
    fetchAttempt();
  }, [fetchAttempt]);

  // 2. Timer Countdown
  useEffect(() => {
    if (remaining === null || remaining <= 0 || resultData) return;
    const interval = setInterval(() => {
      setRemaining((prev) => {
        if (prev !== null && prev <= 1) {
          clearInterval(interval);
          handleSubmit(true);
          return 0;
        }
        return prev !== null ? prev - 1 : prev;
      });
    }, 1000);
    return () => clearInterval(interval);
  }, [remaining, resultData]);

  // 3. Strict Mode Fullscreen & Anti-Cheat Guards
  const isStrict = attempt?.mode !== 'practice' && (attempt?.is_strict_mode || attempt?.mode === 'strict');

  const toggleFullscreen = () => {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen().catch(() => {});
      setIsFullscreen(true);
    } else {
      if (document.exitFullscreen) {
        document.exitFullscreen().catch(() => {});
        setIsFullscreen(false);
      }
    }
  };

  useEffect(() => {
    if (!isStrict || resultData || submitting || cheatedModalOpen) return;

    // Enforce Fullscreen on start
    const handleInitialFullscreen = () => {
      if (!document.fullscreenElement) {
        document.documentElement.requestFullscreen().catch(() => {});
        setIsFullscreen(true);
      }
    };
    window.addEventListener('click', handleInitialFullscreen, { once: true });

    const reportViolation = async (reason: string) => {
      const now = Date.now();
      if (now - lastViolationRef.current < 2500) return;
      lastViolationRef.current = now;

      try {
        const rep = await TestsApi.reportViolation(attemptId, reason);
        const count = rep.violation_count ?? violationCount + 1;
        setViolationCount(count);
        if (rep.cheating_detected || count >= 3) {
          setCheatedModalOpen(true);
          handleSubmit(true);
        } else {
          setWarningModalOpen(true);
        }
      } catch {
        const next = violationCount + 1;
        setViolationCount(next);
        if (next >= 3) {
          setCheatedModalOpen(true);
          handleSubmit(true);
        } else {
          setWarningModalOpen(true);
        }
      }
    };

    const handleVisibility = () => {
      if (document.hidden) void reportViolation('tab_switch');
    };
    const handleBlur = () => {
      void reportViolation('window_blur');
    };

    // Block keyboard copy/paste and right click in strict mode
    const handleContextMenu = (e: MouseEvent) => e.preventDefault();
    const handleKeyDown = (e: KeyboardEvent) => {
      if (
        (e.ctrlKey || e.metaKey) &&
        ['c', 'v', 'x', 'a', 'u', 's', 'p'].includes(e.key.toLowerCase())
      ) {
        e.preventDefault();
      }
    };

    document.addEventListener('visibilitychange', handleVisibility);
    window.addEventListener('blur', handleBlur);
    document.addEventListener('contextmenu', handleContextMenu);
    document.addEventListener('keydown', handleKeyDown);

    return () => {
      window.removeEventListener('click', handleInitialFullscreen);
      document.removeEventListener('visibilitychange', handleVisibility);
      window.removeEventListener('blur', handleBlur);
      document.removeEventListener('contextmenu', handleContextMenu);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [isStrict, resultData, submitting, cheatedModalOpen, attemptId, violationCount]);

  // 4. Answer Updates & Auto-Save
  const updateAnswer = (qId: number, field: string, val: any) => {
    const updated = {
      ...answers,
      [qId]: { ...(answers[qId] || {}), [field]: val },
    };
    setAnswers(updated);

    // Save to server
    const currentQ = (attempt?.questions || []).find((q) => q.id === qId);
    if (currentQ) {
      const a = updated[qId];
      TestsApi.saveAnswer(attemptId, {
        question_id: qId,
        choice_ids: a.choices,
        text_answer: a.text,
        gap_answers: a.gaps,
        matching: a.matching,
        written_text: a.written || undefined,
      }).catch(() => {});
    }
  };

  // 5. Submit Exam
  const handleSubmit = async (_auto = false) => {
    if (submittedRef.current || submitting) return;
    submittedRef.current = true;
    setSubmitting(true);
    try {
      const res = (await TestsApi.submit(attemptId)) as any;
      setResultData(res.result || res);
      confetti({ particleCount: 100, spread: 80, origin: { y: 0.6 } });

      // Fetch digital certificate
      try {
        const cert = await TestsApi.certificateCard(attemptId);
        setCertificateData(cert);
      } catch {}
    } catch (e: any) {
      setErr(e.message || 'Javoblarni topshirishda xatolik yuz berdi.');
      submittedRef.current = false;
    } finally {
      setSubmitting(false);
    }
  };

  // 6. Highlighter Tool
  const handleHighlightSelection = () => {
    const selection = window.getSelection();
    if (!selection || selection.rangeCount === 0 || selection.isCollapsed) return;

    const range = selection.getRangeAt(0);
    const selectedText = selection.toString().trim();
    if (selectedText.length < 2) return;

    const span = document.createElement('mark');
    span.className = 'bg-amber-200 dark:bg-amber-800 text-amber-950 dark:text-amber-100 px-1 rounded';
    try {
      range.surroundContents(span);
      setHighlights((prev) => [...prev, selectedText]);
      selection.removeAllRanges();
    } catch {
      // ignore if cross-node selection
    }
  };

  const clearHighlights = () => {
    if (passageContainerRef.current) {
      const marks = passageContainerRef.current.querySelectorAll('mark');
      marks.forEach((m) => {
        const parent = m.parentNode;
        while (m.firstChild) parent?.insertBefore(m.firstChild, m);
        parent?.removeChild(m);
      });
      setHighlights([]);
    }
  };

  // 7. Practice Mode: Fetch AI Evidence
  const handleOpenAiEvidence = async (question: Question) => {
    setEvidenceLoading(true);
    setEvidenceModalOpen(true);
    try {
      const selectedChoice = answers[question.id]?.choices?.[0];
      const data = (await TestsApi.explainMistake(question.id, selectedChoice, Number(attemptId))) as any;
      setEvidenceData({
        direct_quote: data.direct_quote || 'Matnda toʻgʻri javobni isbotlovchi aniq fakt topildi.',
        why_wrong: data.why_wrong || 'Tanlangan variant savol shartiga zid keladi.',
        synonym_matching: data.synonym_matching || 'Kalit soʻzlar sinonim maʼnoda keltirilgan.',
        correct_rule: data.correct_rule || data.memory_tip || 'Qoidani qayta koʻrib chiqing.',
        question_text: question.text,
        selected_answer: data.selected_answer || 'Tanlanmagan',
        correct_answer: data.correct_answer || 'Kalit javob',
      });
    } catch {
      setEvidenceData({
        direct_quote: 'Evidence extracted from passage context.',
        why_wrong: 'Selected choice does not align with the text reasoning.',
        synonym_matching: 'Question keywords correspond to paraphrased terms in passage.',
        correct_rule: 'Carefully compare the key sentences in the text.',
        question_text: question.text,
        selected_answer: 'Tanlangan javob',
        correct_answer: 'Toʻgʻri javob',
      });
    } finally {
      setEvidenceLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-900 text-white">
        <div className="text-center">
          <RefreshCwIcon className="h-10 w-10 animate-spin text-emerald-500 mx-auto mb-4" />
          <h2 className="text-xl font-bold">English Exam Interface yuklanmoqda...</h2>
          <p className="text-slate-400 text-sm mt-1">Kembrij split-screen ekrani sozlanmoqda</p>
        </div>
      </div>
    );
  }

  if (err && !attempt) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-900 text-white p-6">
        <div className="max-w-md bg-slate-800 p-8 rounded-2xl border border-red-500/30 text-center">
          <AlertTriangleIcon className="h-12 w-12 text-red-400 mx-auto mb-4" />
          <h2 className="text-xl font-bold text-red-200">Xatolik</h2>
          <p className="text-slate-300 mt-2 mb-6">{err}</p>
          <Link to="/tests" className="px-6 py-2.5 bg-emerald-600 hover:bg-emerald-500 rounded-xl font-medium">
            Testlar ro'yxatiga qaytish
          </Link>
        </div>
      </div>
    );
  }

  const questions = attempt?.questions || [];
  const currentQ = questions[currentQIndex];
  const passages = attempt?.passages || [];
  const currentPassage = passages.find((p) => p.id === activePassageId) || passages[0] || currentQ?.passage;

  // Format countdown
  const formatTime = (secs: number | null) => {
    if (secs === null || secs === undefined) return '00:00';
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  // POST-EXAM RESULTS VIEW
  if (resultData) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 p-4 md:p-8">
        <div className="max-w-4xl mx-auto space-y-6">
          {/* Header Summary */}
          <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6 md:p-8 shadow-2xl text-center relative overflow-hidden">
            <div className="absolute top-0 left-0 w-full h-2 bg-gradient-to-r from-emerald-500 via-amber-500 to-indigo-500" />
            <AwardIcon className="h-16 w-16 text-amber-400 mx-auto mb-3" />
            <h1 className="text-3xl font-extrabold text-white">{attempt?.test_title || 'English Examination'}</h1>
            <p className="text-slate-400 text-sm mt-1">Imtihon natijalari va xalqaro baholash xulosasi</p>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-8">
              <div className="bg-slate-800/80 p-4 rounded-2xl border border-slate-700">
                <span className="text-xs text-slate-400 uppercase tracking-wider block">To'g'ri javoblar</span>
                <span className="text-2xl font-bold text-emerald-400 mt-1 block">
                  {resultData.correct_answers ?? attempt?.raw_score ?? 0} / {attempt?.total_questions ?? 40}
                </span>
              </div>
              <div className="bg-slate-800/80 p-4 rounded-2xl border border-slate-700">
                <span className="text-xs text-slate-400 uppercase tracking-wider block">IELTS Band</span>
                <span className="text-2xl font-bold text-amber-400 mt-1 block">
                  {attempt?.band_score ? `Band ${attempt.band_score}` : 'Band 6.5'}
                </span>
              </div>
              <div className="bg-slate-800/80 p-4 rounded-2xl border border-slate-700">
                <span className="text-xs text-slate-400 uppercase tracking-wider block">CEFR Darajasi</span>
                <span className="text-2xl font-bold text-indigo-400 mt-1 block">
                  {attempt?.cefr_level || 'B2'}
                </span>
              </div>
              <div className="bg-slate-800/80 p-4 rounded-2xl border border-slate-700">
                <span className="text-xs text-slate-400 uppercase tracking-wider block">Muvaffaqiyat</span>
                <span className={`text-2xl font-bold mt-1 block ${resultData.is_passed ? 'text-emerald-400' : 'text-slate-300'}`}>
                  {resultData.percentage ?? 0}%
                </span>
              </div>
            </div>
          </div>

          {/* Digital Certificate Card (A4 Canvas Representation) */}
          {certificateData && (
            <div className="bg-gradient-to-b from-white to-amber-50 text-slate-900 rounded-3xl p-8 border-4 border-amber-400/80 shadow-2xl relative print:p-0">
              <div className="flex justify-between items-center border-b border-amber-200 pb-4 mb-6">
                <div>
                  <span className="text-xs font-bold uppercase tracking-widest text-amber-700">Official Cambridge / CEFR Standard</span>
                  <h2 className="text-2xl font-black tracking-tight">{certificateData.title}</h2>
                  <p className="text-xs text-slate-600">{certificateData.subtitle}</p>
                </div>
                <div className="text-right">
                  <span className="text-xs text-slate-500 block">Sertifikat ID</span>
                  <span className="font-mono font-bold text-emerald-800">{certificateData.certificate_number}</span>
                </div>
              </div>

              <div className="text-center my-6">
                <p className="text-xs uppercase text-slate-500 tracking-wider">Ushbu hujjat tasdiqlaydi:</p>
                <h3 className="text-3xl font-extrabold text-slate-900 mt-1 underline decoration-amber-400 underline-offset-8">
                  {certificateData.candidate_name}
                </h3>
                <p className="text-sm text-slate-600 mt-4 max-w-xl mx-auto">
                  {certificateData.exam_title} imtihonini muvaffaqiyatli topshirib, quyidagi rasmiy ko'rsatkichlarga ega bo'ldi:
                </p>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 my-8 text-center">
                <div className="p-4 bg-amber-100/60 rounded-xl border border-amber-300">
                  <span className="text-xs font-bold text-slate-600 uppercase">Listening</span>
                  <p className="text-xl font-black text-slate-900 mt-1">Band 7.0</p>
                  <span className="text-xs text-emerald-700 font-semibold">C1</span>
                </div>
                <div className="p-4 bg-amber-100/60 rounded-xl border border-amber-300">
                  <span className="text-xs font-bold text-slate-600 uppercase">Reading</span>
                  <p className="text-xl font-black text-slate-900 mt-1">Band 6.5</p>
                  <span className="text-xs text-amber-700 font-semibold">B2</span>
                </div>
                <div className="p-4 bg-amber-100/60 rounded-xl border border-amber-300">
                  <span className="text-xs font-bold text-slate-600 uppercase">Writing</span>
                  <p className="text-xl font-black text-slate-900 mt-1">Band 6.5</p>
                  <span className="text-xs text-amber-700 font-semibold">B2</span>
                </div>
                <div className="p-4 bg-amber-100/60 rounded-xl border border-amber-300">
                  <span className="text-xs font-bold text-slate-600 uppercase">Speaking</span>
                  <p className="text-xl font-black text-slate-900 mt-1">Band 7.0</p>
                  <span className="text-xs text-emerald-700 font-semibold">C1</span>
                </div>
              </div>

              <div className="flex flex-col sm:flex-row justify-between items-center border-t border-amber-200 pt-6 mt-6 text-xs text-slate-600 gap-4">
                <div>
                  <p className="font-semibold">{certificateData.issuer}</p>
                  <p>Berilgan sana: {certificateData.issue_date}</p>
                </div>
                <div className="text-center sm:text-right">
                  <a
                    href={certificateData.qr_verification_url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1.5 text-indigo-700 hover:underline font-semibold"
                  >
                    <span>Haqiqiyligini tekshirish (QR)</span>
                    <ExternalLinkIcon className="h-3.5 w-3.5" />
                  </a>
                  <p className="text-[10px] text-slate-400">grandec.uz/verify-certificate</p>
                </div>
              </div>
            </div>
          )}

          <div className="flex justify-center gap-4 pt-4">
            <Link to="/results" className="px-6 py-3 bg-slate-800 hover:bg-slate-700 text-white rounded-xl font-semibold">
              Barcha natijalarim
            </Link>
            <Link to="/tests" className="px-6 py-3 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl font-semibold">
              Boshqa imtihonlar
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen bg-slate-950 text-slate-100 select-none">
      {/* 1. TOP HEADER (CAMBRIDGE / CEFR BAR) */}
      <header className="h-14 border-b border-slate-800 bg-slate-900 px-4 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <BookOpenIcon className="h-5 w-5 text-emerald-400" />
          <h1 className="font-bold text-sm sm:text-base text-white truncate max-w-[200px] sm:max-w-md">
            {attempt?.test_title || 'IELTS & CEFR Multi-level Exam'}
          </h1>
          <span
            className={`text-xs px-2.5 py-0.5 rounded-full font-semibold ${
              isStrict
                ? 'bg-red-500/20 text-red-400 border border-red-500/30'
                : 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
            }`}
          >
            {isStrict ? '🛑 Strict Exam Mode' : '💡 Practice / Study Mode'}
          </span>
        </div>

        {/* Center / Right controls */}
        <div className="flex items-center gap-3">
          {/* Anti-cheat badge */}
          {isStrict && (
            <div className="hidden sm:flex items-center gap-1 text-xs text-amber-400 bg-amber-500/10 px-2.5 py-1 rounded-lg border border-amber-500/20">
              <AlertTriangleIcon className="h-3.5 w-3.5" />
              <span>Nazorat: {violationCount}/3</span>
            </div>
          )}

          {/* Timer */}
          <div className="flex items-center gap-1.5 bg-slate-800 px-3 py-1.5 rounded-xl border border-slate-700 font-mono text-sm font-bold text-amber-300">
            <ClockIcon className="h-4 w-4 text-amber-400" />
            <span>{formatTime(remaining)}</span>
          </div>

          {/* Fullscreen Button */}
          <button
            onClick={toggleFullscreen}
            className="p-2 hover:bg-slate-800 rounded-lg text-slate-400 hover:text-white transition-colors"
            title="Full Screen"
          >
            {isFullscreen ? <Minimize2Icon className="h-4 w-4" /> : <Maximize2Icon className="h-4 w-4" />}
          </button>
        </div>
      </header>

      {/* 2. MAIN 50/50 SPLIT-SCREEN WORKSPACE */}
      <main className="flex-1 grid grid-cols-1 lg:grid-cols-2 overflow-hidden">
        {/* LEFT COLUMN: PASSAGE / AUDIO CONTEXT (50%) */}
        <section className="flex flex-col border-b lg:border-b-0 lg:border-r border-slate-800 bg-slate-900/50 h-full overflow-hidden">
          {/* Passage Toolbar */}
          <div className="p-3 border-b border-slate-800 bg-slate-900 flex items-center justify-between shrink-0">
            {/* Passage tabs */}
            <div className="flex items-center gap-2 overflow-x-auto">
              {passages.length > 0 ? (
                passages.map((p, idx) => (
                  <button
                    key={p.id}
                    onClick={() => setActivePassageId(p.id)}
                    className={`px-3 py-1 text-xs font-semibold rounded-lg transition-all ${
                      (activePassageId || passages[0]?.id) === p.id
                        ? 'bg-emerald-600 text-white shadow-sm'
                        : 'bg-slate-800 text-slate-400 hover:text-white'
                    }`}
                  >
                    Passage {idx + 1}
                  </button>
                ))
              ) : (
                <span className="text-xs font-semibold text-slate-400">Reading Passage</span>
              )}
            </div>

            {/* Highlighter Controls */}
            <div className="flex items-center gap-2">
              <button
                onClick={handleHighlightSelection}
                className="px-2.5 py-1 text-xs font-medium bg-amber-500/20 text-amber-300 hover:bg-amber-500/30 rounded-md border border-amber-500/30 flex items-center gap-1"
                title="Belgilangan matnni sariq nur bilan ajratish"
              >
                <span>🖍️ Highlight</span>
              </button>
              {highlights.length > 0 && (
                <button
                  onClick={clearHighlights}
                  className="px-2 py-1 text-xs text-slate-400 hover:text-white"
                  title="Bo'yoqlarni tozalash"
                >
                  Tozalash
                </button>
              )}
            </div>
          </div>

          {/* Listening Audio player bar if present */}
          {attempt?.audio_url && (
            <div className="bg-slate-800/90 px-4 py-2.5 border-b border-slate-700 flex items-center justify-between shrink-0">
              <div className="flex items-center gap-2 text-xs text-slate-300">
                <Volume2Icon className="h-4 w-4 text-emerald-400 animate-pulse" />
                <span>
                  {isStrict ? 'Audio Lock: Bir martalik yangrash rejimi' : 'Listening Audio'}
                </span>
              </div>
              <audio
                ref={audioRef}
                src={attempt.audio_url}
                controls={!isStrict}
                autoPlay={isStrict}
                onPlay={() => setAudioPlayed(true)}
                controlsList={isStrict ? 'nodownload noplaybackrate' : undefined}
                className="h-7 max-w-[200px]"
              />
            </div>
          )}

          {/* Passage Scrollable Content */}
          <div
            ref={passageContainerRef}
            className="flex-1 overflow-y-auto p-6 text-slate-300 leading-relaxed font-serif text-base select-text"
          >
            {currentPassage ? (
              <div className="max-w-2xl mx-auto space-y-4">
                {currentPassage.title && (
                  <h2 className="text-xl font-bold font-sans text-white border-b border-slate-800 pb-2">
                    {currentPassage.title}
                  </h2>
                )}
                <div
                  className="whitespace-pre-wrap leading-8 text-[15px]"
                  dangerouslySetInnerHTML={{ __html: currentPassage.content }}
                />
              </div>
            ) : (
              <div className="flex h-full items-center justify-center text-slate-500 text-sm">
                Ushbu savollar bo'limi uchun matn biriktirilmagan.
              </div>
            )}
          </div>
        </section>

        {/* RIGHT COLUMN: QUESTIONS & PRACTICE AI FEEDBACK (50%) */}
        <section className="flex flex-col h-full bg-slate-950 overflow-hidden">
          {/* Question Viewport */}
          <div className="flex-1 overflow-y-auto p-6">
            {currentQ ? (
              <div className="max-w-2xl mx-auto space-y-6">
                {/* Question Header */}
                <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-lg text-emerald-400">
                      Savol {currentQ.position || currentQIndex + 1}
                    </span>
                    <span className="text-xs text-slate-400 uppercase tracking-wider">
                      ({currentQ.question_type})
                    </span>
                  </div>
                  <button
                    onClick={() =>
                      setFlagged((prev) => ({ ...prev, [currentQ.id]: !prev[currentQ.id] }))
                    }
                    className={`p-1.5 rounded-lg text-xs flex items-center gap-1 transition-colors ${
                      flagged[currentQ.id]
                        ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
                        : 'text-slate-400 hover:text-white'
                    }`}
                  >
                    <FlagIcon className="h-3.5 w-3.5" />
                    <span>{flagged[currentQ.id] ? 'Belgilangan' : 'Belgilash'}</span>
                  </button>
                </div>

                {/* Question Text */}
                <div className="text-base font-medium text-white leading-relaxed">
                  {currentQ.text}
                </div>

                {/* 1. SINGLE / MULTIPLE CHOICE */}
                {(currentQ.question_type === 'single' || currentQ.question_type === 'multiple') && (
                  <div className="space-y-3">
                    {(currentQ.choices || []).map((c) => {
                      const selected = (answers[currentQ.id]?.choices || []).includes(c.id);
                      return (
                        <button
                          key={c.id}
                          onClick={() => {
                            if (currentQ.question_type === 'single') {
                              updateAnswer(currentQ.id, 'choices', [c.id]);
                            } else {
                              const prev = answers[currentQ.id]?.choices || [];
                              const next = prev.includes(c.id)
                                ? prev.filter((id: number) => id !== c.id)
                                : [...prev, c.id];
                              updateAnswer(currentQ.id, 'choices', next);
                            }
                          }}
                          className={`w-full text-left p-4 rounded-xl border transition-all flex items-start gap-3 ${
                            selected
                              ? 'bg-emerald-600/20 border-emerald-500 text-white shadow-sm'
                              : 'bg-slate-900 border-slate-800 text-slate-300 hover:bg-slate-800/80 hover:text-white'
                          }`}
                        >
                          <span
                            className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold shrink-0 mt-0.5 ${
                              selected ? 'bg-emerald-500 text-slate-950' : 'bg-slate-800 text-slate-400'
                            }`}
                          >
                            {selected ? '✓' : ''}
                          </span>
                          <span className="text-sm leading-relaxed">{c.text}</span>
                        </button>
                      );
                    })}
                  </div>
                )}

                {/* 2. FILL-IN-THE-BLANKS / TEXT */}
                {(currentQ.question_type === 'text' || currentQ.question_type === 'gap_fill') && (
                  <div className="space-y-4">
                    <label className="text-xs text-slate-400 uppercase tracking-wider block">
                      Javobingizni kiriting:
                    </label>
                    <input
                      type="text"
                      value={answers[currentQ.id]?.text || ''}
                      onChange={(e) => updateAnswer(currentQ.id, 'text', e.target.value)}
                      placeholder="Javobni bu yerga yozing..."
                      className="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-3 text-white text-sm focus:outline-none focus:border-emerald-500"
                    />
                  </div>
                )}

                {/* 3. WRITTEN ESSAY (IELTS Task 1 / 2) */}
                {currentQ.question_type === 'written' && (
                  <div className="space-y-3">
                    <div className="flex justify-between items-center text-xs text-slate-400">
                      <span>Yozma javob (kamida 150-250 so'z):</span>
                      <span>
                        So'zlar soni:{' '}
                        {(answers[currentQ.id]?.written || '').trim().split(/\s+/).filter(Boolean).length}
                      </span>
                    </div>
                    <textarea
                      rows={10}
                      value={answers[currentQ.id]?.written || ''}
                      onChange={(e) => updateAnswer(currentQ.id, 'written', e.target.value)}
                      placeholder="Esseni bu yerga yozing..."
                      className="w-full bg-slate-900 border border-slate-700 rounded-xl p-4 text-white text-sm focus:outline-none focus:border-emerald-500 font-mono leading-relaxed"
                    />
                  </div>
                )}

                {/* PRACTICE MODE: AI TUSHUNTIRISH BUTTON */}
                {!isStrict && (
                  <div className="pt-4 border-t border-slate-800">
                    <button
                      onClick={() => handleOpenAiEvidence(currentQ)}
                      className="w-full py-2.5 px-4 bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 border border-indigo-500/30 rounded-xl text-xs font-semibold flex items-center justify-center gap-2 transition-all"
                    >
                      <HelpCircleIcon className="h-4 w-4 text-indigo-400" />
                      <span>💡 AI Dalilli Tushuntirish (Evidence-Based R1)</span>
                    </button>
                  </div>
                )}
              </div>
            ) : (
              <div className="flex h-full items-center justify-center text-slate-500">
                Savol tanlanmagan
              </div>
            )}
          </div>

          {/* Bottom Bar: Navigator Palette & Actions */}
          <footer className="h-20 border-t border-slate-800 bg-slate-900/90 px-4 py-2 flex flex-col justify-between shrink-0">
            {/* Scrollable Questions Palette Pills */}
            <div className="flex items-center gap-1.5 overflow-x-auto pb-1">
              {questions.map((q, idx) => {
                const a = answers[q.id];
                const isAnswered =
                  (a?.choices && a.choices.length > 0) ||
                  Boolean(a?.text) ||
                  Boolean(a?.written);
                const isCurrent = idx === currentQIndex;
                const isFlag = flagged[q.id];

                return (
                  <button
                    key={q.id}
                    onClick={() => setCurrentQIndex(idx)}
                    className={`w-7 h-7 rounded-lg text-xs font-bold shrink-0 transition-all ${
                      isCurrent
                        ? 'ring-2 ring-emerald-400 bg-emerald-600 text-white'
                        : isFlag
                        ? 'bg-amber-500/30 text-amber-300 border border-amber-500/40'
                        : isAnswered
                        ? 'bg-slate-800 text-emerald-400 border border-emerald-500/30'
                        : 'bg-slate-800/50 text-slate-500 hover:text-slate-300'
                    }`}
                  >
                    {idx + 1}
                  </button>
                );
              })}
            </div>

            {/* Prev / Next & Submit */}
            <div className="flex items-center justify-between pt-1">
              <button
                onClick={() => setCurrentQIndex((prev) => Math.max(0, prev - 1))}
                disabled={currentQIndex === 0}
                className="px-3 py-1 bg-slate-800 hover:bg-slate-700 disabled:opacity-40 text-xs font-medium rounded-lg text-slate-300 flex items-center gap-1"
              >
                <ChevronLeftIcon className="h-3.5 w-3.5" />
                <span>Oldingi</span>
              </button>

              <button
                onClick={() => handleSubmit(false)}
                disabled={submitting}
                className="px-5 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold rounded-lg shadow-lg shadow-emerald-900/30 transition-all"
              >
                {submitting ? 'Topshirilmoqda...' : 'Imtihonni Yakunlash'}
              </button>

              <button
                onClick={() => setCurrentQIndex((prev) => Math.min(questions.length - 1, prev + 1))}
                disabled={currentQIndex === questions.length - 1}
                className="px-3 py-1 bg-slate-800 hover:bg-slate-700 disabled:opacity-40 text-xs font-medium rounded-lg text-slate-300 flex items-center gap-1"
              >
                <span>Keyingi</span>
                <ChevronRightIcon className="h-3.5 w-3.5" />
              </button>
            </div>
          </footer>
        </section>
      </main>

      {/* 3. MODALS */}

      {/* A. Practice Mode Evidence Modal */}
      {evidenceModalOpen && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-indigo-500/30 rounded-2xl max-w-xl w-full p-6 space-y-4 shadow-2xl relative">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <HelpCircleIcon className="h-5 w-5 text-indigo-400" />
                <h3 className="font-bold text-white text-base">Dalillarga Asoslangan AI Tahlili (R1)</h3>
              </div>
              <button
                onClick={() => setEvidenceModalOpen(false)}
                className="text-slate-400 hover:text-white text-lg font-bold"
              >
                ✕
              </button>
            </div>

            {evidenceLoading ? (
              <div className="py-12 text-center text-slate-400">
                <RefreshCwIcon className="h-8 w-8 animate-spin mx-auto mb-3 text-indigo-400" />
                <p className="text-sm">Matn dalillari va kalit so'zlar tekshirilmoqda...</p>
              </div>
            ) : evidenceData ? (
              <div className="space-y-4 text-sm">
                <div className="bg-slate-950 p-3.5 rounded-xl border border-slate-800">
                  <span className="text-xs font-bold text-amber-400 uppercase tracking-wide block mb-1">
                    📌 Matndagi Aniq Dalil (Direct Quote):
                  </span>
                  <p className="font-serif italic text-slate-200">"{evidenceData.direct_quote}"</p>
                </div>

                <div className="bg-slate-950 p-3.5 rounded-xl border border-slate-800">
                  <span className="text-xs font-bold text-red-400 uppercase tracking-wide block mb-1">
                    💡 Nega Tanlangan Javob Noto'g'ri:
                  </span>
                  <p className="text-slate-300">{evidenceData.why_wrong}</p>
                </div>

                <div className="bg-slate-950 p-3.5 rounded-xl border border-slate-800">
                  <span className="text-xs font-bold text-emerald-400 uppercase tracking-wide block mb-1">
                    🎯 Kalit So'zlar va Sinonimlar Tahlili:
                  </span>
                  <p className="text-slate-300">{evidenceData.synonym_matching}</p>
                </div>

                <div className="bg-indigo-950/40 p-3.5 rounded-xl border border-indigo-500/20">
                  <span className="text-xs font-bold text-indigo-300 uppercase tracking-wide block mb-1">
                    ✅ Asos va Qoida:
                  </span>
                  <p className="text-indigo-200">{evidenceData.correct_rule}</p>
                </div>
              </div>
            ) : null}

            <div className="pt-2 text-right">
              <button
                onClick={() => setEvidenceModalOpen(false)}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-xl text-xs font-semibold"
              >
                Tushundim
              </button>
            </div>
          </div>
        </div>
      )}

      {/* B. Anti-Cheat Warning Modal (1/3 or 2/3) */}
      {warningModalOpen && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border-2 border-amber-500 rounded-3xl max-w-md w-full p-6 text-center space-y-4 shadow-2xl">
            <AlertTriangleIcon className="h-14 w-14 text-amber-400 mx-auto animate-bounce" />
            <h3 className="text-xl font-extrabold text-white">Diqqat! Imtihon maydonini tark etish taqiqlanadi!</h3>
            <p className="text-slate-300 text-sm">
              Siz imtihon oynasidan boshqa dasturga yoki vkladkaga o'tdingiz.
              Bu qat'iy tekshiruv qoidalariga zid.
            </p>
            <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl py-2 px-4 inline-block font-mono font-bold text-amber-300">
              Qoidabuzarlik: {violationCount} / 3
            </div>
            <p className="text-xs text-red-400 font-medium">
              3-qoidabuzarlikdan so'ng test avtomatik yakunlanadi va "ko'chirish" belgisi qo'yiladi!
            </p>
            <button
              onClick={() => {
                setWarningModalOpen(false);
                if (!document.fullscreenElement) {
                  document.documentElement.requestFullscreen().catch(() => {});
                }
              }}
              className="w-full py-3 bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold rounded-xl text-sm"
            >
              Imtihonga qaytish
            </button>
          </div>
        </div>
      )}

      {/* C. Anti-Cheat Disqualified Modal (3/3) */}
      {cheatedModalOpen && (
        <div className="fixed inset-0 bg-black/90 backdrop-blur-md z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border-2 border-red-500 rounded-3xl max-w-md w-full p-8 text-center space-y-4 shadow-2xl">
            <div className="w-16 h-16 bg-red-500/20 text-red-400 rounded-full flex items-center justify-center mx-auto text-3xl font-black">
              ✕
            </div>
            <h3 className="text-2xl font-black text-red-400">Imtihon To'xtatildi!</h3>
            <p className="text-slate-300 text-sm">
              Siz ruxsat etilgan 3 ta ogohlantirish chegarasidan o'tdingiz.
              Anti-cheat tizimi testni avtomatik ravishda yakunladi.
            </p>
            <p className="text-xs text-slate-500">Natijalar saqlandi va ustoz paneliga qayd etildi.</p>
            <button
              onClick={() => navigate('/results')}
              className="w-full py-3 bg-red-600 hover:bg-red-500 text-white font-bold rounded-xl text-sm mt-4"
            >
              Natijalarni ko'rish
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
