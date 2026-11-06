import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import confetti from 'canvas-confetti';
import { useAuth } from '../context/AuthContext';
import { api } from '../lib/api';

export interface OnboardingProps {
  isModal?: boolean;
  onClose?: () => void;
  onSuccess?: () => void;
}

type ActiveSubject = 'uzbek' | 'english' | 'biology' | 'chemistry' | 'law';
type TargetExam = 'milliy_sertifikat' | 'cefr' | 'ielts' | 'attestatsiya' | 'other';
type PrepLevel = 'zero' | 'beginner' | 'intermediate';
type ReminderSlot = 'morning' | 'afternoon' | 'evening';

const SUB_SUBJECTS = ['Matematika', 'Huquq', 'Tarix', 'Kimyo/Biologiya'] as const;

const STEP1_OPTIONS = [
  { id: 'tiktok_instagram', icon: '📱', title: 'TikTok / Instagram', subtitle: 'Ijtimoiy tarmoqlardagi videolar orqali' },
  { id: 'telegram', icon: '✈️', title: 'Telegram kanal yoki guruhdan', subtitle: 'Rasmiy kanallar va taʼlim guruhlaridan' },
  { id: 'google', icon: '🔍', title: 'Google Qidiruv', subtitle: 'Internet orqali qidirib topdim' },
  { id: 'friends', icon: '🤝', title: "Do'stlarim va tanishlarimdan", subtitle: 'Ustoz yoki kursdoshlarim tavsiya qildi' },
  { id: 'other', icon: '🌐', title: 'Boshqa manbadan', subtitle: "O'quv markazi, reklama yoki boshqa joydan" },
] as const;

const STEP2_OPTIONS = [
  {
    id: 'certificate',
    icon: '🏆',
    title: 'Davlat va xalqaro sertifikat olish (BMB / IELTS / CEFR)',
    subtitle: 'Rasmiy imtihondan yuqori daraja (A+, C1, Band 7.5+) olish',
  },
  {
    id: 'university_grant',
    icon: '🎓',
    title: 'Oliygohga grantga kirish va imtiyoz olish',
    subtitle: 'Maksimal ball va muddatidan oldin 100% imtiyozga ega boʻlish',
  },
  {
    id: 'attestation_bonus',
    icon: '📜',
    title: 'Attestatsiya va ustama (Pedagoglar uchun)',
    subtitle: 'Oliy toifa va 70% vazir jamgʻarmasi ustamasini qoʻlga kiritish',
  },
  {
    id: 'self_development',
    icon: '💡',
    title: 'Yangi bilim va shaxsiy rivojlanish',
    subtitle: 'Savodxonlik, nutq va akademik koʻnikmalarni oshirish',
  },
] as const;

const STEP3_OPTIONS: Array<{
  id: TargetExam;
  icon: string;
  title: string;
  subtitle: string;
  active_subject: ActiveSubject;
  target_exam: TargetExam;
}> = [
  {
    id: 'milliy_sertifikat',
    icon: '🇺🇿',
    title: '🇺🇿 Ona tili va Adabiyot (Milliy sertifikat)',
    subtitle: 'BMB 45 talik test va 12 mezonli AI Esse tahlili',
    active_subject: 'uzbek',
    target_exam: 'milliy_sertifikat',
  },
  {
    id: 'cefr',
    icon: '🇬🇧',
    title: '🇬🇧 Ingliz tili (CEFR Multi-level)',
    subtitle: 'B1, B2, C1 darajali CBT Mock, Writing va Speaking',
    active_subject: 'english',
    target_exam: 'cefr',
  },
  {
    id: 'ielts',
    icon: '🎓',
    title: '🎓 IELTS Academic / General',
    subtitle: 'Band 1.0–9.0 CD-IELTS simulyatori, Writing Task 1/2 va Speaking',
    active_subject: 'english',
    target_exam: 'ielts',
  },
  {
    id: 'attestatsiya',
    icon: '📜',
    title: '📜 Pedagoglar Attestatsiyasi',
    subtitle: '50 talik sinov, kasbiy standart va pedagogik mahorat testlari',
    active_subject: 'uzbek',
    target_exam: 'attestatsiya',
  },
  {
    id: 'other',
    icon: '📚',
    title: '📚 Boshqa fanlar (Matematika, Huquq, Tarix va b.)',
    subtitle: 'Qoʻshimcha majburiy va mutaxassislik fanlaridan tayyorgarlik',
    active_subject: 'uzbek',
    target_exam: 'other',
  },
];

