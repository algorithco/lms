import { useEffect, useMemo, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { useLang } from '../i18n/LangContext';
import { School } from '../lib/api';
import GooeyNav from '../components/GooeyNav';
import BlurText from '../components/BlurText';
import DepthCarousel from '../components/DepthCarousel';
import TrendChart from '../components/TrendChart';
import {
  AwardIcon,
  BotIcon,
  ClockIcon,
  FileTextIcon,
  FlameIcon,
  GamepadIcon,
  LightbulbIcon,
  MapPinIcon,
  MenuIcon,
  SendIcon,
  ShieldIcon,
  SwordsIcon,
  TrophyIcon,
  XIcon,
  ZapIcon,
} from '../components/icons';

export default function Landing() {
  const { t } = useLang();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [slide, setSlide] = useState(0);

  // Live platform totals (GET /api/v1/school/public-stats/, AllowAny).
  // Failure is silent by design: the curated showcase chart below stays.
  const [stats, setStats] = useState<{
    totals: { tests: number; students: number; essays_graded: number };
  } | null>(null);
  useEffect(() => {
    let live = true;
    School.publicStats()
      .then((s) => {
        if (live) setStats(s);
      })
      .catch(() => {
        /* offline / backend down — keep the curated demo curves */
      });
    return () => {
      live = false;
    };
  }, []);

  // Newsletter mirrors legacy home.html subscribeNewsletter: client-only
  // (no backend endpoint exists — it clears the field and confirms).
  const [newsEmail, setNewsEmail] = useState('');
  const [newsDone, setNewsDone] = useState(false);
  const subscribeNews = (e: FormEvent) => {
    e.preventDefault();
    if (newsEmail.trim()) {
      setNewsEmail('');
      setNewsDone(true);
    }
  };

  // Advertising showcase: 12-month platform growth (curated demo curves).
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

  // Single source of truth for section-nav order — matches the page
  // top-to-bottom flow: carousel → features → stats → how.
  const sectionNav: [string, string][] = [
    ['nav_programs', '#carousel'],
    ['nav_features', '#features'],
    ['nav_stats', '#stats'],
    ['nav_how', '#how'],
  ];
  const navRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    const id = setInterval(() => setSlide((s) => (s + 1) % 3), 6000);
    return () => clearInterval(id);
  }, []);

  // Continuous scroll-driven navbar (desktop/tablet ≥768px only).
  // progress = clamp(scrollY / 140, 0, 1) → written to --nav-p on the nav.
  // CSS calc() interpolates width/margin/radius/height/shadow every frame.
  // No React state → zero re-renders; mobile never gets a value above 0.
  useEffect(() => {
    const SHRINK_DISTANCE = 140;
    const mq = window.matchMedia('(min-width: 768px)');
    let ticking = false;
    let last = -1;
    const update = () => {
      ticking = false;
      const el = navRef.current;
      if (!el) return;
      const raw = mq.matches ? window.scrollY / SHRINK_DISTANCE : 0;
      const p = Math.min(Math.max(raw, 0), 1);
      const q = Math.round(p * 1000) / 1000;
      if (q !== last) {
        last = q;
        el.style.setProperty('--nav-p', String(q));
      }
    };
    const onScroll = () => {
      if (!ticking) {
        ticking = true;
        requestAnimationFrame(update);
      }
    };
    update();
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', onScroll);
    return () => {
      window.removeEventListener('scroll', onScroll);
      window.removeEventListener('resize', onScroll);
    };
  }, []);

  const features = [
    { Icon: FileTextIcon, title: t('feat_tests_title'), desc: t('feat_tests_desc') },
    { Icon: ZapIcon, title: t('feat_essay_title'), desc: t('feat_essay_desc') },
    { Icon: SwordsIcon, title: t('feat_arena_title'), desc: t('feat_arena_desc') },
    { Icon: GamepadIcon, title: t('feat_games_title'), desc: t('feat_games_desc') },
    { Icon: SendIcon, title: t('feat_tg_title'), desc: t('feat_tg_desc') },
    { Icon: TrophyIcon, title: t('feat_achiev_title'), desc: t('feat_achiev_desc') },
  ];

  const featureSlides = useMemo(
    () =>
      features.map((f) => ({
        content: (
          <div className="feat-slide">
            <div style={{
              width: 48, height: 48, borderRadius: 16, display: 'flex', alignItems: 'center',
              justifyContent: 'center', marginBottom: 20, background: 'rgba(250,204,21,.08)', color: '#FACC15',
              flexShrink: 0,
            }}>
              <f.Icon size={24} />
            </div>
            <h3 className="land-ink">{f.title}</h3>
            <p className="land-muted">{f.desc}</p>
          </div>
        ),
      })),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [t],
  );

  return (
    <div className="landing" style={{ background: 'var(--bg)', minHeight: '100svh' }}>
      <style>{`
        .landing-nav { position: fixed; top: 0; left: 0; right: 0; z-index: 80; width: 100%; overflow-x: clip; }
        .landing-nav-bar { width: 100%; border-radius: 0; }
        .landing-nav-inner { margin: 0 auto; width: 100%; max-width: 72rem; padding: 0 1rem; height: 4rem; display: flex; align-items: center; justify-content: space-between; gap: 0.5rem; }
        @media (min-width: 640px) { .landing-nav-inner { padding: 0 1.5rem; } }
        @media (min-width: 1024px) { .landing-nav-inner { padding: 0 2rem; } }
        .landing-links { display: none; }
        @media (min-width: 1024px) { .landing-links { display: flex; align-items: center; gap: 0.25rem; font-size: 14px; font-weight: 600; } }
        .landing-links a { padding: 0.5rem 0.75rem; border-radius: 12px; text-decoration: none; white-space: nowrap; }
        @media (min-width: 1280px) { .landing-links a { padding: 0.5rem 1rem; } }
        .landing-cta { display: inline-flex; align-items: center; gap: 6px; padding: 10px 12px; font-size: 14px; font-weight: 700; color: #111111; border-radius: 12px; text-decoration: none; white-space: nowrap; background: linear-gradient(135deg,#EAB308,#FACC15); box-shadow: 0 6px 18px rgba(250,204,21,.35); border: none; }
        @media (min-width: 640px) { .landing-cta { padding: 10px 20px; gap: 8px; } }
        .landing-login { display: none; font-size: 14px; font-weight: 600; padding: 10px 12px; border-radius: 12px; text-decoration: none; }
        @media (min-width: 640px) { .landing-login { display: inline-flex; } }
        .landing-burger { padding: 10px; border-radius: 12px; border: none; background: transparent; font-size: 20px; cursor: pointer; color: inherit; }
        @media (min-width: 1024px) { .landing-burger { display: none; } }
        .landing-nav-bar { max-width: none; border-left: 0; border-right: 0; }
        /* Continuous scroll-driven transformation — desktop/tablet only (≥768px).
           --nav-p is 0→1 progress written from scrollY (0px→140px) via rAF.
           Every property interpolates with calc(): no states, no jumps.
           Mobile (<768px) has no rules here and stays exactly as-is. */
        @media (min-width: 768px) {
          .landing-nav-bar {
            margin: calc(var(--nav-p, 0) * 12px) auto 0;
            width: calc(100% - var(--nav-p, 0) * clamp(0px, 8vw, 128px));
            border-radius: calc(var(--nav-p, 0) * 20px);
            border-left: 1px solid rgba(43, 43, 43, var(--nav-p, 0));
            border-right: 1px solid rgba(43, 43, 43, var(--nav-p, 0));
            box-shadow: 0 calc(var(--nav-p, 0) * 12px) calc(var(--nav-p, 0) * 40px) rgba(0, 0, 0, calc(var(--nav-p, 0) * 0.5));
          }
          .landing-nav-inner { height: calc(4rem - var(--nav-p, 0) * 0.5rem); }
        }
        @media (prefers-reduced-motion: reduce) {
          .landing-nav-bar, .landing-nav-inner { transition: none; }
        }
        .landing-mobile { border-top: 1px solid var(--border); }
        .landing-mobile a { display: block; padding: 10px 16px; border-radius: 12px; font-size: 14px; font-weight: 600; text-decoration: none; }
        .hide-sm-arrow { display: none; }
        @media (min-width: 420px) { .hide-sm-arrow { display: block; } }
        @media (max-width: 639px) { .hide-sm { display: none; } }
        .hero-h1 { font-size: clamp(1.7rem, 8vw, 2.125rem); line-height: 1.12; font-weight: 900; letter-spacing: -0.02em; }
        /* Per-word gradient: transform/filter live ON the same element as
           background-clip, so Chrome always paints it (unlike nested). */
        .grad-word {
          background: linear-gradient(92deg, #fef08a 0%, #facc15 45%, #eab308 100%);
          -webkit-background-clip: text;
          background-clip: text;
          color: transparent;
        }
        @media (min-width: 640px) { .hero-h1 { font-size: 3rem; line-height: 1.08; } }
        @media (min-width: 1024px) { .hero-h1 { font-size: 3.75rem; } }
        .slide-h2 { font-size: 1.7rem; line-height: 1.2; font-weight: 900; letter-spacing: -0.02em; }
        @media (min-width: 640px) { .slide-h2 { font-size: 2.25rem; } }
        .slide-grid { display: grid; grid-template-columns: 1fr; gap: 2rem; align-items: center; }
        @media (min-width: 1024px) { .slide-grid { grid-template-columns: 1fr 1fr; gap: 3rem; } }
        .cta-row { display: flex; flex-direction: column; gap: 0.75rem; margin-top: 1.5rem; }
        @media (min-width: 480px) { .cta-row { flex-direction: row; flex-wrap: wrap; align-items: center; } }
        .cta-row .landing-cta, .cta-row .ghost-cta { justify-content: center; width: 100%; }
        @media (min-width: 480px) { .cta-row .landing-cta, .cta-row .ghost-cta { width: auto; } }
        .ghost-cta { display: inline-flex; align-items: center; justify-content: center; gap: 8px; padding: 12px 24px; font-size: 14px; font-weight: 700; border-radius: 16px; text-decoration: none; border: 1px solid #2b2b2b; }
        .dots { display: flex; align-items: center; justify-content: center; gap: 0.5rem; margin-top: 1.75rem; }
        .dot { width: 9px; height: 9px; border-radius: 999px; border: none; background: rgba(148,163,184,.5); cursor: pointer; padding: 0; transition: all .3s ease; }
        .dot.on { width: 26px; background: linear-gradient(90deg,#FACC15,#EAB308); box-shadow: 0 0 12px rgba(250,204,21,.7); }
        .feat-grid { display: grid; grid-template-columns: 1fr; gap: 1.25rem; }
        @media (min-width: 640px) { .feat-grid { grid-template-columns: 1fr 1fr; } }
        @media (min-width: 1024px) { .feat-grid { grid-template-columns: 1fr 1fr 1fr; } }
        .features-carousel { height: 470px; }
        @media (min-width: 640px) { .features-carousel { height: 500px; } }
        .feat-slide { height: 100%; padding: 28px 24px; display: flex; flex-direction: column; }
        .feat-slide h3 { font-size: 20px; font-weight: 800; margin: 0 0 10px; }
        .feat-slide p { font-size: 14px; line-height: 1.65; margin: 0; flex: 1; }
        .steps-grid { display: grid; grid-template-columns: 1fr; gap: 1.5rem; }
        @media (min-width: 768px) { .steps-grid { grid-template-columns: 1fr 1fr 1fr; } }
        .foot-grid { display: grid; grid-template-columns: 1fr; gap: 2.5rem; }
        @media (min-width: 768px) { .foot-grid { grid-template-columns: 1fr 1fr; } }
        @media (min-width: 1024px) { .foot-grid { grid-template-columns: repeat(4, 1fr); } }
        .news-form { display: flex; flex-direction: column; gap: 0.5rem; }
        @media (min-width: 420px) { .news-form { flex-direction: row; } }
      `}</style>

      {/* NAVBAR */}
      <nav ref={navRef} className="landing-nav">
        <div className="glass-card landing-nav-bar">
          <div className="landing-nav-inner">
            <Link to="/" style={{ display: 'flex', alignItems: 'center', gap: 10, textDecoration: 'none', minWidth: 0 }}>
              <span style={{ position: 'relative', flexShrink: 0 }}>
                <img src="/grandec.png" alt="GRANDEC" className="brand-badge" style={{ width: 32, height: 32, padding: 0, objectFit: 'cover' }} />
              </span>
              <span style={{ lineHeight: 1.2, minWidth: 0 }}>
                <span className="land-ink" style={{ display: 'block', fontSize: 15, fontWeight: 800, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  GRANDEC
                </span>
                <span style={{ display: 'block', fontSize: 9, fontWeight: 700, letterSpacing: '0.2em', color: '#FACC15' }}>LMS PLATFORM</span>
              </span>
            </Link>
            <div className="landing-links">
              <GooeyNav
                items={sectionNav.map(([k, href]) => ({ label: t(k), href }))}
                particleCount={15}
                particleDistances={[90, 10]}
                particleR={100}
                initialActiveIndex={0}
                animationTime={600}
                timeVariance={300}
                colors={[1, 2, 3, 1, 2, 3, 1, 4]}
              />
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 4, flexShrink: 0 }}>
              <Link to="/login" className="landing-login land-muted">{t('login')}</Link>
              <Link to="/register" className="landing-cta btn-glow">
                {t('start_free')}
                <svg className="hide-sm-arrow" width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
                </svg>
              </Link>
              <button className="landing-burger land-muted" aria-label="Menu" onClick={() => setMobileOpen((v) => !v)}>
                {mobileOpen ? <XIcon size={20} /> : <MenuIcon size={20} />}
              </button>
            </div>
          </div>
          {mobileOpen && (
            <div className="landing-mobile">
              <div style={{ margin: '0 auto', maxWidth: 72 * 16, padding: '12px 16px', display: 'flex', flexDirection: 'column', gap: 4 }}>
                {sectionNav.map(([k, href]) => (
                  <a key={k} href={href} className="land-muted" onClick={() => setMobileOpen(false)}>
                    {t(k)}
                  </a>
                ))}
                <Link to="/login" className="land-muted" onClick={() => setMobileOpen(false)}>
                  {t('login')}
                </Link>
              </div>
            </div>
          )}
        </div>
      </nav>

      {/* HERO */}
      <section id="carousel" style={{ position: 'relative', paddingTop: 64, overflow: 'hidden' }}>
        <div style={{ position: 'absolute', inset: 0 }} aria-hidden="true">
          <div className="hero-grid-bg" />
          <div className="hero-orb" style={{ width: 480, height: 480, background: '#EAB308', top: -160, left: -96 }} />
          <div className="hero-orb" style={{ width: 420, height: 420, background: '#FACC15', top: 40, right: -96 }} />
          <span className="float-letter f-dance" style={{ fontSize: 150, top: 56, left: '4%' }}>O'</span>
          <span className="float-letter f-dance-2" style={{ fontSize: 120, top: 96, right: '6%' }}>A</span>
        </div>

        <div style={{ position: 'relative', margin: '0 auto', maxWidth: 72 * 16, padding: '32px 16px 16px', width: '100%' }}>
          <div className="reveal in" style={{ textAlign: 'center', marginBottom: 32 }}>
            <span style={{
              display: 'inline-flex', alignItems: 'center', gap: 8, padding: '6px 16px',
              borderRadius: 999, fontSize: 12, fontWeight: 700,
              background: 'rgba(250,204,21,.1)', color: '#EAB308', border: '1px solid rgba(250,204,21,.25)',
            }}>
              <span style={{ width: 8, height: 8, borderRadius: 999, background: '#FACC15' }} />
              {t('land_eyebrow')}
            </span>
          </div>

          <div style={{ textAlign: 'center', maxWidth: 56 * 16, margin: '0 auto 40px' }}>
            <h1 className="hero-h1 land-ink">
              <BlurText text={t('hero_title_1')} delay={70} as="span" style={{ justifyContent: 'center' }} />
              <BlurText
                text={t('hero_title_2')}
                delay={90}
                as="span"
                style={{ display: 'inline', textAlign: 'center' }}
                wordClassName="grad-word"
              />
            </h1>
            <p className="land-muted" style={{ marginTop: 16, fontSize: 15, lineHeight: 1.7, textWrap: 'balance' }}>
              {t('land_subhead_1')} <b style={{ color: '#EAB308' }}>{t('land_subhead_b1')}</b>{' '}
              {t('land_subhead_2')} <b style={{ color: '#EAB308' }}>{t('land_subhead_b2')}</b>{' '}
              {t('land_subhead_3')}
            </p>
          </div>

          {/* Slides */}
          {slide === 0 && (
            <div className="slide-grid">
              <div>
                <span style={{
                  display: 'inline-flex', alignItems: 'center', gap: 8, padding: '4px 12px',
                  borderRadius: 999, fontSize: 11, fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase',
                  background: 'linear-gradient(135deg,rgba(234,179,8,.15),rgba(250,204,21,.08))',
                  color: '#EAB308', border: '1px solid rgba(250,204,21,.3)',
                }}>
                  <ShieldIcon size={13} /> {t('slide1_badge')}
                </span>
                <h2 className="slide-h2 land-ink" style={{ marginTop: 20 }}>
                  {t('slide1_h2_1')}
                  <br />
                  <span style={{ color: '#EAB308' }}>{t('slide1_h2_2')}</span>
                </h2>
                <p className="land-muted" style={{ marginTop: 16, lineHeight: 1.7, maxWidth: 28 * 16 }}>{t('slide1_p')}</p>
                <div className="cta-row">
                  <Link to="/register" className="landing-cta btn-glow" style={{ padding: '12px 28px' }}>
                    {t('cta_start_course')} →
                  </Link>
                  <a href="#features" className="ghost-cta lpill land-muted">{t('cta_demo')}</a>
                </div>
                <div className="land-muted" style={{ marginTop: 24, display: 'flex', flexWrap: 'wrap', gap: '8px 24px', fontSize: 12 }}>
                  <span><span className="dot-mini" style={{ background: '#FACC15' }} /> {t('meta_qbank')}</span>
                  <span><span className="dot-mini" style={{ background: '#EAB308' }} /> {t('meta_criteria')}</span>
                  <span><span className="dot-mini" style={{ background: '#A16207' }} /> {t('meta_cert')}</span>
                </div>
              </div>
              <div style={{ position: 'relative', minWidth: 0 }}>
                <div className="lcard" style={{ borderRadius: 24, padding: 20, boxShadow: '0 24px 70px rgba(0,0,0,.18)', position: 'relative' }}>
                  <p style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.18em', color: '#FACC15' }}>{t('slide1_badge')}</p>
                  <p className="land-ink" style={{ fontSize: 14, fontWeight: 800 }}>{t('mock_sample_test')}</p>
                  {[
                    [t('mock_read'), '8/10 ✓', 80, '#FACC15'],
                    ['Grammatika', '14/15 ✓', 93, '#FACC15'],
                    [t('mock_lit'), '9/15', 60, '#EAB308'],
                  ].map(([label, val, w, c]) => (
                    <div key={String(label)} style={{ marginTop: 14 }}>
                      <div className="land-muted" style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, fontWeight: 600 }}>
                        <span>{label}</span>
                        <span style={{ color: String(c) }}>{val}</span>
                      </div>
                      <div style={{ height: 8, borderRadius: 999, background: '#122424', marginTop: 6 }}>
                        <div style={{ height: 8, borderRadius: 999, width: `${w}%`, background: `linear-gradient(90deg, ${c}, ${c})` }} />
                      </div>
                    </div>
                  ))}
                  <div style={{
                    marginTop: 20, display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    borderRadius: 16, padding: '12px 16px',
                    background: 'linear-gradient(135deg,rgba(234,179,8,.1),rgba(250,204,21,.04))',
                  }}>
                    <div>
                      <p style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.15em', color: '#EAB308' }}>{t('mock_score')}</p>
                      <p className="land-ink" style={{ fontSize: 24, fontWeight: 900 }}>
                        78.3<span style={{ fontSize: 14, color: '#EAB308' }}>%</span>
                      </p>
                    </div>
                    <span style={{
                      padding: '6px 12px', borderRadius: 12, fontSize: 11, fontWeight: 700, color: '#111111',
                      background: 'linear-gradient(135deg,#EAB308,#FACC15)',
                    }}>
                      {t('mock_passed')}
                    </span>
                  </div>
                </div>
                <div className="float-badge glass-card" style={{
                  position: 'absolute', top: -20, left: -8, display: 'flex', alignItems: 'center',
                  gap: 8, padding: '8px 16px', borderRadius: 16, fontSize: 12, fontWeight: 700,
                }}>
                  <AwardIcon size={14} /> {t('badge_exam_mode')}
                </div>
                <div className="float-badge-2 glass-card" style={{
                  position: 'absolute', bottom: -20, right: 16, display: 'flex', alignItems: 'center',
                  gap: 8, padding: '8px 16px', borderRadius: 16, fontSize: 12, fontWeight: 700,
                }}>
                  <ClockIcon size={14} /> {t('badge_time')}
                </div>
              </div>
            </div>
          )}

          {slide === 1 && (
            <div className="slide-grid">
              <div>
                <span style={{
                  display: 'inline-flex', alignItems: 'center', gap: 8, padding: '4px 12px',
                  borderRadius: 999, fontSize: 11, fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase',
                  background: 'linear-gradient(135deg,rgba(250,204,21,.14),rgba(250,204,21,.08))',
                  color: '#EAB308', border: '1px solid rgba(250,204,21,.3)',
                }}>
                  <ZapIcon size={13} /> AI Essay
                </span>
                <h2 className="slide-h2 land-ink" style={{ marginTop: 20 }}>
                  {t('slide2_h2_1')}
                  <br />
                  <span style={{ color: '#EAB308' }}>{t('slide2_h2_2')}</span>
                </h2>
                <p className="land-muted" style={{ marginTop: 16, lineHeight: 1.7, maxWidth: 28 * 16 }}>{t('slide2_p')}</p>
                <div className="cta-row">
                  <Link to="/register" className="landing-cta btn-glow" style={{ padding: '12px 28px' }}>
                    {t('cta_write_essay')} →
                  </Link>
                  <a href="#features" className="ghost-cta lpill land-muted">{t('cta_criteria')}</a>
                </div>
              </div>
              <div style={{ position: 'relative', minWidth: 0 }}>
                <div className="lcard" style={{ borderRadius: 24, padding: 20, boxShadow: '0 24px 70px rgba(0,0,0,.18)' }}>
                  <p style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.18em', color: '#FACC15' }}>{t('mock_ai_result')}</p>
                  <p className="land-ink" style={{ fontSize: 14, fontWeight: 800 }}>{t('mock_essay_title')}</p>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 20, marginTop: 16 }}>
                    <div style={{ textAlign: 'center' }}>
                      <p className="land-ink" style={{ fontSize: 26, fontWeight: 900 }}>16.5</p>
                      <p className="land-muted" style={{ fontSize: 9, fontWeight: 700 }}>{t('mock_ball')}</p>
                    </div>
                    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 10, fontSize: 12 }}>
                      {[
                        [t('mock_topic'), '5/5', '#EAB308'],
                        [t('mock_spelling'), '4/5', '#EAB308'],
                        [t('mock_style'), '3/5', '#EAB308'],
                        [t('mock_composition'), '4.5/5', '#EAB308'],
                      ].map(([label, val, c]) => (
                        <div key={String(label)} style={{ display: 'flex', justifyContent: 'space-between' }}>
                          <span className="land-muted">{label}</span>
                          <b style={{ color: String(c) }}>{val}</b>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div style={{ marginTop: 16, borderRadius: 12, padding: '10px 14px', fontSize: 12, background: 'rgba(234,179,8,.08)' }}>
                    <LightbulbIcon size={14} /> <b className="land-ink">{t('mock_reco')}</b>{' '}
                    <span className="land-muted">{t('mock_reco_text')}</span>
                  </div>
                </div>
                <div className="float-badge glass-card" style={{
                  position: 'absolute', top: -20, right: -8, display: 'flex', alignItems: 'center',
                  gap: 8, padding: '8px 16px', borderRadius: 16, fontSize: 12, fontWeight: 700,
                }}>
                  <BotIcon size={14} /> {t('badge_bmb')}
                </div>
                <div className="float-badge-2 glass-card" style={{
                  position: 'absolute', bottom: -20, left: 16, display: 'flex', alignItems: 'center',
                  gap: 8, padding: '8px 16px', borderRadius: 16, fontSize: 12, fontWeight: 700,
                }}>
                  <ZapIcon size={14} /> {t('badge_15s')}
                </div>
              </div>
            </div>
          )}

          {slide === 2 && (
            <div className="slide-grid">
              <div>
                <span style={{
                  display: 'inline-flex', alignItems: 'center', gap: 8, padding: '4px 12px',
                  borderRadius: 999, fontSize: 11, fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase',
                  background: 'linear-gradient(135deg,rgba(250,204,21,.14),rgba(250,204,21,.08))',
                  color: '#A16207', border: '1px solid rgba(250,204,21,.3)',
                }}>
                  <GamepadIcon size={13} /> {t('slide3_badge')}
                </span>
                <h2 className="slide-h2 land-ink" style={{ marginTop: 20 }}>
                  {t('slide3_h2_1')}
                  <br />
                  <span style={{ color: '#EAB308' }}>{t('slide3_h2_2')}</span>
                </h2>
                <p className="land-muted" style={{ marginTop: 16, lineHeight: 1.7, maxWidth: 28 * 16 }}>{t('slide3_p')}</p>
                <div className="cta-row">
                  <Link to="/register" className="landing-cta btn-glow" style={{ padding: '12px 28px' }}>
                    {t('cta_arena')} →
                  </Link>
                  <span className="ghost-cta lpill land-muted"><FlameIcon size={13} /> {t('badge_10wins')}</span>
                </div>
              </div>
              <div style={{ position: 'relative', minWidth: 0 }}>
                <div className="lcard" style={{ borderRadius: 24, padding: 20, boxShadow: '0 24px 70px rgba(0,0,0,.18)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0, flex: 1 }}>
                      <span style={{
                        width: 32, height: 32, borderRadius: 999, flexShrink: 0, fontSize: 11, fontWeight: 900,
                        color: '#111111', display: 'flex', alignItems: 'center', justifyContent: 'center',
                        background: 'linear-gradient(135deg,#EAB308,#EAB308)',
                      }}>
                        SIZ
                      </span>
                      <span style={{ minWidth: 0 }}>
                        <b className="land-ink" style={{ display: 'block', fontSize: 13, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                          {t('mock_you')}
                        </b>
                        <small style={{ color: '#FACC15', fontWeight: 700, fontSize: 9 }}>ELO 1180</small>
                      </span>
                    </div>
                    <b className="land-ink" style={{ fontSize: 14, flexShrink: 0 }}>3 : 2</b>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0, flex: 1, justifyContent: 'flex-end' }}>
                      <span style={{ minWidth: 0, textAlign: 'right' }}>
                        <b className="land-ink" style={{ display: 'block', fontSize: 13, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                          {t('mock_rival')}
                        </b>
                        <small style={{ color: '#EAB308', fontWeight: 700, fontSize: 9 }}>ELO 1195</small>
                      </span>
                      <span style={{
                        width: 32, height: 32, borderRadius: 999, flexShrink: 0, fontSize: 11, fontWeight: 900,
                        color: '#111111', display: 'flex', alignItems: 'center', justifyContent: 'center',
                        background: 'linear-gradient(135deg,#eab308,#a16207)',
                      }}>
                        AI
                      </span>
                    </div>
                  </div>
                  <div style={{
                    marginTop: 16, borderRadius: 16, padding: '12px 16px',
                    background: 'linear-gradient(135deg,rgba(250,204,21,.08),rgba(250,204,21,.06))',
                  }}>
                    <p style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.15em', color: '#EAB308' }}>{t('mock_q4')}</p>
                    <p className="land-ink" style={{ fontSize: 14, fontWeight: 700 }}>{t('mock_q_text')}</p>
                  </div>
                  <div style={{ marginTop: 12, display: 'grid', gap: 8 }}>
                    {[
                      [`A · ${t('mock_ans_a')}`, false],
                      [`B · ${t('mock_ans_b')}`, true],
                      [`C · ${t('mock_ans_c')}`, false],
                    ].map(([label, right]) => (
                      <div
                        key={String(label)}
                        className="land-ink"
                        style={{
                          display: 'flex', justifyContent: 'space-between', padding: '8px 14px',
                          borderRadius: 12, fontSize: 12, fontWeight: 600, border: '1px solid #2b2b2b',
                          ...(right
                            ? { color: '#111111', border: 'none', background: 'linear-gradient(135deg,#EAB308,#FACC15)' }
                            : {}),
                        }}
                      >
                        <span>{label}</span>
                        <span>{right ? '✓' : '✗'}</span>
                      </div>
                    ))}
                  </div>
                </div>
                <div className="float-badge glass-card" style={{
                  position: 'absolute', top: -20, left: -8, display: 'flex', alignItems: 'center',
                  gap: 8, padding: '8px 16px', borderRadius: 16, fontSize: 12, fontWeight: 700,
                }}>
                  <TrophyIcon size={14} /> {t('f_leaderboard')}
                </div>
                <div className="float-badge-2 glass-card" style={{
                  position: 'absolute', bottom: -20, right: 16, display: 'flex', alignItems: 'center',
                  gap: 8, padding: '8px 16px', borderRadius: 16, fontSize: 12, fontWeight: 700,
                }}>
                  <BotIcon size={14} /> {t('f_bot_15s')}
                </div>
              </div>
            </div>
          )}

          <div className="dots">
            {[0, 1, 2].map((i) => (
              <button key={i} aria-label={`Slide ${i + 1}`} className={`dot${slide === i ? ' on' : ''}`} onClick={() => setSlide(i)} />
            ))}
          </div>
        </div>
      </section>

      {/* FEATURES */}
      <section id="features" style={{ padding: '56px 0' }}>
        <div style={{ margin: '0 auto', maxWidth: 72 * 16, padding: '0 16px', width: '100%' }}>
          <div style={{ textAlign: 'center', maxWidth: 42 * 16, margin: '0 auto 40px' }}>
            <span style={{ fontSize: 11, fontWeight: 900, letterSpacing: '0.25em', color: '#EAB308' }}>
              {t('features_eyebrow')}
            </span>
            <h2 className="land-ink" style={{ marginTop: 12, fontSize: 'clamp(1.5rem,5vw,2.25rem)', fontWeight: 900 }}>
              {t('features_title_1')} <span className="hero-title-gradient">{t('features_title_2')}</span>{' '}
              {t('features_title_3')}
            </h2>
            <p className="land-muted" style={{ marginTop: 12 }}>{t('features_subtitle')}</p>
          </div>
          <div className="features-carousel">
            <DepthCarousel
              items={featureSlides}
              cardWidth={280}
              cardHeight={360}
              radius={24}
              spread={70}
              tilt={18}
              depth={220}
              visibleCards={3}
              autoplay
              autoplayDelay={3200}
            />
          </div>
        </div>
      </section>

      {/* STATS — live totals + showcase chart */}
      <section id="stats" style={{ padding: '28px 0' }}>
        <div style={{ margin: '0 auto', maxWidth: 72 * 16, padding: '0 16px', width: '100%' }}>
          {stats && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, justifyContent: 'center', marginBottom: 20 }}>
              {[
                [t('total_tests'), stats.totals.tests],
                [t('students'), stats.totals.students],
                [t('total_essays'), stats.totals.essays_graded],
              ].map(([label, value]) => (
                <div
                  key={String(label)}
                  className="glass-card"
                  style={{ borderRadius: 16, padding: '12px 24px', textAlign: 'center', minWidth: 140 }}
                >
                  <p className="land-ink" style={{ margin: 0, fontSize: 24, fontWeight: 900 }}>
                    {Number(value).toLocaleString()}
                  </p>
                  <p className="land-muted" style={{ margin: '4px 0 0', fontSize: 12, fontWeight: 600 }}>
                    {label}
                  </p>
                </div>
              ))}
            </div>
          )}
          <div style={{ marginTop: 8 }}>
            <p style={{ fontSize: 11, fontWeight: 900, letterSpacing: '0.25em', color: '#EAB308', margin: '0 0 8px', textAlign: 'center' }}>
              {t('an_platform_growth')}
            </p>
            <TrendChart data={trend} />
          </div>
        </div>
      </section>

      {/* HOW */}
      <section id="how" style={{ padding: '56px 0', background: '#070F0F', borderTop: '1px solid rgba(250,204,21,.1)', borderBottom: '1px solid rgba(250,204,21,.1)' }}>
        <div style={{ margin: '0 auto', maxWidth: 64 * 16, padding: '0 16px', width: '100%' }}>
          <div style={{ textAlign: 'center', maxWidth: 42 * 16, margin: '0 auto 40px' }}>
            <span style={{ fontSize: 11, fontWeight: 900, letterSpacing: '0.25em', color: '#EAB308' }}>
              {t('how_eyebrow')}
            </span>
            <h2 className="land-ink" style={{ marginTop: 12, fontSize: 'clamp(1.5rem,5vw,2.25rem)', fontWeight: 900 }}>
              {t('how_title_1')} <span className="hero-title-gradient">{t('how_title_2')}</span>
            </h2>
          </div>
          <div className="steps-grid">
            {[
              [t('step1_title'), t('step1_desc'), '#FACC15'],
              [t('step2_title'), t('step2_desc'), '#EAB308'],
              [t('step3_title'), t('step3_desc'), '#A16207'],
            ].map(([title, desc, c], i) => (
              <div key={i} style={{ textAlign: 'center' }}>
                <div style={{
                  width: 64, height: 64, borderRadius: 24, display: 'inline-flex', alignItems: 'center',
                  justifyContent: 'center', color: '#111111', fontSize: 20, fontWeight: 900, marginBottom: 16,
                  background: `linear-gradient(135deg, ${c}, ${c})`,
                }}>
                  {i + 1}
                </div>
                <h3 className="land-ink" style={{ fontSize: 18, fontWeight: 800, margin: '0 0 8px' }}>{title}</h3>
                <p className="land-muted" style={{ fontSize: 14, lineHeight: 1.6, maxWidth: 20 * 16, margin: '0 auto' }}>{desc}</p>
              </div>
            ))}
          </div>
          <div style={{ marginTop: 40, textAlign: 'center' }}>
            <Link to="/register" className="landing-cta btn-glow" style={{ padding: '14px 32px', fontSize: 16 }}>
              {t('cta_free_account')} →
            </Link>
          </div>
        </div>
      </section>

      {/* FOOTER */}
      <footer style={{ marginTop: 40 }}>
        <div style={{ height: 1, background: 'linear-gradient(90deg, rgba(250,204,21,.35), rgba(250,204,21,.12), transparent)' }} />
        <div className="land-foot-bg" style={{ position: 'relative', overflow: 'hidden' }}>
          <div style={{ margin: '0 auto', maxWidth: 72 * 16, padding: '64px 16px 40px', width: '100%', position: 'relative', zIndex: 1 }}>
            <div className="foot-grid">
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <img src="/grandec.png" alt="GRANDEC" className="brand-badge" style={{ width: 32, height: 32, padding: 0, objectFit: 'cover' }} />
                  <span style={{ lineHeight: 1.3 }}>
                    <b className="land-foot-ink" style={{ display: 'block', fontSize: 15 }}>GRANDEC</b>
                    <small style={{ fontSize: 9, fontWeight: 700, letterSpacing: '0.2em', color: '#EAB308' }}>LMS PLATFORM</small>
                  </span>
                </div>
                <p className="land-foot-muted" style={{ fontSize: 14, lineHeight: 1.7, marginTop: 16 }}>
                  {t('foot_mission')}
                </p>
              </div>
              <div>
                <h4 style={{ fontSize: 12, fontWeight: 900, letterSpacing: '0.2em', color: '#EAB308', margin: '0 0 20px' }}>
                  {t('foot_pages')}
                </h4>
                <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 12, fontSize: 14 }}>
                  {sectionNav.map(([k, href]) => (
                    <li key={k}>
                      <a href={href} className="footer-link land-foot-muted" style={{ textDecoration: 'none' }}>{t(k)}</a>
                    </li>
                  ))}
                  <li><a href="/login" className="footer-link land-foot-muted" style={{ textDecoration: 'none' }}>{t('login')}</a></li>
                  <li><a href="/register" className="footer-link land-foot-muted" style={{ textDecoration: 'none' }}>{t('register')}</a></li>
                </ul>
              </div>
              <div>
                <h4 style={{ fontSize: 12, fontWeight: 900, letterSpacing: '0.2em', color: '#EAB308', margin: '0 0 20px' }}>
                  {t('foot_news')}
                </h4>
                <p className="land-foot-muted" style={{ fontSize: 14, lineHeight: 1.7, margin: '0 0 16px' }}>
                  {t('foot_newsletter_desc')}
                </p>
                {newsDone ? (
                  <p style={{ fontSize: 14, fontWeight: 600, color: '#FACC15', margin: 0 }}>
                    {t('foot_subscribed_toast')}
                  </p>
                ) : (
                  <form className="news-form" onSubmit={subscribeNews}>
                    <input
                      type="email"
                      required
                      placeholder={t('foot_email_placeholder')}
                      value={newsEmail}
                      onChange={(e) => setNewsEmail(e.target.value)}
                      aria-label="Email"
                      style={{
                        flex: 1, minWidth: 0, padding: '12px 16px', borderRadius: 16,
                        fontSize: 14, background: '#0C1818', color: '#fff',
                        border: '1px solid #1A3333',
                      }}
                    />
                    <button type="submit" className="landing-cta btn-glow" style={{ flexShrink: 0, border: 'none', cursor: 'pointer' }}>
                      {t('foot_subscribe')}
                    </button>
                  </form>
                )}
                <p className="land-foot-muted" style={{ marginTop: 12, fontSize: 11 }}>
                  {t('foot_privacy_note')}
                </p>
              </div>
              <div>
                <h4 style={{ fontSize: 12, fontWeight: 900, letterSpacing: '0.2em', color: '#EAB308', margin: '0 0 20px' }}>
                  {t('foot_contact')}
                </h4>
                <ul className="land-foot-muted" style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 20, fontSize: 14 }}>
                  <li style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <span style={{
                      width: 36, height: 36, borderRadius: 12, display: 'flex', alignItems: 'center',
                      justifyContent: 'center', flexShrink: 0, color: '#FACC15', background: 'rgba(250,204,21,.08)',
                    }}>
                      <BotIcon size={17} />
                    </span>
                    <span style={{ minWidth: 0 }}>
                      <b className="land-foot-ink" style={{ display: 'block', fontSize: 14 }}>Telegram bot</b>
                      <a href="https://t.me/uz_essaygrader_bot" target="_blank" rel="noreferrer" style={{ color: '#FACC15', fontSize: 13 }}>
                        @uz_essaygrader_bot
                      </a>
                    </span>
                  </li>
                  <li style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <span style={{
                      width: 36, height: 36, borderRadius: 12, display: 'flex', alignItems: 'center',
                      justifyContent: 'center', flexShrink: 0, color: '#FACC15', background: 'rgba(250,204,21,.08)',
                    }}>
                      <ClockIcon size={17} />
                    </span>
                    <span style={{ minWidth: 0 }}>
                      <b className="land-foot-ink" style={{ display: 'block', fontSize: 14 }}>{t('foot_hours')}</b>
                      <span className="land-foot-muted" style={{ fontSize: 13 }}>{t('foot_hours_value')}</span>
                    </span>
                  </li>
                  <li style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <span style={{
                      width: 36, height: 36, borderRadius: 12, display: 'flex', alignItems: 'center',
                      justifyContent: 'center', flexShrink: 0, color: '#FACC15', background: 'rgba(250,204,21,.08)',
                    }}>
                      <MapPinIcon size={17} />
                    </span>
                    <span style={{ minWidth: 0 }}>
                      <b className="land-foot-ink" style={{ display: 'block', fontSize: 14 }}>{t('foot_online')}</b>
                      <span className="land-foot-muted" style={{ fontSize: 13 }}>{t('foot_online_value')}</span>
                    </span>
                  </li>
                </ul>
              </div>
            </div>
            <div className="land-foot-muted" style={{
              marginTop: 48, paddingTop: 24, borderTop: '1px solid rgba(255,255,255,.06)',
              display: 'flex', flexWrap: 'wrap', gap: '12px 24px', justifyContent: 'space-between',
              alignItems: 'center', fontSize: 12,
            }}>
              <div>
                <p style={{ margin: 0 }}>© 2026 GRANDEC · Barcha huquqlar himoyalangan.</p>
                <p style={{ margin: '6px 0 0', fontSize: 11, opacity: 0.7 }}>
                  {t('foot_website')} •{' '}
                  <a href="https://www.instagram.com/rozievkomiljon/" target="_blank" rel="noreferrer" style={{ color: '#EAB308', fontWeight: 600 }}>
                    Komiljon Roziyev
                  </a>{' '}
                  {t('foot_created_by')}
                </p>
              </div>
              <p style={{ margin: 0, display: 'flex', gap: 20, alignItems: 'center' }}>
                <a href="/login" className="footer-link land-foot-muted" style={{ textDecoration: 'none' }}>{t('foot_privacy')}</a>
                <a href="/login" className="footer-link land-foot-muted" style={{ textDecoration: 'none' }}>{t('foot_terms')}</a>
                <span style={{
                  display: 'inline-flex', alignItems: 'center', gap: 8, padding: '6px 14px',
                  borderRadius: 999, border: '1px solid rgba(250,204,21,.25)', fontSize: 11, fontWeight: 700,
                }}>
                  <span className="dot-mini" style={{ background: '#FACC15', margin: 0 }} /> {t('foot_healthy')}
                </span>
              </p>
            </div>
          </div>
          {/* Oversized watermark — purely decorative, cropped at the bottom edge */}
          <div
            aria-hidden="true"
            style={{
              userSelect: 'none',
              pointerEvents: 'none',
              width: '100%',
              overflow: 'hidden',
              textAlign: 'center',
              fontWeight: 900,
              textTransform: 'uppercase',
              fontFamily: "Inter, system-ui, -apple-system, 'Segoe UI', Roboto, Arial, sans-serif",
              letterSpacing: '-0.02em',
              lineHeight: 0.8,
              whiteSpace: 'nowrap',
              color: 'rgba(255,255,255,0.05)',
              fontSize: 'clamp(64px, 18.5vw, 260px)',
              marginTop: 8,
              marginBottom: '-0.22em',
              position: 'relative',
              zIndex: 0,
            }}
          >
            GRANDEC
          </div>
        </div>
      </footer>
    </div>
  );
}
