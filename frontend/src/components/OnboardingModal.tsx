import { useCallback, useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import {
  GraduationCap,
  Award,
  Clock,
  ArrowRight,
  ArrowLeft,
  CheckCircle2,
  Sparkles,
  Calendar,
} from 'lucide-react';
import confetti from 'canvas-confetti';
import { PlacementQuiz, type PlacementQuestion, type PlacementSubmitResponse } from '../lib/api';
import { useAuth } from '../auth/AuthContext';
import SubjectSwitcher from './SubjectSwitcher';

interface OnboardingModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: () => void;
}

type Step = 'goals' | 'quiz' | 'result';
type TargetType = 'national_certificate' | 'attestation' | 'ielts' | 'multilevel';

export default function OnboardingModal({ isOpen, onClose, onSuccess }: OnboardingModalProps) {
  const { user, updateUserLocal, refreshUser } = useAuth();

  const role = (user?.role || '').toLowerCase();
  const isStaffOrTeacher = role === 'admin' || role === 'teacher' || role === 'superadmin' || Boolean(user?.is_staff) || Boolean(user?.is_superuser);
  const isStudent = role === 'student' && !isStaffOrTeacher;

  const isDismissed = typeof window !== 'undefined' && (
    localStorage.getItem('onboarding_dismissed') === 'true' ||
    localStorage.getItem('grandec_onboarding_done') === 'true'
  );

  const [activeSubject, setActiveSubject] = useState<'uzbek' | 'english'>(() => {
    const track = localStorage.getItem('grandec_selected_track');
    if (track === 'ielts' || track === 'multilevel') return 'english';
    if (track === 'national_certificate' || track === 'attestation') return 'uzbek';
    if (user?.active_subject === 'english') return 'english';
    const saved = localStorage.getItem('landing_subject') || localStorage.getItem('lms_subject');
    return saved === 'english' ? 'english' : 'uzbek';
  });

  // 1-Step: Goals
  const [examTarget, setExamTarget] = useState<TargetType>(() => {
    const track = localStorage.getItem('grandec_selected_track') as TargetType | null;
    if (track && ['ielts', 'multilevel', 'national_certificate', 'attestation'].includes(track)) {
      return track;
    }
    const isEng =
      user?.active_subject === 'english' ||
      localStorage.getItem('landing_subject') === 'english' ||
      localStorage.getItem('lms_subject') === 'english';
    return isEng ? 'ielts' : 'national_certificate';
  });
  const [timelineMonths, setTimelineMonths] = useState<number>(3);
  const [targetGrade, setTargetGrade] = useState<string>(() => {
    const track = localStorage.getItem('grandec_selected_track');
    if (track === 'attestation') return 'Oliy toifa';
    if (track === 'ielts') return 'Band 7.5';
    if (track === 'multilevel') return 'C1 daraja';
    if (track === 'national_certificate') return 'A+';
    const isEng =
      user?.active_subject === 'english' ||
      localStorage.getItem('landing_subject') === 'english' ||
      localStorage.getItem('lms_subject') === 'english';
    return isEng ? 'Band 7.5' : 'A+';
  });

  // 2-Step: Quiz state
  const [step, setStep] = useState<Step>('goals');
  const [loadingQuiz, setLoadingQuiz] = useState<boolean>(false);
  const [questions, setQuestions] = useState<PlacementQuestion[]>([]);
  const [currentIdx, setCurrentIdx] = useState<number>(0);
  const [selectedAnswers, setSelectedAnswers] = useState<Record<number, number>>({});
  const [timeLeft, setTimeLeft] = useState<number>(300);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [submitResult, setSubmitResult] = useState<PlacementSubmitResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [savingPlan, setSavingPlan] = useState<boolean>(false);

  const persistLocalPlan = useCallback((tgt: TargetType, tl: number, gr: string) => {
    localStorage.setItem('onboarding_dismissed', 'true');
    localStorage.setItem('grandec_onboarding_done', 'true');
    localStorage.setItem(
      'grandec_user_plan',
      JSON.stringify({
        target: tgt,
        timeline: `${tl} oy`,
        grade: gr,
      }),
    );
  }, []);

  const handleSkip = useCallback(() => {
    persistLocalPlan(examTarget, timelineMonths, targetGrade);
    updateUserLocal({
      onboarding_completed: true,
      exam_target: examTarget,
      target_timeline_months: timelineMonths,
      target_grade: targetGrade,
    });
    // Silently notify backend so onboarding_completed persists on profile
    PlacementQuiz.submit({
      target: examTarget,
      target_timeline_months: timelineMonths,
      target_grade: targetGrade,
      answers: [],
    }).catch(() => {});
    onClose();
  }, [examTarget, timelineMonths, targetGrade, persistLocalPlan, updateUserLocal, onClose]);

  const handleSavePlanOnly = async () => {
    setSavingPlan(true);
    setErrorMsg(null);
    try {
      persistLocalPlan(examTarget, timelineMonths, targetGrade);
      const res = await PlacementQuiz.submit({
        target: examTarget,
        target_timeline_months: timelineMonths,
        target_grade: targetGrade,
        answers: [],
      });
      updateUserLocal({
        exam_target: examTarget,
        target_timeline_months: timelineMonths,
        target_grade: targetGrade,
        onboarding_completed: true,
        daily_plan_summary: res.daily_plan as Record<string, unknown>,
      });
      onClose();
      if (onSuccess) onSuccess();
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : "Rejani saqlashda xatolik yuz berdi.");
    } finally {
      setSavingPlan(false);
    }
  };

  // Update target grade defaults when exam target changes
  const handleTargetChange = (target: TargetType) => {
    setExamTarget(target);
    if (target === 'attestation') {
      setTargetGrade('Oliy toifa');
    } else if (target === 'ielts') {
      setTargetGrade('Band 7.5');
    } else if (target === 'multilevel') {
      setTargetGrade('C1 daraja');
    } else {
      setTargetGrade('A+');
    }
  };

  // Sync state whenever modal opens
  useEffect(() => {
    if (isOpen) {
      const track = localStorage.getItem('grandec_selected_track') as TargetType | null;
      let sub: 'uzbek' | 'english';
      let tgt: TargetType;

      if (track && ['ielts', 'multilevel', 'national_certificate', 'attestation'].includes(track)) {
        tgt = track;
        sub = (track === 'ielts' || track === 'multilevel') ? 'english' : 'uzbek';
      } else {
        sub =
          user?.active_subject === 'english' ||
          localStorage.getItem('landing_subject') === 'english' ||
          localStorage.getItem('lms_subject') === 'english'
            ? 'english'
            : 'uzbek';
        tgt =
          sub === 'english'
            ? user?.exam_target === 'multilevel'
              ? 'multilevel'
              : 'ielts'
            : user?.exam_target === 'attestation'
            ? 'attestation'
            : 'national_certificate';
      }

      setActiveSubject(sub);
      setExamTarget(tgt);
      setTimelineMonths(user?.target_timeline_months || 3);
      setTargetGrade(
        user?.target_grade ||
          (tgt === 'attestation'
            ? 'Oliy toifa'
            : tgt === 'ielts'
            ? 'Band 7.5'
            : tgt === 'multilevel'
            ? 'C1 daraja'
            : 'A+'),
      );
      setStep('goals');
      setErrorMsg(null);
    }
  }, [isOpen, user]);

  // Timer for quiz
  useEffect(() => {
    if (!isOpen || step !== 'quiz' || timeLeft <= 0 || submitting) return;
    const interval = setInterval(() => {
      setTimeLeft((prev) => {
        if (prev <= 1) {
          clearInterval(interval);
          handleAutoSubmit();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, step, timeLeft, submitting]);

  // Start 5-minute quiz
  const handleStartQuiz = async () => {
    persistLocalPlan(examTarget, timelineMonths, targetGrade);
    setLoadingQuiz(true);
    setErrorMsg(null);
    try {
      const res = await PlacementQuiz.get(examTarget);
      if (res && res.questions && res.questions.length > 0) {
        setQuestions(res.questions);
        setTimeLeft(res.time_limit_seconds || 300);
        setCurrentIdx(0);
        setSelectedAnswers({});
        setStep('quiz');
      } else {
        throw new Error("Savollar bazasini yuklashda xatolik yuz berdi.");
      }
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : "Diagnostika testini yuklashda xatolik.");
    } finally {
      setLoadingQuiz(false);
    }
  };

  // Select an option
  const handlePickChoice = (questionId: number, choiceId: number) => {
    setSelectedAnswers((prev) => ({
      ...prev,
      [questionId]: choiceId,
    }));
  };

  // Submit quiz
  const handleSubmitQuiz = useCallback(async () => {
    if (submitting) return;
    setSubmitting(true);
    setErrorMsg(null);
    try {
      const answersList = questions.map((q) => ({
        question_id: q.id,
        selected_choice_id: selectedAnswers[q.id] || 0,
      }));

      const res = await PlacementQuiz.submit({
        target: examTarget,
        target_timeline_months: timelineMonths,
        target_grade: targetGrade,
        answers: answersList,
      });

      persistLocalPlan(examTarget, timelineMonths, targetGrade);
      setSubmitResult(res);
      updateUserLocal({
        exam_target: examTarget,
        target_timeline_months: timelineMonths,
        target_grade: targetGrade,
        placement_score: res.score,
        onboarding_completed: true,
        daily_plan_summary: res.daily_plan as Record<string, unknown>,
      });

      try {
        confetti({
          particleCount: 70,
          spread: 60,
          origin: { y: 0.6 },
          colors: ['#10B981', '#34D399', '#F59E0B', '#FBBF24'],
        });
      } catch {
        /* ignore */
      }

      setStep('result');
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : "Natijalarni saqlashda xatolik yuz berdi.");
    } finally {
      setSubmitting(false);
    }
  }, [submitting, questions, selectedAnswers, examTarget, timelineMonths, targetGrade, updateUserLocal]);

  const handleAutoSubmit = useCallback(() => {
    handleSubmitQuiz();
  }, [handleSubmitQuiz]);

  const handleFinish = async () => {
    await refreshUser();
    onClose();
    if (onSuccess) onSuccess();
  };

  const formatTimer = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${s < 10 ? '0' : ''}${s}`;
  };

  if (!isOpen || !isStudent || isDismissed) return null;

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9999,
        background: 'rgba(5, 7, 15, 0.85)',
        backdropFilter: 'blur(8px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '16px',
      }}
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 15 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 15 }}
        transition={{ duration: 0.25 }}
        style={{
          width: '100%',
          maxWidth: '680px',
          background: 'linear-gradient(180deg, #161b26 0%, #0d1117 100%)',
          border: '1px solid rgba(255, 255, 255, 0.1)',
          borderRadius: '20px',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.7)',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
          maxHeight: '92vh',
        }}
      >
        {/* Header Bar */}
        <div
          style={{
            padding: '20px 24px',
            borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            background: 'rgba(255, 255, 255, 0.02)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div
              style={{
                width: 36,
                height: 36,
                borderRadius: 10,
                background: 'linear-gradient(135deg, #10B981 0%, #059669 100%)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#fff',
              }}
            >
              <Sparkles size={18} />
            </div>
            <div>
              <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 800, color: 'var(--ink)' }}>
                {step === 'goals' && "Smart Onboarding — Maqsad va Reja"}
                {step === 'quiz' && "5 Daqiqalik Tezkor Diagnostika"}
                {step === 'result' && "Sizning Shaxsiy AI Rejangiz"}
              </h3>
              <span style={{ fontSize: '0.78rem', color: 'var(--ink-muted)' }}>
                {step === 'goals' && "1-bosqich: O'quv yo'nalishi va maqsadli daraja"}
                {step === 'quiz' && `2-bosqich: Savol ${currentIdx + 1} / ${questions.length || 5}`}
                {step === 'result' && "Diagnostika xulosasi va kunlik jadval"}
              </span>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            {step === 'quiz' && (
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                  padding: '6px 12px',
                  borderRadius: 20,
                  background: timeLeft <= 60 ? 'rgba(244, 63, 94, 0.15)' : 'rgba(245, 158, 11, 0.15)',
                  border: `1px solid ${timeLeft <= 60 ? '#f43f5e' : '#f59e0b'}`,
                  color: timeLeft <= 60 ? '#f43f5e' : '#f59e0b',
                  fontWeight: 700,
                  fontSize: '0.9rem',
                }}
              >
                <Clock size={16} />
                <span>{formatTimer(timeLeft)}</span>
              </div>
            )}

            <button
              type="button"
              onClick={handleSkip}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                padding: '6px 12px',
                borderRadius: 10,
                border: '1px solid rgba(255, 255, 255, 0.12)',
                background: 'rgba(255, 255, 255, 0.04)',
                color: 'var(--ink-muted)',
                fontSize: '0.8rem',
                fontWeight: 700,
                cursor: 'pointer',
              }}
              title="O'tkazib yuborish (Keyinroq sozlash)"
            >
              <span>✕ O&apos;tkazib yuborish</span>
            </button>
          </div>
        </div>

        {/* Modal Body */}
        <div style={{ padding: '24px', overflowY: 'auto', flex: 1 }}>
          {errorMsg && (
            <div
              style={{
                padding: '12px 16px',
                borderRadius: 10,
                background: 'rgba(244, 63, 94, 0.15)',
                border: '1px solid #f43f5e',
                color: '#f43f5e',
                marginBottom: 16,
                fontSize: '0.88rem',
              }}
            >
              {errorMsg}
            </div>
          )}

          {/* STEP 1: GOALS & TIMELINE */}
          {step === 'goals' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
              {/* Question 0: Subject Choice */}
              <div>
                <label style={{ display: 'block', fontSize: '0.92rem', fontWeight: 700, marginBottom: 8, color: 'var(--ink)' }}>
                  📚 Tayyorlanmoqchi bo'lgan faningizni tanlang:
                </label>
                <div style={{ marginTop: 4 }}>
                  <SubjectSwitcher
                    size="md"
                    onSwitch={(newSub) => {
                      setActiveSubject(newSub);
                      if (newSub === 'english') {
                        handleTargetChange('ielts');
                      } else {
                        handleTargetChange('national_certificate');
                      }
                    }}
                  />
                </div>
              </div>

              {/* Question 1: Main Goal */}
              <div>
                <label style={{ display: 'block', fontSize: '0.92rem', fontWeight: 700, marginBottom: 10, color: 'var(--ink)' }}>
                  1. Asosiy maqsadingiz nima?
                </label>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 12 }}>
                  {activeSubject === 'english' ? (
                    <>
                      <button
                        type="button"
                        onClick={() => handleTargetChange('ielts')}
                        style={{
                          padding: '16px',
                          borderRadius: 14,
                          border: `2px solid ${examTarget === 'ielts' ? '#6366F1' : 'rgba(255, 255, 255, 0.08)'}`,
                          background: examTarget === 'ielts' ? 'rgba(99, 102, 241, 0.12)' : 'rgba(255, 255, 255, 0.02)',
                          textAlign: 'left',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'flex-start',
                          gap: 12,
                          transition: 'all 0.2s ease',
                        }}
                      >
                        <div style={{ padding: 8, borderRadius: 10, background: 'rgba(99, 102, 241, 0.2)', color: '#6366F1' }}>
                          <GraduationCap size={22} />
                        </div>
                        <div>
                          <div style={{ fontWeight: 800, fontSize: '0.98rem', color: 'var(--ink)', marginBottom: 4 }}>
                            🇬🇧 IELTS Academic & General
                          </div>
                          <div style={{ fontSize: '0.8rem', color: 'var(--ink-muted)' }}>
                            Writing Task 1/2 (Band 1.0–9.0) va Listening/Reading CBT simulyatori
                          </div>
                        </div>
                      </button>

                      <button
                        type="button"
                        onClick={() => handleTargetChange('multilevel')}
                        style={{
                          padding: '16px',
                          borderRadius: 14,
                          border: `2px solid ${examTarget === 'multilevel' ? '#10B981' : 'rgba(255, 255, 255, 0.08)'}`,
                          background: examTarget === 'multilevel' ? 'rgba(16, 185, 129, 0.12)' : 'rgba(255, 255, 255, 0.02)',
                          textAlign: 'left',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'flex-start',
                          gap: 12,
                          transition: 'all 0.2s ease',
                        }}
                      >
                        <div style={{ padding: 8, borderRadius: 10, background: 'rgba(16, 185, 129, 0.2)', color: '#10B981' }}>
                          <Award size={22} />
                        </div>
                        <div>
                          <div style={{ fontWeight: 800, fontSize: '0.98rem', color: 'var(--ink)', marginBottom: 4 }}>
                            🎯 CEFR Multi-level (B2 / C1)
                          </div>
                          <div style={{ fontSize: '0.8rem', color: 'var(--ink-muted)' }}>
                            Milliy sertifikat (ingliz tili) darajali test va insho baholash
                          </div>
                        </div>
                      </button>
                    </>
                  ) : (
                    <>
                      <button
                        type="button"
                        onClick={() => handleTargetChange('national_certificate')}
                        style={{
                          padding: '16px',
                          borderRadius: 14,
                          border: `2px solid ${examTarget === 'national_certificate' ? '#10B981' : 'rgba(255, 255, 255, 0.08)'}`,
                          background: examTarget === 'national_certificate' ? 'rgba(16, 185, 129, 0.1)' : 'rgba(255, 255, 255, 0.02)',
                          textAlign: 'left',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'flex-start',
                          gap: 12,
                          transition: 'all 0.2s ease',
                        }}
                      >
                        <div style={{ padding: 8, borderRadius: 10, background: 'rgba(16, 185, 129, 0.2)', color: '#10B981' }}>
                          <GraduationCap size={22} />
                        </div>
                        <div>
                          <div style={{ fontWeight: 800, fontSize: '0.98rem', color: 'var(--ink)', marginBottom: 4 }}>
                            🎓 Milliy sertifikat
                          </div>
                          <div style={{ fontSize: '0.8rem', color: 'var(--ink-muted)' }}>
                            Abituriyentlar va o'quvchilar uchun (BMB 12 mezon, Ona tili va Adabiyot)
                          </div>
                        </div>
                      </button>

                      <button
                        type="button"
                        onClick={() => handleTargetChange('attestation')}
                        style={{
                          padding: '16px',
                          borderRadius: 14,
                          border: `2px solid ${examTarget === 'attestation' ? '#3B82F6' : 'rgba(255, 255, 255, 0.08)'}`,
                          background: examTarget === 'attestation' ? 'rgba(59, 130, 246, 0.1)' : 'rgba(255, 255, 255, 0.02)',
                          textAlign: 'left',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'flex-start',
                          gap: 12,
                          transition: 'all 0.2s ease',
                        }}
                      >
                        <div style={{ padding: 8, borderRadius: 10, background: 'rgba(59, 130, 246, 0.2)', color: '#3B82F6' }}>
                          <Award size={22} />
                        </div>
                        <div>
                          <div style={{ fontWeight: 800, fontSize: '0.98rem', color: 'var(--ink)', marginBottom: 4 }}>
                            👨‍🏫 Attestatsiya 2026
                          </div>
                          <div style={{ fontSize: '0.8rem', color: 'var(--ink-muted)' }}>
                            O'qituvchilar va pedagoglar uchun toifa sinovlari (50 ta savol)
                          </div>
                        </div>
                      </button>
                    </>
                  )}
                </div>
              </div>

              {/* Question 2: Timeline */}
              <div>
                <label style={{ display: 'block', fontSize: '0.92rem', fontWeight: 700, marginBottom: 10, color: 'var(--ink)' }}>
                  2. Imtihoningizga qancha vaqt qoldi?
                </label>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
                  {[
                    { m: 1, label: '1 oy', sub: 'Tezkor sprint' },
                    { m: 3, label: '3 oy', sub: 'Standart reja' },
                    { m: 6, label: '6 oy', sub: 'Keng qamrovli' },
                  ].map((item) => (
                    <button
                      key={item.m}
                      type="button"
                      onClick={() => setTimelineMonths(item.m)}
                      style={{
                        padding: '12px 10px',
                        borderRadius: 12,
                        border: `2px solid ${timelineMonths === item.m ? '#F59E0B' : 'rgba(255, 255, 255, 0.08)'}`,
                        background: timelineMonths === item.m ? 'rgba(245, 158, 11, 0.12)' : 'rgba(255, 255, 255, 0.02)',
                        textAlign: 'center',
                        cursor: 'pointer',
                        transition: 'all 0.2s ease',
                      }}
                    >
                      <div style={{ fontWeight: 800, fontSize: '1rem', color: timelineMonths === item.m ? '#F59E0B' : 'var(--ink)' }}>
                        {item.label}
                      </div>
                      <div style={{ fontSize: '0.72rem', color: 'var(--ink-muted)', marginTop: 2 }}>
                        {item.sub}
                      </div>
                    </button>
                  ))}
                </div>
              </div>

              {/* Question 3: Target Grade */}
              <div>
                <label style={{ display: 'block', fontSize: '0.92rem', fontWeight: 700, marginBottom: 10, color: 'var(--ink)' }}>
                  3. Qaysi natija / darajani olmoqchisiz?
                </label>
                <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                  {(examTarget === 'ielts'
                    ? ['Band 6.5', 'Band 7.0', 'Band 7.5', 'Band 8.0+']
                    : examTarget === 'multilevel'
                    ? ['B2 daraja', 'C1 daraja', 'C2 daraja']
                    : examTarget === 'attestation'
                    ? ['Oliy toifa', '1-toifa', '2-toifa']
                    : ['A+', 'A', 'B+']
                  ).map((grade) => (
                    <button
                      key={grade}
                      type="button"
                      onClick={() => setTargetGrade(grade)}
                      style={{
                        flex: 1,
                        minWidth: '90px',
                        padding: '12px 16px',
                        borderRadius: 12,
                        border: `2px solid ${targetGrade === grade ? '#10B981' : 'rgba(255, 255, 255, 0.08)'}`,
                        background: targetGrade === grade ? 'rgba(16, 185, 129, 0.15)' : 'rgba(255, 255, 255, 0.02)',
                        color: targetGrade === grade ? '#10B981' : 'var(--ink)',
                        fontWeight: 800,
                        fontSize: '0.95rem',
                        cursor: 'pointer',
                        textAlign: 'center',
                      }}
                    >
                      {grade}
                    </button>
                  ))}
                </div>
              </div>

              {/* Action Buttons */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 10 }}>
                <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                  <button
                    type="button"
                    onClick={handleStartQuiz}
                    disabled={loadingQuiz || savingPlan}
                    style={{
                      flex: 2,
                      minWidth: '220px',
                      padding: '14px 18px',
                      borderRadius: 12,
                      background: 'linear-gradient(135deg, #10B981 0%, #059669 100%)',
                      border: 'none',
                      color: '#fff',
                      fontWeight: 800,
                      fontSize: '0.96rem',
                      cursor: loadingQuiz || savingPlan ? 'not-allowed' : 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: 8,
                      boxShadow: '0 8px 20px -4px rgba(16, 185, 129, 0.4)',
                    }}
                  >
                    {loadingQuiz ? (
                      "Diagnostika test savollari tayyorlanmoqda..."
                    ) : (
                      <>
                        <span>5 daqiqalik diagnostikani boshlash</span>
                        <ArrowRight size={18} />
                      </>
                    )}
                  </button>

                  <button
                    type="button"
                    onClick={handleSavePlanOnly}
                    disabled={loadingQuiz || savingPlan}
                    style={{
                      flex: 1,
                      minWidth: '150px',
                      padding: '14px 16px',
                      borderRadius: 12,
                      background: 'rgba(255, 255, 255, 0.06)',
                      border: '1px solid rgba(255, 255, 255, 0.15)',
                      color: 'var(--ink)',
                      fontWeight: 700,
                      fontSize: '0.9rem',
                      cursor: loadingQuiz || savingPlan ? 'not-allowed' : 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: 6,
                    }}
                  >
                    {savingPlan ? "Saqlanmoqda..." : "💾 Rejani saqlash"}
                  </button>
                </div>

                <button
                  type="button"
                  onClick={handleSkip}
                  style={{
                    background: 'transparent',
                    border: 'none',
                    color: 'var(--ink-muted)',
                    fontSize: '0.82rem',
                    fontWeight: 600,
                    cursor: 'pointer',
                    textDecoration: 'underline',
                    padding: '6px',
                    textAlign: 'center',
                  }}
                >
                  ✕ O&apos;tkazib yuborish (Keyinroq sozlash va darhol testlarni ishlash)
                </button>
              </div>
            </div>
          )}

          {/* STEP 2: 5-MINUTE PLACEMENT QUIZ */}
          {step === 'quiz' && questions.length > 0 && (
            <div>
              {/* Question Progress dots */}
              <div style={{ display: 'flex', gap: 6, marginBottom: 16 }}>
                {questions.map((q, idx) => {
                  const isAnswered = selectedAnswers[q.id] !== undefined;
                  const isCur = idx === currentIdx;
                  return (
                    <div
                      key={q.id}
                      onClick={() => setCurrentIdx(idx)}
                      style={{
                        flex: 1,
                        height: 6,
                        borderRadius: 3,
                        background: isCur ? '#f59e0b' : isAnswered ? '#10B981' : 'rgba(255, 255, 255, 0.1)',
                        cursor: 'pointer',
                        transition: 'all 0.2s ease',
                      }}
                    />
                  );
                })}
              </div>

              {(() => {
                const curQ = questions[currentIdx];
                if (!curQ) return null;
                const chosenId = selectedAnswers[curQ.id];

                return (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                    {curQ.passage && (
                      <div
                        style={{
                          padding: '12px 14px',
                          borderRadius: 10,
                          background: 'rgba(255, 255, 255, 0.03)',
                          border: '1px solid rgba(255, 255, 255, 0.07)',
                          fontSize: '0.85rem',
                          color: 'var(--ink-muted)',
                          maxHeight: '120px',
                          overflowY: 'auto',
                          lineHeight: 1.5,
                        }}
                      >
                        <span style={{ fontWeight: 700, color: '#f59e0b', marginRight: 4 }}>📖 Matn:</span>
                        {curQ.passage}
                      </div>
                    )}

                    <div style={{ fontSize: '1.05rem', fontWeight: 700, lineHeight: 1.55, color: 'var(--ink)' }}>
                      <span style={{ color: '#10B981', marginRight: 6 }}>{currentIdx + 1}.</span>
                      {curQ.text}
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 6 }}>
                      {curQ.choices.map((c, ci) => {
                        const isChosen = chosenId === c.id;
                        const letter = String.fromCharCode(65 + ci);
                        return (
                          <button
                            key={c.id}
                            type="button"
                            onClick={() => handlePickChoice(curQ.id, c.id)}
                            style={{
                              padding: '12px 16px',
                              borderRadius: 12,
                              border: `1.5px solid ${isChosen ? '#10B981' : 'rgba(255, 255, 255, 0.08)'}`,
                              background: isChosen ? 'rgba(16, 185, 129, 0.15)' : 'rgba(255, 255, 255, 0.02)',
                              color: 'var(--ink)',
                              textAlign: 'left',
                              cursor: 'pointer',
                              display: 'flex',
                              alignItems: 'center',
                              gap: 12,
                              transition: 'all 0.15s ease',
                            }}
                          >
                            <span
                              style={{
                                width: 28,
                                height: 28,
                                borderRadius: 8,
                                background: isChosen ? '#10B981' : 'rgba(255, 255, 255, 0.08)',
                                color: isChosen ? '#111' : 'var(--ink)',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                fontWeight: 800,
                                fontSize: '0.88rem',
                              }}
                            >
                              {letter}
                            </span>
                            <span style={{ fontSize: '0.95rem', fontWeight: isChosen ? 600 : 400 }}>
                              {c.text}
                            </span>
                          </button>
                        );
                      })}
                    </div>

                    {/* Navigation Buttons */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 14 }}>
                      <button
                        type="button"
                        disabled={currentIdx === 0}
                        onClick={() => setCurrentIdx((i) => Math.max(0, i - 1))}
                        style={{
                          padding: '10px 16px',
                          borderRadius: 10,
                          border: '1px solid rgba(255, 255, 255, 0.1)',
                          background: 'transparent',
                          color: currentIdx === 0 ? 'rgba(255, 255, 255, 0.2)' : 'var(--ink)',
                          cursor: currentIdx === 0 ? 'not-allowed' : 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: 6,
                          fontWeight: 600,
                        }}
                      >
                        <ArrowLeft size={16} />
                        Oldingi
                      </button>

                      {currentIdx < questions.length - 1 ? (
                        <button
                          type="button"
                          onClick={() => setCurrentIdx((i) => Math.min(questions.length - 1, i + 1))}
                          style={{
                            padding: '10px 20px',
                            borderRadius: 10,
                            background: '#f59e0b',
                            border: 'none',
                            color: '#111',
                            fontWeight: 700,
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            gap: 6,
                          }}
                        >
                          Keyingi
                          <ArrowRight size={16} />
                        </button>
                      ) : (
                        <button
                          type="button"
                          disabled={submitting}
                          onClick={handleSubmitQuiz}
                          style={{
                            padding: '10px 22px',
                            borderRadius: 10,
                            background: 'linear-gradient(135deg, #10B981 0%, #059669 100%)',
                            border: 'none',
                            color: '#fff',
                            fontWeight: 800,
                            cursor: submitting ? 'not-allowed' : 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            gap: 6,
                            boxShadow: '0 4px 14px rgba(16, 185, 129, 0.4)',
                          }}
                        >
                          {submitting ? 'Hisoblanmoqda...' : 'Natijani hisoblash ✓'}
                        </button>
                      )}
                    </div>
                  </div>
                );
              })()}
            </div>
          )}

          {/* STEP 3: RESULT & AI PERSONALIZED ROADMAP */}
          {step === 'result' && submitResult && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
              {/* Score Banner */}
              <div
                style={{
                  padding: '20px',
                  borderRadius: 16,
                  background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.15) 0%, rgba(5, 150, 105, 0.05) 100%)',
                  border: '1px solid rgba(16, 185, 129, 0.3)',
                  textAlign: 'center',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: 8,
                }}
              >
                <div style={{ color: '#10B981', display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.85rem', fontWeight: 800 }}>
                  <CheckCircle2 size={18} />
                  DIAGNOSTIKA YAKUNLANDI
                </div>
                <div style={{ fontSize: '2rem', fontWeight: 900, color: 'var(--ink)' }}>
                  {submitResult.score} / {submitResult.total}
                  <span style={{ fontSize: '1.1rem', color: '#10B981', marginLeft: 8 }}>
                    ({submitResult.percentage}%)
                  </span>
                </div>
                <div
                  style={{
                    display: 'inline-block',
                    padding: '4px 14px',
                    borderRadius: 20,
                    background: '#10B981',
                    color: '#111',
                    fontWeight: 800,
                    fontSize: '0.88rem',
                  }}
                >
                  Boshlang'ich daraja: {submitResult.initial_level}
                </div>
              </div>

              {/* Study Plan Card */}
              <div
                style={{
                  padding: '18px',
                  borderRadius: 14,
                  background: 'rgba(255, 255, 255, 0.03)',
                  border: '1px solid rgba(255, 255, 255, 0.08)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 12,
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#f59e0b', fontWeight: 800, fontSize: '0.92rem' }}>
                  <Calendar size={18} />
                  <span>{submitResult.daily_plan?.schedule_label || "AI Shaxsiy Reja"}</span>
                </div>

                <p style={{ margin: 0, fontSize: '0.9rem', lineHeight: 1.55, color: 'var(--ink)' }}>
                  {submitResult.daily_plan?.advice}
                </p>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: 10, marginTop: 4 }}>
                  <div style={{ padding: '10px 12px', borderRadius: 10, background: 'rgba(255, 255, 255, 0.04)', textAlign: 'center' }}>
                    <span style={{ fontSize: '0.72rem', color: 'var(--ink-muted)' }}>Kunlik testlar</span>
                    <div style={{ fontSize: '1.1rem', fontWeight: 800, color: '#10B981', marginTop: 2 }}>
                      {submitResult.daily_plan?.tests_per_day} ta / kun
                    </div>
                  </div>
                  <div style={{ padding: '10px 12px', borderRadius: 10, background: 'rgba(255, 255, 255, 0.04)', textAlign: 'center' }}>
                    <span style={{ fontSize: '0.72rem', color: 'var(--ink-muted)' }}>Haftalik esselar</span>
                    <div style={{ fontSize: '1.1rem', fontWeight: 800, color: '#3B82F6', marginTop: 2 }}>
                      {submitResult.daily_plan?.essays_per_week} ta / hafta
                    </div>
                  </div>
                  <div style={{ padding: '10px 12px', borderRadius: 10, background: 'rgba(255, 255, 255, 0.04)', textAlign: 'center' }}>
                    <span style={{ fontSize: '0.72rem', color: 'var(--ink-muted)' }}>Kunlik vaqt</span>
                    <div style={{ fontSize: '1.1rem', fontWeight: 800, color: '#F59E0B', marginTop: 2 }}>
                      ~{submitResult.daily_plan?.daily_minutes} daqiqa
                    </div>
                  </div>
                </div>

                {submitResult.daily_plan?.focus_areas && submitResult.daily_plan.focus_areas.length > 0 && (
                  <div style={{ marginTop: 4 }}>
                    <span style={{ fontSize: '0.76rem', fontWeight: 700, color: 'var(--ink-muted)', display: 'block', marginBottom: 6 }}>
                      📌 E'tibor qaratiladigan mavzular:
                    </span>
                    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                      {submitResult.daily_plan.focus_areas.map((area, i) => (
                        <span
                          key={i}
                          style={{
                            fontSize: '0.78rem',
                            padding: '4px 10px',
                            borderRadius: 8,
                            background: 'rgba(255, 255, 255, 0.05)',
                            border: '1px solid rgba(255, 255, 255, 0.08)',
                            color: 'var(--ink)',
                          }}
                        >
                          {area}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Action Button */}
              <button
                type="button"
                onClick={handleFinish}
                style={{
                  width: '100%',
                  padding: '15px',
                  borderRadius: 12,
                  background: 'linear-gradient(135deg, #10B981 0%, #059669 100%)',
                  border: 'none',
                  color: '#fff',
                  fontWeight: 800,
                  fontSize: '1rem',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 8,
                  boxShadow: '0 8px 20px -4px rgba(16, 185, 129, 0.4)',
                }}
              >
                <span>Boshqaruv paneliga o'tish</span>
                <ArrowRight size={18} />
              </button>
            </div>
          )}
        </div>
      </motion.div>
    </div>
  );
}