const STEP4_OPTIONS: Array<{
  id: PrepLevel;
  icon: string;
  title: string;
  subtitle: string;
}> = [
  {
    id: 'zero',
    icon: '🌱',
    title: '🌱 Nol darajadaman (Yangi boshlovchi)',
    subtitle: 'Endi boshlayapman, tartibli poydevor va tushuntirish kerak',
  },
  {
    id: 'beginner',
    icon: '⚡',
    title: "⚡ Boshlang'ich tushuncham bor",
    subtitle: 'Qoidalarni bilaman, lekin test va inshoda amaliyot kam',
  },
  {
    id: 'intermediate',
    icon: '🔥',
    title: "🔥 O'rta darajadaman (Mock ishlaganman)",
    subtitle: 'Zaif mavzularimni aniqlab, natijamni A+ / C1 darajaga koʻtarmoqchiman',
  },
];

const STEP5_OPTIONS: Array<{
  minutes: number;
  icon: string;
  title: string;
  subtitle: string;
}> = [
  { minutes: 5, icon: '⏱', title: '⏱ Kuniga 5 daqiqa (Oson)', subtitle: 'Har kuni bitta tezkor mashq' },
  { minutes: 15, icon: '⚡', title: "⚡ Kuniga 15 daqiqa (O'rtacha)", subtitle: 'Barqaror oʻsish uchun tavsiya etiladi' },
  { minutes: 30, icon: '🔥', title: '🔥 Kuniga 30 daqiqa (Jiddiy)', subtitle: 'Tezkor natija va toʻliq boʻlim tahlili' },
  { minutes: 60, icon: '🚀', title: '🚀 Kuniga 1 soat (Intensiv)', subtitle: 'Maksimal sprint va toʻliq Mock imtihonlar' },
];

const STEP6_OPTIONS: Array<{
  id: ReminderSlot;
  icon: string;
  title: string;
  subtitle: string;
}> = [
  { id: 'morning', icon: '🌅', title: '🌅 Ertalab (08:00 - 12:00)', subtitle: 'Kunni tetik va samarali mashq bilan boshlash' },
  { id: 'afternoon', icon: '☀️', title: '☀️ Tushdan keyin (12:00 - 18:00)', subtitle: 'Darsdan soʻng tanaffus paytida shugʻullanish' },
  { id: 'evening', icon: '🌙', title: '🌙 Kechqurun (18:00 - 22:00)', subtitle: 'Kechki sokin vaqtda tahlil va insho yozish' },
];

const STEP_TITLES: Record<number, string> = {
  1: 'Biz haqimizda qayerdan eshitdingiz?',
  2: 'Asosiy maqsadingiz nima?',
  3: "Qaysi yo'nalishga tayyorlanmoqchisiz?",
  4: 'Tayyorgarlik darajangiz qanday?',
  5: 'Kuniga qancha vaqt ajrata olasiz?',
  6: 'Eslatmalarni qaysi vaqtda olishni xohlaysiz?',
};

