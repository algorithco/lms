import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';
import { Mic, Headphones } from 'lucide-react';
import { useAuth } from '../auth/AuthContext';
import { useLang } from '../i18n/LangContext';
import { useTheme } from '../theme/ThemeContext';
import { landingFor, formatDisplayName } from '../lib/api';
import HeroCarousel from '../components/HeroCarousel';
import HowItWorks from '../components/HowItWorks';
import SEO from '../components/SEO';
import LanguageSwitcher from '../components/LanguageSwitcher';
import UserNavDropdown from '../components/UserNavDropdown';
import MobileBottomBar from '../components/MobileBottomBar';
import MobileNavDrawer from '../components/MobileNavDrawer';
import MobileProfileDrawer from '../components/MobileProfileDrawer';
import PwaInstallButton from '../components/PwaInstallButton';
import PassingScoresModal from '../components/PassingScoresModal';
import {
  CheckIcon,
  FileTextIcon,
  LightbulbIcon,
  MenuIcon,
  MoonIcon,
  PenLineIcon,
  SunIcon,
  SwordsIcon,
  TrophyIcon,
  XIcon,
} from '../components/icons';

// ---------------------------------------------------------------------------
// TYPES & DATA DEFINITIONS
// ---------------------------------------------------------------------------
export type MainSubject = 'uzbek' | 'english';
export type ExamTrack = 'ielts' | 'multilevel' | 'national_certificate' | 'attestation';

const sectionNav: [string, string][] = [
  ['nav_features', '#features'],
  ['nav_how', '#how'],
  ['nav_comparison', '#comparison'],
  ['nav_pricing', '#pricing'],
  ['nav_faq', '#faq'],
];

