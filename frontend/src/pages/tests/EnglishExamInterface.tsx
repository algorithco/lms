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
  VolumeXIcon,
  HelpCircleIcon,
  AlertTriangleIcon,
  BookOpenIcon,
  AwardIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  RefreshCwIcon,
  ExternalLinkIcon,
  LogOutIcon,
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

  // Kiosk font size toggle (Standard | Large)
  const [fontSize, setFontSize] = useState<'standard' | 'large'>('standard');

  // Mobile tab toggle (passage vs questions)
  const [mobileTab, setMobileTab] = useState<'passage' | 'questions'>('passage');
  // Exit confirmation modal
  const [exitModalOpen, setExitModalOpen] = useState(false);

  const handleConfirmExit = useCallback(() => {
    if (document.fullscreenElement && document.exitFullscreen) {
      document.exitFullscreen().catch(() => {});
    }
    navigate('/tests');
  }, [navigate]);

  // Finish confirmation modal
  const [confirmSubmitOpen, setConfirmSubmitOpen] = useState(false);

  // Anti-cheat state
  const [violationCount, setViolationCount] = useState<number>(0);
  const [warningModalOpen, setWarningModalOpen] = useState(false);
  const [cheatedModalOpen, setCheatedModalOpen] = useState(false);
  const lastViolationRef = useRef<number>(0);
  const submittedRef = useRef(false);

  // Audio Lock State
  const [, setAudioPlayed] = useState(false);
  const [volume, setVolume] = useState<number>(0.8);
  const [isMuted, setIsMuted] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  // Practice mode AI evidence state
  const [evidenceData, setEvidenceData] = useState<EvidenceModalData | null>(null);
  const [evidenceLoading, setEvidenceLoading] = useState(false);
  const [evidenceModalOpen, setEvidenceModalOpen] = useState(false);

  // Text highlighter & selection popover
  const passageContainerRef = useRef<HTMLDivElement | null>(null);
  const [highlights, setHighlights] = useState<string[]>([]);
  const [floatingPill, setFloatingPill] = useState<{ x: number; y: number } | null>(null);

  // 1. Submit Exam Callback (defined first for effect dependencies)
  const handleSubmit = useCallback(async (_auto = false) => {
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
  }, [attemptId, submitting]);

  // 2. Fetch Attempt Data
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
    void fetchAttempt();
  }, [fetchAttempt]);

  // 3. Timer Countdown
  useEffect(() => {
    if (remaining === null || remaining <= 0 || resultData) return;
    const interval = setInterval(() => {
      setRemaining((prev) => {
        if (prev !== null && prev <= 1) {
          clearInterval(interval);
          void handleSubmit(true);
          return 0;
        }
        return prev !== null ? prev - 1 : prev;
      });
    }, 1000);
    return () => clearInterval(interval);
  }, [remaining, resultData, handleSubmit]);

  // 4. Strict Mode Fullscreen & Anti-Cheat Guards
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
          void handleSubmit(true);
        } else {
          setWarningModalOpen(true);
        }
      } catch {
        const next = violationCount + 1;
        setViolationCount(next);
        if (next >= 3) {
          setCheatedModalOpen(true);
          void handleSubmit(true);
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
      if (document.fullscreenElement && document.exitFullscreen) {
        document.exitFullscreen().catch(() => {});
      }
      window.removeEventListener('click', handleInitialFullscreen);
      document.removeEventListener('visibilitychange', handleVisibility);
      window.removeEventListener('blur', handleBlur);
      document.removeEventListener('contextmenu', handleContextMenu);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [isStrict, resultData, submitting, cheatedModalOpen, attemptId, violationCount, handleSubmit]);

  // 5. Answer Updates & Auto-Save
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

  // 6. Highlighter Tool & Selection Popover
  const handleHighlightSelection = () => {
    const selection = window.getSelection();
    if (!selection || selection.rangeCount === 0 || selection.isCollapsed) return;

    const range = selection.getRangeAt(0);
    const selectedText = selection.toString().trim();
    if (selectedText.length < 2) return;

    const span = document.createElement('mark');
    span.className = 'bg-amber-300 text-slate-950 px-1 rounded font-medium shadow-sm';
    try {
      range.surroundContents(span);
      setHighlights((prev) => [...prev, selectedText]);
      selection.removeAllRanges();
      setFloatingPill(null);
    } catch {
      // ignore if selection crosses complex nested node boundaries
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
      setFloatingPill(null);
    }
  };

  const handleMouseUpPassage = () => {
    const selection = window.getSelection();
    if (!selection || selection.rangeCount === 0 || selection.isCollapsed) {
      setFloatingPill(null);
      return;
    }
    const selectedText = selection.toString().trim();
    if (selectedText.length < 2) {
      setFloatingPill(null);
      return;
    }
    try {
      const range = selection.getRangeAt(0);
      const rect = range.getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0) {
        setFloatingPill(null);
        return;
      }
      setFloatingPill({
        x: Math.max(20, rect.left + rect.width / 2),
        y: Math.max(20, rect.top - 10),
      });
    } catch {
      setFloatingPill(null);
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

  // Helper: check if a question is answered
  const isQuestionAnswered = (qId: number) => {
    const a = answers[qId];
    if (!a) return false;
    if (Array.isArray(a.choices) && a.choices.length > 0) return true;
    if (typeof a.text === 'string' && a.text.trim().length > 0) return true;
    if (typeof a.written === 'string' && a.written.trim().length > 0) return true;
    if (a.gaps && Object.values(a.gaps).some((v) => typeof v === 'string' && v.trim().length > 0)) return true;
    if (a.matching && Object.values(a.matching).some((v) => v !== null && v !== undefined)) return true;
    return false;
  };

  if (loading) {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-slate-950 text-white">
        <div className="text-center">
          <RefreshCwIcon className="h-10 w-10 animate-spin text-blue-500 mx-auto mb-4" />
          <h2 className="text-xl font-bold">Cambridge CD-IELTS / BMB CBT muhiti yuklanmoqda...</h2>
          <p className="text-slate-400 text-sm mt-1">Split-screen interfeysi va test savollari sozlanmoqda</p>
        </div>
      </div>
    );
  }

  if (err && !attempt) {
    return (
      <div className="flex h-screen w-screen items-center justify-center bg-slate-950 text-white p-6">
        <div className="max-w-md bg-slate-900 p-8 rounded-2xl border border-red-500/30 text-center">
          <AlertTriangleIcon className="h-12 w-12 text-red-400 mx-auto mb-4" />
          <h2 className="text-xl font-bold text-red-200">Xatolik</h2>
          <p className="text-slate-300 mt-2 mb-6">{err}</p>
          <Link to="/tests" className="px-6 py-2.5 bg-blue-600 hover:bg-blue-500 rounded-xl font-medium">
            Testlar ro'yxatiga qaytish
          </Link>
        </div>
      </div>
    );
  }

  const questions = attempt?.questions || [];
  const currentQ = questions[currentQIndex];
  const passages = attempt?.passages || [];
  const currentPassageIndex = passages.findIndex((p) => p.id === activePassageId);
  const currentPassage = passages[currentPassageIndex] || passages[0] || currentQ?.passage;

  // Format countdown
  const formatTime = (secs: number | null) => {
    if (secs === null || secs === undefined) return '00:00';
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  // Stats for bottom bar & confirm modal
  const answeredCount = questions.filter((q) => isQuestionAnswered(q.id)).length;
  const unansweredCount = questions.length - answeredCount;
  const flaggedCount = questions.filter((q) => flagged[q.id]).length;

  // POST-EXAM RESULTS VIEW
  if (resultData) {
    return (
      <div className="min-h-screen w-screen bg-slate-950 text-slate-100 p-4 md:p-8 overflow-y-auto">
        <div className="max-w-4xl mx-auto space-y-6">
          {/* Header Summary */}
          <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6 md:p-8 shadow-2xl text-center relative overflow-hidden">
            <div className="absolute top-0 left-0 w-full h-2 bg-gradient-to-r from-emerald-500 via-blue-500 to-indigo-500" />
            <AwardIcon className="h-16 w-16 text-amber-400 mx-auto mb-3" />
            <h1 className="text-3xl font-extrabold text-white">{attempt?.test_title || 'English Examination'}</h1>
            <p className="text-slate-400 text-sm mt-1">Imtihon natijalari va xalqaro baholash xulosasi</p>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-8">
              <div className="bg-slate-800/80 p-4 rounded-2xl border border-slate-700">
                <span className="text-xs text-slate-400 uppercase tracking-wider block">To'g'ri javoblar</span>
                <span className="text-2xl font-bold text-emerald-400 mt-1 block">
                  {resultData.correct_answers ?? attempt?.raw_score ?? 0} / {attempt?.total_questions ?? questions.length}
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

          {/* Digital Certificate Card */}
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
            <Link to="/tests" className="px-6 py-3 bg-blue-600 hover:bg-blue-500 text-white rounded-xl font-semibold">
              Boshqa imtihonlar
            </Link>
          </div>
        </div>
      </div>
    );
  }

  // Render passage paragraphs with Cambridge Drop Cap badges (A, B, C...)
  const renderPassageBody = () => {
    if (!currentPassage) {
      return (
        <div className="flex h-full items-center justify-center text-slate-500 text-sm">
          Ushbu savollar bo'limi uchun matn biriktirilmagan.
        </div>
      );
    }

    const content = currentPassage.content || '';
    const hasHtml = /<\/?[a-z][\s\S]*>/i.test(content);

    if (hasHtml) {
      return (
        <div
          className={`whitespace-pre-wrap ${
            fontSize === 'large' ? 'text-[18px] leading-[1.85]' : 'text-[15px] leading-relaxed'
          } text-slate-200 select-text`}
          dangerouslySetInnerHTML={{ __html: content }}
        />
      );
    }

    const paragraphs = content
      .split(/\n\s*\n/)
      .map((p) => p.trim())
      .filter(Boolean);

    if (paragraphs.length <= 1) {
      return (
        <div
          className={`whitespace-pre-wrap ${
            fontSize === 'large' ? 'text-[18px] leading-[1.85]' : 'text-[15px] leading-relaxed'
          } text-slate-200 select-text`}
        >
          {content}
        </div>
      );
    }

    return (
      <div
        className={`space-y-6 ${
          fontSize === 'large' ? 'text-[18px] leading-[1.85]' : 'text-[15px] leading-relaxed'
        } text-slate-200 select-text`}
      >
        {paragraphs.map((p, idx) => {
          const match = p.match(/^(?:Paragraph\s+([A-Z])[\:\.\s]|([A-Z])[\.\:\s])\s*(.*)/i);
          const letter = match ? (match[1] || match[2]).toUpperCase() : String.fromCharCode(65 + idx);
          const text = match ? match[3] : p;

          return (
            <div key={idx} className="relative group">
              <div className="flex items-start gap-3">
                <span className="inline-flex items-center justify-center w-7 h-7 rounded-lg bg-slate-800 border border-slate-700/80 text-xs font-bold text-amber-400 shrink-0 mt-0.5 select-none shadow-sm">
                  {letter}
                </span>
                <p className="flex-1 leading-relaxed">{text}</p>
              </div>
            </div>
          );
        })}
      </div>
    );
  };

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-slate-950 text-slate-100 select-none font-sans">
      {/* 1. TOP HEADER (CAMBRIDGE / BMB CD-IELTS 56px BAR) */}
      <header className="h-14 border-b border-slate-800 bg-slate-900/95 backdrop-blur px-4 sm:px-6 flex items-center justify-between shrink-0 z-30">
        {/* Left: Title + Passage of Total + Mode */}
        <div className="flex items-center gap-3">
          <div className="hidden sm:flex items-center gap-2">
            <span className="px-2 py-0.5 rounded bg-blue-600/20 text-blue-400 border border-blue-500/30 font-black text-xs uppercase tracking-wider">
              CD-IELTS
            </span>
          </div>

          <h1 className="font-bold text-sm sm:text-base text-white truncate max-w-[160px] sm:max-w-xs md:max-w-md">
            {attempt?.test_title || 'IELTS & CEFR Multi-level Exam'}
          </h1>

          {/* Passage Indicator */}
          {passages.length > 0 && (
            <span className="hidden md:inline-flex items-center px-2.5 py-0.5 rounded-md bg-slate-800 border border-slate-700 text-xs font-semibold text-slate-300">
              Passage {currentPassageIndex >= 0 ? currentPassageIndex + 1 : 1} of {passages.length}
            </span>
          )}

          {/* Mode Pill */}
          <span
            className={`text-xs px-2.5 py-0.5 rounded-full font-semibold shrink-0 ${
              isStrict
                ? 'bg-red-500/15 text-red-400 border border-red-500/30'
                : 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
            }`}
          >
            {isStrict ? '🛑 Strict Exam' : '💡 Practice'}
          </span>
        </div>

        {/* Center: Countdown Timer */}
        <div className="flex items-center justify-center">
          <div
            className={`flex items-center gap-2 px-3 sm:px-4 py-1.5 rounded-xl border font-mono text-sm sm:text-base font-bold tracking-wide transition-all ${
              remaining !== null && remaining < 300
                ? 'bg-rose-950/80 border-rose-500 text-rose-300 animate-pulse'
                : 'bg-slate-800/90 border-slate-700 text-amber-300 shadow-sm'
            }`}
          >
            <ClockIcon className={`h-4 w-4 ${remaining !== null && remaining < 300 ? 'text-rose-400' : 'text-amber-400'}`} />
            <span>⏱ {formatTime(remaining)} <span className="hidden sm:inline">remaining</span></span>
          </div>
        </div>

        {/* Right: Tools & Audio */}
        <div className="flex items-center gap-2 sm:gap-3">
          {/* Font Size Toggle */}
          <div className="hidden md:flex items-center bg-slate-800/80 rounded-xl p-0.5 border border-slate-700 text-xs">
            <button
              type="button"
              onClick={() => setFontSize('standard')}
              className={`px-2.5 py-1 rounded-lg font-semibold transition-all ${
                fontSize === 'standard'
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              Standard
            </button>
            <button
              type="button"
              onClick={() => setFontSize('large')}
              className={`px-2.5 py-1 rounded-lg font-semibold transition-all ${
                fontSize === 'large'
                  ? 'bg-blue-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              Large
            </button>
          </div>

          {/* Highlighter Tools */}
          <div className="hidden sm:flex items-center gap-1.5">
            <button
              type="button"
              onClick={handleHighlightSelection}
              className="px-2.5 py-1 text-xs font-semibold bg-amber-500/15 text-amber-300 hover:bg-amber-500/25 rounded-xl border border-amber-500/30 flex items-center gap-1 transition-all"
              title="Belgilangan matnni nur bilan ajratish"
            >
              <span>🖍️ Highlight</span>
            </button>
            {highlights.length > 0 && (
              <button
                type="button"
                onClick={clearHighlights}
                className="px-2 py-1 text-xs text-slate-400 hover:text-white transition-colors"
                title="Bo'yoqlarni tozalash"
              >
                Clear
              </button>
            )}
          </div>

          {/* Audio Volume Minimalist Slider */}
          {attempt?.audio_url && (
            <div className="flex items-center gap-2 bg-slate-800/80 px-2.5 py-1 rounded-xl border border-slate-700">
              <button
                type="button"
                onClick={() => {
                  if (!audioRef.current) return;
                  audioRef.current.muted = !isMuted;
                  setIsMuted(!isMuted);
                }}
                className="text-slate-300 hover:text-white"
                title={isMuted ? 'Ovozni yoqish' : 'Ovozni o\'chirish'}
              >
                {isMuted ? (
                  <VolumeXIcon className="h-3.5 w-3.5 text-rose-400" />
                ) : (
                  <Volume2Icon className="h-3.5 w-3.5 text-emerald-400 animate-pulse" />
                )}
              </button>
              <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                value={isMuted ? 0 : volume}
                onChange={(e) => {
                  const val = parseFloat(e.target.value);
                  setVolume(val);
                  setIsMuted(false);
                  if (audioRef.current) {
                    audioRef.current.volume = val;
                    audioRef.current.muted = false;
                  }
                }}
                className="w-16 h-1 accent-emerald-500 cursor-pointer"
                title="Audio ovozi"
              />
              <audio
                ref={audioRef}
                src={attempt.audio_url}
                autoPlay={isStrict}
                controls={false}
                onPlay={() => setAudioPlayed(true)}
              />
            </div>
          )}

          {/* Anti-cheat status in strict mode */}
          {isStrict && (
            <div className="hidden lg:flex items-center gap-1 text-xs text-amber-400 bg-amber-500/10 px-2.5 py-1 rounded-lg border border-amber-500/20">
              <AlertTriangleIcon className="h-3.5 w-3.5" />
              <span>Nazorat: {violationCount}/3</span>
            </div>
          )}

          {/* Fullscreen Button */}
          <button
            type="button"
            onClick={toggleFullscreen}
            className="p-1.5 hover:bg-slate-800 rounded-lg text-slate-400 hover:text-white transition-colors"
            title="To'liq ekran"
          >
            {isFullscreen ? <Minimize2Icon className="h-4 w-4" /> : <Maximize2Icon className="h-4 w-4" />}
          </button>

          {/* Exit Exam Button */}
          <button
            type="button"
            onClick={() => setExitModalOpen(true)}
            className="p-1.5 hover:bg-slate-800 rounded-lg text-slate-400 hover:text-rose-400 transition-colors"
            title="Testdan chiqish"
          >
            <LogOutIcon className="h-4 w-4" />
          </button>
        </div>
      </header>

      {/* MOBILE TAB SWITCHER (< lg) */}
      <div className="lg:hidden flex border-b border-slate-800 bg-slate-900 shrink-0">
        <button
          type="button"
          onClick={() => setMobileTab('passage')}
          className={`flex-1 py-3 text-xs sm:text-sm font-bold flex items-center justify-center gap-2 border-b-2 transition-all ${
            mobileTab === 'passage'
              ? 'border-blue-500 text-white bg-slate-800/60 shadow-sm'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <BookOpenIcon className="h-4 w-4 text-blue-400" />
          <span>📖 Matn / Passage</span>
        </button>
        <button
          type="button"
          onClick={() => setMobileTab('questions')}
          className={`flex-1 py-3 text-xs sm:text-sm font-bold flex items-center justify-center gap-2 border-b-2 transition-all ${
            mobileTab === 'questions'
              ? 'border-blue-500 text-white bg-slate-800/60 shadow-sm'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <HelpCircleIcon className="h-4 w-4 text-emerald-400" />
          <span>❓ Savollar ({currentQIndex + 1}/{questions.length})</span>
        </button>
      </div>

      {/* 2. MAIN 50/50 SPLIT-SCREEN WORKSPACE */}
      <main className="flex-1 grid grid-cols-1 lg:grid-cols-2 overflow-hidden relative">
        {/* LEFT COLUMN: READING PASSAGE (50%) */}
        <section
          className={`flex flex-col border-b lg:border-b-0 lg:border-r border-slate-800 bg-slate-900/40 h-full overflow-hidden ${
            mobileTab === 'passage' ? 'flex' : 'hidden lg:flex'
          }`}
        >
          {/* Passage Switcher Tabs Bar */}
          <div className="p-3 border-b border-slate-800 bg-slate-900 flex items-center justify-between shrink-0">
            <div className="flex items-center gap-2 overflow-x-auto">
              {passages.length > 0 ? (
                passages.map((p, idx) => (
                  <button
                    key={p.id}
                    type="button"
                    onClick={() => setActivePassageId(p.id)}
                    className={`px-3 py-1 text-xs font-semibold rounded-lg transition-all ${
                      (activePassageId || passages[0]?.id) === p.id
                        ? 'bg-blue-600 text-white shadow-sm'
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

            {/* Mobile Highlighter Trigger */}
            <div className="flex sm:hidden items-center gap-1.5">
              <button
                type="button"
                onClick={handleHighlightSelection}
                className="px-2 py-1 text-xs font-semibold bg-amber-500/20 text-amber-300 rounded-lg border border-amber-500/30"
              >
                🖍️ Highlight
              </button>
            </div>
          </div>

          {/* Scrollable Reading Content */}
          <div
            ref={passageContainerRef}
            onMouseUp={handleMouseUpPassage}
            className="flex-1 overflow-y-auto p-6 lg:p-8 font-serif leading-relaxed select-text"
          >
            <div className="max-w-2xl mx-auto space-y-4">
              {currentPassage?.title && (
                <h2 className="text-xl sm:text-2xl font-bold font-sans text-white border-b border-slate-800 pb-3">
                  {currentPassage.title}
                </h2>
              )}
              {renderPassageBody()}
            </div>
          </div>
        </section>

        {/* RIGHT COLUMN: QUESTIONS & AI EVIDENCE (50%) */}
        <section
          className={`flex flex-col h-full bg-slate-950 overflow-hidden ${
            mobileTab === 'questions' ? 'flex' : 'hidden lg:flex'
          }`}
        >
          {/* Question Viewport */}
          <div className="flex-1 overflow-y-auto p-6 lg:p-8">
            {currentQ ? (
              <div className="max-w-2xl mx-auto space-y-6">
                {/* Top Badge & Points */}
                <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                  <div className="flex items-center gap-2">
                    <span className="font-extrabold text-xl text-blue-400">
                      Question {currentQ.position || currentQIndex + 1}
                    </span>
                    <span className="text-xs text-slate-400 uppercase tracking-wider bg-slate-900 border border-slate-800 px-2 py-0.5 rounded">
                      {currentQ.question_type}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-slate-400 font-medium">
                      {currentQ.points || 1} point
                    </span>
                  </div>
                </div>

                {/* Instruction banner in italics */}
                <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-3 text-xs text-slate-400 italic">
                  {currentQ.question_type === 'single'
                    ? 'Choose the correct letter, A, B, C or D.'
                    : currentQ.question_type === 'multiple'
                    ? 'Choose ALL correct options that apply.'
                    : currentQ.question_type === 'text' || currentQ.question_type === 'gap_fill'
                    ? 'Write NO MORE THAN TWO WORDS from the passage for each answer.'
                    : currentQ.question_type === 'written'
                    ? 'Write your response in the box below. Check your grammar and paragraph structure.'
                    : 'Answer the question carefully.'}
                </div>

                {/* Question Text */}
                <div
                  className={`font-medium text-white leading-relaxed ${
                    fontSize === 'large' ? 'text-lg sm:text-xl' : 'text-base sm:text-lg'
                  }`}
                >
                  {currentQ.text}
                </div>

                {/* 1. SINGLE / MULTIPLE CHOICE CARDS */}
                {(currentQ.question_type === 'single' || currentQ.question_type === 'multiple') && (
                  <div className="space-y-3 pt-2">
                    {(currentQ.choices || []).map((c, cIdx) => {
                      const isSelected = (answers[currentQ.id]?.choices || []).includes(c.id);
                      const letter = String.fromCharCode(65 + cIdx);
                      const isTFNG = /^(true|false|not given|yes|no)$/i.test(c.text.trim());

                      return (
                        <button
                          key={c.id}
                          type="button"
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
                          className={`w-full text-left p-4 rounded-xl border transition-all flex items-center gap-3.5 group cursor-pointer ${
                            isSelected
                              ? 'bg-blue-600/15 border-blue-500 text-white ring-1 ring-blue-500/50 shadow-md shadow-blue-950/40'
                              : 'bg-slate-900/90 border-slate-800 text-slate-300 hover:bg-slate-800/80 hover:border-slate-700 hover:text-white'
                          }`}
                        >
                          <span
                            className={`w-7 h-7 rounded-lg flex items-center justify-center text-xs font-bold shrink-0 transition-colors ${
                              isSelected
                                ? 'bg-blue-600 text-white shadow-sm'
                                : 'bg-slate-800 border border-slate-700 text-slate-400 group-hover:text-slate-200 group-hover:border-slate-600'
                            }`}
                          >
                            {isTFNG ? (isSelected ? '✓' : letter) : letter}
                          </span>
                          <span
                            className={`flex-1 font-medium ${
                              isTFNG ? 'uppercase tracking-wider font-bold' : ''
                            } ${fontSize === 'large' ? 'text-base' : 'text-sm'}`}
                          >
                            {c.text}
                          </span>
                          {isSelected && <span className="text-blue-400 font-bold text-sm shrink-0">●</span>}
                        </button>
                      );
                    })}
                  </div>
                )}

                {/* 2. FILL-IN-THE-BLANKS / TEXT INPUT */}
                {(currentQ.question_type === 'text' || currentQ.question_type === 'gap_fill') && (
                  <div className="space-y-4 pt-2">
                    <label className="text-xs text-slate-400 uppercase tracking-wider block font-semibold">
                      Your Answer:
                    </label>
                    <input
                      type="text"
                      value={answers[currentQ.id]?.text || ''}
                      onChange={(e) => updateAnswer(currentQ.id, 'text', e.target.value)}
                      placeholder="Type your answer here..."
                      className="w-full bg-slate-900 border border-slate-700 rounded-xl px-4 py-3.5 text-white text-base focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                    />
                  </div>
                )}

                {/* 3. WRITTEN ESSAY (IELTS Task 1 / Task 2) */}
                {currentQ.question_type === 'written' && (
                  <div className="space-y-3 pt-2">
                    <div className="flex justify-between items-center text-xs text-slate-400">
                      <span>Written response:</span>
                      <span className="font-mono bg-slate-900 px-2 py-1 rounded border border-slate-800">
                        Words:{' '}
                        {(answers[currentQ.id]?.written || '').trim().split(/\s+/).filter(Boolean).length}
                      </span>
                    </div>
                    <textarea
                      rows={12}
                      value={answers[currentQ.id]?.written || ''}
                      onChange={(e) => updateAnswer(currentQ.id, 'written', e.target.value)}
                      placeholder="Write your essay or response here..."
                      className="w-full bg-slate-900 border border-slate-700 rounded-xl p-4 text-white text-sm focus:outline-none focus:border-blue-500 font-mono leading-relaxed"
                    />
                  </div>
                )}

                {/* PRACTICE MODE ONLY: AI EVIDENCE BUTTON (STRICT EXAM HIDES THIS COMPLETELY) */}
                {!isStrict && (
                  <div className="pt-6 border-t border-slate-800">
                    <button
                      type="button"
                      onClick={() => handleOpenAiEvidence(currentQ)}
                      className="w-full py-3 px-4 bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 border border-indigo-500/30 rounded-xl text-xs sm:text-sm font-semibold flex items-center justify-center gap-2 transition-all cursor-pointer shadow-md"
                    >
                      <HelpCircleIcon className="h-4 w-4 text-indigo-400" />
                      <span>💡 AI Dalilli Tushuntirish (DeepSeek-R1 Evidence)</span>
                    </button>
                  </div>
                )}
              </div>
            ) : (
              <div className="flex h-full items-center justify-center text-slate-500 text-sm">
                Savol tanlanmagan
              </div>
            )}
          </div>
        </section>

        {/* FLOATING HIGHLIGHT POPOVER */}
        {floatingPill && (
          <div
            style={{ left: `${floatingPill.x}px`, top: `${floatingPill.y}px` }}
            className="fixed -translate-x-1/2 -translate-y-full z-40 animate-fade-in pointer-events-auto"
          >
            <button
              type="button"
              onClick={handleHighlightSelection}
              className="bg-amber-400 hover:bg-amber-300 text-slate-950 font-bold text-xs px-3 py-1.5 rounded-lg shadow-xl border border-amber-300 flex items-center gap-1 cursor-pointer transition-transform hover:scale-105"
            >
              <span>🖍️ Highlight</span>
            </button>
          </div>
        )}
      </main>

      {/* 3. CAMBRIDGE QUESTION PALETTE FOOTER (FULL-WIDTH FIXED BAR) */}
      <footer className="h-16 border-t border-slate-800 bg-slate-900/95 backdrop-blur px-4 sm:px-6 flex items-center justify-between shrink-0 z-20 gap-3">
        {/* Left: Scrollable Questions Palette Track */}
        <div className="flex items-center gap-1.5 overflow-x-auto py-1 max-w-[55vw] sm:max-w-[65vw]">
          {questions.map((q, idx) => {
            const answered = isQuestionAnswered(q.id);
            const isCurrent = idx === currentQIndex;
            const isFlag = Boolean(flagged[q.id]);

            return (
              <button
                key={q.id}
                type="button"
                onClick={() => {
                  setCurrentQIndex(idx);
                  setMobileTab('questions');
                }}
                className={`relative min-w-[32px] w-8 h-8 rounded-lg text-xs font-bold shrink-0 transition-all flex items-center justify-center ${
                  isCurrent
                    ? 'ring-2 ring-blue-400 bg-blue-600 text-white font-black shadow-md scale-105'
                    : isFlag
                    ? 'bg-amber-500/20 text-amber-300 border border-amber-500/60'
                    : answered
                    ? 'bg-slate-800 text-sky-400 border border-sky-500/40 font-semibold'
                    : 'bg-slate-800/40 text-slate-500 border border-slate-700/60 hover:text-slate-300 hover:border-slate-500'
                }`}
                title={`Question ${idx + 1}${answered ? ' (Answered)' : ''}${isFlag ? ' (Flagged)' : ''}`}
              >
                {idx + 1}
                {isFlag && (
                  <span className="absolute -top-1 -right-1 w-2.5 h-2.5 bg-amber-400 rounded-full ring-2 ring-slate-900" />
                )}
                {answered && !isCurrent && (
                  <span className="absolute bottom-0.5 left-1/2 -translate-x-1/2 w-3 h-0.5 bg-sky-400 rounded-full" />
                )}
              </button>
            );
          })}
        </div>

        {/* Right: Actions */}
        <div className="flex items-center gap-2 shrink-0">
          <button
            type="button"
            onClick={() =>
              currentQ && setFlagged((prev) => ({ ...prev, [currentQ.id]: !prev[currentQ.id] }))
            }
            className={`hidden md:inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold border transition-all ${
              currentQ && flagged[currentQ.id]
                ? 'bg-amber-500/20 border-amber-500/50 text-amber-300'
                : 'bg-slate-800 border-slate-700 text-slate-400 hover:text-white'
            }`}
          >
            <FlagIcon className="h-3.5 w-3.5" />
            <span>{currentQ && flagged[currentQ.id] ? 'Flagged' : 'Review'}</span>
          </button>

          <button
            type="button"
            onClick={() => {
              setCurrentQIndex((prev) => Math.max(0, prev - 1));
              setMobileTab('questions');
            }}
            disabled={currentQIndex === 0}
            className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 disabled:opacity-40 disabled:hover:bg-slate-800 text-xs font-semibold rounded-xl text-slate-300 flex items-center gap-1 border border-slate-700/80 transition-colors"
          >
            <ChevronLeftIcon className="h-4 w-4" />
            <span className="hidden sm:inline">Back</span>
          </button>

          <button
            type="button"
            onClick={() => {
              setCurrentQIndex((prev) => Math.min(questions.length - 1, prev + 1));
              setMobileTab('questions');
            }}
            disabled={currentQIndex === questions.length - 1}
            className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 disabled:opacity-40 disabled:hover:bg-slate-800 text-xs font-semibold rounded-xl text-slate-300 flex items-center gap-1 border border-slate-700/80 transition-colors"
          >
            <span className="hidden sm:inline">Next</span>
            <ChevronRightIcon className="h-4 w-4" />
          </button>

          <button
            type="button"
            onClick={() => setConfirmSubmitOpen(true)}
            disabled={submitting}
            className="px-4 sm:px-5 py-2 bg-gradient-to-r from-red-600 via-rose-600 to-amber-600 hover:from-red-500 hover:to-amber-500 text-white text-xs sm:text-sm font-bold rounded-xl shadow-lg shadow-red-950/50 transition-all flex items-center gap-1.5 cursor-pointer"
          >
            <span>Finish Test</span>
          </button>
        </div>
      </footer>

      {/* 4. MODALS */}

      {/* Exit Confirmation Modal */}
      {exitModalOpen && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-3xl max-w-md w-full p-6 space-y-5 shadow-2xl text-center">
            <div className="w-12 h-12 rounded-2xl bg-rose-500/20 text-rose-400 flex items-center justify-center mx-auto border border-rose-500/30">
              <LogOutIcon className="h-6 w-6" />
            </div>

            <div>
              <h3 className="text-xl font-bold text-white">Testdan chiqmoqchimisiz?</h3>
              <p className="text-slate-400 text-xs mt-1">
                Kiritilgan javoblaringiz saqlanib qoladi. Keyinroq yana davom ettirishingiz mumkin.
              </p>
            </div>

            <div className="flex gap-3 pt-2">
              <button
                type="button"
                onClick={() => setExitModalOpen(false)}
                className="flex-1 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 font-semibold text-xs border border-slate-700"
              >
                Davom etish
              </button>
              <button
                type="button"
                onClick={handleConfirmExit}
                className="flex-1 py-2.5 rounded-xl bg-rose-600 hover:bg-rose-500 text-white font-bold text-xs shadow-lg shadow-rose-950/50"
              >
                Testdan chiqish
              </button>
            </div>
          </div>
        </div>
      )}

      {/* A. Finish Confirmation Modal */}
      {confirmSubmitOpen && (
        <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-3xl max-w-md w-full p-6 space-y-5 shadow-2xl text-center">
            <div className="w-12 h-12 rounded-2xl bg-amber-500/20 text-amber-400 flex items-center justify-center mx-auto border border-amber-500/30">
              <AlertTriangleIcon className="h-6 w-6" />
            </div>

            <div>
              <h3 className="text-xl font-bold text-white">Imtihonni yakunlaysizmi?</h3>
              <p className="text-slate-400 text-xs mt-1">
                Topshirishdan oldin javoblaringizni tekshirib oling.
              </p>
            </div>

            <div className="grid grid-cols-3 gap-3 bg-slate-950 p-3 rounded-2xl border border-slate-800">
              <div className="text-center">
                <span className="text-[10px] text-slate-500 uppercase tracking-wider block">Javob berildi</span>
                <span className="text-lg font-bold text-emerald-400">{answeredCount}</span>
              </div>
              <div className="text-center border-x border-slate-800">
                <span className="text-[10px] text-slate-500 uppercase tracking-wider block">Javobsiz</span>
                <span className={`text-lg font-bold ${unansweredCount > 0 ? 'text-rose-400' : 'text-slate-400'}`}>
                  {unansweredCount}
                </span>
              </div>
              <div className="text-center">
                <span className="text-[10px] text-slate-500 uppercase tracking-wider block">Belgilangan</span>
                <span className="text-lg font-bold text-amber-400">{flaggedCount}</span>
              </div>
            </div>

            {unansweredCount > 0 && (
              <div className="bg-rose-950/30 border border-rose-500/30 rounded-xl p-3 text-left flex items-start gap-2.5">
                <AlertTriangleIcon className="h-4 w-4 text-rose-400 shrink-0 mt-0.5" />
                <p className="text-xs text-rose-300">
                  Siz <strong>{unansweredCount} ta</strong> savolga hali javob bermadingiz. Yakunlangach, javob berilmagan savollarga 0 ball hisoblanadi.
                </p>
              </div>
            )}

            <div className="flex gap-3 pt-2">
              <button
                type="button"
                onClick={() => setConfirmSubmitOpen(false)}
                className="flex-1 py-2.5 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold rounded-xl border border-slate-700 transition-colors cursor-pointer"
              >
                Testga qaytish
              </button>
              <button
                type="button"
                onClick={() => {
                  setConfirmSubmitOpen(false);
                  void handleSubmit(false);
                }}
                disabled={submitting}
                className="flex-1 py-2.5 bg-gradient-to-r from-red-600 to-amber-600 hover:from-red-500 hover:to-amber-500 text-white text-xs font-bold rounded-xl shadow-lg shadow-red-950/40 transition-all flex items-center justify-center gap-1.5 cursor-pointer"
              >
                {submitting ? (
                  <>
                    <RefreshCwIcon className="h-3.5 w-3.5 animate-spin" />
                    <span>Topshirilmoqda...</span>
                  </>
                ) : (
                  <span>Ha, yakunlash</span>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* B. Practice Mode Evidence Modal */}
      {evidenceModalOpen && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-indigo-500/30 rounded-2xl max-w-xl w-full p-6 space-y-4 shadow-2xl relative">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                <HelpCircleIcon className="h-5 w-5 text-indigo-400" />
                <h3 className="font-bold text-white text-base">Dalillarga Asoslangan AI Tahlili (R1)</h3>
              </div>
              <button
                type="button"
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
                type="button"
                onClick={() => setEvidenceModalOpen(false)}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-xl text-xs font-semibold"
              >
                Tushundim
              </button>
            </div>
          </div>
        </div>
      )}

      {/* C. Anti-Cheat Warning Modal (1/3 or 2/3) */}
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
              type="button"
              onClick={() => {
                setWarningModalOpen(false);
                if (!document.fullscreenElement) {
                  document.documentElement.requestFullscreen().catch(() => {});
                }
              }}
              className="w-full py-3 bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold rounded-xl text-sm cursor-pointer"
            >
              Imtihonga qaytish
            </button>
          </div>
        </div>
      )}

      {/* D. Anti-Cheat Disqualified Modal (3/3) */}
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
              type="button"
              onClick={() => navigate('/results')}
              className="w-full py-3 bg-red-600 hover:bg-red-500 text-white font-bold rounded-xl text-sm mt-4 cursor-pointer"
            >
              Natijalarni ko'rish
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
