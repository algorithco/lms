import { useState, useEffect } from 'react';
import type { ReactNode } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { CheckIcon } from './icons';
import { useLang } from '../i18n/LangContext';
import { useTheme } from '../theme/ThemeContext';

interface HeroCarouselProps {
  onAction: (path: string) => void;
}

interface SlideData {
  id: number;
  badge: string;
  badgeIcon: string;
  badgeColor: string;
  title: string;
  subtitle: string;
  ctaText: string;
  ctaPath: string;
  renderVisual: () => ReactNode;
}

export default function HeroCarousel({ onAction }: HeroCarouselProps) {
  const { t } = useLang();
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme !== 'light';

  const [current, setCurrent] = useState(0);
  const [direction, setDirection] = useState(1);
  const [isPaused, setIsPaused] = useState(false);

  const slides: SlideData[] = [
    // 1-Slayd: AI Esse Baholash
    {
      id: 1,
      badge: t('carousel.slide1_badge', 'BMB 12 Mezon Rasmiy Tahlili'),
      badgeIcon: '✍️',
      badgeColor: '#D97706',
      title: t('carousel.slide1_title', 'Inshongizni 15 soniyada rasmiy BMB mezonlari asosida tekshiring'),
      subtitle: t(
        'carousel.slide1_subtitle',
        'Sunʼiy intellekt har bir jumla, leksika va fikriy mantiqni Davlat BMB komissiyasi standartida baholaydi.'
      ),
      ctaText: t('carousel.slide1_cta', 'Esse yozib ko‘rish →'),
      ctaPath: '/essays',
      renderVisual: () => (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {/* Result card top */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '12px 16px',
              borderRadius: 14,
              background: isDark ? 'rgba(245, 158, 11, 0.12)' : 'rgba(245, 158, 11, 0.08)',
              border: isDark ? '1px solid rgba(245, 158, 11, 0.35)' : '1px solid rgba(245, 158, 11, 0.3)',
            }}
          >
            <div>
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 700,
                  color: '#F59E0B',
                  textTransform: 'uppercase',
                  letterSpacing: '0.06em',
                }}
              >
                {t('carousel.slide1_res_title', 'BMB Insho Natijasi')}
              </span>
              <div
                style={{
                  fontSize: 24,
                  fontWeight: 900,
                  color: isDark ? '#FFFFFF' : '#0F172A',
                  display: 'flex',
                  alignItems: 'baseline',
                  gap: 6,
                }}
              >
                54.5{' '}
                <span style={{ fontSize: 14, color: isDark ? '#94A3B8' : '#64748B' }}>
                  / 60 {t('carousel.slide1_res_points', 'ball')}
                </span>
              </div>
            </div>
            <div
              style={{
                padding: '6px 14px',
                borderRadius: 999,
                background: isDark ? 'rgba(16, 185, 129, 0.18)' : 'rgba(16, 185, 129, 0.12)',
                border: isDark ? '1px solid rgba(16, 185, 129, 0.4)' : '1px solid rgba(16, 185, 129, 0.35)',
                color: isDark ? '#34D399' : '#059669',
                fontSize: 12,
                fontWeight: 800,
              }}
            >
              ⭐ A+ (90.8%)
            </div>
          </div>

          {/* 3 Criteria bars */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {[
              {
                label: t('carousel.slide1_crit1', 'Mazmun va mavzuning to‘liq ochilishi'),
                score: '19.0 / 20',
                pct: 95,
                color: '#059669',
              },
              {
                label: t('carousel.slide1_crit2', 'Uslubiy ravonlik va boy so‘z boyligi'),
                score: '18.5 / 20',
                pct: 92,
                color: '#D97706',
              },
              {
                label: t('carousel.slide1_crit3', 'Imlo, grammatika va tinish belgilari'),
                score: '17.0 / 20',
                pct: 85,
                color: '#0284C7',
              },
            ].map((crit, i) => (
              <div
                key={i}
                style={{
                  padding: '8px 12px',
                  borderRadius: 10,
                  background: isDark ? '#1E293B' : '#F8FAFC',
                  border: isDark ? '1px solid rgba(255, 255, 255, 0.08)' : '1px solid rgba(226, 232, 240, 0.9)',
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    fontSize: 11.5,
                    fontWeight: 600,
                    color: isDark ? '#F1F5F9' : '#1E293B',
                    marginBottom: 4,
                  }}
                >
                  <span>{crit.label}</span>
                  <span style={{ color: crit.color, fontWeight: 800 }}>{crit.score}</span>
                </div>
                <div
                  style={{
                    width: '100%',
                    height: 6,
                    borderRadius: 3,
                    background: isDark ? 'rgba(255, 255, 255, 0.1)' : 'rgba(226, 232, 240, 0.8)',
                    overflow: 'hidden',
                  }}
                >
                  <div style={{ width: `${crit.pct}%`, height: '100%', background: crit.color, borderRadius: 3 }} />
                </div>
              </div>
            ))}
          </div>

          {/* Advice card */}
          <div
            style={{
              padding: '10px 14px',
              borderRadius: 12,
              background: isDark ? 'rgba(16, 185, 129, 0.12)' : 'rgba(16, 185, 129, 0.08)',
              border: isDark ? '1px solid rgba(16, 185, 129, 0.3)' : '1px solid rgba(16, 185, 129, 0.25)',
              fontSize: 12,
              lineHeight: 1.5,
              color: isDark ? '#34D399' : '#065F46',
            }}
          >
            <strong>{t('carousel.slide1_ai_tip_label', '💡 AI Tavsiyasi:')}</strong>{' '}
            &ldquo;{t('carousel.slide1_ai_tip_text', 'Xulosa qismida Navoiy qarashlari mukammal tahlil etilgan. Grammatik xatolar 0 ta, leksik boylik yuqori.')}&rdquo;
          </div>
        </div>
      ),
    },

    // 2-Slayd: CBT Milliy Sertifikat Test Simulyatori
    {
      id: 2,
      badge: t('carousel.slide2_badge', 'CBT Davlat Formati • 2026'),
      badgeIcon: '📝',
      badgeColor: '#059669',
      title: t('carousel.slide2_title', 'Haqiqiy davlat imtihoni muhiti va vaqt nazorati'),
      subtitle: t(
        'carousel.slide2_subtitle',
        'Kompensatsiyalangan qatʼiy taymer, rasmiy 45 talik savollar va test yakunlanishi bilan bir zumda batafsil tahlil.'
      ),
      ctaText: t('carousel.slide2_cta', 'Testni boshlash →'),
      ctaPath: '/tests',
      renderVisual: () => (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {/* CBT top bar */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '9px 14px',
              borderRadius: 12,
              background: isDark ? '#1E293B' : '#F8FAFC',
              border: isDark ? '1px solid rgba(255, 255, 255, 0.08)' : '1px solid rgba(226, 232, 240, 0.95)',
              fontSize: 12,
              fontWeight: 700,
            }}
          >
            <span style={{ color: isDark ? '#F1F5F9' : '#0F172A' }}>
              {t('carousel.slide2_subject', 'Ona tili va Adabiyot (BMB-101)')}
            </span>
            <span style={{ color: '#D97706', fontFamily: 'monospace', fontSize: 13, fontWeight: 800 }}>⏱ 01:28:45</span>
          </div>

          {/* Question preview box */}
          <div
            style={{
              padding: '14px 16px',
              borderRadius: 14,
              background: isDark ? '#1E293B' : '#FFFFFF',
              border: isDark ? '1px solid rgba(255, 255, 255, 0.08)' : '1px solid rgba(226, 232, 240, 0.95)',
              boxShadow: isDark ? '0 4px 14px rgba(0, 0, 0, 0.3)' : '0 4px 14px rgba(0, 0, 0, 0.03)',
            }}
          >
            <div style={{ fontSize: 11, color: '#D97706', fontWeight: 800, textTransform: 'uppercase', marginBottom: 4 }}>
              {t('carousel.slide2_q_num', '14-Savol (Badiiy tahlil)')}
            </div>
            <p
              style={{
                fontSize: 12.5,
                color: isDark ? '#FFFFFF' : '#0F172A',
                fontWeight: 600,
                margin: '0 0 10px',
                lineHeight: 1.45,
              }}
            >
              {t('carousel.slide2_q_text', 'Navoiyning "Hayrat ul-abror" dostonidagi durroj masalining bosh g‘oyasi nimaga qaratilgan?')}
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {[
                { key: 'A', text: t('carousel.slide2_opt_a', 'Ilm-ma’rifatga intilish'), correct: false },
                {
                  key: 'B',
                  text: t('carousel.slide2_opt_b', 'Tilni tiyish va noo‘rin so‘zlashdan saqlanish'),
                  correct: true,
                },
                { key: 'C', text: t('carousel.slide2_opt_c', 'Saxovat va mehmondo‘stlik odobi'), correct: false },
              ].map((opt) => (
                <div
                  key={opt.key}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    padding: '7px 10px',
                    borderRadius: 8,
                    fontSize: 11.5,
                    fontWeight: 600,
                    background: opt.correct
                      ? isDark
                        ? 'rgba(16, 185, 129, 0.18)'
                        : 'rgba(16, 185, 129, 0.12)'
                      : isDark
                      ? '#0F172A'
                      : '#F8FAFC',
                    border: opt.correct
                      ? isDark
                        ? '1px solid rgba(16, 185, 129, 0.45)'
                        : '1px solid rgba(16, 185, 129, 0.4)'
                      : isDark
                      ? '1px solid rgba(255, 255, 255, 0.06)'
                      : '1px solid rgba(226, 232, 240, 0.85)',
                    color: opt.correct ? (isDark ? '#6EE7B7' : '#065F46') : isDark ? '#CBD5E1' : '#475569',
                  }}
                >
                  <span
                    style={{
                      width: 18,
                      height: 18,
                      borderRadius: 999,
                      background: opt.correct ? '#059669' : isDark ? 'rgba(255, 255, 255, 0.12)' : 'rgba(100, 116, 139, 0.15)',
                      color: opt.correct ? '#FFFFFF' : isDark ? '#CBD5E1' : '#475569',
                      fontSize: 10,
                      fontWeight: 800,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    {opt.key}
                  </span>
                  <span>{opt.text}</span>
                  {opt.correct && <CheckIcon size={14} style={{ marginLeft: 'auto', color: '#059669' }} />}
                </div>
              ))}
            </div>
          </div>

          {/* Quick analysis badge */}
          <div
            style={{
              padding: '8px 12px',
              borderRadius: 10,
              background: isDark ? 'rgba(16, 185, 129, 0.15)' : 'rgba(16, 185, 129, 0.1)',
              border: isDark ? '1px solid rgba(16, 185, 129, 0.35)' : '1px solid rgba(16, 185, 129, 0.28)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              fontSize: 12,
              fontWeight: 700,
              color: isDark ? '#6EE7B7' : '#065F46',
            }}
          >
            <span>{t('carousel.slide2_stat_correct', '🎯 42/45 to‘g‘ri (93.3%)')}</span>
            <span style={{ fontSize: 11, color: isDark ? '#34D399' : '#047857', fontWeight: 800 }}>
              {t('carousel.slide2_grade_guarantee', 'A Daraja kafolatlangan')}
            </span>
          </div>
        </div>
      ),
    },

    // 3-Slayd: Jonli 1v1 Arena Bellashuvi
    {
      id: 3,
      badge: t('carousel.slide3_badge', 'PvP Bilim Jangi • Real-vaqt'),
      badgeIcon: '⚔️',
      badgeColor: '#0284C7',
      title: t('carousel.slide3_title', 'O‘zbekiston bo‘yicha tengdoshlaringiz bilan 60 soniyalik bilim jangi'),
      subtitle: t(
        'carousel.slide3_subtitle',
        'Jonli ELO reytingi, raqobat ruhi va har bir to‘g‘ri javob uchun tezkor ochkolar bilan bilimingizni charxlang.'
      ),
      ctaText: t('carousel.slide3_cta', 'Arenada bellashish ⚔️'),
      ctaPath: '/arena',
      renderVisual: () => (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {/* Live battle banner */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '10px 14px',
              borderRadius: 12,
              background: isDark
                ? 'linear-gradient(135deg, rgba(245, 158, 11, 0.18), rgba(2, 132, 199, 0.16))'
                : 'linear-gradient(135deg, rgba(245, 158, 11, 0.12), rgba(2, 132, 199, 0.1))',
              border: isDark ? '1px solid rgba(245, 158, 11, 0.35)' : '1px solid rgba(245, 158, 11, 0.25)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ width: 8, height: 8, borderRadius: 999, background: '#10B981', boxShadow: '0 0 8px #10B981' }} />
              <span style={{ fontSize: 11.5, fontWeight: 800, color: '#F59E0B', textTransform: 'uppercase' }}>
                {t('carousel.slide3_banner', 'Jonli Jang • 1v1 Arena')}
              </span>
            </div>
            <span
              style={{
                fontSize: 11,
                fontWeight: 700,
                color: isDark ? '#38BDF8' : '#0284C7',
                background: isDark ? 'rgba(2, 132, 199, 0.2)' : 'rgba(2, 132, 199, 0.1)',
                padding: '2px 8px',
                borderRadius: 6,
              }}
            >
              {t('carousel.slide3_timer', '60 soniya')}
            </span>
          </div>

          {/* 2 Players Cards */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr auto 1fr', alignItems: 'center', gap: 10 }}>
            {/* Player 1 (You) */}
            <div
              style={{
                padding: '12px 10px',
                borderRadius: 12,
                background: isDark ? 'rgba(16, 185, 129, 0.15)' : 'rgba(16, 185, 129, 0.08)',
                border: isDark ? '1px solid rgba(16, 185, 129, 0.35)' : '1px solid rgba(16, 185, 129, 0.25)',
                textAlign: 'center',
              }}
            >
              <div style={{ fontSize: 24, marginBottom: 4 }}>😎</div>
              <div style={{ fontSize: 13, fontWeight: 800, color: isDark ? '#FFFFFF' : '#0F172A' }}>
                {t('carousel.slide3_you', 'Siz')}
              </div>
              <div style={{ fontSize: 11, fontWeight: 700, color: '#059669', marginTop: 2 }}>1 540 ELO</div>
              <div style={{ fontSize: 11, color: isDark ? '#34D399' : '#047857', fontWeight: 800, marginTop: 4 }}>
                {t('carousel.slide3_score_you', '5/5 to‘g‘ri ⚡')}
              </div>
            </div>

            {/* VS Badge */}
            <div
              style={{
                width: 32,
                height: 32,
                borderRadius: 999,
                background: 'linear-gradient(135deg, #F59E0B, #EF4444)',
                color: '#fff',
                fontSize: 11,
                fontWeight: 900,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                boxShadow: '0 0 14px rgba(245, 158, 11, 0.3)',
              }}
            >
              VS
            </div>

            {/* Player 2 (Opponent) */}
            <div
              style={{
                padding: '12px 10px',
                borderRadius: 12,
                background: isDark ? '#1E293B' : '#F8FAFC',
                border: isDark ? '1px solid rgba(255, 255, 255, 0.08)' : '1px solid rgba(226, 232, 240, 0.95)',
                textAlign: 'center',
              }}
            >
              <div style={{ fontSize: 24, marginBottom: 4 }}>🎯</div>
              <div style={{ fontSize: 13, fontWeight: 800, color: isDark ? '#FFFFFF' : '#0F172A' }}>
                {t('carousel.slide3_opponent', 'Raqib (Toshkent)')}
              </div>
              <div style={{ fontSize: 11, fontWeight: 700, color: isDark ? '#94A3B8' : '#64748B', marginTop: 2 }}>
                1 510 ELO
              </div>
              <div style={{ fontSize: 11, color: isDark ? '#94A3B8' : '#64748B', fontWeight: 700, marginTop: 4 }}>
                {t('carousel.slide3_score_opp', '4/5 to‘g‘ri')}
              </div>
            </div>
          </div>

          {/* Victory announcement */}
          <div
            style={{
              padding: '10px 14px',
              borderRadius: 12,
              background: isDark ? 'rgba(245, 158, 11, 0.15)' : 'rgba(245, 158, 11, 0.1)',
              border: isDark ? '1px solid rgba(245, 158, 11, 0.35)' : '1px solid rgba(245, 158, 11, 0.25)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              fontSize: 12,
              fontWeight: 800,
              color: isDark ? '#FBBF24' : '#B45309',
            }}
          >
            <span>{t('carousel.slide3_win_text', '🏆 G‘alaba: +25 ELO ball!')}</span>
            <span style={{ fontSize: 11, color: isDark ? '#CBD5E1' : '#475569', fontWeight: 600 }}>
              {t('carousel.slide3_league', 'Oltin Liga (Top 3%)')}
            </span>
          </div>
        </div>
      ),
    },

    // 4-Slayd: Titul (OMR) Skaneri
    {
      id: 4,
      badge: t('carousel.slide4_badge', 'Vision AI OCR • Qog‘oz Test Skaneri'),
      badgeIcon: '📷',
      badgeColor: '#7C3AED',
      title: t('carousel.slide4_title', 'Qog‘ozdagi test javoblarini kamerada 1 soniyada tekshiring'),
      subtitle: t(
        'carousel.slide4_subtitle',
        'Qog‘oz titul varaqasini rasmga oling — Vision AI bo‘yalgan doiralarni o‘qib, darhol natija va tahlil chiqaradi.'
      ),
      ctaText: t('carousel.slide4_cta', 'Titulni skanerlash 📷'),
      ctaPath: '/tests/scan-omr',
      renderVisual: () => (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {/* Scanner view */}
          <div
            style={{
              padding: '12px 14px',
              borderRadius: 14,
              background: isDark ? 'rgba(124, 58, 237, 0.12)' : 'rgba(124, 58, 237, 0.05)',
              border: isDark ? '1px dashed rgba(167, 139, 250, 0.45)' : '1px dashed rgba(124, 58, 237, 0.35)',
              position: 'relative',
              overflow: 'hidden',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <span style={{ fontSize: 11, fontWeight: 800, color: isDark ? '#C4B5FD' : '#6D28D9', textTransform: 'uppercase' }}>
                {t('carousel.slide4_scanner_title', '📷 Vision AI OMR Skaner')}
              </span>
              <span
                style={{
                  fontSize: 10.5,
                  fontWeight: 700,
                  color: isDark ? '#34D399' : '#059669',
                  background: isDark ? 'rgba(16, 185, 129, 0.2)' : 'rgba(16, 185, 129, 0.15)',
                  padding: '2px 8px',
                  borderRadius: 6,
                }}
              >
                {t('carousel.slide4_time', '1.2 soniya')}
              </span>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 6, margin: '8px 0' }}>
              {[
                { q: 'Q1', ok: true },
                { q: 'Q2', ok: true },
                { q: 'Q3', ok: false },
                { q: 'Q4', ok: true },
                { q: 'Q5', ok: true },
              ].map((item, idx) => (
                <div
                  key={idx}
                  style={{
                    padding: '6px 4px',
                    borderRadius: 8,
                    textAlign: 'center',
                    fontSize: 11,
                    fontWeight: 800,
                    background: item.ok
                      ? isDark
                        ? 'rgba(16, 185, 129, 0.22)'
                        : 'rgba(16, 185, 129, 0.15)'
                      : isDark
                      ? 'rgba(239, 68, 68, 0.22)'
                      : 'rgba(239, 68, 68, 0.15)',
                    border: item.ok
                      ? isDark
                        ? '1px solid rgba(16, 185, 129, 0.45)'
                        : '1px solid rgba(16, 185, 129, 0.35)'
                      : isDark
                      ? '1px solid rgba(239, 68, 68, 0.45)'
                      : '1px solid rgba(239, 68, 68, 0.35)',
                    color: item.ok ? (isDark ? '#6EE7B7' : '#059669') : isDark ? '#FCA5A5' : '#DC2626',
                  }}
                >
                  {item.q} {item.ok ? '✓' : '✗'}
                </div>
              ))}
            </div>

            <div style={{ fontSize: 11, color: isDark ? '#94A3B8' : '#64748B', marginTop: 4 }}>
              {t('carousel.slide4_detected_code', 'Aniqlangan kod:')}{' '}
              <strong style={{ color: isDark ? '#FFFFFF' : '#0F172A' }}>
                {t('carousel.slide4_subject', 'BMB-101 (Ona tili)')}
              </strong>
            </div>
          </div>

          {/* OMR Results bar */}
          <div
            style={{
              padding: '10px 14px',
              borderRadius: 12,
              background: isDark ? '#1E293B' : '#F8FAFC',
              border: isDark ? '1px solid rgba(255, 255, 255, 0.08)' : '1px solid rgba(226, 232, 240, 0.95)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <div>
              <div style={{ fontSize: 11, color: isDark ? '#94A3B8' : '#64748B' }}>
                {t('carousel.slide4_total_score', 'Jami ball')}
              </div>
              <div style={{ fontSize: 18, fontWeight: 900, color: isDark ? '#FFFFFF' : '#0F172A' }}>
                41 / 45 <span style={{ fontSize: 11, color: '#059669' }}>(91.1%)</span>
              </div>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: 11, color: isDark ? '#94A3B8' : '#64748B' }}>
                {t('carousel.slide4_detected_errors', 'Aniqlangan xatolar')}
              </div>
              <div style={{ fontSize: 13, fontWeight: 700, color: isDark ? '#F87171' : '#DC2626' }}>
                {t('carousel.slide4_errors_desc', '4 ta savolda tahlil mavjud')}
              </div>
            </div>
          </div>
        </div>
      ),
    },
  ];

  // Auto rotate every 5 seconds unless paused
  useEffect(() => {
    if (isPaused) return;
    const interval = setInterval(() => {
      setDirection(1);
      setCurrent((prev) => (prev + 1) % slides.length);
    }, 5000);
    return () => clearInterval(interval);
  }, [isPaused, slides.length]);

  const goToSlide = (idx: number) => {
    setDirection(idx > current ? 1 : -1);
    setCurrent(idx);
  };

  const prevSlide = () => {
    setDirection(-1);
    setCurrent((prev) => (prev - 1 + slides.length) % slides.length);
  };

  const nextSlide = () => {
    setDirection(1);
    setCurrent((prev) => (prev + 1) % slides.length);
  };

  const activeSlide = slides[current];

  return (
    <div
      onMouseEnter={() => setIsPaused(true)}
      onMouseLeave={() => setIsPaused(false)}
      className="hero-carousel-card bg-white dark:bg-slate-900 rounded-3xl border border-slate-200 dark:border-slate-800 shadow-xl shadow-slate-200/50 dark:shadow-none p-6"
      style={{
        position: 'relative',
        borderRadius: 24,
        padding: '28px 24px 22px',
        background: isDark ? '#0F172A' : '#FFFFFF',
        border: isDark ? '1px solid rgba(255, 255, 255, 0.08)' : '1px solid #E2E8F0',
        boxShadow: isDark
          ? '0 20px 45px -10px rgba(0, 0, 0, 0.6), 0 0 25px -5px rgba(217, 119, 6, 0.15)'
          : '0 20px 45px -10px rgba(148, 163, 184, 0.25), 0 0 25px -5px rgba(217, 119, 6, 0.08)',
        minHeight: 460,
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        transition: 'all 0.3s ease',
      }}
    >
      {/* Top Header: Badge and Slide Counter */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
            padding: '5px 12px',
            borderRadius: 999,
            fontSize: 11.5,
            fontWeight: 800,
            background: `${activeSlide.badgeColor}18`,
            border: `1px solid ${activeSlide.badgeColor}4D`,
            color: activeSlide.badgeColor,
            letterSpacing: '0.04em',
          }}
        >
          <span>{activeSlide.badgeIcon}</span>
          <span>{activeSlide.badge}</span>
        </span>

        {/* Prev / Next Chevrons */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <button
            type="button"
            onClick={prevSlide}
            aria-label="Previous slide"
            style={{
              width: 32,
              height: 32,
              borderRadius: 8,
              background: isDark ? '#1E293B' : '#F1F5F9',
              border: isDark ? '1px solid rgba(255, 255, 255, 0.1)' : '1px solid #E2E8F0',
              color: isDark ? '#F1F5F9' : '#1E293B',
              fontSize: 16,
              fontWeight: 800,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
              transition: 'all 0.15s ease',
            }}
          >
            ‹
          </button>
          <span
            style={{
              fontSize: 11.5,
              fontWeight: 700,
              color: isDark ? '#94A3B8' : '#64748B',
              minWidth: 32,
              textAlign: 'center',
            }}
          >
            {current + 1} / {slides.length}
          </span>
          <button
            type="button"
            onClick={nextSlide}
            aria-label="Next slide"
            style={{
              width: 32,
              height: 32,
              borderRadius: 8,
              background: isDark ? '#1E293B' : '#F1F5F9',
              border: isDark ? '1px solid rgba(255, 255, 255, 0.1)' : '1px solid #E2E8F0',
              color: isDark ? '#F1F5F9' : '#1E293B',
              fontSize: 16,
              fontWeight: 800,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
              transition: 'all 0.15s ease',
            }}
          >
            ›
          </button>
        </div>
      </div>

      {/* Slide Body (Animated) */}
      <AnimatePresence mode="wait">
        <motion.div
          key={current}
          initial={{ opacity: 0, x: direction * 24 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -direction * 24 }}
          transition={{ duration: 0.28, ease: 'easeOut' }}
          style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'space-between', gap: 16 }}
        >
          {/* Slide Heading */}
          <div>
            <h3
              className="text-slate-900 dark:text-white font-black"
              style={{
                fontSize: 'clamp(1.15rem, 2vw, 1.35rem)',
                fontWeight: 900,
                color: isDark ? '#FFFFFF' : '#0F172A',
                margin: '0 0 6px',
                lineHeight: 1.3,
                letterSpacing: '-0.01em',
              }}
            >
              {activeSlide.title}
            </h3>
            <p
              className="text-slate-600 dark:text-slate-300"
              style={{
                fontSize: 12.5,
                color: isDark ? '#CBD5E1' : '#64748B',
                margin: 0,
                lineHeight: 1.5,
              }}
            >
              {activeSlide.subtitle}
            </p>
          </div>

          {/* Slide Visual Widget */}
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
            {activeSlide.renderVisual()}
          </div>

          {/* Quick CTA inside slide */}
          <button
            type="button"
            onClick={() => onAction(activeSlide.ctaPath)}
            className="btn-shimmer"
            style={{
              width: '100%',
              padding: '12px 18px',
              borderRadius: 14,
              background: 'linear-gradient(135deg, #F59E0B, #D97706)',
              border: 'none',
              color: '#FFFFFF',
              fontWeight: 900,
              fontSize: 13.5,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 8,
              boxShadow: '0 4px 15px rgba(217, 119, 6, 0.25)',
              transition: 'all 0.18s ease',
            }}
          >
            <span>{activeSlide.ctaText}</span>
          </button>
        </motion.div>
      </AnimatePresence>

      {/* Bottom Dot Indicators */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 8,
          marginTop: 18,
          paddingTop: 12,
          borderTop: isDark ? '1px solid rgba(255, 255, 255, 0.08)' : '1px solid rgba(226, 232, 240, 0.8)',
        }}
      >
        {slides.map((s, idx) => {
          const isActive = idx === current;
          return (
            <button
              key={s.id}
              type="button"
              onClick={() => goToSlide(idx)}
              aria-label={`Slide ${idx + 1}`}
              style={{
                width: isActive ? 28 : 8,
                height: 7,
                borderRadius: 4,
                background: isActive
                  ? 'linear-gradient(135deg, #D97706, #059669)'
                  : isDark
                  ? 'rgba(255, 255, 255, 0.2)'
                  : 'rgba(203, 213, 225, 0.8)',
                border: 'none',
                cursor: 'pointer',
                transition: 'all 0.25s ease',
                boxShadow: isActive ? '0 0 8px rgba(217, 119, 6, 0.4)' : 'none',
              }}
            />
          );
        })}
      </div>
    </div>
  );
}