export default function Landing() {
  const { t } = useLang();
  const { user, openAuthModal } = useAuth();
  const { resolvedTheme, setTheme } = useTheme();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [navDrawerOpen, setNavDrawerOpen] = useState(false);
  const [profileDrawerOpen, setProfileDrawerOpen] = useState(false);
  const [scoresModalOpen, setScoresModalOpen] = useState(false);

  // -------------------------------------------------------------------------
  // HIERARCHICAL 2-LEVEL SUBJECT & EXAM SELECTOR STATE
  // -------------------------------------------------------------------------
  const [landingSubject] = useState<MainSubject>(() => {
    const track = localStorage.getItem('grandec_selected_track');
    if (track === 'ielts' || track === 'multilevel') return 'english';
    if (track === 'national_certificate' || track === 'attestation') return 'uzbek';
    const saved = localStorage.getItem('landing_subject') || localStorage.getItem('lms_subject');
    return saved === 'english' ? 'english' : 'uzbek';
  });

  const [selectedTrack] = useState<ExamTrack>(() => {
    const track = localStorage.getItem('grandec_selected_track') as ExamTrack | null;
    if (track && ['ielts', 'multilevel', 'national_certificate', 'attestation'].includes(track)) {
      return track;
    }
    const savedSub = localStorage.getItem('landing_subject') || localStorage.getItem('lms_subject');
    return savedSub === 'english' ? 'ielts' : 'national_certificate';
  });

  const startTo = user ? landingFor(user) : '/register';

  // Lock scroll on mobile drawer
  useEffect(() => {
    document.body.style.overflow = mobileOpen ? 'hidden' : '';
    return () => {
      document.body.style.overflow = '';
    };
  }, [mobileOpen]);

  // Option click handlers with celebratory confetti






  const handleAction = (destination: string) => {
    localStorage.setItem('grandec_selected_track', selectedTrack);
    localStorage.setItem('landing_subject', landingSubject);
    localStorage.setItem('lms_subject', landingSubject);
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
          "Milliy sertifikat (Ona tili) va IELTS & Multi-level (Ingliz tili) bo'yicha AI Esse, AI Speaking va CBT test platformasi.",
        sameAs: ['https://t.me/uz_essaygrader_bot'],
      },
    ],
    [],
  );

  return (
    <div
      className="landing"
      style={{
        background: 'var(--bg)',
        color: 'var(--ink)',
        minHeight: '100svh',
        position: 'relative',
        overflowX: 'clip',
      }}
    >
      <SEO
        title={
          selectedTrack === 'ielts'
            ? 'IELTS Academic & General LMS | AI Writing & Speaking Simulator'
            : selectedTrack === 'multilevel'
            ? 'CEFR Multi-level LMS | Davlat BMB Imtihoni & AI Insho'
            : selectedTrack === 'attestation'
            ? 'Pedagoglar Attestatsiyasi 2026 | 70% Ustama & Toifa Testlari'
            : 'Ona tili va adabiyot LMS | Milliy sertifikat & AI Esse'
        }
        description={
          selectedTrack === 'ielts'
            ? "IELTS Band 1.0–9.0 bo'yicha Writing Task 1 & 2 AI baholash, interaktiv Speaking trenajyori va Cambridge CBT Listening/Reading — GRAND EDUCATION."
            : selectedTrack === 'multilevel'
            ? "Davlat CEFR Multi-level (B2/C1) imtihoniga tayyorlovchi rasmiy CBT testlar va AI Writing insho tahlili."
            : selectedTrack === 'attestation'
            ? "O'qituvchilar attestatsiyasi 2026: 50 talik rasmiy sinov (mutaxassislik, kasbiy standart, pedagogik mahorat) va toifa diagnostikasi."
            : "BMB Davlat standarti bo'yicha 12 ta mezonli AI Esse tahlili, 45 talik testlar va 1v1 intellektual Arena."
        }
        jsonLd={jsonLdData}
      />

      {/* Global Background Glow & Ambient Mesh Glow (Warm Academic Luxury) */}
      <div
        style={{
          position: 'absolute',
          top: 0,
          left: '50%',
          transform: 'translateX(-50%)',
          width: '100vw',
          height: 600,
          background: 'radial-gradient(ellipse 80% 60% at 50% -10%, rgba(245, 158, 11, 0.08), rgba(248, 250, 252, 0))',
          pointerEvents: 'none',
          zIndex: 0,
        }}
      />
      <div
        style={{
          position: 'absolute',
          top: 80,
          left: '8%',
          width: 380,
          height: 380,
          borderRadius: 999,
          background: 'radial-gradient(circle, rgba(16, 185, 129, 0.06) 0%, transparent 70%)',
          filter: 'blur(50px)',
          pointerEvents: 'none',
          zIndex: 0,
        }}
      />
      <div
        style={{
          position: 'absolute',
          top: 100,
          right: '8%',
          width: 420,
          height: 420,
          borderRadius: 999,
          background: 'radial-gradient(circle, rgba(245, 158, 11, 0.06) 0%, transparent 70%)',
          filter: 'blur(50px)',
          pointerEvents: 'none',
          zIndex: 0,
        }}
      />

      {/* NAVBAR */}
      <header
        className="landing-header backdrop-blur-md"
        style={{
          position: 'sticky',
          top: 0,
          zIndex: 50,
          backdropFilter: 'blur(16px)',
          WebkitBackdropFilter: 'blur(16px)',
          background: 'var(--header-bg)',
          borderBottom: '1px solid var(--border)',
          transition: 'background 0.3s ease, border-color 0.3s ease',
        }}
      >
        <div
          style={{
            margin: '0 auto',
            maxWidth: 1200,
            padding: '10px 16px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 12,
          }}
        >
          {/* 1. Chapda: GRANDEC rasmiy logotipi (h-8 w-auto) */}
          <Link
            to="/"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              textDecoration: 'none',
              color: 'inherit',
              flexShrink: 0,
            }}
          >
            <img
              src="/logo-mark.png"
              alt="GRANDEC"
              style={{
                height: 32,
                width: 'auto',
                objectFit: 'contain',
              }}
            />
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              <span
                style={{
                  fontSize: 16,
                  fontWeight: 900,
                  letterSpacing: '-0.02em',
                  color: 'var(--ink)',
                  lineHeight: 1.1,
                }}
              >
                GRANDEC
              </span>
              <span
                style={{
                  fontSize: 8,
                  fontWeight: 800,
                  letterSpacing: '0.12em',
                  color: '#D97706',
                  textTransform: 'uppercase',
                  marginTop: 1,
                }}
              >
                ACADEMIC EDTECH
              </span>
            </div>
          </Link>

          {/* 2. Desktop Nav Anchors — Strictly hidden on mobile (< 768px) */}
          <nav
            className="hidden md:flex items-center gap-1"
            aria-label="Asosiy navigatsiya"
          >
            <Link
              to="/tests"
              style={{
                padding: '8px 14px',
                borderRadius: 10,
                fontSize: 14,
                fontWeight: 700,
                color: 'var(--ink)',
                textDecoration: 'none',
                transition: 'all 0.15s ease',
              }}
            >
              {t('nav_tests', 'Testlar')}
            </Link>
            <Link
              to="/essays"
              style={{
                padding: '8px 14px',
                borderRadius: 10,
                fontSize: 14,
                fontWeight: 700,
                color: 'var(--ink)',
                textDecoration: 'none',
                transition: 'all 0.15s ease',
              }}
            >
              {t('nav_essays', 'AI Esse')}
            </Link>
            <Link
              to="/arena"
              style={{
                padding: '8px 14px',
                borderRadius: 10,
                fontSize: 14,
                fontWeight: 700,
                color: 'var(--ink)',
                textDecoration: 'none',
                transition: 'all 0.15s ease',
              }}
            >
              {t('nav_arena', '1v1 Arena')}
            </Link>
            <button
              type="button"
              onClick={() => setScoresModalOpen(true)}
              style={{
                padding: '8px 14px',
                borderRadius: 10,
                fontSize: 14,
                fontWeight: 700,
                color: 'var(--ink)',
                background: 'transparent',
                border: 'none',
                cursor: 'pointer',
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
              }}
            >
              <span>{t('nav_passing_scores', "O'tish ballari")} 2026</span>
              <span
                style={{
                  fontSize: 10,
                  fontWeight: 800,
                  padding: '2px 6px',
                  borderRadius: 999,
                  background: 'rgba(16, 185, 129, 0.15)',
                  color: '#059669',
                }}
              >
                Yangi
              </span>
            </button>
            <Link
              to="/pricing"
              style={{
                padding: '8px 14px',
                borderRadius: 10,
                fontSize: 14,
                fontWeight: 700,
                color: 'var(--ink)',
                textDecoration: 'none',
                transition: 'all 0.15s ease',
              }}
            >
              {t('nav_pricing', 'Tariflar')}
            </Link>
          </nav>

          {/* 3. O'ng tomon: Desktop (PWA, Lang, Theme, Auth) va Mobile (Faqat Avatar + Gamburger) */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {/* Desktop-only right controls */}
            <div className="hidden md:flex items-center gap-2">
              <PwaInstallButton />
              {user ? (
                <UserNavDropdown />
              ) : (
                <>
                  <LanguageSwitcher />
                  <button
                    type="button"
                    onClick={() => setTheme(resolvedTheme === 'light' ? 'dark' : 'light')}
                    title={resolvedTheme === 'light' ? "Qorong'i rejimga o'tish" : "Yorug' rejimga o'tish"}
                    aria-label={resolvedTheme === 'light' ? "Qorong'i rejim" : "Yorug' rejim"}
                    style={{
                      width: 36,
                      height: 36,
                      borderRadius: 10,
                      background: 'var(--card)',
                      border: '1px solid var(--border)',
                      color: 'var(--ink)',
                      display: 'inline-flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      cursor: 'pointer',
                      transition: 'all 0.2s ease',
                    }}
                  >
                    {resolvedTheme === 'light' ? <MoonIcon size={16} /> : <SunIcon size={16} />}
                  </button>
                  <button
                    type="button"
                    onClick={() => openAuthModal('login')}
                    className="btn-glow btn-shimmer"
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 8,
                      padding: '9px 20px',
                      borderRadius: 12,
                      fontSize: 14,
                      fontWeight: 800,
                      color: '#FFFFFF',
                      background: 'linear-gradient(135deg, #F59E0B, #D97706)',
                      border: 'none',
                      cursor: 'pointer',
                      boxShadow: '0 4px 16px rgba(217, 119, 6, 0.3)',
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
                </>
              )}
            </div>

            {/* Mobile-only right controls: Faqat Profil Avatari (NJ / KR) va Gamburger menyu (☰) */}
            <div className="flex md:hidden items-center gap-2">
              <button
                type="button"
                onClick={() => {
                  if (user) {
                    setProfileDrawerOpen(true);
                  } else {
                    openAuthModal('login');
                  }
                }}
                aria-label="Profil"
                style={{
                  width: 32,
                  height: 32,
                  borderRadius: '50%',
                  background: 'linear-gradient(135deg, #F59E0B 0%, #D97706 100%)',
                  color: '#FFFFFF',
                  border: '2px solid rgba(245, 158, 11, 0.7)',
                  boxShadow: '0 2px 8px rgba(217, 119, 6, 0.3)',
                  cursor: 'pointer',
                  padding: 0,
                  overflow: 'hidden',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                {user?.avatar ? (
                  <img src={user.avatar} alt="Avatar" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                ) : (
                  <span style={{ fontSize: 11, fontWeight: 900 }}>
                    {user
                      ? (user.full_name || '?').split(' ').map((p) => p[0]).join('').slice(0, 2).toUpperCase() || 'KR'
                      : 'KR'}
                  </span>
                )}
              </button>

              <button
                type="button"
                onClick={() => setNavDrawerOpen(true)}
                aria-label="Menyu ochish"
                style={{
                  width: 34,
                  height: 34,
                  borderRadius: 10,
                  background: 'var(--card-2)',
                  border: '1px solid var(--border)',
                  color: 'var(--ink)',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  padding: 0,
                }}
              >
                <MenuIcon size={18} />
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* MOBILE DRAWER */}
      {mobileOpen && (
        <div style={{ position: 'relative', zIndex: 100 }}>
          <div
            style={{
              position: 'fixed',
              inset: 0,
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
              background: 'var(--card)',
              borderLeft: '1px solid var(--border)',
              padding: '24px 20px',
              display: 'flex',
              flexDirection: 'column',
              boxShadow: '-12px 0 40px rgba(0, 0, 0, 0.5)',
            }}
            role="dialog"
            aria-modal="true"
            aria-label="Mobil navigatsiya"
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 28 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <img src="/grandec.png" alt="GRANDEC" style={{ width: 30, height: 30 }} />
                <span style={{ fontWeight: 900, fontSize: 16, color: '#0F172A' }}>GRAND EDUCATION</span>
              </div>
              <button
                type="button"
                onClick={() => setMobileOpen(false)}
                style={{
                  background: 'none',
                  border: 'none',
                  color: '#64748B',
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
                    color: '#64748B',
                    textDecoration: 'none',
                  }}
                >
                  {t(k)}
                </a>
              ))}
            </nav>

            <div style={{ borderTop: '1px solid var(--border)', paddingTop: 20 }}>
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
                  {formatDisplayName(user.full_name, user.email)} →
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
        </div>
      )}

      {/* MAIN CONTENT WRAPPER */}
      <main id="main-content">
        {/* HERO SECTION */}
        <section id="hero" style={{ padding: '40px 20px 64px' }}>
          <div
            style={{
              margin: '0 auto',
              maxWidth: 1200,
            }}
          >
            {/* HERO GRID */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
                gap: 48,
                alignItems: 'center',
              }}
              className="hero-grid"
            >
              {/* Left Column: Clean, Elegant Headline & 1-Click CTAs */}
              <div>
                {/* 1 Single Elegant Badge */}
                <div style={{ marginBottom: 20 }}>
                  <span className="bg-amber-100/80 border border-amber-300 text-amber-900 font-semibold px-4 py-1.5 rounded-full inline-block text-xs sm:text-sm shadow-sm">
                    ✨ 2026-yilgi Rasmiy BMB Milliy Sertifikat va Attestatsiya Dvigateli
                  </span>
                </div>

                {/* Main Headline (TestMakon Contrast Sarlavha) */}
                <h1
                  className="text-slate-900 font-black tracking-tight"
                  style={{
                    fontSize: 'clamp(2.4rem, 4.8vw, 3.8rem)',
                    lineHeight: 1.15,
                    fontWeight: 900,
                    letterSpacing: '-0.03em',
                    color: '#0F172A',
                    margin: '0 0 20px',
                  }}
                >
                  Milliy sertifikatga tayyorgarlik{' '}
                  <span
                    style={{
                      background: 'linear-gradient(135deg, #F59E0B 0%, #D97706 100%)',
                      color: '#FFFFFF',
                      padding: '4px 16px',
                      borderRadius: 18,
                      display: 'inline-block',
                      boxShadow: '0 8px 20px -3px rgba(217, 119, 6, 0.45)',
                    }}
                  >
                    AI tahlili
                  </span>{' '}
                  bilan
                </h1>

                {/* Subhead */}
                <p
                  className="text-slate-600 font-medium"
                  style={{
                    fontSize: 'clamp(1.05rem, 1.8vw, 1.2rem)',
                    lineHeight: 1.7,
                    color: '#475569',
                    maxWidth: 560,
                    margin: '0 0 32px',
                  }}
                >
                  Shaxsiy AI mentor zaif mavzularingizni topadi, 12 mezonli inshoni baholaydi va kunlik mashq rejasini tuzadi.
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
                    onClick={() => handleAction('/register')}
                    className="bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-600 hover:to-amber-700 text-white font-bold shadow-lg shadow-amber-500/25 px-8 py-3.5 rounded-xl text-base inline-flex items-center gap-2 transition-all cursor-pointer border-none"
                    style={{
                      padding: '14px 32px',
                      borderRadius: 14,
                      fontSize: 15,
                      fontWeight: 800,
                      color: '#FFFFFF',
                      background: 'linear-gradient(135deg, #F59E0B, #D97706)',
                      boxShadow: '0 8px 25px -4px rgba(217, 119, 6, 0.4)',
                    }}
                  >
                    <span>⚡️ Bepul boshlash</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => navigate('/tests')}
                    className="bg-white border-2 border-slate-200 hover:border-amber-400 text-slate-800 font-bold px-7 py-3.5 rounded-xl shadow-sm text-base inline-flex items-center gap-2 transition-all cursor-pointer"
                    style={{
                      padding: '13px 28px',
                      borderRadius: 14,
                      fontSize: 14.5,
                      fontWeight: 800,
                      color: '#1E293B',
                      background: '#FFFFFF',
                      border: '2px solid #E2E8F0',
                      boxShadow: '0 2px 10px rgba(0, 0, 0, 0.04)',
                    }}
                  >
                    <span>Testlarni ko&apos;rish</span>
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
                    color: '#64748B',
                  }}
                >
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                    <CheckIcon size={16} style={{ color: '#059669' }} />
                    BMB 12 mezonli rasmiy standart
                  </span>
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                    <CheckIcon size={16} style={{ color: '#D97706' }} />
                    99.4% imtihon aniqligi
                  </span>
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                    <CheckIcon size={16} style={{ color: '#0284C7' }} />
                    Ona tili va Ingliz tili
                  </span>
                </div>

                {/* Mobile 3D Direction Cards (TestMakon 2x2 Grid) */}
                <div className="grid grid-cols-2 gap-3 mt-6 md:hidden">
                  <button
                    type="button"
                    onClick={() => handleAction('/essays')}
                    style={{
                      padding: '16px 14px',
                      borderRadius: '18px',
                      background: 'linear-gradient(135deg, #FFFBEB 0%, #FEF3C7 100%)',
                      border: '1.5px solid #FDE68A',
                      boxShadow: '0 6px 16px -3px rgba(217, 119, 6, 0.15)',
                      textAlign: 'left',
                      cursor: 'pointer',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: 6,
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <span style={{ fontSize: 26 }}>✍️</span>
                      <span style={{ fontSize: 9.5, fontWeight: 800, padding: '2px 7px', borderRadius: 999, background: 'rgba(217, 119, 6, 0.15)', color: '#B45309' }}>
                        12 mezon
                      </span>
                    </div>
                    <div>
                      <h4 style={{ margin: 0, fontSize: 14.5, fontWeight: 900, color: '#92400E' }}>AI Esse</h4>
                      <p style={{ margin: '2px 0 0', fontSize: 10.5, fontWeight: 600, color: '#B45309' }}>
                        BMB rasmiy tahlil
                      </p>
                    </div>
                  </button>

                  <button
                    type="button"
                    onClick={() => handleAction('/tests')}
                    style={{
                      padding: '16px 14px',
                      borderRadius: '18px',
                      background: 'linear-gradient(135deg, #ECFDF5 0%, #D1FAE5 100%)',
                      border: '1.5px solid #A7F3D0',
                      boxShadow: '0 6px 16px -3px rgba(5, 150, 105, 0.15)',
                      textAlign: 'left',
                      cursor: 'pointer',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: 6,
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <span style={{ fontSize: 26 }}>📝</span>
                      <span style={{ fontSize: 9.5, fontWeight: 800, padding: '2px 7px', borderRadius: 999, background: 'rgba(5, 150, 105, 0.15)', color: '#047857' }}>
                        CBT Test
                      </span>
                    </div>
                    <div>
                      <h4 style={{ margin: 0, fontSize: 14.5, fontWeight: 900, color: '#065F46' }}>Testlar</h4>
                      <p style={{ margin: '2px 0 0', fontSize: 10.5, fontWeight: 600, color: '#047857' }}>
                        Davlat standarti
                      </p>
                    </div>
                  </button>

                  <button
                    type="button"
                    onClick={() => handleAction('/arena')}
                    style={{
                      padding: '16px 14px',
                      borderRadius: '18px',
                      background: 'linear-gradient(135deg, #FEF2F2 0%, #FEE2E2 100%)',
                      border: '1.5px solid #FECACA',
                      boxShadow: '0 6px 16px -3px rgba(220, 38, 38, 0.15)',
                      textAlign: 'left',
                      cursor: 'pointer',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: 6,
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <span style={{ fontSize: 26 }}>⚔️</span>
                      <span style={{ fontSize: 9.5, fontWeight: 800, padding: '2px 7px', borderRadius: 999, background: 'rgba(220, 38, 38, 0.15)', color: '#B91C1C' }}>
                        Jonli jang
                      </span>
                    </div>
                    <div>
                      <h4 style={{ margin: 0, fontSize: 14.5, fontWeight: 900, color: '#991B1B' }}>1v1 Arena</h4>
                      <p style={{ margin: '2px 0 0', fontSize: 10.5, fontWeight: 600, color: '#B91C1C' }}>
                        Tezkor duel
                      </p>
                    </div>
                  </button>

                  <button
                    type="button"
                    onClick={() => handleAction('/tests/scan-omr')}
                    style={{
                      padding: '16px 14px',
                      borderRadius: '18px',
                      background: 'linear-gradient(135deg, #F5F3FF 0%, #EDE9FE 100%)',
                      border: '1.5px solid #DDD6FE',
                      boxShadow: '0 6px 16px -3px rgba(124, 58, 237, 0.15)',
                      textAlign: 'left',
                      cursor: 'pointer',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: 6,
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <span style={{ fontSize: 26 }}>📷</span>
                      <span style={{ fontSize: 9.5, fontWeight: 800, padding: '2px 7px', borderRadius: 999, background: 'rgba(124, 58, 237, 0.15)', color: '#6D28D9' }}>
                        Skaner
                      </span>
                    </div>
                    <div>
                      <h4 style={{ margin: 0, fontSize: 14.5, fontWeight: 900, color: '#5B21B6' }}>Titul Skaner</h4>
                      <p style={{ margin: '2px 0 0', fontSize: 10.5, fontWeight: 600, color: '#6D28D9' }}>
                        Kamera orqali
                      </p>
                    </div>
                  </button>
                </div>
              </div>

              {/* Right Column: Modern Interactive Hero Carousel (Desktop Only) */}
              <div className="hidden md:block">
                <HeroCarousel onAction={handleAction} />
              </div>
            </div>
          </div>
        </section>
        {/* QAYSI IMTIHONGA TAYYORLANASIZ? (TESTMAKON 3D TOIFALAR KARTALARI) */}
        <section style={{ padding: '20px 20px 60px' }}>
          <div style={{ maxWidth: 1200, margin: '0 auto' }}>
            <div style={{ textAlign: 'center', marginBottom: 32 }}>
              <h2 style={{ fontSize: 'clamp(1.8rem, 3vw, 2.4rem)', fontWeight: 900, color: 'var(--ink)', margin: '0 0 10px', letterSpacing: '-0.02em' }}>
                Qaysi imtihonga tayyorlanasiz?
              </h2>
              <p style={{ fontSize: 15, color: '#64748B', margin: 0, fontWeight: 600 }}>
                Rasmiy BMB va xalqaro standartlar asosida ishlab chiqilgan yo&apos;nalishni tanlang.
              </p>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
              {/* 1. BMB Milliy Sertifikat */}
              <div
                onClick={() => handleAction('/tests')}
                className="rounded-3xl bg-white border border-slate-200/80 hover:shadow-xl hover:-translate-y-1 transition-all p-6 cursor-pointer flex flex-col justify-between"
                style={{
                  boxShadow: '0 8px 24px -4px rgba(0, 0, 0, 0.05)',
                  minHeight: 240,
                }}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
                    <span style={{ fontSize: 40 }}>🥇</span>
                    <span style={{ fontSize: 11, fontWeight: 800, padding: '4px 10px', borderRadius: 999, background: 'rgba(245, 158, 11, 0.15)', color: '#D97706' }}>
                      BMB Standart
                    </span>
                  </div>
                  <h3 style={{ margin: '0 0 8px', fontSize: 18, fontWeight: 900, color: '#0F172A' }}>
                    BMB Milliy Sertifikat
                  </h3>
                  <p style={{ margin: 0, fontSize: 13, color: '#64748B', lineHeight: 1.5, fontWeight: 500 }}>
                    A+ dan C gacha rasmiy darajalar, 45 talik test formati va maksimal OTM imtiyozi.
                  </p>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 20 }}>
                  <span style={{ fontSize: 12.5, fontWeight: 800, color: '#D97706' }}>Testga kirish</span>
                  <span
                    style={{
                      width: 36,
                      height: 36,
                      borderRadius: '50%',
                      background: 'linear-gradient(135deg, #F59E0B, #D97706)',
                      color: '#FFFFFF',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: 16,
                      fontWeight: 900,
                      boxShadow: '0 4px 12px rgba(217, 119, 6, 0.35)',
                    }}
                  >
                    →
                  </span>
                </div>
              </div>

              {/* 2. Pedagoglar Attestatsiyasi 2026 */}
              <div
                onClick={() => handleAction('/tests')}
                className="rounded-3xl bg-white border border-slate-200/80 hover:shadow-xl hover:-translate-y-1 transition-all p-6 cursor-pointer flex flex-col justify-between"
                style={{
                  boxShadow: '0 8px 24px -4px rgba(0, 0, 0, 0.05)',
                  minHeight: 240,
                }}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
                    <span style={{ fontSize: 40 }}>🎓</span>
                    <span style={{ fontSize: 11, fontWeight: 800, padding: '4px 10px', borderRadius: 999, background: 'rgba(139, 92, 246, 0.15)', color: '#7C3AED' }}>
                      70% Ustama
                    </span>
                  </div>
                  <h3 style={{ margin: '0 0 8px', fontSize: 18, fontWeight: 900, color: '#0F172A' }}>
                    Attestatsiya 2026
                  </h3>
                  <p style={{ margin: 0, fontSize: 13, color: '#64748B', lineHeight: 1.5, fontWeight: 500 }}>
                    O&apos;qituvchilar toifa sinovlari, 50 talik yangi namuna va oylik ustama kafolati.
                  </p>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 20 }}>
                  <span style={{ fontSize: 12.5, fontWeight: 800, color: '#7C3AED' }}>Toifani oshirish</span>
                  <span
                    style={{
                      width: 36,
                      height: 36,
                      borderRadius: '50%',
                      background: 'linear-gradient(135deg, #8B5CF6, #7C3AED)',
                      color: '#FFFFFF',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: 16,
                      fontWeight: 900,
                      boxShadow: '0 4px 12px rgba(139, 92, 246, 0.35)',
                    }}
                  >
                    →
                  </span>
                </div>
              </div>

              {/* 3. AI Esse Studiyasi (12 Mezon) */}
              <div
                onClick={() => handleAction('/essays')}
                className="rounded-3xl bg-white border border-slate-200/80 hover:shadow-xl hover:-translate-y-1 transition-all p-6 cursor-pointer flex flex-col justify-between"
                style={{
                  boxShadow: '0 8px 24px -4px rgba(0, 0, 0, 0.05)',
                  minHeight: 240,
                }}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
                    <span style={{ fontSize: 40 }}>✍️</span>
                    <span style={{ fontSize: 11, fontWeight: 800, padding: '4px 10px', borderRadius: 999, background: 'rgba(16, 185, 129, 0.15)', color: '#059669' }}>
                      12 Mezon
                    </span>
                  </div>
                  <h3 style={{ margin: '0 0 8px', fontSize: 18, fontWeight: 900, color: '#0F172A' }}>
                    AI Esse Studiyasi
                  </h3>
                  <p style={{ margin: 0, fontSize: 13, color: '#64748B', lineHeight: 1.5, fontWeight: 500 }}>
                    15 soniyada to&apos;liq grammatik va uslubiy tahlil, A daraja bo&apos;yicha professional tavsiyalar.
                  </p>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 20 }}>
                  <span style={{ fontSize: 12.5, fontWeight: 800, color: '#059669' }}>Insho yozish</span>
                  <span
                    style={{
                      width: 36,
                      height: 36,
                      borderRadius: '50%',
                      background: 'linear-gradient(135deg, #10B981, #059669)',
                      color: '#FFFFFF',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: 16,
                      fontWeight: 900,
                      boxShadow: '0 4px 12px rgba(16, 185, 129, 0.35)',
                    }}
                  >
                    →
                  </span>
                </div>
              </div>

              {/* 4. CEFR & IELTS (Ingliz tili) */}
              <div
                onClick={() => handleAction('/tests')}
                className="rounded-3xl bg-white border border-slate-200/80 hover:shadow-xl hover:-translate-y-1 transition-all p-6 cursor-pointer flex flex-col justify-between"
                style={{
                  boxShadow: '0 8px 24px -4px rgba(0, 0, 0, 0.05)',
                  minHeight: 240,
                }}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
                    <span style={{ fontSize: 40 }}>🇬🇧</span>
                    <span style={{ fontSize: 11, fontWeight: 800, padding: '4px 10px', borderRadius: 999, background: 'rgba(2, 132, 199, 0.15)', color: '#0284C7' }}>
                      Cambridge CBT
                    </span>
                  </div>
                  <h3 style={{ margin: '0 0 8px', fontSize: 18, fontWeight: 900, color: '#0F172A' }}>
                    CEFR & IELTS
                  </h3>
                  <p style={{ margin: 0, fontSize: 13, color: '#64748B', lineHeight: 1.5, fontWeight: 500 }}>
                    Reading & Listening mock sinovlari va interaktiv AI Speaking trenajyori.
                  </p>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 20 }}>
                  <span style={{ fontSize: 12.5, fontWeight: 800, color: '#0284C7' }}>Ingliz tili CBT</span>
                  <span
                    style={{
                      width: 36,
                      height: 36,
                      borderRadius: '50%',
                      background: 'linear-gradient(135deg, #0284C7, #0369A1)',
                      color: '#FFFFFF',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: 16,
                      fontWeight: 900,
                      boxShadow: '0 4px 12px rgba(2, 132, 199, 0.35)',
                    }}
                  >
                    →
                  </span>
                </div>
              </div>
            </div>
          </div>
        </section>


        {/* 3 CORE DIRECTIONS SECTION ("IMKONIYATLAR") */}
        <section
          id="features"
          className="hidden md:block"
          style={{
            padding: '70px 20px',
            position: 'relative',
          }}
        >
          <div style={{ margin: '0 auto', maxWidth: 1200 }}>
            <div style={{ textAlign: 'center', maxWidth: 680, margin: '0 auto 48px' }}>
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 900,
                  letterSpacing: '0.22em',
                  color: '#F59E0B',
                  textTransform: 'uppercase',
                }}
              >
                {selectedTrack === 'ielts'
                  ? 'CAMBRIDGE & IDP IELTS ECOSYSTEM'
                  : selectedTrack === 'multilevel'
                  ? 'BMB / CEFR RASMIY STANDARTI'
                  : selectedTrack === 'attestation'
                  ? 'PEDAGOGLAR ATTESTATSIYASI 2026'
                  : t('features_main_eyebrow')}
              </span>
              <h2
                style={{
                  fontSize: 'clamp(1.8rem, 3.5vw, 2.5rem)',
                  fontWeight: 900,
                  color: '#0F172A',
                  margin: '12px 0',
                }}
              >
                {selectedTrack === 'ielts' ? (
                  <>
                    IELTS Band 7.5+ ga erishish imkoniyatlari{' '}
                    <span className="hero-title-gradient">bitta platformada</span>
                  </>
                ) : selectedTrack === 'multilevel' ? (
                  <>
                    Davlat Multi-level (B2/C1) imkoniyatlari{' '}
                    <span className="hero-title-gradient">bitta platformada</span>
                  </>
                ) : selectedTrack === 'attestation' ? (
                  <>
                    Toifa oshirish va 70% ustama olish uchun{' '}
                    <span className="hero-title-gradient">maxsus tizim</span>
                  </>
                ) : (
                  <>
                    {t('features_main_title_1')}{' '}
                    <span className="hero-title-gradient">{t('features_main_title_2')}</span>
                  </>
                )}
              </h2>
              <p style={{ fontSize: 15, color: '#64748B', lineHeight: 1.6, margin: 0 }}>
                {selectedTrack === 'ielts'
                  ? 'Writing Task 1 & 2, real-vaqt Speaking simulyatori va Cambridge CBT testlari.'
                  : selectedTrack === 'multilevel'
                  ? 'DTM/BMB formati boʻyicha yozma insho, 35 talik CBT testlar va leksik trenajyorlar.'
                  : selectedTrack === 'attestation'
                  ? '50 talik rasmiy sinov formati, pedagogik mahorat va toifa ehtimolligi kalkulyatori.'
                  : t('features_main_subtitle')}
              </p>
            </div>

            {/* 3 Core Direction Cards Grid */}
            <AnimatePresence mode="wait">
              <motion.div
                key={selectedTrack}
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -16 }}
                transition={{ duration: 0.22 }}
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
                  gap: 24,
                }}
              >
                {/* IELTS 3 Cards */}
                {selectedTrack === 'ielts' && (
                  <>
                    <div className="card lcard-hover bg-white border border-slate-200/80 rounded-2xl shadow-sm" style={{ borderRadius: 24, padding: '32px 28px', display: 'flex', flexDirection: 'column' }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
                        <div style={{ width: 52, height: 52, borderRadius: 16, background: 'rgba(56, 189, 248, 0.12)', border: '1px solid rgba(56, 189, 248, 0.28)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#38BDF8' }}>
                          <PenLineIcon size={26} />
                        </div>
                        <span style={{ padding: '4px 10px', borderRadius: 999, fontSize: 11, fontWeight: 800, background: 'rgba(56, 189, 248, 0.15)', color: '#38BDF8', border: '1px solid rgba(56, 189, 248, 0.3)' }}>
                          Task 1 & 2
                        </span>
                      </div>
                      <h3 style={{ fontSize: 20, fontWeight: 900, color: 'var(--ink)', margin: '0 0 10px' }}>
                        IELTS Writing AI Grader
                      </h3>
                      <p style={{ fontSize: 14, color: 'var(--muted)', lineHeight: 1.65, margin: '0 0 20px', flex: 1 }}>
                        Cambridge 4 ta mezoni (TR, CC, LR, GRA) boʻyicha 15 soniyada toʻliq baholash, xatolar tuzatmasi va Band prognozi.
                      </p>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 24, fontSize: 13, color: 'var(--ink)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#38BDF8' }} />
                          <span>Task 1 (Grafiklar) va Task 2 (Esse) toʻliq qoʻllab-quvvatlash</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#38BDF8' }} />
                          <span>Akademik lugʻat boyligi va sinonimlar tavsiyasi</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#38BDF8' }} />
                          <span>Band 7.5+ namunaviy insholar bilan solishtirish</span>
                        </div>
                      </div>
                      <button type="button" onClick={() => handleAction('/speaking')} style={{ width: '100%', padding: '12px', borderRadius: 12, background: 'rgba(56, 189, 248, 0.15)', border: '1px solid rgba(56, 189, 248, 0.35)', color: '#38BDF8', fontWeight: 800, fontSize: 14, cursor: 'pointer' }}>
                        {t('feat_ielts_w_btn')}
                      </button>
                    </div>

                    <div className="card lcard-hover bg-white border border-slate-200/80 rounded-2xl shadow-sm" style={{ borderRadius: 24, padding: '32px 28px', display: 'flex', flexDirection: 'column' }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
                        <div style={{ width: 52, height: 52, borderRadius: 16, background: 'rgba(16, 185, 129, 0.12)', border: '1px solid rgba(16, 185, 129, 0.28)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#34D399' }}>
                          <Mic size={26} />
                        </div>
                        <span style={{ padding: '4px 10px', borderRadius: 999, fontSize: 11, fontWeight: 800, background: 'rgba(16, 185, 129, 0.15)', color: '#34D399', border: '1px solid rgba(16, 185, 129, 0.3)' }}>
                          Part 1, 2, 3
                        </span>
                      </div>
                      <h3 style={{ fontSize: 20, fontWeight: 900, color: 'var(--ink)', margin: '0 0 10px' }}>
                        {t('feat_ielts_spk_title')}
                      </h3>
                      <p style={{ fontSize: 14, color: 'var(--muted)', lineHeight: 1.65, margin: '0 0 20px', flex: 1 }}>
                        {t('feat_ielts_spk_sub')}
                      </p>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 24, fontSize: 13, color: 'var(--ink)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#34D399' }} />
                          <span>Part 2 Cue Card va 1 daqiqalik tayyorgarlik taymeri</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#34D399' }} />
                          <span>Grammatik va talaffuz xatolarini audio orqali koʻrsatish</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#34D399' }} />
                          <span>Jonli ELO reyting va boshqa oʻquvchilar bilan solishtirish</span>
                        </div>
                      </div>
                      <button type="button" onClick={() => handleAction('/speaking')} style={{ width: '100%', padding: '12px', borderRadius: 12, background: 'rgba(16, 185, 129, 0.15)', border: '1px solid rgba(16, 185, 129, 0.35)', color: '#34D399', fontWeight: 800, fontSize: 14, cursor: 'pointer' }}>
                        {t('feat_ielts_spk_btn')}
                      </button>
                    </div>

                    <div className="card lcard-hover bg-white border border-slate-200/80 rounded-2xl shadow-sm" style={{ borderRadius: 24, padding: '32px 28px', display: 'flex', flexDirection: 'column' }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
                        <div style={{ width: 52, height: 52, borderRadius: 16, background: 'rgba(99, 102, 241, 0.12)', border: '1px solid rgba(99, 102, 241, 0.28)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#818CF8' }}>
                          <Headphones size={26} />
                        </div>
                        <span style={{ padding: '4px 10px', borderRadius: 999, fontSize: 11, fontWeight: 800, background: 'rgba(99, 102, 241, 0.15)', color: '#818CF8', border: '1px solid rgba(99, 102, 241, 0.3)' }}>
                          Reading & Listening
                        </span>
                      </div>
                      <h3 style={{ fontSize: 20, fontWeight: 900, color: 'var(--ink)', margin: '0 0 10px' }}>
                        {t('feat_ielts_cbt_title')}
                      </h3>
                      <p style={{ fontSize: 14, color: 'var(--muted)', lineHeight: 1.65, margin: '0 0 20px', flex: 1 }}>
                        {t('feat_ielts_cbt_sub')}
                      </p>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 24, fontSize: 13, color: 'var(--ink)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#818CF8' }} />
                          <span>Cambridge 10–19 rasmiy test savollari</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#818CF8' }} />
                          <span>Vaqt nazorati va avtomatik Band hisoblash</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#818CF8' }} />
                          <span>Tezkor xatolar ustida ishlash rejimi</span>
                        </div>
                      </div>
                      <button type="button" onClick={() => handleAction('/tests')} style={{ width: '100%', padding: '12px', borderRadius: 12, background: 'rgba(99, 102, 241, 0.15)', border: '1px solid rgba(99, 102, 241, 0.35)', color: '#818CF8', fontWeight: 800, fontSize: 14, cursor: 'pointer' }}>
                        {t('feat_ielts_cbt_btn')}
                      </button>
                    </div>
                  </>
                )}

                {/* Multi-level 3 Cards */}
                {selectedTrack === 'multilevel' && (
                  <>
                    <div className="card lcard-hover bg-white border border-slate-200/80 rounded-2xl shadow-sm" style={{ borderRadius: 24, padding: '32px 28px', display: 'flex', flexDirection: 'column' }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
                        <div style={{ width: 52, height: 52, borderRadius: 16, background: 'rgba(99, 102, 241, 0.12)', border: '1px solid rgba(99, 102, 241, 0.28)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#818CF8' }}>
                          <PenLineIcon size={26} />
                        </div>
                        <span style={{ padding: '4px 10px', borderRadius: 999, fontSize: 11, fontWeight: 800, background: 'rgba(99, 102, 241, 0.15)', color: '#818CF8', border: '1px solid rgba(99, 102, 241, 0.3)' }}>
                          B2 / C1 Insho
                        </span>
                      </div>
                      <h3 style={{ fontSize: 20, fontWeight: 900, color: 'var(--ink)', margin: '0 0 10px' }}>
                        CEFR Writing AI Tahlili
                      </h3>
                      <p style={{ fontSize: 14, color: 'var(--muted)', lineHeight: 1.65, margin: '0 0 20px', flex: 1 }}>
                        Davlat BMB standarti boʻyicha rasmiy insho va rasmiy xatlar tekshiruvi, leksik boylik va grammatik aniqlik.
                      </p>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 24, fontSize: 13, color: 'var(--ink)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#818CF8' }} />
                          <span>Part 1 (Xat/Email) va Part 2 (Esse) 20 ballik tizimda</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#818CF8' }} />
                          <span>B2 va C1 darajasiga mos soʻz birikmalari tahlili</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#818CF8' }} />
                          <span>Xatolar tuzatmasi bilan bir zumda hisobot</span>
                        </div>
                      </div>
                      <button type="button" onClick={() => handleAction('/essays')} style={{ width: '100%', padding: '12px', borderRadius: 12, background: 'rgba(99, 102, 241, 0.15)', border: '1px solid rgba(99, 102, 241, 0.35)', color: '#818CF8', fontWeight: 800, fontSize: 14, cursor: 'pointer' }}>
                        {t('feat_multi_w_btn')}
                      </button>
                    </div>

                    <div className="card lcard-hover bg-white border border-slate-200/80 rounded-2xl shadow-sm" style={{ borderRadius: 24, padding: '32px 28px', display: 'flex', flexDirection: 'column' }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
                        <div style={{ width: 52, height: 52, borderRadius: 16, background: 'rgba(56, 189, 248, 0.12)', border: '1px solid rgba(56, 189, 248, 0.28)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#38BDF8' }}>
                          <FileTextIcon size={26} />
                        </div>
                        <span style={{ padding: '4px 10px', borderRadius: 999, fontSize: 11, fontWeight: 800, background: 'rgba(56, 189, 248, 0.15)', color: '#38BDF8', border: '1px solid rgba(56, 189, 248, 0.3)' }}>
                          35 talik Savollar
                        </span>
                      </div>
                      <h3 style={{ fontSize: 20, fontWeight: 900, color: 'var(--ink)', margin: '0 0 10px' }}>
                        {t('feat_multi_cbt_title')}
                      </h3>
                      <p style={{ fontSize: 14, color: 'var(--muted)', lineHeight: 1.65, margin: '0 0 20px', flex: 1 }}>
                        {t('feat_multi_cbt_sub')}
                      </p>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 24, fontSize: 13, color: 'var(--ink)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#38BDF8' }} />
                          <span>Haqiqiy imtihon interfeysi va taymer</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#38BDF8' }} />
                          <span>Savollar boʻyicha batafsil izoh va tushuntirish</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#38BDF8' }} />
                          <span>B1, B2, C1 darajasi ehtimolligi kalkulyatori</span>
                        </div>
                      </div>
                      <button type="button" onClick={() => handleAction('/tests')} style={{ width: '100%', padding: '12px', borderRadius: 12, background: 'rgba(56, 189, 248, 0.15)', border: '1px solid rgba(56, 189, 248, 0.35)', color: '#38BDF8', fontWeight: 800, fontSize: 14, cursor: 'pointer' }}>
                        {t('feat_multi_cbt_btn')}
                      </button>
                    </div>

                    <div className="card lcard-hover bg-white border border-slate-200/80 rounded-2xl shadow-sm" style={{ borderRadius: 24, padding: '32px 28px', display: 'flex', flexDirection: 'column' }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
                        <div style={{ width: 52, height: 52, borderRadius: 16, background: 'rgba(16, 185, 129, 0.12)', border: '1px solid rgba(16, 185, 129, 0.28)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#34D399' }}>
                          <SwordsIcon size={26} />
                        </div>
                        <span style={{ padding: '4px 10px', borderRadius: 999, fontSize: 11, fontWeight: 800, background: 'rgba(16, 185, 129, 0.15)', color: '#34D399', border: '1px solid rgba(16, 185, 129, 0.3)' }}>
                          B1 · B2 · C1
                        </span>
                      </div>
                      <h3 style={{ fontSize: 20, fontWeight: 900, color: 'var(--ink)', margin: '0 0 10px' }}>
                        Lugʻat va Grammatika Arenasi
                      </h3>
                      <p style={{ fontSize: 14, color: 'var(--muted)', lineHeight: 1.65, margin: '0 0 20px', flex: 1 }}>
                        CEFR darajalari uchun maxsus leksik mini-trenajyorlar va boshqa abituriyentlar bilan 1v1 viktorinalar.
                      </p>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 24, fontSize: 13, color: 'var(--ink)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#34D399' }} />
                          <span>Oxford 3000 & 5000 soʻzlar bazasi</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#34D399' }} />
                          <span>1v1 intellektual bellashuv va ball toʻplash</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#34D399' }} />
                          <span>Kundalik soʻz yodlash maratoni (Streak)</span>
                        </div>
                      </div>
                      <button type="button" onClick={() => handleAction('/arena')} style={{ width: '100%', padding: '12px', borderRadius: 12, background: 'rgba(16, 185, 129, 0.15)', border: '1px solid rgba(16, 185, 129, 0.35)', color: '#34D399', fontWeight: 800, fontSize: 14, cursor: 'pointer' }}>
                        Arenaga kirish →
                      </button>
                    </div>
                  </>
                )}

                {/* National Certificate 3 Cards */}
                {selectedTrack === 'national_certificate' && (
                  <>
                    <div className="card lcard-hover bg-white border border-slate-200/80 rounded-2xl shadow-sm" style={{ borderRadius: 24, padding: '32px 28px', display: 'flex', flexDirection: 'column' }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
                        <div style={{ width: 52, height: 52, borderRadius: 16, background: 'rgba(245, 158, 11, 0.12)', border: '1px solid rgba(245, 158, 11, 0.28)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#F59E0B' }}>
                          <PenLineIcon size={26} />
                        </div>
                        <span style={{ padding: '4px 10px', borderRadius: 999, fontSize: 11, fontWeight: 800, background: 'rgba(245, 158, 11, 0.15)', color: '#F59E0B', border: '1px solid rgba(245, 158, 11, 0.3)' }}>
                          {t('feature_card_essay_badge')}
                        </span>
                      </div>
                      <h3 style={{ fontSize: 20, fontWeight: 900, color: 'var(--ink)', margin: '0 0 10px' }}>
                        {t('feature_card_essay_title')}
                      </h3>
                      <p style={{ fontSize: 14, color: 'var(--muted)', lineHeight: 1.65, margin: '0 0 20px', flex: 1 }}>
                        {t('feature_card_essay_desc')}
                      </p>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 24, fontSize: 13, color: 'var(--ink)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#F59E0B' }} />
                          <span>{t('feature_card_essay_bullet1')}</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#F59E0B' }} />
                          <span>{t('feature_card_essay_bullet2')}</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#F59E0B' }} />
                          <span>{t('feature_card_essay_bullet3')}</span>
                        </div>
                      </div>
                      <button type="button" onClick={() => handleAction('/essays')} style={{ width: '100%', padding: '12px', borderRadius: 12, background: 'rgba(245, 158, 11, 0.15)', border: '1px solid rgba(245, 158, 11, 0.35)', color: '#F59E0B', fontWeight: 800, fontSize: 14, cursor: 'pointer' }}>
                        {t('feature_card_essay_action')}
                      </button>
                    </div>

                    <div className="card lcard-hover bg-white border border-slate-200/80 rounded-2xl shadow-sm" style={{ borderRadius: 24, padding: '32px 28px', display: 'flex', flexDirection: 'column' }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
                        <div style={{ width: 52, height: 52, borderRadius: 16, background: 'rgba(16, 185, 129, 0.12)', border: '1px solid rgba(16, 185, 129, 0.28)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#10B981' }}>
                          <FileTextIcon size={26} />
                        </div>
                        <span style={{ padding: '4px 10px', borderRadius: 999, fontSize: 11, fontWeight: 800, background: 'rgba(16, 185, 129, 0.15)', color: '#10B981', border: '1px solid rgba(16, 185, 129, 0.3)' }}>
                          {t('feature_card_tests_badge')}
                        </span>
                      </div>
                      <h3 style={{ fontSize: 20, fontWeight: 900, color: 'var(--ink)', margin: '0 0 10px' }}>
                        {t('feature_card_tests_title')}
                      </h3>
                      <p style={{ fontSize: 14, color: 'var(--muted)', lineHeight: 1.65, margin: '0 0 20px', flex: 1 }}>
                        {t('feature_card_tests_desc')}
                      </p>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 24, fontSize: 13, color: 'var(--ink)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#10B981' }} />
                          <span>{t('feature_card_tests_bullet1')}</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#10B981' }} />
                          <span>{t('feature_card_tests_bullet2')}</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#10B981' }} />
                          <span>{t('feature_card_tests_bullet3')}</span>
                        </div>
                      </div>
                      <button type="button" onClick={() => handleAction('/tests')} style={{ width: '100%', padding: '12px', borderRadius: 12, background: 'rgba(16, 185, 129, 0.15)', border: '1px solid rgba(16, 185, 129, 0.35)', color: '#34D399', fontWeight: 800, fontSize: 14, cursor: 'pointer' }}>
                        {t('feature_card_tests_action')}
                      </button>
                    </div>

                    <div className="card lcard-hover bg-white border border-slate-200/80 rounded-2xl shadow-sm" style={{ borderRadius: 24, padding: '32px 28px', display: 'flex', flexDirection: 'column' }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
                        <div style={{ width: 52, height: 52, borderRadius: 16, background: 'rgba(139, 92, 246, 0.12)', border: '1px solid rgba(139, 92, 246, 0.28)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#8B5CF6' }}>
                          <SwordsIcon size={26} />
                        </div>
                        <span style={{ padding: '4px 10px', borderRadius: 999, fontSize: 11, fontWeight: 800, background: 'rgba(139, 92, 246, 0.15)', color: '#8B5CF6', border: '1px solid rgba(139, 92, 246, 0.3)' }}>
                          {t('feature_card_arena_badge')}
                        </span>
                      </div>
                      <h3 style={{ fontSize: 20, fontWeight: 900, color: 'var(--ink)', margin: '0 0 10px' }}>
                        {t('feature_card_arena_title')}
                      </h3>
                      <p style={{ fontSize: 14, color: 'var(--muted)', lineHeight: 1.65, margin: '0 0 20px', flex: 1 }}>
                        {t('feature_card_arena_desc')}
                      </p>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 24, fontSize: 13, color: 'var(--ink)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#8B5CF6' }} />
                          <span>{t('feature_card_arena_bullet1')}</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#8B5CF6' }} />
                          <span>{t('feature_card_arena_bullet2')}</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#8B5CF6' }} />
                          <span>{t('feature_card_arena_bullet3')}</span>
                        </div>
                      </div>
                      <button type="button" onClick={() => handleAction('/arena')} style={{ width: '100%', padding: '12px', borderRadius: 12, background: 'rgba(139, 92, 246, 0.15)', border: '1px solid rgba(139, 92, 246, 0.35)', color: '#A78BFA', fontWeight: 800, fontSize: 14, cursor: 'pointer' }}>
                        {t('feature_card_arena_action')}
                      </button>
                    </div>
                  </>
                )}

                {/* Attestation 3 Cards */}
                {selectedTrack === 'attestation' && (
                  <>
                    <div className="card lcard-hover bg-white border border-slate-200/80 rounded-2xl shadow-sm" style={{ borderRadius: 24, padding: '32px 28px', display: 'flex', flexDirection: 'column' }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
                        <div style={{ width: 52, height: 52, borderRadius: 16, background: 'rgba(245, 158, 11, 0.12)', border: '1px solid rgba(245, 158, 11, 0.28)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#F59E0B' }}>
                          <FileTextIcon size={26} />
                        </div>
                        <span style={{ padding: '4px 10px', borderRadius: 999, fontSize: 11, fontWeight: 800, background: 'rgba(245, 158, 11, 0.15)', color: '#F59E0B', border: '1px solid rgba(245, 158, 11, 0.3)' }}>
                          50 talik Format
                        </span>
                      </div>
                      <h3 style={{ fontSize: 20, fontWeight: 900, color: 'var(--ink)', margin: '0 0 10px' }}>
                        Attestatsiya Simulyatori
                      </h3>
                      <p style={{ fontSize: 14, color: 'var(--muted)', lineHeight: 1.65, margin: '0 0 20px', flex: 1 }}>
                        Mutaxassislik fani (35), Kasbiy standart (5) va Pedagogik mahorat (10) savollarini oʻz ichiga olgan rasmiy sinov formati.
                      </p>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 24, fontSize: 13, color: 'var(--ink)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#F59E0B' }} />
                          <span>Haqiqiy davlat test tizimiga 100% mos vaqt taymeri</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#F59E0B' }} />
                          <span>Grammatika va adabiyot boʻyicha chuqur tahlillar</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#F59E0B' }} />
                          <span>Barcha xatolarni boʻlimlar boʻyicha koʻrsatish</span>
                        </div>
                      </div>
                      <button type="button" onClick={() => handleAction('/tests')} style={{ width: '100%', padding: '12px', borderRadius: 12, background: 'rgba(245, 158, 11, 0.15)', border: '1px solid rgba(245, 158, 11, 0.35)', color: '#F59E0B', fontWeight: 800, fontSize: 14, cursor: 'pointer' }}>
                        50 talik testni boshlash →
                      </button>
                    </div>

                    <div className="card lcard-hover bg-white border border-slate-200/80 rounded-2xl shadow-sm" style={{ borderRadius: 24, padding: '32px 28px', display: 'flex', flexDirection: 'column' }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
                        <div style={{ width: 52, height: 52, borderRadius: 16, background: 'rgba(16, 185, 129, 0.12)', border: '1px solid rgba(16, 185, 129, 0.28)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#10B981' }}>
                          <LightbulbIcon size={26} />
                        </div>
                        <span style={{ padding: '4px 10px', borderRadius: 999, fontSize: 11, fontWeight: 800, background: 'rgba(16, 185, 129, 0.15)', color: '#10B981', border: '1px solid rgba(16, 185, 129, 0.3)' }}>
                          Metodika & Keyslar
                        </span>
                      </div>
                      <h3 style={{ fontSize: 20, fontWeight: 900, color: 'var(--ink)', margin: '0 0 10px' }}>
                        Pedagogik Mahorat Trenajyori
                      </h3>
                      <p style={{ fontSize: 14, color: 'var(--muted)', lineHeight: 1.65, margin: '0 0 20px', flex: 1 }}>
                        Yangi milliy oʻquv dasturi, 4K koʻnikmalari va formativ baholash metodikasi boʻyicha amaliy keys savollari.
                      </p>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 24, fontSize: 13, color: 'var(--ink)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#10B981' }} />
                          <span>Dars tahlili va interaktiv metodlar boʻyicha amaliyot</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#10B981' }} />
                          <span>Inklyuziv taʻlim va oʻquvchi psixologiyasi savollari</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#10B981' }} />
                          <span>Davlat taʻlim standarti qonunchiligi asosidagi keyslar</span>
                        </div>
                      </div>
                      <button type="button" onClick={() => handleAction('/tests')} style={{ width: '100%', padding: '12px', borderRadius: 12, background: 'rgba(16, 185, 129, 0.15)', border: '1px solid rgba(16, 185, 129, 0.35)', color: '#34D399', fontWeight: 800, fontSize: 14, cursor: 'pointer' }}>
                        Metodik keyslarni yechish →
                      </button>
                    </div>

                    <div className="card lcard-hover bg-white border border-slate-200/80 rounded-2xl shadow-sm" style={{ borderRadius: 24, padding: '32px 28px', display: 'flex', flexDirection: 'column' }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
                        <div style={{ width: 52, height: 52, borderRadius: 16, background: 'rgba(59, 130, 246, 0.12)', border: '1px solid rgba(59, 130, 246, 0.28)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#3B82F6' }}>
                          <TrophyIcon size={26} />
                        </div>
                        <span style={{ padding: '4px 10px', borderRadius: 999, fontSize: 11, fontWeight: 800, background: 'rgba(59, 130, 246, 0.15)', color: '#3B82F6', border: '1px solid rgba(59, 130, 246, 0.3)' }}>
                          70% Ustama
                        </span>
                      </div>
                      <h3 style={{ fontSize: 20, fontWeight: 900, color: 'var(--ink)', margin: '0 0 10px' }}>
                        Toifa va Ustama Prognozi
                      </h3>
                      <p style={{ fontSize: 14, color: 'var(--muted)', lineHeight: 1.65, margin: '0 0 20px', flex: 1 }}>
                        1-toifa va Oliy toifaga erishish ehtimolligi hamda oylik maoshga qoʻshiladigan 70% ustama kalkulyatori.
                      </p>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 24, fontSize: 13, color: 'var(--ink)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#3B82F6' }} />
                          <span>86+ ball bilan Oliy toifa uchun individual reja</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#3B82F6' }} />
                          <span>Kuchsiz boʻlimlarni avtomatik aniqlash va kuchaytirish</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#3B82F6' }} />
                          <span>Attestatsiyagacha qolgan vaqt boʻyicha tayyorgarlik</span>
                        </div>
                      </div>
                      <button type="button" onClick={() => handleAction('/profile')} style={{ width: '100%', padding: '12px', borderRadius: 12, background: 'rgba(59, 130, 246, 0.15)', border: '1px solid rgba(59, 130, 246, 0.35)', color: '#60A5FA', fontWeight: 800, fontSize: 14, cursor: 'pointer' }}>
                        Toifa rejasini tuzish →
                      </button>
                    </div>
                  </>
                )}
              </motion.div>
            </AnimatePresence>
          </div>
        </section>

        {/* HOW IT WORKS SECTION */}
        <HowItWorks />

        {/* COMPARISON TABLE */}
        <section
          id="comparison"
          className="hidden md:block"
          style={{
            padding: '70px 20px',
            position: 'relative',
          }}
        >
          <div style={{ margin: '0 auto', maxWidth: 960 }}>
            <div style={{ textAlign: 'center', maxWidth: 640, margin: '0 auto 40px' }}>
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 900,
                  letterSpacing: '0.22em',
                  color: '#F59E0B',
                  textTransform: 'uppercase',
                }}
              >
                {t('cmp_eyebrow')}
              </span>
              <h2
                style={{
                  fontSize: 'clamp(1.8rem, 3.5vw, 2.4rem)',
                  fontWeight: 900,
                  color: '#0F172A',
                  margin: '12px 0',
                }}
              >
                {t('cmp_title_1')}{' '}
                <span className="hero-title-gradient">{t('cmp_title_2')}</span>
              </h2>
              <p style={{ fontSize: 14, color: '#64748B', lineHeight: 1.6, margin: 0 }}>
                {t('cmp_subtitle')}
              </p>
            </div>

            <div
              className="card"
              style={{
                borderRadius: 20,
                overflow: 'hidden',
                background: 'var(--card)',
                border: '1px solid var(--border)',
                boxShadow: '0 10px 30px -10px rgba(0, 0, 0, 0.1)',
              }}
            >
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: '1.4fr 1fr 1fr',
                  padding: '16px 20px',
                  background: 'var(--card-2)',
                  borderBottom: '1px solid var(--border)',
                  fontSize: 12,
                  fontWeight: 800,
                  textTransform: 'uppercase',
                  letterSpacing: '0.08em',
                  color: 'var(--muted)',
                }}
              >
                <div>{t('cmp_col_param')}</div>
                <div style={{ textAlign: 'center' }}>{t('cmp_col_traditional')}</div>
                <div style={{ textAlign: 'center', color: '#F59E0B' }}>GRAND EDUCATION AI</div>
              </div>

              {[
                [t('cmp_row_speed'), t('cmp_row_speed_trad'), t('cmp_row_speed_grand'), true],
                [t('cmp_row_criteria'), t('cmp_row_criteria_trad'), t('cmp_row_criteria_grand'), true],
                [t('cmp_row_practice'), t('cmp_row_practice_trad'), t('cmp_row_practice_grand'), true],
                [t('cmp_row_analytics'), t('cmp_row_analytics_trad'), t('cmp_row_analytics_grand'), true],
                [t('cmp_row_cost'), t('cmp_row_cost_trad'), t('cmp_row_cost_grand'), true],
              ].map(([param, trad, grand, isGood], i) => (
                <div
                  key={i}
                  style={{
                    display: 'grid',
                    gridTemplateColumns: '1.4fr 1fr 1fr',
                    padding: '16px 20px',
                    borderBottom: i < 4 ? '1px solid var(--border)' : 'none',
                    fontSize: 13,
                    alignItems: 'center',
                  }}
                >
                  <div style={{ fontWeight: 700, color: 'var(--ink)' }}>{param}</div>
                  <div style={{ textAlign: 'center', color: 'var(--muted)' }}>{trad}</div>
                  <div
                    style={{
                      textAlign: 'center',
                      fontWeight: 800,
                      color: isGood ? '#10B981' : '#F59E0B',
                    }}
                  >
                    {grand}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* PRICING SECTION */}
        <section
          id="pricing"
          className="hidden md:block"
          style={{
            padding: '70px 20px',
            position: 'relative',
          }}
        >
          <div style={{ margin: '0 auto', maxWidth: 1240 }}>
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
                {t('pricing_eyebrow')}
              </span>
              <h2
                style={{
                  fontSize: 'clamp(1.8rem, 3.5vw, 2.5rem)',
                  fontWeight: 900,
                  color: '#0F172A',
                  margin: '12px 0',
                }}
              >
                {t('pricing_title_1')}{' '}
                <span className="hero-title-gradient">{t('pricing_title_2')}</span>
              </h2>
              <p style={{ fontSize: 14, color: '#64748B', lineHeight: 1.6, margin: 0 }}>
                {t('pricing_subtitle')}
              </p>
            </div>

            <div
              className="pricing-4col-grid grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6"
              style={{
                display: 'grid',
                alignItems: 'stretch',
              }}
            >
              {/* 1. Free Plan */}
              <div
                className="card lcard-hover"
                style={{
                  borderRadius: 22,
                  padding: '28px 24px',
                  display: 'flex',
                  flexDirection: 'column',
                  background: 'var(--card)',
                  border: '1px solid var(--border)',
                  boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.04)',
                  transition: 'all 0.3s ease',
                }}
              >
                <div style={{ fontSize: 17, fontWeight: 900, color: 'var(--ink)', marginBottom: 6 }}>
                  {t('plan_free_name')}
                </div>
                <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 18, minHeight: 36, lineHeight: 1.5 }}>
                  {t('plan_free_desc')}
                </div>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, marginBottom: 22 }}>
                  <span style={{ fontSize: 32, fontWeight: 900, color: 'var(--ink)' }}>0</span>
                  <span style={{ fontSize: 13, color: 'var(--muted)' }}>{t('plan_free_period', "so'm / umrbod")}</span>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 26, flex: 1, fontSize: 12.5 }}>
                  {[
                    t('plan_free_f1'),
                    t('plan_free_f2'),
                    t('plan_free_f3'),
                    t('plan_free_f4'),
                  ].map((f, i) => (
                    <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <CheckIcon size={15} style={{ color: '#10B981', flexShrink: 0 }} />
                      <span style={{ color: 'var(--ink)' }}>{f}</span>
                    </div>
                  ))}
                </div>
                <button
                  type="button"
                  onClick={() => handleAction('/register')}
                  style={{
                    width: '100%',
                    padding: 12,
                    borderRadius: 12,
                    background: '#F1F5F9',
                    border: '1px solid #E2E8F0',
                    color: '#1E293B',
                    fontWeight: 700,
                    fontSize: 13.5,
                    cursor: 'pointer',
                    marginTop: 'auto',
                    transition: 'all 0.18s ease',
                  }}
                >
                  {t('plan_free_cta')}
                </button>
              </div>

              {/* 2. Starter Plan (New) */}
              <div
                className="card lcard-hover"
                style={{
                  borderRadius: 22,
                  padding: '28px 24px',
                  display: 'flex',
                  flexDirection: 'column',
                  position: 'relative',
                  background: '#FFFFFF',
                  border: '1px solid rgba(16, 185, 129, 0.35)',
                  boxShadow: '0 10px 25px -5px rgba(16, 185, 129, 0.1)',
                  transition: 'all 0.3s ease',
                }}
              >
                <div
                  style={{
                    position: 'absolute',
                    top: -11,
                    left: '50%',
                    transform: 'translateX(-50%)',
                    padding: '3px 12px',
                    borderRadius: 999,
                    background: 'rgba(16, 185, 129, 0.18)',
                    border: '1px solid rgba(16, 185, 129, 0.35)',
                    color: '#34D399',
                    fontSize: 10.5,
                    fontWeight: 800,
                    letterSpacing: '0.08em',
                    textTransform: 'uppercase',
                  }}
                >
                  ⚡ {t('plan_starter_badge', 'Yangi')}
                </div>
                <div style={{ fontSize: 17, fontWeight: 900, color: '#0F172A', marginBottom: 6 }}>
                  ⚡ {t('plan_starter_name', 'Starter')}
                </div>
                <div style={{ fontSize: 12, color: '#64748B', marginBottom: 18, minHeight: 36, lineHeight: 1.5 }}>
                  {t('plan_starter_desc', "Tezkor sinov va 5 ta to'liq test yechish imkoniyati")}
                </div>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, marginBottom: 22 }}>
                  <span style={{ fontSize: 32, fontWeight: 900, color: '#10B981' }}>7 000</span>
                  <span style={{ fontSize: 13, color: '#64748B' }}>{t('plan_starter_period', "so'm / to'plam")}</span>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 26, flex: 1, fontSize: 12.5 }}>
                  {[
                    "5 ta to'liq test",
                    'Haftasiga 3 ta esse tekshirish',
                    'Xatolar tahlili',
                    'Kuniga 10 ta AI repetitor izohi',
                  ].map((f, i) => (
                    <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <CheckIcon size={15} style={{ color: '#10B981', flexShrink: 0 }} />
                      <span style={{ color: 'var(--ink)' }}>{f}</span>
                    </div>
                  ))}
                </div>
                <button
                  type="button"
                  onClick={() => handleAction('/subscribe?plan=starter')}
                  className="btn-glow btn-shimmer"
                  style={{
                    width: '100%',
                    padding: 12,
                    borderRadius: 12,
                    background: 'linear-gradient(135deg, #10B981, #059669)',
                    border: 'none',
                    color: '#FFFFFF',
                    fontWeight: 800,
                    fontSize: 13.5,
                    cursor: 'pointer',
                    marginTop: 'auto',
                    transition: 'all 0.18s ease',
                  }}
                >
                  {t('plan_starter_cta', 'Starter paketini olish')}
                </button>
              </div>

              {/* 3. Pro Plan (Popular) */}
              <div
                className="card lcard-hover"
                style={{
                  borderRadius: 22,
                  padding: '28px 24px',
                  display: 'flex',
                  flexDirection: 'column',
                  position: 'relative',
                  background: '#FFFFFF',
                  border: '2px solid #D97706',
                  boxShadow: '0 16px 35px -8px rgba(217, 119, 6, 0.22)',
                  transform: 'translateY(-4px)',
                  transition: 'all 0.3s ease',
                }}
              >
                <div
                  style={{
                    position: 'absolute',
                    top: -12,
                    left: '50%',
                    transform: 'translateX(-50%)',
                    padding: '3px 12px',
                    borderRadius: 999,
                    background: 'rgba(245, 158, 11, 0.2)',
                    border: '1px solid rgba(245, 158, 11, 0.3)',
                    color: '#FBBF24',
                    fontSize: 11,
                    fontWeight: 700,
                    letterSpacing: '0.06em',
                    textTransform: 'uppercase',
                  }}
                >
                  🔥 {t('plan_pro_badge', 'Eng Ommabop')}
                </div>
                <div style={{ fontSize: 17, fontWeight: 900, color: '#0F172A', marginBottom: 6 }}>
                  🔥 {t('plan_pro_name')}
                </div>
                <div style={{ fontSize: 12, color: '#64748B', marginBottom: 18, minHeight: 36, lineHeight: 1.5 }}>
                  {t('plan_pro_desc')}
                </div>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, marginBottom: 22 }}>
                  <span style={{ fontSize: 32, fontWeight: 900, color: '#F59E0B' }}>15 000</span>
                  <span style={{ fontSize: 13, color: '#64748B' }}>{t('plan_pro_period', "so'm / oy")}</span>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 26, flex: 1, fontSize: 12.5 }}>
                  {[
                    'Haftasiga 15 ta esse',
                    'Kunlik rasmiy Mock testlar',
                    'Barcha CBT testlar va tahlil',
                    'AI repetitor izohlari',
                    'Xatolar ustida chuqur ishlash',
                  ].map((f, i) => (
                    <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <CheckIcon size={15} style={{ color: '#10B981', flexShrink: 0 }} />
                      <span style={{ color: 'var(--ink)' }}>{f}</span>
                    </div>
                  ))}
                </div>
                <button
                  type="button"
                  onClick={() => handleAction('/subscribe?plan=pro')}
                  className="btn-glow btn-shimmer"
                  style={{
                    width: '100%',
                    padding: 12,
                    borderRadius: 12,
                    background: 'linear-gradient(135deg, #F59E0B, #FBBF24)',
                    border: 'none',
                    color: '#090d16',
                    fontWeight: 900,
                    fontSize: 13.5,
                    cursor: 'pointer',
                    marginTop: 'auto',
                    transition: 'all 0.18s ease',
                  }}
                >
                  {t('plan_pro_cta')}
                </button>
              </div>

              {/* 4. Premium Plan (VIP) */}
              <div
                className="card lcard-hover"
                style={{
                  borderRadius: 22,
                  padding: '28px 24px',
                  display: 'flex',
                  flexDirection: 'column',
                  position: 'relative',
                  background: '#FFFFFF',
                  border: '1px solid rgba(139, 92, 246, 0.35)',
                  boxShadow: '0 10px 25px -5px rgba(139, 92, 246, 0.1)',
                  transition: 'all 0.3s ease',
                }}
              >
                <div
                  style={{
                    position: 'absolute',
                    top: -11,
                    left: '50%',
                    transform: 'translateX(-50%)',
                    padding: '3px 12px',
                    borderRadius: 999,
                    background: 'rgba(139, 92, 246, 0.2)',
                    border: '1px solid rgba(139, 92, 246, 0.4)',
                    color: '#A78BFA',
                    fontSize: 10.5,
                    fontWeight: 800,
                    letterSpacing: '0.08em',
                    textTransform: 'uppercase',
                  }}
                >
                  👑 {t('plan_premium_badge', 'VIP / Cheksiz')}
                </div>
                <div style={{ fontSize: 17, fontWeight: 900, color: '#0F172A', marginBottom: 6 }}>
                  👑 {t('plan_master_name')}
                </div>
                <div style={{ fontSize: 12, color: '#64748B', marginBottom: 18, minHeight: 36, lineHeight: 1.5 }}>
                  {t('plan_master_desc')}
                </div>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, marginBottom: 22 }}>
                  <span style={{ fontSize: 32, fontWeight: 900, color: '#A78BFA' }}>27 000</span>
                  <span style={{ fontSize: 13, color: '#64748B' }}>{t('plan_master_period', "so'm / oy")}</span>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 26, flex: 1, fontSize: 12.5 }}>
                  {[
                    'Cheksiz rasmli va matnli esse',
                    'Barcha CBT testlar',
                    '1v1 Arena',
                    'Ustoz tekshiruvi',
                    'Rasmiy PDF sertifikat',
                  ].map((f, i) => (
                    <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <CheckIcon size={15} style={{ color: '#10B981', flexShrink: 0 }} />
                      <span style={{ color: 'var(--ink)' }}>{f}</span>
                    </div>
                  ))}
                </div>
                <button
                  type="button"
                  onClick={() => handleAction('/subscribe?plan=premium')}
                  className="btn-glow btn-shimmer"
                  style={{
                    width: '100%',
                    padding: 12,
                    borderRadius: 12,
                    background: 'linear-gradient(135deg, #8B5CF6, #6366F1)',
                    border: 'none',
                    color: '#FFFFFF',
                    fontWeight: 800,
                    fontSize: 13.5,
                    cursor: 'pointer',
                    marginTop: 'auto',
                    transition: 'all 0.18s ease',
                  }}
                >
                  {t('plan_master_cta')}
                </button>
              </div>
            </div>
          </div>
        </section>

        {/* FAQ SECTION */}
        <section
          id="faq"
          style={{
            padding: '70px 20px',
            position: 'relative',
          }}
        >
          <div style={{ margin: '0 auto', maxWidth: 840 }}>
            <div style={{ textAlign: 'center', marginBottom: 44 }}>
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 900,
                  letterSpacing: '0.22em',
                  color: '#F59E0B',
                  textTransform: 'uppercase',
                }}
              >
                {t('faq_eyebrow')}
              </span>
              <h2
                style={{
                  fontSize: 'clamp(1.8rem, 3.5vw, 2.4rem)',
                  fontWeight: 900,
                  color: '#0F172A',
                  margin: '12px 0',
                }}
              >
                {t('faq_title_1')}{' '}
                <span className="hero-title-gradient">{t('faq_title_2')}</span>
              </h2>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              {[
                [t('faq_q1'), t('faq_a1')],
                [t('faq_q2'), t('faq_a2')],
                [t('faq_q3'), t('faq_a3')],
                [t('faq_q4'), t('faq_a4')],
                [t('faq_q5'), t('faq_a5')],
              ].map(([q, a], i) => (
                <details
                  key={i}
                  className="card"
                  style={{
                    borderRadius: 16,
                    padding: '16px 20px',
                    cursor: 'pointer',
                    background: 'var(--card)',
                    border: '1px solid var(--border)',
                  }}
                >
                  <summary
                    style={{
                      fontSize: 15,
                      fontWeight: 700,
                      color: 'var(--ink)',
                      listStyle: 'none',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                    }}
                  >
                    <span>{q}</span>
                    <span style={{ fontSize: 18, color: '#F59E0B' }}>+</span>
                  </summary>
                  <p
                    style={{
                      margin: '12px 0 0',
                      fontSize: 13,
                      color: 'var(--muted)',
                      lineHeight: 1.65,
                    }}
                  >
                    {a}
                  </p>
                </details>
              ))}
            </div>
          </div>
        </section>

        {/* BOTTOM CTA BANNER */}
        <section style={{ padding: '40px 20px 80px' }} className="hidden md:block">
          <div
            style={{
              margin: '0 auto',
              maxWidth: 1040,
              borderRadius: 28,
              padding: '48px 32px',
              textAlign: 'center',
              position: 'relative',
              background:
                landingSubject === 'english'
                  ? 'linear-gradient(135deg, rgba(56, 189, 248, 0.14), rgba(99, 102, 241, 0.12))'
                  : 'linear-gradient(135deg, rgba(245, 158, 11, 0.14), rgba(139, 92, 246, 0.12))',
              border:
                landingSubject === 'english'
                  ? '1px solid rgba(56, 189, 248, 0.3)'
                  : '1px solid rgba(245, 158, 11, 0.3)',
            }}
          >
            <h2
              style={{
                fontSize: 'clamp(2rem, 3.8vw, 2.8rem)',
                fontWeight: 900,
                lineHeight: 1.25,
                padding: '4px 0',
                background: 'linear-gradient(135deg, #0F172A 30%, #D97706 100%)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
                margin: '0 0 16px',
              }}
            >
              {selectedTrack === 'ielts'
                ? 'IELTS Band 7.5+ ga erishishga tayyormisiz?'
                : selectedTrack === 'multilevel'
                ? 'Multi-level C1 sertifikatini olishga tayyormisiz?'
                : selectedTrack === 'attestation'
                ? 'Oliy toifa va 70% ustama sinoviga tayyormisiz?'
                : t('cta_banner_title')}
            </h2>
            <p
              style={{
                fontSize: 15,
                color: '#64748B',
                maxWidth: 580,
                margin: '0 auto 32px',
                lineHeight: 1.65,
              }}
            >
              {selectedTrack === 'ielts'
                ? 'Hozir roʻyxatdan oʻting va birinchi Writing hamda Speaking sinovini mutlaqo bepul topshiring!'
                : selectedTrack === 'multilevel'
                ? '35 talik namunaviy test va yozma insho tahlilidan bepul foydalaning.'
                : selectedTrack === 'attestation'
                ? '50 talik sinov diagnostikasini ishlab, toifa ehtimolligingizni aniqlang.'
                : t('cta_banner_subtitle')}
            </p>
            <div style={{ display: 'flex', justifyContent: 'center', gap: 14, flexWrap: 'wrap' }}>
              <button
                type="button"
                onClick={() => handleAction('/register')}
                className="btn-glow btn-shimmer"
                style={{
                  padding: '14px 32px',
                  borderRadius: 14,
                  fontSize: 15,
                  fontWeight: 800,
                  color: '#090d16',
                  background: 'linear-gradient(135deg, #F59E0B, #FBBF24)',
                  border: 'none',
                  cursor: 'pointer',
                  boxShadow: '0 4px 20px rgba(245, 158, 11, 0.4)',
                }}
              >
                {t('cta_banner_btn')} →
              </button>
            </div>
          </div>
        </section>
      </main>
      <PassingScoresModal isOpen={scoresModalOpen} onClose={() => setScoresModalOpen(false)} />
      <div className="md:hidden"><MobileBottomBar onOpenProfile={() => setProfileDrawerOpen(true)} /></div>
      <MobileNavDrawer isOpen={navDrawerOpen} onClose={() => setNavDrawerOpen(false)} />
      <MobileProfileDrawer isOpen={profileDrawerOpen} onClose={() => setProfileDrawerOpen(false)} />

      {/* FOOTER */}
      <footer
        style={{
          borderTop: '1px solid var(--border)',
          background: 'var(--header-bg)',
          padding: '48px 20px 32px',
        }}
      >
        <div style={{ margin: '0 auto', maxWidth: 1200 }}>
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
              gap: 36,
              marginBottom: 40,
            }}
          >
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
                <img src="/logo-mark.png" alt="GRANDEC" style={{ height: 32, width: 'auto', objectFit: 'contain' }} />
                <div style={{ display: 'flex', flexDirection: 'column' }}>
                  <span style={{ fontWeight: 900, fontSize: 16, color: '#0F172A', lineHeight: 1.1 }}>GRANDEC</span>
                  <span style={{ fontSize: 8.5, fontWeight: 800, color: '#D97706', letterSpacing: '0.12em', textTransform: 'uppercase' }}>ACADEMIC EDTECH</span>
                </div>
              </div>
              <p style={{ fontSize: 13, color: '#64748B', lineHeight: 1.6, margin: 0 }}>
                {t('foot_desc')}
              </p>
            </div>

            <div>
              <div style={{ fontSize: 13, fontWeight: 800, color: 'var(--ink)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 14 }}>
                {t('foot_col_platform')}
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: 13 }}>
                <Link to="/essays" style={{ color: '#64748B', textDecoration: 'none' }}>AI Esse Grader</Link>
                <Link to="/tests" style={{ color: '#64748B', textDecoration: 'none' }}>CBT Testlar</Link>
                <Link to="/speaking" style={{ color: '#64748B', textDecoration: 'none' }}>AI Speaking</Link>
                <Link to="/arena" style={{ color: '#64748B', textDecoration: 'none' }}>1v1 Arena</Link>
              </div>
            </div>

            <div>
              <div style={{ fontSize: 13, fontWeight: 800, color: 'var(--ink)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 14 }}>
                {t('foot_col_legal')}
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: 13 }}>
                <Link to="/terms" style={{ color: '#64748B', textDecoration: 'none' }}>{t('foot_terms')}</Link>
                <Link to="/privacy" style={{ color: '#64748B', textDecoration: 'none' }}>{t('foot_privacy')}</Link>
                <Link to="/public-offer" style={{ color: '#64748B', textDecoration: 'none' }}>{t('foot_offer')}</Link>
              </div>
            </div>

            <div>
              <div style={{ fontSize: 13, fontWeight: 800, color: 'var(--ink)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 14 }}>
                {t('foot_col_contact')}
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, fontSize: 13, color: '#64748B' }}>
                <a href="https://t.me/uz_essaygrader_bot" target="_blank" rel="noreferrer" style={{ color: '#F59E0B', textDecoration: 'none' }}>
                  @uz_essaygrader_bot
                </a>
                <span>Toshkent, Oʻzbekiston</span>
              </div>
            </div>
          </div>

          <div
            style={{
              borderTop: '1px solid var(--border)',
              paddingTop: 24,
              display: 'flex',
              flexWrap: 'wrap',
              justifyContent: 'space-between',
              gap: 12,
              fontSize: 12,
              color: '#64748B',
            }}
          >
            <span>&copy; {new Date().getFullYear()} GRAND EDUCATION (grandec.uz). {t('foot_rights')}</span>
            <span>
              Website <a href="https://www.instagram.com/rozievkomiljon/" target="_blank" rel="noopener noreferrer" style={{ color: '#fbbf24', textDecoration: 'underline' }}>Komiljon Roziyev</a> tomonidan ishlab chiqilgan
            </span>
          </div>
        </div>
      </footer>

      {/* Style overrides for media queries */}
      <style>{`
        @keyframes wavePulse {
          0%, 100% { height: 6px; }
          50% { height: 26px; }
        }
        .waveform-bar {
          width: 4px;
          border-radius: 999px;
          background: #38BDF8;
          transition: height 0.2s ease;
        }
        .waveform-bar.playing {
          animation: wavePulse 0.9s ease-in-out infinite;
        }
        .hero-subject-switcher {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          padding: 5px;
          background: var(--card-2);
          border: 1px solid var(--border);
          border-radius: 999px;
          box-shadow: 0 4px 20px rgba(0, 0, 0, 0.18);
          max-width: 100%;
        }
        .hero-switcher-btn {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          padding: 8px 18px;
          border-radius: 999px;
          font-size: 13px;
          font-weight: 700;
          color: var(--muted);
          background: transparent;
          border: none;
          cursor: pointer;
          transition: all 0.2s ease;
          white-space: nowrap;
        }
        .hero-switcher-btn:hover {
          color: var(--ink);
        }
        .hero-switcher-btn.active {
          background: linear-gradient(135deg, #F59E0B, #FBBF24);
          color: #090d16;
          box-shadow: 0 2px 12px rgba(245, 158, 11, 0.35);
        }
        .hero-exam-switcher {
          display: flex;
          align-items: center;
          gap: 8px;
          flex-wrap: wrap;
        }
        .hero-exam-btn {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          padding: 8px 16px;
          border-radius: 12px;
          font-size: 13px;
          font-weight: 700;
          cursor: pointer;
          min-height: 42px;
          background: var(--card-2);
          border: 1px solid var(--border);
          color: var(--muted);
          transition: all 0.2s ease;
          box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
        }
        .hero-exam-btn:hover {
          border-color: rgba(245, 158, 11, 0.4);
          color: var(--ink);
        }
        .hero-exam-btn.active.active-eng {
          background: rgba(56, 189, 248, 0.16);
          border: 1px solid #38BDF8;
          color: #38BDF8;
          box-shadow: 0 4px 14px rgba(56, 189, 248, 0.25);
        }
        .hero-exam-btn.active.active-uz {
          background: rgba(245, 158, 11, 0.16);
          border: 1px solid #F59E0B;
          color: #F59E0B;
          box-shadow: 0 4px 14px rgba(245, 158, 11, 0.25);
        }
        .exam-btn-badge {
          font-size: 11px;
          font-weight: 800;
          padding: 2px 7px;
          border-radius: 6px;
          background: rgba(255, 255, 255, 0.08);
        }
        .switcher-subtag {
          font-size: 11px;
          font-weight: 800;
          padding: 2px 8px;
          border-radius: 6px;
          background: rgba(9, 13, 22, 0.22);
          color: inherit;
        }
        .hero-switcher-btn:not(.active) .switcher-subtag {
          background: var(--border);
          color: var(--muted);
        }
        @media (max-width: 640px) {
          .hero-subject-switcher {
            width: 100%;
            border-radius: 16px;
            flex-direction: column;
            gap: 4px;
            padding: 4px;
          }
          .hero-switcher-btn {
            width: 100%;
            border-radius: 12px;
            justify-content: center;
            padding: 10px 14px;
          }
          .hero-exam-switcher {
            width: 100%;
            display: grid;
            grid-template-columns: 1fr;
            gap: 8px;
          }
          .hero-exam-btn {
            width: 100%;
            justify-content: center;
            min-height: 44px;
          }
        }
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
