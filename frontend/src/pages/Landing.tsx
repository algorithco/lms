import { useEffect, useMemo, useState } from 'react';
import type { FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { useLang } from '../i18n/LangContext';
import { School, landingFor } from '../lib/api';
import TrendChart from '../components/TrendChart';
import SEO from '../components/SEO';
import LanguageSwitcher from '../components/LanguageSwitcher';
import confetti from 'canvas-confetti';
import {
  BotIcon,
  CheckIcon,
  ClockIcon,
  FileTextIcon,
  LightbulbIcon,
  MapPinIcon,
  MenuIcon,
  PenLineIcon,
  SwordsIcon,
  TrophyIcon,
  XIcon,
} from '../components/icons';

// 12 BMB Milliy Sertifikat Essay Assessment Criteria
interface CriterionData {
  id: number;
  name: string;
  score: string;
  max: number;
  percent: number;
  desc: string;
  advice: string;
  category: 'content' | 'grammar' | 'style';
}

const ESSAY_12_CRITERIA: CriterionData[] = [
  {
    id: 1,
    name: 'Mavzuning toʻliq ochib berilishi',
    score: '5 / 5',
    max: 5,
    percent: 100,
    desc: 'Asosiy gʻoya va muammo teran ochilgan, mavzudan chetlanish kuzatilmadi.',
    advice: 'Tezis va unga berilgan dalillar ketma-ketligi ideal darajada.',
    category: 'content',
  },
  {
    id: 2,
    name: 'Matn kompozitsiyasi va tuzilishi',
    score: '4.5 / 5',
    max: 5,
    percent: 90,
    desc: 'Kirish, asosiy qism va xulosa mutanosib va mantiqan mustahkam bogʻlangan.',
    advice: 'Kirish qismida muammo dolzarbligini yana bir jumla bilan kuchaytirish mumkin.',
    category: 'content',
  },
  {
    id: 3,
    name: 'Fikrlarning dalillanishi va iqtiboslar',
    score: '4.5 / 5',
    max: 5,
    percent: 90,
    desc: 'Alisher Navoiy asarlaridan keltirilgan misollar va baytlar oʻrinli.',
    advice: 'Badiiy tahlil bilan birga hayotiy misol keltirilgani bahoni oshirdi.',
    category: 'content',
  },
  {
    id: 4,
    name: 'Grammatik qoidalar va sintaksis',
    score: '4.5 / 5',
    max: 5,
    percent: 90,
    desc: 'Murakkab qoʻshma gaplar va soʻz birikmalari grammatik toʻgʻri shakllantirilgan.',
    advice: 'Ergashgan qoʻshma gaplarda bogʻlovchi vositalar toʻgʻri tanlangan.',
    category: 'grammar',
  },
  {
    id: 5,
    name: 'Orfografiya (imlo) qoidalari',
    score: '4 / 5',
    max: 5,
    percent: 80,
    desc: '1 ta noaniq imlo xatosi aniqlandi: "yondosh" soʻzi adabiy tilda "yondash" yoziladi.',
    advice: 'Davlat taʼlim standarti boʻyicha imlo qoidalariga qatʼiy rioya qiling.',
    category: 'grammar',
  },
  {
    id: 6,
    name: 'Punktuatsiya va tinish belgilari',
    score: '3.5 / 5',
    max: 5,
    percent: 70,
    desc: 'Ajratilgan va uyushiq boʻlaklar orasida 2 ta vergul tushirib qoldirilgan.',
    advice: 'Kirish soʻzlar va ergash gaplarni bogʻlovchi vergullarga eʼtibor qarating.',
    category: 'grammar',
  },
  {
    id: 7,
    name: 'Uslubiy ravonlik va adabiy til meʼyori',
    score: '4.5 / 5',
    max: 5,
    percent: 90,
    desc: 'Soʻz takroriga yoʻl qoʻyilmagan, nutq ifodali va tasirchan.',
    advice: 'Fikr bayonidagi balandparvozlik meʼyorda saqlangan.',
    category: 'style',
  },
  {
    id: 8,
    name: 'Leksik boylik va sinonimlar',
    score: '4.5 / 5',
    max: 5,
    percent: 90,
    desc: 'Badiiy tasvir vositalari va boy adabiy leksika muvaffaqiyatli qoʻllangan.',
    advice: 'Sinonimik qatorlardan unumli foydalanilgan.',
    category: 'style',
  },
  {
    id: 9,
    name: 'Kirish qismining dolzarbligi',
    score: '4.5 / 5',
    max: 5,
    percent: 90,
    desc: 'Mavzuga jalb qiluvchi kuchli tezis va falsafiy savol bilan boshlangan.',
    advice: 'Oʻquvchini oʻyga toldiruvchi boshlanma.',
    category: 'content',
  },
  {
    id: 10,
    name: 'Xulosa va mustaqil dunyoqarash',
    score: '5 / 5',
    max: 5,
    percent: 100,
    desc: 'Muallifning shaxsiy nuqtayi nazari va qatʼiy xulosasi toʻliq yoritilgan.',
    advice: 'Xulosa asosiy gʻoyaga toʻliq javob beradi.',
    category: 'content',
  },
  {
    id: 11,
    name: 'Abzaslararo mantiqiy oʻtishlar',
    score: '4 / 5',
    max: 5,
    percent: 80,
    desc: 'Fikrlar oqimi ravon va keyingi fikrga silliq ulanadi.',
    advice: '2 va 3-abzaslar orasidagi bogʻlovchi jumlani biroz silliqlash mumkin.',
    category: 'style',
  },
  {
    id: 12,
    name: 'Matn hajmi va meʼyoriy koʻlam',
    score: '5 / 5',
    max: 5,
    percent: 100,
    desc: 'Belgilangan 250-300 soʻz talabiga toʻliq mos (278 soʻz yozilgan).',
    advice: 'Hajm koʻlami BMB talabiga 100% mos.',
    category: 'style',
  },
];

// Interactive CBT Sample Question
interface CbtSampleQuestion {
  question: string;
  options: { key: string; text: string; correct: boolean }[];
  explanation: string;
}

const CBT_QUESTION: CbtSampleQuestion = {
  question: "Alisher Navoiyning 'Xamsa' tarkibiga kirmaydigan dostonini aniqlang:",
  options: [
    { key: 'A', text: 'Hayrat ul-abror', correct: false },
    { key: 'B', text: 'Farhod va Shirin', correct: false },
    { key: 'C', text: 'Lison ut-tayr', correct: true },
    { key: 'D', text: 'Saddi Iskandariy', correct: false },
  ],
  explanation:
    "'Lison ut-tayr' (Qushlar tili) Navoiyning alohida falsafiy dostoni boʻlib, 'Xamsa' beshligiga kirmaydi. 'Xamsa' beshligiga: Hayrat ul-abror, Farhod va Shirin, Layli va Majnun, Sab'ai sayyor hamda Saddi Iskandariy dostonlari kiradi.",
};

export default function Landing() {
  const { t } = useLang();
  const { user, openAuthModal } = useAuth();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);

  // Hero interactive demo widget mode
  const [demoTab, setDemoTab] = useState<'essay' | 'test'>('essay');
  const [selectedCrit, setSelectedCrit] = useState<CriterionData>(ESSAY_12_CRITERIA[0]);

  // CBT interactive choice state
  const [selectedOptionKey, setSelectedOptionKey] = useState<string | null>(null);

  // Live platform stats
  const [stats, setStats] = useState<{
    totals: { tests: number; students: number; essays_graded: number };
  } | null>(null);

  // Newsletter
  const [newsEmail, setNewsEmail] = useState('');
  const [newsDone, setNewsDone] = useState(false);

  const startTo = user ? landingFor(user) : '/register';
  const initials =
    (user?.full_name || '?')
      .split(' ')
      .map((p) => p[0])
      .join('')
      .slice(0, 2)
      .toUpperCase() || '?';

  useEffect(() => {
    let live = true;
    School.publicStats()
      .then((s) => {
        if (live) setStats(s);
      })
      .catch(() => {});
    return () => {
      live = false;
    };
  }, []);

  // Lock scroll on mobile drawer
  useEffect(() => {
    document.body.style.overflow = mobileOpen ? 'hidden' : '';
    return () => {
      document.body.style.overflow = '';
    };
  }, [mobileOpen]);

  // Section nav
  const sectionNav: [string, string][] = [
    ['nav_features', '#features'],
    ['nav_stats', '#stats'],
    ['nav_how', '#how'],
  ];

  // 12-month platform growth trend
  const trend = useMemo(() => {
    const attempts = [120, 150, 140, 180, 210, 260, 240, 300, 330, 310, 360, 420];
    const avg = [62, 64, 63, 68, 70, 72, 71, 76, 78, 77, 82, 85];
    const certs = [8, 12, 10, 18, 22, 30, 28, 40, 48, 45, 60, 72];
    const students = [60, 95, 140, 190, 260, 340, 420, 520, 640, 780, 940, 1100];
    const essays = [20, 35, 30, 55, 70, 90, 85, 120, 140, 135, 170, 200];
    const today = new Date();
    return attempts.map((a, k) => {
      const d = new Date(today.getFullYear(), today.getMonth() - (11 - k), 1);
      return {
        date: `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-01`,
        attempts: a,
        avg: avg[k],
        certs: certs[k],
        students: students[k],
        essays: essays[k],
      };
    });
  }, []);

  const handleCbtOptionClick = (key: string) => {
    setSelectedOptionKey(key);
    if (key === 'C') {
      try {
        confetti({
          particleCount: 40,
          spread: 60,
          origin: { y: 0.65 },
          colors: ['#10B981', '#34D399', '#F59E0B'],
        });
      } catch {
        /* ignore */
      }
    }
  };

  const subscribeNews = (e: FormEvent) => {
    e.preventDefault();
    if (newsEmail.trim()) {
      setNewsEmail('');
      setNewsDone(true);
    }
  };

  const handleAction = (destination: string) => {
    if (user) {
      navigate(destination);
    } else {
      openAuthModal('register');
    }
  };

  // SEO schema
  const jsonLdData = useMemo(
    () => [
      {
        '@context': 'https://schema.org',
        '@type': 'EducationalOrganization',
        name: 'GRAND EDUCATION LMS',
        url: 'https://grandec.uz',
        logo: 'https://grandec.uz/grandec.png',
        description:
          "Ona tili va adabiyoti bo'yicha Milliy sertifikatga tayyorlovchi zamonaviy LMS va AI Esse platformasi.",
        sameAs: ['https://t.me/uz_essaygrader_bot'],
      },
    ],
    [],
  );

  return (
    <div
      className="landing"
      style={{
        background: '#090d16',
        color: '#f8fafc',
        minHeight: '100svh',
        position: 'relative',
        overflowX: 'clip',
      }}
    >
      <SEO
        title="Ona tili va adabiyot LMS | Milliy sertifikat & AI Esse"
        description="Ona tili va adabiyotidan Milliy sertifikatga tayyorlovchi LMS platformasi — GRAND EDUCATION (grandec.uz). 12 mezonli AI Esse tahlili, Fast CBT simulyatori va 1v1 Arena."
        canonical="/"
        jsonLd={jsonLdData}
      />

      {/* BACKGROUND: Subtle Dot Matrix + Radial Ambient Glow */}
      <div className="subtle-dot-bg" aria-hidden="true" />
      <div className="radial-glow-hero" aria-hidden="true" />

      {/* NAVBAR */}
      <nav
        className="landing-nav"
        style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          zIndex: 50,
          background: 'rgba(9, 13, 22, 0.85)',
          backdropFilter: 'blur(16px)',
          WebkitBackdropFilter: 'blur(16px)',
          borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
        }}
        aria-label="Asosiy navigatsiya"
      >
        <div
          style={{
            margin: '0 auto',
            maxWidth: 1200,
            padding: '0 20px',
            height: '4.25rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 16,
          }}
        >
          {/* Logo */}
          <Link
            to="/"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              textDecoration: 'none',
              minWidth: 0,
            }}
            aria-label="GRANDEC LMS Bosh sahifasi"
          >
            <div
              style={{
                width: 36,
                height: 36,
                borderRadius: 10,
                background: 'rgba(245, 158, 11, 0.12)',
                border: '1px solid rgba(245, 158, 11, 0.25)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
              }}
            >
              <img
                src="/grandec.png"
                alt="GRANDEC"
                style={{ width: 26, height: 26, objectFit: 'cover' }}
              />
            </div>
            <div>
              <span
                style={{
                  display: 'block',
                  fontSize: 16,
                  fontWeight: 900,
                  letterSpacing: '-0.02em',
                  color: '#f8fafc',
                  lineHeight: 1.1,
                }}
              >
                GRAND EDUCATION
              </span>
              <span
                style={{
                  display: 'block',
                  fontSize: 10,
                  fontWeight: 800,
                  letterSpacing: '0.18em',
                  color: '#F59E0B',
                }}
              >
                LMS PLATFORMA
              </span>
            </div>
          </Link>

          {/* Desktop Nav Items */}
          <div
            className="landing-desktop-nav"
            style={{
              display: 'none',
              alignItems: 'center',
              gap: 6,
            }}
          >
            {sectionNav.map(([k, href]) => (
              <a
                key={k}
                href={href}
                style={{
                  padding: '8px 14px',
                  borderRadius: 10,
                  fontSize: 14,
                  fontWeight: 600,
                  color: '#94a3b8',
                  textDecoration: 'none',
                  transition: 'all 0.2s ease',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.color = '#f8fafc';
                  e.currentTarget.style.background = 'rgba(255, 255, 255, 0.05)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.color = '#94a3b8';
                  e.currentTarget.style.background = 'transparent';
                }}
              >
                {t(k)}
              </a>
            ))}
          </div>

          {/* Right Area: Language Switcher & Auth Button */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <LanguageSwitcher />

            {user ? (
              <Link
                to={startTo}
                className="btn-glow"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '8px 16px 8px 10px',
                  borderRadius: 12,
                  fontSize: 13,
                  fontWeight: 800,
                  color: '#090d16',
                  background: 'linear-gradient(135deg, #F59E0B, #FBBF24)',
                  textDecoration: 'none',
                  boxShadow: '0 4px 14px rgba(245, 158, 11, 0.35)',
                }}
              >
                <span
                  style={{
                    width: 24,
                    height: 24,
                    borderRadius: 999,
                    background: 'rgba(9, 13, 22, 0.2)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: 11,
                    fontWeight: 900,
                  }}
                >
                  {initials}
                </span>
                <span style={{ maxWidth: 100, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {user.full_name}
                </span>
              </Link>
            ) : (
              <button
                type="button"
                onClick={() => openAuthModal('login')}
                className="btn-glow"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '9px 20px',
                  borderRadius: 12,
                  fontSize: 14,
                  fontWeight: 800,
                  color: '#090d16',
                  background: 'linear-gradient(135deg, #F59E0B, #FBBF24)',
                  border: 'none',
                  cursor: 'pointer',
                  boxShadow: '0 4px 16px rgba(245, 158, 11, 0.35)',
                  transition: 'all 0.2s ease',
                }}
              >
                <span>{t('login')}</span>
                <span
                  style={{
                    fontSize: 10,
                    fontWeight: 800,
                    padding: '2px 6px',
                    borderRadius: 6,
                    background: 'rgba(9, 13, 22, 0.2)',
                  }}
                >
                  1-klik
                </span>
              </button>
            )}

            {/* Mobile Hamburger */}
            <button
              type="button"
              className="landing-burger-btn"
              aria-label={mobileOpen ? 'Menyuni yopish' : 'Menyuni ochish'}
              onClick={() => setMobileOpen((v) => !v)}
              style={{
                width: 40,
                height: 40,
                borderRadius: 10,
                border: '1px solid rgba(255, 255, 255, 0.1)',
                background: 'rgba(15, 23, 42, 0.6)',
                color: '#f8fafc',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              {mobileOpen ? <XIcon size={20} /> : <MenuIcon size={20} />}
            </button>
          </div>
        </div>
      </nav>

      {/* MOBILE DRAWER */}
      {mobileOpen && (
        <>
          <div
            style={{
              position: 'fixed',
              inset: 0,
              zIndex: 90,
              background: 'rgba(4, 7, 13, 0.75)',
              backdropFilter: 'blur(10px)',
              WebkitBackdropFilter: 'blur(10px)',
            }}
            onClick={() => setMobileOpen(false)}
            aria-hidden="true"
          />
          <div
            style={{
              position: 'fixed',
              top: 0,
              right: 0,
              bottom: 0,
              width: '85%',
              maxWidth: 340,
              zIndex: 100,
              background: '#0f172a',
              borderLeft: '1px solid rgba(255, 255, 255, 0.08)',
              padding: '24px 20px',
              display: 'flex',
              flexDirection: 'column',
              boxShadow: '-12px 0 40px rgba(0, 0, 0, 0.8)',
            }}
            role="dialog"
            aria-modal="true"
            aria-label="Mobil navigatsiya"
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 28 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <img src="/grandec.png" alt="GRANDEC" style={{ width: 30, height: 30 }} />
                <span style={{ fontWeight: 900, fontSize: 16, color: '#f8fafc' }}>GRAND EDUCATION</span>
              </div>
              <button
                type="button"
                onClick={() => setMobileOpen(false)}
                style={{
                  background: 'none',
                  border: 'none',
                  color: '#94a3b8',
                  cursor: 'pointer',
                }}
              >
                <XIcon size={20} />
              </button>
            </div>

            <nav style={{ display: 'flex', flexDirection: 'column', gap: 8, flex: 1 }}>
              {sectionNav.map(([k, href]) => (
                <a
                  key={k}
                  href={href}
                  onClick={() => setMobileOpen(false)}
                  style={{
                    padding: '12px 14px',
                    borderRadius: 12,
                    fontSize: 15,
                    fontWeight: 600,
                    color: '#94a3b8',
                    textDecoration: 'none',
                  }}
                >
                  {t(k)}
                </a>
              ))}
            </nav>

            <div style={{ borderTop: '1px solid rgba(255, 255, 255, 0.08)', paddingTop: 20 }}>
              {user ? (
                <Link
                  to={startTo}
                  onClick={() => setMobileOpen(false)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    width: '100%',
                    padding: '12px 20px',
                    borderRadius: 12,
                    background: 'linear-gradient(135deg, #F59E0B, #FBBF24)',
                    color: '#090d16',
                    fontWeight: 800,
                    fontSize: 14,
                    textDecoration: 'none',
                  }}
                >
                  {user.full_name} →
                </Link>
              ) : (
                <button
                  type="button"
                  onClick={() => {
                    setMobileOpen(false);
                    openAuthModal('login');
                  }}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    width: '100%',
                    padding: '12px 20px',
                    borderRadius: 12,
                    background: 'linear-gradient(135deg, #F59E0B, #FBBF24)',
                    color: '#090d16',
                    fontWeight: 800,
                    fontSize: 14,
                    border: 'none',
                    cursor: 'pointer',
                  }}
                >
                  {t('login')} (1-klik)
                </button>
              )}
            </div>
          </div>
        </>
      )}

      {/* MAIN HERO SECTION */}
      <main id="main-content" style={{ position: 'relative', zIndex: 1, paddingTop: '5.5rem' }}>
        <section id="hero" style={{ padding: '40px 20px 60px' }}>
          <div
            style={{
              margin: '0 auto',
              maxWidth: 1200,
              display: 'grid',
              gridTemplateColumns: '1fr',
              gap: 44,
              alignItems: 'center',
            }}
            className="hero-grid"
          >
            {/* Left Column: Headlines & 1-Click CTAs */}
            <div>
              {/* Badge */}
              <div style={{ marginBottom: 20 }}>
                <span
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 8,
                    padding: '6px 16px',
                    borderRadius: 999,
                    fontSize: 12,
                    fontWeight: 700,
                    background: 'rgba(245, 158, 11, 0.1)',
                    color: '#F59E0B',
                    border: '1px solid rgba(245, 158, 11, 0.25)',
                    boxShadow: '0 0 20px rgba(245, 158, 11, 0.1)',
                  }}
                >
                  <span
                    style={{
                      width: 8,
                      height: 8,
                      borderRadius: 999,
                      background: '#10B981',
                      boxShadow: '0 0 10px #10B981',
                    }}
                  />
                  Milliy sertifikat — Ona tili va adabiyot (2026 yangi formati)
                </span>
              </div>

              {/* Main Headline */}
              <h1
                style={{
                  fontSize: 'clamp(2.4rem, 5vw, 3.8rem)',
                  lineHeight: 1.1,
                  fontWeight: 900,
                  letterSpacing: '-0.03em',
                  color: '#f8fafc',
                  margin: '0 0 20px',
                }}
              >
                Milliy sertifikatga{' '}
                <span className="hero-title-gradient">AI bilan tayyorlaning</span>
              </h1>

              {/* Subhead */}
              <p
                style={{
                  fontSize: 'clamp(1.05rem, 1.8vw, 1.2rem)',
                  lineHeight: 1.7,
                  color: '#94a3b8',
                  maxWidth: 540,
                  margin: '0 0 32px',
                }}
              >
                BMB Davlat standarti asosidagi <b style={{ color: '#F59E0B' }}>12 ta mezonli</b> AI Esse tahlili,{' '}
                <b style={{ color: '#10B981' }}>Fast CBT</b> test simulyatori va jonli 1v1 Arena bellashuvlari.
              </p>

              {/* 1-Click Action Buttons */}
              <div
                style={{
                  display: 'flex',
                  flexWrap: 'wrap',
                  gap: 14,
                  alignItems: 'center',
                  marginBottom: 28,
                }}
              >
                <button
                  type="button"
                  onClick={() => (user ? navigate(startTo) : openAuthModal('register'))}
                  className="btn-glow"
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 8,
                    padding: '14px 28px',
                    borderRadius: 14,
                    fontSize: 15,
                    fontWeight: 800,
                    color: '#090d16',
                    background: 'linear-gradient(135deg, #F59E0B, #FBBF24)',
                    border: 'none',
                    cursor: 'pointer',
                    boxShadow: '0 4px 20px rgba(245, 158, 11, 0.4)',
                    transition: 'all 0.2s ease',
                  }}
                >
                  <span>🚀 Bepul boshlash</span>
                  <span style={{ fontSize: 16 }}>→</span>
                </button>

                <button
                  type="button"
                  onClick={() => (user ? navigate(startTo) : openAuthModal('login'))}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 8,
                    padding: '13px 22px',
                    borderRadius: 14,
                    fontSize: 14,
                    fontWeight: 700,
                    color: '#f8fafc',
                    background: 'rgba(255, 255, 255, 0.05)',
                    border: '1px solid rgba(255, 255, 255, 0.14)',
                    cursor: 'pointer',
                    backdropFilter: 'blur(12px)',
                    transition: 'all 0.2s ease',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.borderColor = 'rgba(245, 158, 11, 0.4)';
                    e.currentTarget.style.background = 'rgba(255, 255, 255, 0.08)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.14)';
                    e.currentTarget.style.background = 'rgba(255, 255, 255, 0.05)';
                  }}
                >
                  <span>⚡ 1-klikda kirish</span>
                </button>
              </div>

              {/* Trust Indicators */}
              <div
                style={{
                  display: 'flex',
                  flexWrap: 'wrap',
                  gap: '10px 24px',
                  fontSize: 13,
                  fontWeight: 600,
                  color: '#94a3b8',
                }}
              >
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                  <CheckIcon size={16} className="text-emerald" style={{ color: '#10B981' }} />
                  15 soniyada AI tahlil
                </span>
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                  <CheckIcon size={16} className="text-amber" style={{ color: '#F59E0B' }} />
                  12 ta rasmiy BMB mezoni
                </span>
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                  <CheckIcon size={16} className="text-purple" style={{ color: '#8B5CF6' }} />
                  1v1 Jonli ELO Arena
                </span>
              </div>
            </div>

            {/* Right Column: High-End Interactive Demo Widget */}
            <div>
              <div
                className="glass-card lcard-hover"
                style={{
                  borderRadius: 24,
                  padding: 24,
                  background: 'rgba(15, 23, 42, 0.7)',
                  border: '1px solid rgba(255, 255, 255, 0.08)',
                  backdropFilter: 'blur(16px)',
                  boxShadow: '0 24px 60px -15px rgba(0, 0, 0, 0.7), inset 0 1px 0 rgba(255, 255, 255, 0.06)',
                }}
              >
                {/* Segmented Demo Tabs */}
                <div
                  style={{
                    display: 'flex',
                    background: 'rgba(30, 41, 59, 0.6)',
                    borderRadius: 14,
                    padding: 4,
                    marginBottom: 20,
                    border: '1px solid rgba(255, 255, 255, 0.06)',
                  }}
                >
                  <button
                    type="button"
                    onClick={() => setDemoTab('essay')}
                    style={{
                      flex: 1,
                      padding: '10px 14px',
                      borderRadius: 10,
                      fontSize: 13,
                      fontWeight: 800,
                      border: 'none',
                      cursor: 'pointer',
                      transition: 'all 0.2s ease',
                      background: demoTab === 'essay' ? 'rgba(245, 158, 11, 0.18)' : 'transparent',
                      color: demoTab === 'essay' ? '#F59E0B' : '#94a3b8',
                      boxShadow: demoTab === 'essay' ? '0 0 12px rgba(245, 158, 11, 0.2)' : 'none',
                    }}
                  >
                    ✍️ AI Esse (12 Mezon)
                  </button>
                  <button
                    type="button"
                    onClick={() => setDemoTab('test')}
                    style={{
                      flex: 1,
                      padding: '10px 14px',
                      borderRadius: 10,
                      fontSize: 13,
                      fontWeight: 800,
                      border: 'none',
                      cursor: 'pointer',
                      transition: 'all 0.2s ease',
                      background: demoTab === 'test' ? 'rgba(16, 185, 129, 0.18)' : 'transparent',
                      color: demoTab === 'test' ? '#10B981' : '#94a3b8',
                      boxShadow: demoTab === 'test' ? '0 0 12px rgba(16, 185, 129, 0.2)' : 'none',
                    }}
                  >
                    📚 Fast CBT Test
                  </button>
                </div>

                {/* TAB 1: AI ESSE DEMO */}
                {demoTab === 'essay' && (
                  <div>
                    {/* Demo Topic Header */}
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        gap: 10,
                        marginBottom: 12,
                      }}
                    >
                      <div>
                        <span style={{ fontSize: 11, fontWeight: 700, color: '#F59E0B', textTransform: 'uppercase' }}>
                          Insho mavzusi
                        </span>
                        <h4 style={{ margin: '4px 0 0', fontSize: 15, fontWeight: 800, color: '#f8fafc' }}>
                          Alisher Navoiy ijodida insonparvarlik gʻoyalari
                        </h4>
                      </div>
                      <span
                        style={{
                          padding: '4px 10px',
                          borderRadius: 8,
                          fontSize: 11,
                          fontWeight: 800,
                          background: 'rgba(16, 185, 129, 0.15)',
                          color: '#34D399',
                          border: '1px solid rgba(16, 185, 129, 0.3)',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        A daraja · 90.8%
                      </span>
                    </div>

                    {/* Score summary bar */}
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '12px 16px',
                        borderRadius: 14,
                        background: 'linear-gradient(135deg, rgba(245, 158, 11, 0.1), rgba(16, 185, 129, 0.08))',
                        border: '1px solid rgba(245, 158, 11, 0.2)',
                        marginBottom: 16,
                      }}
                    >
                      <div>
                        <span style={{ fontSize: 10, fontWeight: 700, color: '#94a3b8' }}>Umumiy ball:</span>
                        <div style={{ fontSize: 22, fontWeight: 900, color: '#f8fafc' }}>
                          54.5 <span style={{ fontSize: 14, color: '#F59E0B' }}>/ 60</span>
                        </div>
                      </div>
                      <div style={{ textAlign: 'right' }}>
                        <span style={{ fontSize: 10, fontWeight: 700, color: '#94a3b8' }}>Matn hajmi:</span>
                        <div style={{ fontSize: 14, fontWeight: 800, color: '#10B981' }}>278 soʻz (Yetarli)</div>
                      </div>
                    </div>

                    {/* Criteria Selector Chips */}
                    <p style={{ fontSize: 11, fontWeight: 700, color: '#94a3b8', margin: '0 0 8px' }}>
                      Mezonni tanlang (jonli tahlil):
                    </p>
                    <div
                      style={{
                        display: 'flex',
                        flexWrap: 'wrap',
                        gap: 6,
                        marginBottom: 14,
                      }}
                    >
                      {ESSAY_12_CRITERIA.slice(0, 6).map((crit) => {
                        const isSel = selectedCrit.id === crit.id;
                        return (
                          <button
                            key={crit.id}
                            type="button"
                            onClick={() => setSelectedCrit(crit)}
                            style={{
                              padding: '6px 10px',
                              borderRadius: 8,
                              fontSize: 11,
                              fontWeight: 700,
                              cursor: 'pointer',
                              border: `1px solid ${isSel ? 'rgba(245, 158, 11, 0.5)' : 'rgba(255, 255, 255, 0.08)'}`,
                              background: isSel ? 'rgba(245, 158, 11, 0.18)' : 'rgba(30, 41, 59, 0.4)',
                              color: isSel ? '#F59E0B' : '#cbd5e1',
                              transition: 'all 0.15s ease',
                            }}
                          >
                            {crit.id}. {crit.name.split(' ')[0]} ({crit.score})
                          </button>
                        );
                      })}
                    </div>

                    {/* Active Criterion Critique Box */}
                    <div
                      style={{
                        padding: '14px',
                        borderRadius: 14,
                        background: 'rgba(15, 23, 42, 0.9)',
                        border: '1px solid rgba(245, 158, 11, 0.25)',
                        marginBottom: 16,
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                        <b style={{ fontSize: 13, color: '#F59E0B' }}>
                          {selectedCrit.id}. {selectedCrit.name}
                        </b>
                        <span style={{ fontSize: 12, fontWeight: 800, color: '#10B981' }}>{selectedCrit.score}</span>
                      </div>
                      <p style={{ fontSize: 12, color: '#cbd5e1', margin: '0 0 6px', lineHeight: 1.5 }}>
                        {selectedCrit.desc}
                      </p>
                      <div
                        style={{
                          fontSize: 11,
                          color: '#94a3b8',
                          background: 'rgba(245, 158, 11, 0.08)',
                          padding: '6px 10px',
                          borderRadius: 8,
                          display: 'flex',
                          alignItems: 'center',
                          gap: 6,
                        }}
                      >
                        <LightbulbIcon size={14} style={{ color: '#F59E0B', flexShrink: 0 }} />
                        <span>{selectedCrit.advice}</span>
                      </div>
                    </div>

                    <button
                      type="button"
                      onClick={() => handleAction('/essays')}
                      style={{
                        width: '100%',
                        padding: '11px',
                        borderRadius: 12,
                        background: 'rgba(245, 158, 11, 0.15)',
                        border: '1px solid rgba(245, 158, 11, 0.35)',
                        color: '#F59E0B',
                        fontSize: 13,
                        fontWeight: 800,
                        cursor: 'pointer',
                        transition: 'all 0.2s ease',
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.background = 'rgba(245, 158, 11, 0.25)';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.background = 'rgba(245, 158, 11, 0.15)';
                      }}
                    >
                      O‘z essengizni tahlil qiling →
                    </button>
                  </div>
                )}

                {/* TAB 2: FAST CBT TEST DEMO */}
                {demoTab === 'test' && (
                  <div>
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        fontSize: 12,
                        fontWeight: 700,
                        color: '#94a3b8',
                        marginBottom: 12,
                      }}
                    >
                      <span style={{ color: '#10B981' }}>● 38 / 45-savol</span>
                      <span>Qolgan vaqt: 01:24:50</span>
                    </div>

                    <h4 style={{ fontSize: 15, fontWeight: 800, color: '#f8fafc', margin: '0 0 16px', lineHeight: 1.5 }}>
                      {CBT_QUESTION.question}
                    </h4>

                    {/* Choices */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 16 }}>
                      {CBT_QUESTION.options.map((opt) => {
                        const isChosen = selectedOptionKey === opt.key;
                        const isCorrect = opt.correct;
                        const showCorrectState = selectedOptionKey !== null && isCorrect;
                        const showWrongState = isChosen && !isCorrect;

                        return (
                          <button
                            key={opt.key}
                            type="button"
                            onClick={() => handleCbtOptionClick(opt.key)}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'space-between',
                              width: '100%',
                              padding: '11px 14px',
                              borderRadius: 12,
                              fontSize: 13,
                              fontWeight: 700,
                              cursor: 'pointer',
                              textAlign: 'left',
                              transition: 'all 0.2s ease',
                              background: showCorrectState
                                ? 'rgba(16, 185, 129, 0.2)'
                                : showWrongState
                                ? 'rgba(239, 68, 68, 0.2)'
                                : 'rgba(30, 41, 59, 0.4)',
                              border: `1px solid ${
                                showCorrectState
                                  ? '#10B981'
                                  : showWrongState
                                  ? '#ef4444'
                                  : 'rgba(255, 255, 255, 0.08)'
                              }`,
                              color: showCorrectState
                                ? '#34D399'
                                : showWrongState
                                ? '#f87171'
                                : '#f8fafc',
                            }}
                          >
                            <span>
                              <b>{opt.key})</b> {opt.text}
                            </span>
                            {showCorrectState && <span>✓ To‘g‘ri</span>}
                            {showWrongState && <span>✕ Noto‘g‘ri</span>}
                          </button>
                        );
                      })}
                    </div>

                    {/* Explanation */}
                    {selectedOptionKey && (
                      <div
                        style={{
                          padding: '12px 14px',
                          borderRadius: 12,
                          background: 'rgba(16, 185, 129, 0.1)',
                          border: '1px solid rgba(16, 185, 129, 0.25)',
                          fontSize: 12,
                          color: '#cbd5e1',
                          lineHeight: 1.5,
                          marginBottom: 16,
                        }}
                      >
                        <b style={{ color: '#10B981', display: 'block', marginBottom: 4 }}>💡 Tahlil va izoh:</b>
                        {CBT_QUESTION.explanation}
                      </div>
                    )}

                    <button
                      type="button"
                      onClick={() => handleAction('/tests')}
                      style={{
                        width: '100%',
                        padding: '11px',
                        borderRadius: 12,
                        background: 'rgba(16, 185, 129, 0.15)',
                        border: '1px solid rgba(16, 185, 129, 0.35)',
                        color: '#10B981',
                        fontSize: 13,
                        fontWeight: 800,
                        cursor: 'pointer',
                        transition: 'all 0.2s ease',
                      }}
                    >
                      To‘liq test sinovini boshlash →
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>
        </section>

        {/* 3 CORE DIRECTIONS SECTION ("IMKONIYATLAR") */}
        <section
          id="features"
          style={{
            padding: '70px 20px',
            position: 'relative',
          }}
        >
          <div style={{ margin: '0 auto', maxWidth: 1200 }}>
            <div style={{ textAlign: 'center', maxWidth: 640, margin: '0 auto 48px' }}>
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 900,
                  letterSpacing: '0.22em',
                  color: '#F59E0B',
                  textTransform: 'uppercase',
                }}
              >
                PLATFORMA IMKONIYATLARI
              </span>
              <h2
                style={{
                  fontSize: 'clamp(1.8rem, 3.5vw, 2.5rem)',
                  fontWeight: 900,
                  color: '#f8fafc',
                  margin: '12px 0',
                }}
              >
                Milliy sertifikatga tayyorlovchi{' '}
                <span className="hero-title-gradient">3 ta asosiy yo‘nalish</span>
              </h2>
              <p style={{ fontSize: 15, color: '#94a3b8', lineHeight: 1.6, margin: 0 }}>
                BMB talablariga to‘liq moslashtirilgan sunʼiy intellekt va interaktiv tizimlar
              </p>
            </div>

            {/* 3 Core Direction Cards Grid */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
                gap: 24,
              }}
            >
              {/* Card 1: AI Esse */}
              <div
                className="glass-card lcard-hover"
                style={{
                  borderRadius: 24,
                  padding: '32px 28px',
                  display: 'flex',
                  flexDirection: 'column',
                  background: 'rgba(15, 23, 42, 0.65)',
                  border: '1px solid rgba(255, 255, 255, 0.08)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
                  <div
                    style={{
                      width: 52,
                      height: 52,
                      borderRadius: 16,
                      background: 'rgba(245, 158, 11, 0.12)',
                      border: '1px solid rgba(245, 158, 11, 0.28)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: '#F59E0B',
                      boxShadow: '0 0 20px rgba(245, 158, 11, 0.15)',
                    }}
                  >
                    <PenLineIcon size={26} />
                  </div>
                  <span
                    style={{
                      padding: '4px 10px',
                      borderRadius: 999,
                      fontSize: 11,
                      fontWeight: 800,
                      background: 'rgba(245, 158, 11, 0.15)',
                      color: '#F59E0B',
                      border: '1px solid rgba(245, 158, 11, 0.3)',
                    }}
                  >
                    12 BMB Mezon
                  </span>
                </div>

                <h3 style={{ fontSize: 20, fontWeight: 900, color: '#f8fafc', margin: '0 0 10px' }}>
                  ✍️ AI Esse Baholash
                </h3>
                <p style={{ fontSize: 14, color: '#94a3b8', lineHeight: 1.65, margin: '0 0 20px', flex: 1 }}>
                  12 ta rasmiy mezon boʻyicha inshongizni 15 soniya ichida grammatika, uslub, punktuatsiya va dalillanish
                  darajasigacha chuqur tahlil qilib, aniq tavsiyalar beradi.
                </p>

                <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 24, fontSize: 13, color: '#cbd5e1' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <CheckIcon size={16} style={{ color: '#F59E0B' }} />
                    <span>12 ta BMB mezoniga 100% muvofiqlik</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <CheckIcon size={16} style={{ color: '#F59E0B' }} />
                    <span>Imlo va punktuatsiya xatolarini ko‘rsatish</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <CheckIcon size={16} style={{ color: '#F59E0B' }} />
                    <span>A darajaga erishish uchun tavsiyalar</span>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={() => handleAction('/essays')}
                  style={{
                    width: '100%',
                    padding: '12px',
                    borderRadius: 12,
                    background: 'rgba(245, 158, 11, 0.15)',
                    border: '1px solid rgba(245, 158, 11, 0.35)',
                    color: '#F59E0B',
                    fontWeight: 800,
                    fontSize: 14,
                    cursor: 'pointer',
                    transition: 'all 0.2s ease',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = 'rgba(245, 158, 11, 0.25)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = 'rgba(245, 158, 11, 0.15)';
                  }}
                >
                  Esseni sinash →
                </button>
              </div>

              {/* Card 2: CBT Tests */}
              <div
                className="glass-card lcard-hover"
                style={{
                  borderRadius: 24,
                  padding: '32px 28px',
                  display: 'flex',
                  flexDirection: 'column',
                  background: 'rgba(15, 23, 42, 0.65)',
                  border: '1px solid rgba(255, 255, 255, 0.08)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
                  <div
                    style={{
                      width: 52,
                      height: 52,
                      borderRadius: 16,
                      background: 'rgba(16, 185, 129, 0.12)',
                      border: '1px solid rgba(16, 185, 129, 0.28)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: '#10B981',
                      boxShadow: '0 0 20px rgba(16, 185, 129, 0.15)',
                    }}
                  >
                    <FileTextIcon size={26} />
                  </div>
                  <span
                    style={{
                      padding: '4px 10px',
                      borderRadius: 999,
                      fontSize: 11,
                      fontWeight: 800,
                      background: 'rgba(16, 185, 129, 0.15)',
                      color: '#34D399',
                      border: '1px solid rgba(16, 185, 129, 0.3)',
                    }}
                  >
                    Fast CBT Rejimi
                  </span>
                </div>

                <h3 style={{ fontSize: 20, fontWeight: 900, color: '#f8fafc', margin: '0 0 10px' }}>
                  📚 Milliy Sertifikat Testlari
                </h3>
                <p style={{ fontSize: 14, color: '#94a3b8', lineHeight: 1.65, margin: '0 0 20px', flex: 1 }}>
                  Haqiqiy CBT imtihon muhiti — 1 tadan ishlash rejimi, aniq vaqt nazorati va har bir savolga professional
                  ustozlar tahlili.
                </p>

                <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 24, fontSize: 13, color: '#cbd5e1' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <CheckIcon size={16} style={{ color: '#10B981' }} />
                    <span>1 tadan ishlash (Fast CBT interfeys)</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <CheckIcon size={16} style={{ color: '#10B981' }} />
                    <span>BMB 2026 yangi formati (45 ta savol)</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <CheckIcon size={16} style={{ color: '#10B981' }} />
                    <span>Har bir savolga batafsil tahliliy izoh</span>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={() => handleAction('/tests')}
                  style={{
                    width: '100%',
                    padding: '12px',
                    borderRadius: 12,
                    background: 'rgba(16, 185, 129, 0.15)',
                    border: '1px solid rgba(16, 185, 129, 0.35)',
                    color: '#34D399',
                    fontWeight: 800,
                    fontSize: 14,
                    cursor: 'pointer',
                    transition: 'all 0.2s ease',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = 'rgba(16, 185, 129, 0.25)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = 'rgba(16, 185, 129, 0.15)';
                  }}
                >
                  Testlarni ishlash →
                </button>
              </div>

              {/* Card 3: 1v1 Arena */}
              <div
                className="glass-card lcard-hover"
                style={{
                  borderRadius: 24,
                  padding: '32px 28px',
                  display: 'flex',
                  flexDirection: 'column',
                  background: 'rgba(15, 23, 42, 0.65)',
                  border: '1px solid rgba(255, 255, 255, 0.08)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
                  <div
                    style={{
                      width: 52,
                      height: 52,
                      borderRadius: 16,
                      background: 'rgba(139, 92, 246, 0.12)',
                      border: '1px solid rgba(139, 92, 246, 0.28)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: '#A78BFA',
                      boxShadow: '0 0 20px rgba(139, 92, 246, 0.15)',
                    }}
                  >
                    <SwordsIcon size={26} />
                  </div>
                  <span
                    style={{
                      padding: '4px 10px',
                      borderRadius: 999,
                      fontSize: 11,
                      fontWeight: 800,
                      background: 'rgba(139, 92, 246, 0.15)',
                      color: '#A78BFA',
                      border: '1px solid rgba(139, 92, 246, 0.3)',
                    }}
                  >
                    Jonli ELO Duel
                  </span>
                </div>

                <h3 style={{ fontSize: 20, fontWeight: 900, color: '#f8fafc', margin: '0 0 10px' }}>
                  ⚔️ Real-vaqt 1v1 Arena
                </h3>
                <p style={{ fontSize: 14, color: '#94a3b8', lineHeight: 1.65, margin: '0 0 20px', flex: 1 }}>
                  Butun respublika oʻquvchilari yoki AI bot bilan 60 soniyalik tezkor bilim jangi. ELO reytingingizni
                  oshiring va ligalarda yetakchilik qiling!
                </p>

                <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 24, fontSize: 13, color: '#cbd5e1' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <CheckIcon size={16} style={{ color: '#A78BFA' }} />
                    <span>Real vaqtda jonli raqib bilan bellashuv</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <CheckIcon size={16} style={{ color: '#A78BFA' }} />
                    <span>ELO reytingi va respublika ligalari</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <CheckIcon size={16} style={{ color: '#A78BFA' }} />
                    <span>60 soniyalik adrenalinli tezkor jang</span>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={() => handleAction('/arena')}
                  style={{
                    width: '100%',
                    padding: '12px',
                    borderRadius: 12,
                    background: 'rgba(139, 92, 246, 0.15)',
                    border: '1px solid rgba(139, 92, 246, 0.35)',
                    color: '#A78BFA',
                    fontWeight: 800,
                    fontSize: 14,
                    cursor: 'pointer',
                    transition: 'all 0.2s ease',
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = 'rgba(139, 92, 246, 0.25)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = 'rgba(139, 92, 246, 0.15)';
                  }}
                >
                  Arenada bellashish →
                </button>
              </div>
            </div>
          </div>
        </section>

        {/* STATS SECTION */}
        <section id="stats" style={{ padding: '40px 20px 60px' }}>
          <div style={{ margin: '0 auto', maxWidth: 1200 }}>
            {/* Platform totals */}
            {stats && (
              <div
                style={{
                  display: 'flex',
                  flexWrap: 'wrap',
                  gap: 16,
                  justifyContent: 'center',
                  marginBottom: 32,
                }}
              >
                {[
                  { label: t('total_tests'), value: stats.totals.tests, Icon: FileTextIcon, color: '#F59E0B' },
                  { label: t('students'), value: stats.totals.students, Icon: TrophyIcon, color: '#10B981' },
                  { label: t('total_essays'), value: stats.totals.essays_graded, Icon: PenLineIcon, color: '#8B5CF6' },
                ].map((item) => (
                  <div
                    key={item.label}
                    className="glass-card lcard-hover"
                    style={{
                      borderRadius: 18,
                      padding: '16px 28px',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 16,
                      minWidth: 180,
                    }}
                  >
                    <div
                      style={{
                        width: 44,
                        height: 44,
                        borderRadius: 12,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        background: `rgba(${
                          item.color === '#F59E0B' ? '245,158,11' : item.color === '#10B981' ? '16,185,129' : '139,92,246'
                        }, 0.12)`,
                        color: item.color,
                      }}
                    >
                      <item.Icon size={22} />
                    </div>
                    <div>
                      <p style={{ margin: 0, fontSize: 22, fontWeight: 900, color: '#f8fafc' }}>
                        {Number(item.value).toLocaleString()}
                      </p>
                      <p style={{ margin: '2px 0 0', fontSize: 12, fontWeight: 600, color: '#94a3b8' }}>
                        {item.label}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Platform Growth TrendChart */}
            <div style={{ marginTop: 20 }}>
              <div style={{ textAlign: 'center', marginBottom: 16 }}>
                <span
                  style={{
                    fontSize: 11,
                    fontWeight: 900,
                    letterSpacing: '0.2em',
                    color: '#F59E0B',
                    textTransform: 'uppercase',
                  }}
                >
                  {t('an_platform_growth')}
                </span>
              </div>
              <TrendChart data={trend} />
            </div>
          </div>
        </section>

        {/* HOW IT WORKS */}
        <section
          id="how"
          style={{
            padding: '70px 20px',
            background: 'rgba(9, 13, 22, 0.95)',
            borderTop: '1px solid rgba(255, 255, 255, 0.08)',
            borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
          }}
        >
          <div style={{ margin: '0 auto', maxWidth: 1000 }}>
            <div style={{ textAlign: 'center', maxWidth: 600, margin: '0 auto 48px' }}>
              <span style={{ fontSize: 11, fontWeight: 900, letterSpacing: '0.22em', color: '#F59E0B' }}>
                {t('how_eyebrow')}
              </span>
              <h2 style={{ fontSize: 'clamp(1.8rem, 3.5vw, 2.5rem)', fontWeight: 900, color: '#f8fafc', margin: '12px 0' }}>
                {t('how_title_1')} <span className="hero-title-gradient">{t('how_title_2')}</span>
              </h2>
            </div>

            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
                gap: 24,
              }}
            >
              {[
                [t('step1_title'), t('step1_desc'), '#F59E0B'],
                [t('step2_title'), t('step2_desc'), '#10B981'],
                [t('step3_title'), t('step3_desc'), '#8B5CF6'],
              ].map(([title, desc, c], i) => (
                <div
                  key={i}
                  className="glass-card lcard-hover"
                  style={{
                    borderRadius: 20,
                    padding: '32px 24px',
                    textAlign: 'center',
                    background: 'rgba(15, 23, 42, 0.65)',
                    border: '1px solid rgba(255, 255, 255, 0.08)',
                  }}
                >
                  <div
                    style={{
                      width: 56,
                      height: 56,
                      borderRadius: 18,
                      display: 'inline-flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: '#090d16',
                      fontSize: 22,
                      fontWeight: 900,
                      marginBottom: 18,
                      background: `linear-gradient(135deg, ${c}, ${c}dd)`,
                      boxShadow: `0 8px 24px ${c}40`,
                    }}
                  >
                    {i + 1}
                  </div>
                  <h3 style={{ fontSize: 18, fontWeight: 800, color: '#f8fafc', margin: '0 0 10px' }}>{title}</h3>
                  <p style={{ fontSize: 14, color: '#94a3b8', lineHeight: 1.65, margin: 0 }}>{desc}</p>
                </div>
              ))}
            </div>

            <div style={{ marginTop: 44, textAlign: 'center' }}>
              <button
                type="button"
                onClick={() => (user ? navigate(startTo) : openAuthModal('register'))}
                className="btn-glow"
                style={{
                  padding: '14px 36px',
                  fontSize: 15,
                  fontWeight: 800,
                  borderRadius: 14,
                  background: 'linear-gradient(135deg, #F59E0B, #FBBF24)',
                  color: '#090d16',
                  border: 'none',
                  cursor: 'pointer',
                  boxShadow: '0 4px 20px rgba(245, 158, 11, 0.4)',
                }}
              >
                {t('cta_free_account')} →
              </button>
            </div>
          </div>
        </section>
      </main>

      {/* FOOTER */}
      <footer style={{ marginTop: 20 }}>
        <div style={{ height: 1, background: 'linear-gradient(90deg, rgba(245,158,11,.35), rgba(16,185,129,.2), transparent)' }} />
        <div className="land-foot-bg" style={{ position: 'relative', overflow: 'hidden' }}>
          <div style={{ margin: '0 auto', maxWidth: 1200, padding: '60px 20px 36px', width: '100%' }}>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
                gap: 36,
              }}
            >
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <img src="/grandec.png" alt="GRANDEC" style={{ width: 34, height: 34, objectFit: 'cover' }} />
                  <div>
                    <b style={{ display: 'block', fontSize: 16, color: '#f8fafc' }}>GRAND EDUCATION</b>
                    <small style={{ fontSize: 9, fontWeight: 700, letterSpacing: '0.2em', color: '#F59E0B' }}>
                      LMS PLATFORM
                    </small>
                  </div>
                </div>
                <p style={{ fontSize: 14, lineHeight: 1.7, color: '#94a3b8', marginTop: 16 }}>
                  {t('foot_mission')}
                </p>
              </div>

              <div>
                <h4 style={{ fontSize: 12, fontWeight: 900, letterSpacing: '0.2em', color: '#F59E0B', margin: '0 0 18px', textTransform: 'uppercase' }}>
                  {t('foot_pages')}
                </h4>
                <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 10, fontSize: 14 }}>
                  {sectionNav.map(([k, href]) => (
                    <li key={k}>
                      <a href={href} style={{ color: '#94a3b8', textDecoration: 'none' }}>
                        {t(k)}
                      </a>
                    </li>
                  ))}
                  <li>
                    <button
                      type="button"
                      onClick={() => openAuthModal('login')}
                      style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer', padding: 0, fontSize: 14 }}
                    >
                      {t('login')}
                    </button>
                  </li>
                  <li>
                    <button
                      type="button"
                      onClick={() => openAuthModal('register')}
                      style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer', padding: 0, fontSize: 14 }}
                    >
                      {t('register')}
                    </button>
                  </li>
                </ul>
              </div>

              <div>
                <h4 style={{ fontSize: 12, fontWeight: 900, letterSpacing: '0.2em', color: '#F59E0B', margin: '0 0 18px', textTransform: 'uppercase' }}>
                  {t('foot_news')}
                </h4>
                <p style={{ fontSize: 14, lineHeight: 1.7, color: '#94a3b8', margin: '0 0 14px' }}>
                  {t('foot_newsletter_desc')}
                </p>
                {newsDone ? (
                  <p style={{ fontSize: 14, fontWeight: 600, color: '#10B981', margin: 0 }}>
                    {t('foot_subscribed_toast')}
                  </p>
                ) : (
                  <form onSubmit={subscribeNews} style={{ display: 'flex', gap: 8 }}>
                    <input
                      type="email"
                      required
                      placeholder={t('foot_email_placeholder')}
                      value={newsEmail}
                      onChange={(e) => setNewsEmail(e.target.value)}
                      aria-label="Email manzil"
                      style={{
                        flex: 1,
                        minWidth: 0,
                        padding: '10px 14px',
                        borderRadius: 12,
                        background: 'rgba(15, 23, 42, 0.8)',
                        border: '1px solid rgba(255, 255, 255, 0.1)',
                        color: '#f8fafc',
                        fontSize: 13,
                      }}
                    />
                    <button
                      type="submit"
                      style={{
                        padding: '10px 16px',
                        borderRadius: 12,
                        background: 'linear-gradient(135deg, #F59E0B, #FBBF24)',
                        color: '#090d16',
                        fontWeight: 800,
                        fontSize: 13,
                        border: 'none',
                        cursor: 'pointer',
                      }}
                    >
                      {t('foot_subscribe')}
                    </button>
                  </form>
                )}
              </div>

              <div>
                <h4 style={{ fontSize: 12, fontWeight: 900, letterSpacing: '0.2em', color: '#F59E0B', margin: '0 0 18px', textTransform: 'uppercase' }}>
                  {t('foot_contact')}
                </h4>
                <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 14, fontSize: 14 }}>
                  <li style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <BotIcon size={18} style={{ color: '#F59E0B' }} />
                    <a
                      href="https://t.me/uz_essaygrader_bot"
                      target="_blank"
                      rel="noreferrer"
                      style={{ color: '#F59E0B', textDecoration: 'none' }}
                    >
                      @uz_essaygrader_bot
                    </a>
                  </li>
                  <li style={{ display: 'flex', alignItems: 'center', gap: 10, color: '#94a3b8' }}>
                    <ClockIcon size={18} style={{ color: '#F59E0B' }} />
                    <span>24/7 Avtomatlashtirilgan AI</span>
                  </li>
                  <li style={{ display: 'flex', alignItems: 'center', gap: 10, color: '#94a3b8' }}>
                    <MapPinIcon size={18} style={{ color: '#F59E0B' }} />
                    <span>O‘zbekiston, Toshkent</span>
                  </li>
                </ul>
              </div>
            </div>

            <div
              style={{
                marginTop: 44,
                paddingTop: 24,
                borderTop: '1px solid rgba(255, 255, 255, 0.08)',
                display: 'flex',
                flexWrap: 'wrap',
                justifyContent: 'space-between',
                gap: 12,
                fontSize: 13,
                color: '#64748b',
              }}
            >
              <span>© {new Date().getFullYear()} GRAND EDUCATION (grandec.uz). Barcha huquqlar himoyalangan.</span>
              <span>
                Website{' '}
                <a
                  href="https://www.instagram.com/rozievkomiljon/"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-amber-400 hover:text-amber-300 transition-colors underline underline-offset-4"
                  style={{ color: '#fbbf24', textDecoration: 'underline', textUnderlineOffset: 4, transition: 'color 0.2s' }}
                >
                  Komiljon Ro'ziyev
                </a>{' '}
                tomonidan tayyorlandi
              </span>
            </div>
          </div>
        </div>
      </footer>

      {/* Style overrides for media queries */}
      <style>{`
        @media (min-width: 900px) {
          .hero-grid {
            grid-template-columns: 1.05fr 0.95fr !important;
          }
          .landing-desktop-nav {
            display: flex !important;
          }
          .landing-burger-btn {
            display: none !important;
          }
        }
      `}</style>
    </div>
  );
}
