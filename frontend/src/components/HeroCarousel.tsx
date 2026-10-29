import { useState, useEffect } from 'react';
import type { ReactNode } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { CheckIcon } from './icons';

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
  const [current, setCurrent] = useState(0);
  const [direction, setDirection] = useState(1);
  const [isPaused, setIsPaused] = useState(false);

  const slides: SlideData[] = [
    // 1-Slayd: AI Esse Baholash
    {
      id: 1,
      badge: 'BMB 12 Mezon Rasmiy Tahlili',
      badgeIcon: '✍️',
      badgeColor: '#F59E0B',
      title: 'Inshongizni 15 soniyada rasmiy BMB mezonlari asosida tekshiring',
      subtitle: 'Sunʼiy intellekt har bir jumla, leksika va fikriy mantiqni Davlat BMB komissiyasi standartida baholaydi.',
      ctaText: 'Esse yozib ko‘rish →',
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
              background: 'rgba(245, 158, 11, 0.08)',
              border: '1px solid rgba(245, 158, 11, 0.25)',
            }}
          >
            <div>
              <span style={{ fontSize: 11, fontWeight: 700, color: '#F59E0B', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                BMB Insho Natijasi
              </span>
              <div style={{ fontSize: 24, fontWeight: 900, color: '#F8FAFC', display: 'flex', alignItems: 'baseline', gap: 6 }}>
                54.5 <span style={{ fontSize: 14, color: '#94A3B8' }}>/ 60 ball</span>
              </div>
            </div>
            <div
              style={{
                padding: '6px 14px',
                borderRadius: 999,
                background: 'rgba(16, 185, 129, 0.2)',
                border: '1px solid rgba(16, 185, 129, 0.4)',
                color: '#34D399',
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
              { label: 'Mazmun va mavzuning to‘liq ochilishi', score: '19.0 / 20', pct: 95, color: '#10B981' },
              { label: 'Uslubiy ravonlik va boy so‘z boyligi', score: '18.5 / 20', pct: 92, color: '#F59E0B' },
              { label: 'Imlo, grammatika va tinish belgilari', score: '17.0 / 20', pct: 85, color: '#38BDF8' },
            ].map((crit, i) => (
              <div
                key={i}
                style={{
                  padding: '8px 12px',
                  borderRadius: 10,
                  background: 'rgba(255, 255, 255, 0.03)',
                  border: '1px solid rgba(255, 255, 255, 0.06)',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11.5, fontWeight: 600, color: '#E2E8F0', marginBottom: 4 }}>
                  <span>{crit.label}</span>
                  <span style={{ color: crit.color, fontWeight: 800 }}>{crit.score}</span>
                </div>
                <div style={{ width: '100%', height: 5, borderRadius: 3, background: 'rgba(255, 255, 255, 0.1)', overflow: 'hidden' }}>
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
              background: 'rgba(16, 185, 129, 0.08)',
              border: '1px solid rgba(16, 185, 129, 0.25)',
              fontSize: 12,
              lineHeight: 1.5,
              color: '#A7F3D0',
            }}
          >
            <strong>💡 AI Tavsiyasi:</strong> "Xulosa qismida Navoiy qarashlari mukammal tahlil etilgan. Grammatik xatolar 0 ta, leksik boylik yuqori."
          </div>
        </div>
      ),
    },

    // 2-Slayd: CBT Milliy Sertifikat Test Simulyatori
    {
      id: 2,
      badge: 'CBT Davlat Formati • 2026',
      badgeIcon: '📝',
      badgeColor: '#10B981',
      title: 'Haqiqiy davlat imtihoni muhiti va vaqt nazorati',
      subtitle: 'Kompensatsiyalangan qatʼiy taymer, rasmiy 45 talik savollar va test yakunlanishi bilan bir zumda batafsil tahlil.',
      ctaText: 'Testni boshlash →',
      ctaPath: '/tests',
      renderVisual: () => (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {/* CBT top bar */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '8px 14px',
              borderRadius: 12,
              background: 'rgba(255, 255, 255, 0.04)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              fontSize: 12,
              fontWeight: 700,
            }}
          >
            <span style={{ color: '#E2E8F0' }}>Ona tili va Adabiyot (BMB-101)</span>
            <span style={{ color: '#F59E0B', fontFamily: 'monospace', fontSize: 13 }}>⏱ 01:28:45</span>
          </div>

          {/* Question preview box */}
          <div
            style={{
              padding: '12px 14px',
              borderRadius: 12,
              background: 'rgba(19, 25, 38, 0.9)',
              border: '1px solid rgba(245, 158, 11, 0.2)',
            }}
          >
            <div style={{ fontSize: 11, color: '#F59E0B', fontWeight: 800, textTransform: 'uppercase', marginBottom: 4 }}>
              14-Savol (Badiiy tahlil)
            </div>
            <p style={{ fontSize: 12.5, color: '#F8FAFC', fontWeight: 600, margin: '0 0 10px', lineHeight: 1.45 }}>
              Navoiyning "Hayrat ul-abror" dostonidagi durroj masalining bosh g‘oyasi nimaga qaratilgan?
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {[
                { key: 'A', text: 'Ilm-ma’rifatga intilish', correct: false },
                { key: 'B', text: 'Tilni tiyish va noo‘rin so‘zlashdan saqlanish', correct: true },
                { key: 'C', text: 'Saxovat va mehmondo‘stlik odobi', correct: false },
              ].map((opt) => (
                <div
                  key={opt.key}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    padding: '6px 10px',
                    borderRadius: 8,
                    fontSize: 11.5,
                    fontWeight: 600,
                    background: opt.correct ? 'rgba(16, 185, 129, 0.18)' : 'rgba(255, 255, 255, 0.03)',
                    border: opt.correct ? '1px solid rgba(16, 185, 129, 0.5)' : '1px solid rgba(255, 255, 255, 0.06)',
                    color: opt.correct ? '#34D399' : '#94A3B8',
                  }}
                >
                  <span
                    style={{
                      width: 18,
                      height: 18,
                      borderRadius: 999,
                      background: opt.correct ? '#10B981' : 'rgba(255, 255, 255, 0.1)',
                      color: opt.correct ? '#000' : '#fff',
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
                  {opt.correct && <CheckIcon size={14} style={{ marginLeft: 'auto', color: '#10B981' }} />}
                </div>
              ))}
            </div>
          </div>

          {/* Quick analysis badge */}
          <div
            style={{
              padding: '8px 12px',
              borderRadius: 10,
              background: 'rgba(16, 185, 129, 0.12)',
              border: '1px solid rgba(16, 185, 129, 0.28)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              fontSize: 12,
              fontWeight: 700,
              color: '#34D399',
            }}
          >
            <span>🎯 42/45 to‘g‘ri (93.3%)</span>
            <span style={{ fontSize: 11, color: '#A7F3D0' }}>A Daraja kafolatlangan</span>
          </div>
        </div>
      ),
    },

    // 3-Slayd: Jonli 1v1 Arena Bellashuvi
    {
      id: 3,
      badge: 'PvP Bilim Jangi • Real-vaqt',
      badgeIcon: '⚔️',
      badgeColor: '#38BDF8',
      title: 'O‘zbekiston bo‘yicha tengdoshlaringiz bilan 60 soniyalik bilim jangi',
      subtitle: 'Jonli ELO reytingi, raqobat ruhi va har bir to‘g‘ri javob uchun tezkor ochkolar bilan bilimingizni charxlang.',
      ctaText: 'Arenada bellashish ⚔️',
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
              background: 'linear-gradient(135deg, rgba(245, 158, 11, 0.15), rgba(56, 189, 248, 0.15))',
              border: '1px solid rgba(245, 158, 11, 0.3)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ width: 8, height: 8, borderRadius: 999, background: '#10B981', boxShadow: '0 0 8px #10B981' }} />
              <span style={{ fontSize: 11.5, fontWeight: 800, color: '#FBBF24', textTransform: 'uppercase' }}>
                Jonli Jang • 1v1 Arena
              </span>
            </div>
            <span style={{ fontSize: 11, fontWeight: 700, color: '#38BDF8', background: 'rgba(56, 189, 248, 0.15)', padding: '2px 8px', borderRadius: 6 }}>
              60 soniya
            </span>
          </div>

          {/* 2 Players Cards */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr auto 1fr', alignItems: 'center', gap: 10 }}>
            {/* Player 1 (You) */}
            <div
              style={{
                padding: '12px 10px',
                borderRadius: 12,
                background: 'rgba(16, 185, 129, 0.1)',
                border: '1px solid rgba(16, 185, 129, 0.3)',
                textAlign: 'center',
              }}
            >
              <div style={{ fontSize: 24, marginBottom: 4 }}>😎</div>
              <div style={{ fontSize: 13, fontWeight: 800, color: '#F8FAFC' }}>Siz</div>
              <div style={{ fontSize: 11, fontWeight: 700, color: '#10B981', marginTop: 2 }}>1 540 ELO</div>
              <div style={{ fontSize: 11, color: '#34D399', fontWeight: 800, marginTop: 4 }}>5/5 to‘g‘ri ⚡</div>
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
                boxShadow: '0 0 14px rgba(245, 158, 11, 0.4)',
              }}
            >
              VS
            </div>

            {/* Player 2 (Opponent) */}
            <div
              style={{
                padding: '12px 10px',
                borderRadius: 12,
                background: 'rgba(255, 255, 255, 0.03)',
                border: '1px solid rgba(255, 255, 255, 0.08)',
                textAlign: 'center',
              }}
            >
              <div style={{ fontSize: 24, marginBottom: 4 }}>🎯</div>
              <div style={{ fontSize: 13, fontWeight: 800, color: '#F8FAFC' }}>Raqib (Toshkent)</div>
              <div style={{ fontSize: 11, fontWeight: 700, color: '#94A3B8', marginTop: 2 }}>1 510 ELO</div>
              <div style={{ fontSize: 11, color: '#94A3B8', fontWeight: 700, marginTop: 4 }}>4/5 to‘g‘ri</div>
            </div>
          </div>

          {/* Victory announcement */}
          <div
            style={{
              padding: '10px 14px',
              borderRadius: 12,
              background: 'rgba(245, 158, 11, 0.12)',
              border: '1px solid rgba(245, 158, 11, 0.3)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              fontSize: 12,
              fontWeight: 800,
              color: '#FBBF24',
            }}
          >
            <span>🏆 G‘alaba: +25 ELO ball!</span>
            <span style={{ fontSize: 11, color: '#E2E8F0', fontWeight: 600 }}>Oltin Liga (Top 3%)</span>
          </div>
        </div>
      ),
    },

    // 4-Slayd: Titul (OMR) Skaneri
    {
      id: 4,
      badge: 'Vision AI OCR • Qog‘oz Test Skaneri',
      badgeIcon: '📷',
      badgeColor: '#A78BFA',
      title: 'Qog‘ozdagi test javoblarini kamerada 1 soniyada tekshiring',
      subtitle: 'Qog‘oz titul varaqasini rasmga oling — Vision AI bo‘yalgan doiralarni o‘qib, darhol natija va tahlil chiqaradi.',
      ctaText: 'Titulni skanerlash 📷',
      ctaPath: '/titul-scanner',
      renderVisual: () => (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {/* Scanner view */}
          <div
            style={{
              padding: '12px 14px',
              borderRadius: 14,
              background: 'rgba(139, 92, 246, 0.08)',
              border: '1px dashed rgba(167, 139, 250, 0.4)',
              position: 'relative',
              overflow: 'hidden',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <span style={{ fontSize: 11, fontWeight: 800, color: '#C4B5FD', textTransform: 'uppercase' }}>
                📷 Vision AI OMR Skaner
              </span>
              <span style={{ fontSize: 10.5, fontWeight: 700, color: '#34D399', background: 'rgba(16, 185, 129, 0.15)', padding: '2px 8px', borderRadius: 6 }}>
                1.2 soniya
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
                    background: item.ok ? 'rgba(16, 185, 129, 0.2)' : 'rgba(239, 68, 68, 0.2)',
                    border: item.ok ? '1px solid rgba(16, 185, 129, 0.4)' : '1px solid rgba(239, 68, 68, 0.4)',
                    color: item.ok ? '#34D399' : '#F87171',
                  }}
                >
                  {item.q} {item.ok ? '✓' : '✗'}
                </div>
              ))}
            </div>

            <div style={{ fontSize: 11, color: '#94A3B8', marginTop: 4 }}>
              Aniqlangan kod: <strong style={{ color: '#F8FAFC' }}>BMB-101 (Ona tili)</strong>
            </div>
          </div>

          {/* OMR Results bar */}
          <div
            style={{
              padding: '10px 14px',
              borderRadius: 12,
              background: 'rgba(255, 255, 255, 0.04)',
              border: '1px solid rgba(255, 255, 255, 0.08)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <div>
              <div style={{ fontSize: 11, color: '#94A3B8' }}>Jami ball</div>
              <div style={{ fontSize: 18, fontWeight: 900, color: '#F8FAFC' }}>
                41 / 45 <span style={{ fontSize: 11, color: '#10B981' }}>(91.1%)</span>
              </div>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: 11, color: '#94A3B8' }}>Aniqlangan xatolar</div>
              <div style={{ fontSize: 13, fontWeight: 700, color: '#F87171' }}>4 ta savolda tahlil mavjud</div>
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
      className="hero-carousel-card"
      style={{
        position: 'relative',
        borderRadius: 24,
        padding: '28px 24px 22px',
        background: 'rgba(19, 25, 38, 0.88)',
        backdropFilter: 'blur(20px)',
        WebkitBackdropFilter: 'blur(20px)',
        border: '1px solid rgba(245, 158, 11, 0.22)',
        boxShadow: '0 20px 50px -10px rgba(0, 0, 0, 0.6), 0 0 35px -8px rgba(245, 158, 11, 0.15)',
        minHeight: 460,
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        transition: 'border-color 0.3s ease, box-shadow 0.3s ease',
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
            background: `${activeSlide.badgeColor}1A`,
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
            aria-label="Oldingi slayd"
            style={{
              width: 30,
              height: 30,
              borderRadius: 8,
              background: 'rgba(255, 255, 255, 0.06)',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              color: '#E2E8F0',
              fontSize: 15,
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
          <span style={{ fontSize: 11, fontWeight: 700, color: '#94A3B8', minWidth: 32, textAlign: 'center' }}>
            {current + 1} / {slides.length}
          </span>
          <button
            type="button"
            onClick={nextSlide}
            aria-label="Keyingi slayd"
            style={{
              width: 30,
              height: 30,
              borderRadius: 8,
              background: 'rgba(255, 255, 255, 0.06)',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              color: '#E2E8F0',
              fontSize: 15,
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
              style={{
                fontSize: 'clamp(1.15rem, 2vw, 1.35rem)',
                fontWeight: 900,
                color: '#F8FAFC',
                margin: '0 0 6px',
                lineHeight: 1.3,
                letterSpacing: '-0.01em',
              }}
            >
              {activeSlide.title}
            </h3>
            <p style={{ fontSize: 12.5, color: '#94A3B8', margin: 0, lineHeight: 1.5 }}>
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
              padding: '11px 16px',
              borderRadius: 12,
              background: 'linear-gradient(135deg, #F59E0B, #FBBF24)',
              border: 'none',
              color: '#090D16',
              fontWeight: 900,
              fontSize: 13.5,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 8,
              boxShadow: '0 4px 15px rgba(245, 158, 11, 0.3)',
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
          borderTop: '1px solid rgba(255, 255, 255, 0.06)',
        }}
      >
        {slides.map((s, idx) => {
          const isActive = idx === current;
          return (
            <button
              key={s.id}
              type="button"
              onClick={() => goToSlide(idx)}
              aria-label={`Slayd ${idx + 1}`}
              style={{
                width: isActive ? 28 : 8,
                height: 7,
                borderRadius: 4,
                background: isActive ? 'linear-gradient(135deg, #F59E0B, #10B981)' : 'rgba(255, 255, 255, 0.2)',
                border: 'none',
                cursor: 'pointer',
                transition: 'all 0.25s ease',
                boxShadow: isActive ? '0 0 10px rgba(245, 158, 11, 0.5)' : 'none',
              }}
            />
          );
        })}
      </div>
    </div>
  );
}