export default function Onboarding({ isModal = false, onClose, onSuccess }: OnboardingProps) {
  const navigate = useNavigate();
  const { user, updateUser } = useAuth();

  const [step, setStep] = useState<number>(1);
  const [referralSource, setReferralSource] = useState<string>('');
  const [mainGoal, setMainGoal] = useState<string>('');
  const [targetExam, setTargetExam] = useState<TargetExam | ''>('');
  const [activeSubject, setActiveSubject] = useState<ActiveSubject>('uzbek');
  const [subSubject, setSubSubject] = useState<string>('Matematika');
  const [level, setLevel] = useState<PrepLevel | ''>('');
  const [dailyGoalMinutes, setDailyGoalMinutes] = useState<number | null>(null);
  const [reminderSlot, setReminderSlot] = useState<ReminderSlot | ''>('');
  const [celebrating, setCelebrating] = useState<boolean>(false);
  const [submitting, setSubmitting] = useState<boolean>(false);

  const isStepValid = (): boolean => {
    if (step === 1) return Boolean(referralSource);
    if (step === 2) return Boolean(mainGoal);
    if (step === 3) {
      if (!targetExam) return false;
      if (targetExam === 'other') return Boolean(subSubject);
      return true;
    }
    if (step === 4) return Boolean(level);
    if (step === 5) return dailyGoalMinutes !== null;
    if (step === 6) return Boolean(reminderSlot);
    return false;
  };

  const handleBack = () => {
    if (celebrating || submitting) return;
    if (step > 1) {
      setStep((s) => s - 1);
      return;
    }
    if (isModal && onClose) {
      onClose();
    } else {
      navigate('/dashboard', { replace: true });
    }
  };

  const submitOnboardingPayload = async (payload: Record<string, unknown>) => {
    const endpoints = [
      '/api/v1/users/onboarding/',
      '/v1/users/onboarding/',
      '/api/auth/onboarding/',
      '/auth/onboarding/',
    ];
    for (const ep of endpoints) {
      try {
        await api.post(ep, payload);
        return;
      } catch {
        // try next fallback endpoint
      }
    }
  };

  const handleNextOrFinish = async () => {
    if (!isStepValid() || submitting || celebrating) return;

    if (step < 6) {
      setStep((s) => s + 1);
      return;
    }

    // Step 6 -> Finish & Celebrate
    setSubmitting(true);
    setCelebrating(true);

    try {
      confetti({
        particleCount: 80,
        spread: 70,
        origin: { y: 0.6 },
        colors: ['#C8922A', '#F59E0B', '#10B981', '#FBBF24'],
      });
    } catch {
      /* ignore confetti error */
    }

    const finalExam: TargetExam = (targetExam as TargetExam) || 'milliy_sertifikat';
    let finalSubject: ActiveSubject = activeSubject || 'uzbek';
    if (finalExam === 'other') {
      if (subSubject === 'Huquq') finalSubject = 'law';
      else if (subSubject === 'Kimyo/Biologiya') finalSubject = 'biology';
    }
    const finalMinutes = dailyGoalMinutes ?? 15;
    const finalSubSubject = finalExam === 'other' ? subSubject || 'Matematika' : '';

    const payload = {
      referral_source: referralSource,
      main_goal: mainGoal,
      active_subject: finalSubject,
      target_exam: finalExam,
      exam_target: finalExam,
      sub_subject: finalSubSubject,
      level: level || 'beginner',
      daily_goal_minutes: finalMinutes,
      reminder_slot: reminderSlot || 'evening',
    };

    try {
      localStorage.setItem('active_subject', finalSubject);
      localStorage.setItem('lms_subject', finalSubject);
      localStorage.setItem('landing_subject', finalSubject);
      localStorage.setItem('grand_ed_onboarding_done', 'true');
      localStorage.setItem('grandec_onboarding_done', 'true');
      localStorage.setItem('onboarding_dismissed', 'true');
      localStorage.setItem(
        'grandec_user_plan',
        JSON.stringify({
          ...payload,
          completed_minutes: 0,
          updated_at: new Date().toISOString(),
        }),
      );
      window.dispatchEvent(new CustomEvent('subject-changed', { detail: finalSubject }));
    } catch {
      /* ignore storage errors */
    }

    void submitOnboardingPayload(payload);

    updateUser({
      ...(user || {}),
      onboarding_completed: true,
      active_subject: finalSubject,
      exam_target: finalExam,
      target_exam: finalExam,
      sub_subject: finalSubSubject,
      level: level || 'beginner',
      daily_goal_minutes: finalMinutes,
      reminder_slot: reminderSlot || 'evening',
      daily_plan_summary: {
        ...(user?.daily_plan_summary || {}),
        daily_minutes: finalMinutes,
        target_exam: finalExam,
        sub_subject: finalSubSubject,
        level: level || 'beginner',
        reminder_slot: reminderSlot || 'evening',
      },
    });

    await new Promise((resolve) => setTimeout(resolve, 1200));

    setSubmitting(false);
    if (onSuccess) onSuccess();
    if (onClose) onClose();
    navigate('/dashboard', { replace: true });
  };

  const progressPercent = celebrating ? 100 : Math.round((step / 6) * 100);

  return (
    <div
      className="onb-root"
      style={{
        minHeight: isModal ? '100%' : '100dvh',
        width: '100%',
        background: 'var(--bg-page, var(--bg))',
        color: 'var(--text-primary, var(--ink))',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '20px 16px 28px',
        boxSizing: 'border-box',
      }}
    >
      <style>{`
        .onb-card {
          width: 100%;
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 14px;
          padding: 15px 18px;
          border-radius: 16px;
          background: var(--bg-card, var(--card));
          border: 1.5px solid var(--border-default, var(--border));
          color: var(--text-primary, var(--ink));
          text-align: left;
          cursor: pointer;
          transition: transform 0.18s ease, border-color 0.18s ease, background-color 0.18s ease, box-shadow 0.18s ease;
          box-shadow: 0 2px 10px rgba(0, 0, 0, 0.04);
        }
        .onb-card:hover {
          transform: translateY(-1px);
          border-color: rgba(200, 146, 42, 0.65);
        }
        .onb-card:active {
          transform: translateY(0);
        }
        .onb-card.is-selected {
          border: 2px solid #C8922A;
          background: rgba(200, 146, 42, 0.12);
          box-shadow: 0 8px 24px -6px rgba(200, 146, 42, 0.28);
        }
        .onb-subpill {
          padding: 8px 14px;
          border-radius: 999px;
          font-size: 13px;
          font-weight: 800;
          cursor: pointer;
          transition: all 0.15s ease;
          border: 1.5px solid rgba(200, 146, 42, 0.45);
          background: var(--bg-card, var(--card));
          color: var(--text-primary, var(--ink));
        }
        .onb-subpill.is-active {
          background: linear-gradient(135deg, #C8922A 0%, #F59E0B 100%);
          border-color: #C8922A;
          color: #FFFFFF;
          box-shadow: 0 4px 12px rgba(200, 146, 42, 0.35);
        }
      `}</style>

      {/* TOP HEADER BAR */}
      <header
        style={{
          width: '100%',
          maxWidth: 620,
          display: 'flex',
          flexDirection: 'column',
          gap: 12,
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 12,
          }}
        >
          <button
            type="button"
            onClick={handleBack}
            aria-label="Orqaga"
            title="Orqaga"
            style={{
              width: 40,
              height: 40,
              borderRadius: 12,
              border: '1.5px solid var(--border-default, var(--border))',
              background: 'var(--bg-card, var(--card))',
              color: 'var(--text-primary, var(--ink))',
              fontSize: 18,
              fontWeight: 800,
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
              flexShrink: 0,
            }}
          >
            &lt;
          </button>

          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              flexWrap: 'wrap',
              justifyContent: 'center',
            }}
          >
            <span
              style={{
                fontSize: 12,
                fontWeight: 800,
                letterSpacing: '0.08em',
                color: 'var(--text-secondary, var(--muted))',
                textTransform: 'uppercase',
              }}
            >
              {step}-SAVOL / 6
            </span>
            <span
              style={{
                fontSize: 11,
                fontWeight: 900,
                letterSpacing: '0.1em',
                padding: '4px 10px',
                borderRadius: 999,
                background: 'rgba(200, 146, 42, 0.15)',
                border: '1px solid rgba(200, 146, 42, 0.45)',
                color: '#C8922A',
                textTransform: 'uppercase',
              }}
            >
              SO&apos;ROVNOMA
            </span>
          </div>

          <div style={{ width: 40, height: 40, flexShrink: 0 }} aria-hidden="true" />
        </div>

        {/* 60fps Gold Progress Bar */}
        <div
          role="progressbar"
          aria-valuenow={progressPercent}
          aria-valuemin={0}
          aria-valuemax={100}
          style={{
            width: '100%',
            height: 10,
            borderRadius: 999,
            background: 'var(--bg-card-2, var(--card-2))',
            border: '1px solid var(--border-default, var(--border))',
            overflow: 'hidden',
          }}
        >
          <div
            style={{
              width: `${progressPercent}%`,
              height: '100%',
              borderRadius: 999,
              background: 'linear-gradient(90deg, #C8922A, #F59E0B)',
              transition: 'width 0.35s cubic-bezier(0.22, 1, 0.36, 1)',
            }}
          />
        </div>
      </header>

      {/* MAIN QUESTION / CELEBRATION BODY */}
      <main
        style={{
          width: '100%',
          maxWidth: 620,
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          padding: '24px 0',
        }}
      >
        {celebrating ? (
          <div
            role="status"
            aria-live="polite"
            style={{
              background: 'var(--bg-card, var(--card))',
              border: '2px solid #C8922A',
              borderRadius: 24,
              padding: '44px 28px',
              textAlign: 'center',
              boxShadow: '0 20px 50px -12px rgba(200, 146, 42, 0.25)',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              gap: 16,
            }}
          >
            <div
              style={{
                width: 76,
                height: 76,
                borderRadius: '50%',
                background: 'rgba(200, 146, 42, 0.16)',
                border: '2px solid #C8922A',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 38,
              }}
            >
              🎉
            </div>
            <h2
              style={{
                margin: 0,
                fontSize: 'clamp(1.35rem, 3.5vw, 1.75rem)',
                fontWeight: 900,
                color: 'var(--text-primary, var(--ink))',
                lineHeight: 1.3,
              }}
            >
              Ajoyib! Hammasi tayyor. Siz uchun shaxsiy reja tayyorlanmoqda...
            </h2>
            <p
              style={{
                margin: 0,
                fontSize: 14,
                color: 'var(--text-secondary, var(--muted))',
              }}
            >
              Tanlangan yoʻnalish va kunlik maqsadingiz asosida mashqlar moslashtirildi.
            </p>
          </div>
        ) : (
          <div>
            <h1
              style={{
                margin: '0 0 22px',
                fontSize: 'clamp(1.4rem, 4vw, 1.95rem)',
                fontWeight: 900,
                letterSpacing: '-0.02em',
                color: 'var(--text-primary, var(--ink))',
                lineHeight: 1.25,
              }}
            >
              {STEP_TITLES[step]}
            </h1>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {/* STEP 1 */}
              {step === 1 &&
                STEP1_OPTIONS.map((opt) => {
                  const selected = referralSource === opt.id;
                  return (
                    <button
                      key={opt.id}
                      type="button"
                      className={`onb-card${selected ? ' is-selected' : ''}`}
                      onClick={() => setReferralSource(opt.id)}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: 14, minWidth: 0 }}>
                        <span
                          style={{
                            width: 44,
                            height: 44,
                            borderRadius: 12,
                            background: selected ? 'rgba(200, 146, 42, 0.2)' : 'var(--bg-card-2, var(--card-2))',
                            display: 'inline-flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            fontSize: 22,
                            flexShrink: 0,
                          }}
                        >
                          {opt.icon}
                        </span>
                        <div style={{ minWidth: 0 }}>
                          <div style={{ fontSize: 15, fontWeight: 800, color: 'var(--text-primary, var(--ink))' }}>
                            {opt.title}
                          </div>
                          <div style={{ fontSize: 12.5, color: 'var(--text-secondary, var(--muted))', marginTop: 2 }}>
                            {opt.subtitle}
                          </div>
                        </div>
                      </div>
                      <RadioIndicator selected={selected} />
                    </button>
                  );
                })}

              {/* STEP 2 */}
              {step === 2 &&
                STEP2_OPTIONS.map((opt) => {
                  const selected = mainGoal === opt.id;
                  return (
                    <button
                      key={opt.id}
                      type="button"
                      className={`onb-card${selected ? ' is-selected' : ''}`}
                      onClick={() => setMainGoal(opt.id)}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: 14, minWidth: 0 }}>
                        <span
                          style={{
                            width: 44,
                            height: 44,
                            borderRadius: 12,
                            background: selected ? 'rgba(200, 146, 42, 0.2)' : 'var(--bg-card-2, var(--card-2))',
                            display: 'inline-flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            fontSize: 22,
                            flexShrink: 0,
                          }}
                        >
                          {opt.icon}
                        </span>
                        <div style={{ minWidth: 0 }}>
                          <div style={{ fontSize: 15, fontWeight: 800, color: 'var(--text-primary, var(--ink))' }}>
                            {opt.title}
                          </div>
                          <div style={{ fontSize: 12.5, color: 'var(--text-secondary, var(--muted))', marginTop: 2 }}>
                            {opt.subtitle}
                          </div>
                        </div>
                      </div>
                      <RadioIndicator selected={selected} />
                    </button>
                  );
                })}

              {/* STEP 3 */}
              {step === 3 &&
                STEP3_OPTIONS.map((opt) => {
                  const selected = targetExam === opt.id;
                  return (
                    <div key={opt.id} style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                      <button
                        type="button"
                        className={`onb-card${selected ? ' is-selected' : ''}`}
                        onClick={() => {
                          setTargetExam(opt.target_exam);
                          setActiveSubject(opt.active_subject);
                          if (opt.target_exam === 'other' && !subSubject) {
                            setSubSubject('Matematika');
                          }
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: 14, minWidth: 0 }}>
                          <span
                            style={{
                              width: 44,
                              height: 44,
                              borderRadius: 12,
                              background: selected ? 'rgba(200, 146, 42, 0.2)' : 'var(--bg-card-2, var(--card-2))',
                              display: 'inline-flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              fontSize: 22,
                              flexShrink: 0,
                            }}
                          >
                            {opt.icon}
                          </span>
                          <div style={{ minWidth: 0 }}>
                            <div style={{ fontSize: 15, fontWeight: 800, color: 'var(--text-primary, var(--ink))' }}>
                              {opt.title}
                            </div>
                            <div style={{ fontSize: 12.5, color: 'var(--text-secondary, var(--muted))', marginTop: 2 }}>
                              {opt.subtitle}
                            </div>
                          </div>
                        </div>
                        <RadioIndicator selected={selected} />
                      </button>

                      {/* Nested Sub-Subject Gold Pills when "Boshqa fanlar..." is selected */}
                      {opt.id === 'other' && selected && (
                        <div
                          style={{
                            padding: '12px 16px',
                            borderRadius: 14,
                            background: 'rgba(200, 146, 42, 0.08)',
                            border: '1.5px dashed #C8922A',
                            display: 'flex',
                            flexDirection: 'column',
                            gap: 8,
                          }}
                        >
                          <span
                            style={{
                              fontSize: 12,
                              fontWeight: 800,
                              color: '#C8922A',
                            }}
                          >
                            Fan yoʻnalishini tanlang:
                          </span>
                          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                            {SUB_SUBJECTS.map((sub) => {
                              const isSubActive = subSubject === sub;
                              return (
                                <button
                                  key={sub}
                                  type="button"
                                  className={`onb-subpill${isSubActive ? ' is-active' : ''}`}
                                  onClick={() => setSubSubject(sub)}
                                >
                                  {isSubActive ? `✓ ${sub}` : sub}
                                </button>
                              );
                            })}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}

              {/* STEP 4 */}
              {step === 4 &&
                STEP4_OPTIONS.map((opt) => {
                  const selected = level === opt.id;
                  return (
                    <button
                      key={opt.id}
                      type="button"
                      className={`onb-card${selected ? ' is-selected' : ''}`}
                      onClick={() => setLevel(opt.id)}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: 14, minWidth: 0 }}>
                        <span
                          style={{
                            width: 44,
                            height: 44,
                            borderRadius: 12,
                            background: selected ? 'rgba(200, 146, 42, 0.2)' : 'var(--bg-card-2, var(--card-2))',
                            display: 'inline-flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            fontSize: 22,
                            flexShrink: 0,
                          }}
                        >
                          {opt.icon}
                        </span>
                        <div style={{ minWidth: 0 }}>
                          <div style={{ fontSize: 15, fontWeight: 800, color: 'var(--text-primary, var(--ink))' }}>
                            {opt.title}
                          </div>
                          <div style={{ fontSize: 12.5, color: 'var(--text-secondary, var(--muted))', marginTop: 2 }}>
                            {opt.subtitle}
                          </div>
                        </div>
                      </div>
                      <RadioIndicator selected={selected} />
                    </button>
                  );
                })}

              {/* STEP 5 */}
              {step === 5 &&
                STEP5_OPTIONS.map((opt) => {
                  const selected = dailyGoalMinutes === opt.minutes;
                  return (
                    <button
                      key={opt.minutes}
                      type="button"
                      className={`onb-card${selected ? ' is-selected' : ''}`}
                      onClick={() => setDailyGoalMinutes(opt.minutes)}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: 14, minWidth: 0 }}>
                        <span
                          style={{
                            width: 44,
                            height: 44,
                            borderRadius: 12,
                            background: selected ? 'rgba(200, 146, 42, 0.2)' : 'var(--bg-card-2, var(--card-2))',
                            display: 'inline-flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            fontSize: 22,
                            flexShrink: 0,
                          }}
                        >
                          {opt.icon}
                        </span>
                        <div style={{ minWidth: 0 }}>
                          <div style={{ fontSize: 15, fontWeight: 800, color: 'var(--text-primary, var(--ink))' }}>
                            {opt.title}
                          </div>
                          <div style={{ fontSize: 12.5, color: 'var(--text-secondary, var(--muted))', marginTop: 2 }}>
                            {opt.subtitle}
                          </div>
                        </div>
                      </div>
                      <RadioIndicator selected={selected} />
                    </button>
                  );
                })}

              {/* STEP 6 */}
              {step === 6 &&
                STEP6_OPTIONS.map((opt) => {
                  const selected = reminderSlot === opt.id;
                  return (
                    <button
                      key={opt.id}
                      type="button"
                      className={`onb-card${selected ? ' is-selected' : ''}`}
                      onClick={() => setReminderSlot(opt.id)}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: 14, minWidth: 0 }}>
                        <span
                          style={{
                            width: 44,
                            height: 44,
                            borderRadius: 12,
                            background: selected ? 'rgba(200, 146, 42, 0.2)' : 'var(--bg-card-2, var(--card-2))',
                            display: 'inline-flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            fontSize: 22,
                            flexShrink: 0,
                          }}
                        >
                          {opt.icon}
                        </span>
                        <div style={{ minWidth: 0 }}>
                          <div style={{ fontSize: 15, fontWeight: 800, color: 'var(--text-primary, var(--ink))' }}>
                            {opt.title}
                          </div>
                          <div style={{ fontSize: 12.5, color: 'var(--text-secondary, var(--muted))', marginTop: 2 }}>
                            {opt.subtitle}
                          </div>
                        </div>
                      </div>
                      <RadioIndicator selected={selected} />
                    </button>
                  );
                })}
            </div>
          </div>
        )}
      </main>

      {/* BOTTOM CTA BUTTON */}
      {!celebrating && (
        <footer
          style={{
            width: '100%',
            maxWidth: 620,
            paddingTop: 12,
          }}
        >
          <button
            type="button"
            disabled={!isStepValid() || submitting}
            onClick={() => void handleNextOrFinish()}
            style={{
              width: '100%',
              minHeight: 54,
              borderRadius: 16,
              border: 'none',
              fontSize: 15,
              fontWeight: 900,
              letterSpacing: '0.06em',
              textTransform: 'uppercase',
              cursor: isStepValid() && !submitting ? 'pointer' : 'not-allowed',
              background: isStepValid()
                ? 'linear-gradient(135deg, #C8922A 0%, #F59E0B 100%)'
                : 'var(--bg-card-2, var(--card-2))',
              color: isStepValid() ? '#FFFFFF' : 'var(--text-secondary, var(--muted))',
              boxShadow: isStepValid() ? '0 10px 26px -6px rgba(200, 146, 42, 0.5)' : 'none',
              opacity: isStepValid() ? 1 : 0.65,
              transition: 'all 0.2s ease',
            }}
          >
            {step < 6 ? 'DAVOM ETISH' : 'YAKUNLASH'}
          </button>
        </footer>
      )}
    </div>
  );
}

function RadioIndicator({ selected }: { selected: boolean }) {
  return (
    <span
      aria-hidden="true"
      style={{
        width: 26,
        height: 26,
        borderRadius: '50%',
        border: selected ? '2px solid #C8922A' : '2px solid var(--border-default, var(--border))',
        background: selected ? '#C8922A' : 'transparent',
        color: '#FFFFFF',
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontSize: 14,
        fontWeight: 900,
        flexShrink: 0,
        transition: 'all 0.18s ease',
      }}
    >
      {selected ? '✓' : ''}
    </span>
  );
}
