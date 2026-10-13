import { useEffect, useMemo, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { useLang } from '../i18n/LangContext';
import { School, landingFor } from '../lib/api';
import GooeyNav from '../components/GooeyNav';
import BlurText from '../components/BlurText';
import DepthCarousel from '../components/DepthCarousel';
import TrendChart from '../components/TrendChart';
import SEO from '../components/SEO';
import LanguageSwitcher from '../components/LanguageSwitcher';
import {
  AwardIcon,
  BotIcon,
  CheckIcon,
  ClockIcon,
  FileTextIcon,
  FlameIcon,
  GamepadIcon,
  LightbulbIcon,
  MapPinIcon,
  MenuIcon,
  PenLineIcon,
  SendIcon,
  ShieldCheckIcon,
  SwordsIcon,
  TrophyIcon,
  XIcon,
  ZapIcon,
} from '../components/icons';

// 12 BMB Milliy Sertifikat Essay Assessment Criteria
interface CriterionData {
  id: number;
  name: string;
  score: string;
  max: number;
  percent: number;
  desc: string;
  category: 'content' | 'grammar' | 'style';
}

const ESSAY_12_CRITERIA: CriterionData[] = [
  { id: 1, name: 'Mavzuning toʻliq ochib berilishi', score: '5 / 5', max: 5, percent: 100, desc: "Asosiy gʻoya va muammo teran ochilgan, mavzudan chetlanish yoʻq.", category: 'content' },
  { id: 2, name: 'Matn kompozitsiyasi va mantiqiy tuzilishi', score: '4.5 / 5', max: 5, percent: 90, desc: "Kirish, asosiy qism va xulosa oʻzaro mutanosib va mantiqan bogʻlangan.", category: 'content' },
  { id: 3, name: 'Fikrlarning dalillanishi va asosli iqtiboslar', score: '4.5 / 5', max: 5, percent: 90, desc: "Adabiy asarlar va hayotiy misollar oʻrinli keltirilgan.", category: 'content' },
  { id: 4, name: 'Grammatik qoidalar va sintaktik qurilmalar', score: '4.5 / 5', max: 5, percent: 90, desc: "Murakkab qoʻshma gaplar va soʻz birikmalari toʻgʻri shakllantirilgan.", category: 'grammar' },
  { id: 5, name: 'Orfografiya (imlo) qoidalariga rioya etish', score: '4 / 5', max: 5, percent: 80, desc: "1 ta noaniq imlo xatosi mavjud (yondosh -> yondash).", category: 'grammar' },
  { id: 6, name: 'Punktuatsiya va tinish belgilari', score: '3.5 / 5', max: 5, percent: 70, desc: "Ajratilgan boʻlaklarda va uyushiq boʻlaklarda vergul tushirib qoldirilgan.", category: 'grammar' },
  { id: 7, name: 'Uslubiy ravonlik va adabiy til meʼyorlari', score: '4 / 5', max: 5, percent: 80, desc: "Soʻz takroriga yoʻl qoʻyilmagan, uslubiy gʻalizliklar kuzatilmadi.", category: 'style' },
  { id: 8, name: 'Leksik boylik va sinonimlardan foydalanish', score: '4.5 / 5', max: 5, percent: 90, desc: "Badiiy tasvir vositalari va boy adabiy leksika qoʻllangan.", category: 'style' },
  { id: 9, name: 'Kirish qismining maqsadga muvofiqligi', score: '4.5 / 5', max: 5, percent: 90, desc: "Mavzuga jalb qiluvchi kuchli tezis bilan boshlangan.", category: 'content' },
  { id: 10, name: 'Xulosa va mustaqil dunyoqarash', score: '5 / 5', max: 5, percent: 100, desc: "Muallifning shaxsiy nuqtayi nazari va qatʼiy xulosasi yoritilgan.", category: 'content' },
  { id: 11, name: 'Abzaslararo mantiqiy oʻtishlar', score: '4 / 5', max: 5, percent: 80, desc: "Fikrlar oqimi ravon va keyingi fikrga silliq ulanadi.", category: 'style' },
  { id: 12, name: 'Matn hajmi va meʼyoriy koʻlam', score: '5 / 5', max: 5, percent: 100, desc: "Belgilangan 250-300 soʻz talabiga toʻliq mos (278 soʻz).", category: 'style' },
];

// Interactive Arena Questions
interface ArenaSampleQuestion {
  id: number;
  question: string;
  options: { key: string; text: string; correct: boolean }[];
  explanation: string;
}

const ARENA_QUESTIONS: ArenaSampleQuestion[] = [
  {
    id: 1,
    question: "Alisher Navoiyning 'Xamsa' tarkibiga kirmaydigan dostonini aniqlang:",
    options: [
      { key: 'A', text: "Hayrat ul-abror", correct: false },
      { key: 'B', text: "Farhod va Shirin", correct: false },
      { key: 'C', text: "Lison ut-tayr", correct: true },
      { key: 'D', text: "Saddi Iskandariy", correct: false },
    ],
    explanation: "'Lison ut-tayr' Navoiyning alohida falsafiy dostoni boʻlib, 'Xamsa' beshligiga kirmaydi.",
  },
  {
    id: 2,
    question: "Qaysi gapda tinish belgisi bilan bogʻliq xatolikka yoʻl qoʻyilgan?",
    options: [
      { key: 'A', text: "Kitob — bilim bulogʻi.", correct: false },
      { key: 'B', text: "U yetib keldi va, darhol ishga kirishdi.", correct: true },
      { key: 'C', text: "Bahor kelgach, tabiat uygʻondi.", correct: false },
      { key: 'D', text: "Azizlarim, darsimizni boshlaymiz!", correct: false },
    ],
    explanation: "Teng bogʻlovchi 'va' dan soʻng hech qachon vergul qoʻyilmaydi.",
  },
  {
    id: 3,
    question: "Oʻzbek tilida urgʻu olmaydigan qoʻshimchani belgilang:",
    options: [
      { key: 'A', text: "-chi (yuklama)", correct: true },
      { key: 'B', text: "-kor (shaxs oti yasovchi)", correct: false },
      { key: 'C', text: "-dosh (ot yasovchi)", correct: false },
      { key: 'D', text: "-ona (ravish yasovchi)", correct: false },
    ],
    explanation: "-chi yuklamasi urgʻu olmaydi, undan oldingi boʻgʻin urgʻu oladi.",
  },
];

export default function Landing() {
  const { t } = useLang();
  const { user } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [slide, setSlide] = useState(0);

  // Logged-in visitors go straight to their home
  const startTo = user ? landingFor(user) : '/register';
  const initials = (user?.full_name || '?')
    .split(' ')
    .map((p) => p[0])
    .join('')
    .slice(0, 2)
    .toUpperCase() || '?';

  // Live platform totals (GET /api/v1/school/public-stats/, AllowAny)
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
        /* offline fallback */
      });
    return () => {
      live = false;
    };
  }, []);

  // Lock body scroll when mobile drawer is open
  useEffect(() => {
    if (mobileOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [mobileOpen]);

  // Close mobile drawer on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setMobileOpen(false);
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Newsletter subscription
  const [newsEmail, setNewsEmail] = useState('');
  const [newsDone, setNewsDone] = useState(false);
  const subscribeNews = (e: FormEvent) => {
    e.preventDefault();
    if (newsEmail.trim()) {
      setNewsEmail('');
      setNewsDone(true);
    }
  };

  // Advertising showcase: 12-month platform growth
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

  // Section navigation
  const sectionNav: [string, string][] = [
    ['nav_programs', '#carousel'],
    ['nav_features', '#features'],
    ['nav_stats', '#stats'],
    ['nav_how', '#how'],
  ];
  const navRef = useRef<HTMLElement | null>(null);

  // Auto-advance slides every 8s
  useEffect(() => {
    const id = setInterval(() => setSlide((s) => (s + 1) % 3), 8000);
    return () => clearInterval(id);
  }, []);

  // Continuous scroll-driven navbar for desktop
  useEffect(() => {
    const SHRINK_DISTANCE = 120;
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

  // --- Interactive Essay State ---
  const [selectedCriterion, setSelectedCriterion] = useState<CriterionData>(ESSAY_12_CRITERIA[0]);
  const [showAllCriteria, setShowAllCriteria] = useState(false);

  // --- Interactive Arena Simulation State ---
  const [arenaQuestionIdx, setArenaQuestionIdx] = useState(0);
  const [userSelectedOption, setUserSelectedOption] = useState<string | null>(null);
  const [arenaUserScore, setArenaUserScore] = useState(3);
  const [arenaAiScore, setArenaAiScore] = useState(2);
  const [arenaUserElo, setArenaUserElo] = useState(1180);
  const [arenaAiThinking, setArenaAiThinking] = useState(false);
  const [arenaAnswered, setArenaAnswered] = useState(false);

  const currentArenaQ = ARENA_QUESTIONS[arenaQuestionIdx];

  const handleArenaAnswer = (optionKey: string) => {
    if (arenaAnswered) return;
    setUserSelectedOption(optionKey);
    setArenaAnswered(true);
    setArenaAiThinking(true);

    const isCorrect = currentArenaQ.options.find((o) => o.key === optionKey)?.correct ?? false;
    if (isCorrect) {
      setArenaUserScore((s) => s + 1);
      setArenaUserElo((e) => e + 15);
    } else {
      setArenaAiScore((s) => s + 1);
    }

    setTimeout(() => {
      setArenaAiThinking(false);
    }, 700);
  };

  const handleNextArenaQuestion = () => {
    setUserSelectedOption(null);
    setArenaAnswered(false);
    setArenaAiThinking(false);
    setArenaQuestionIdx((idx) => (idx + 1) % ARENA_QUESTIONS.length);
  };

  // Feature slides for 3D DepthCarousel
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
      features.map((f, i) => ({
        content: (
          <div className="feat-slide" key={i}>
            <div
              style={{
                width: 52,
                height: 52,
                borderRadius: 16,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                marginBottom: 20,
                background: 'rgba(245, 158, 11, 0.12)',
                border: '1px solid rgba(245, 158, 11, 0.25)',
                color: '#F59E0B',
                flexShrink: 0,
                boxShadow: '0 0 20px rgba(245, 158, 11, 0.15)',
              }}
            >
              <f.Icon size={26} />
            </div>
            <h3 className="land-ink" style={{ fontSize: 20, fontWeight: 800, margin: '0 0 10px' }}>
              {f.title}
            </h3>
            <p className="land-muted" style={{ fontSize: 14, lineHeight: 1.7, margin: 0, flex: 1 }}>
              {f.desc}
            </p>
          </div>
        ),
      })),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [t],
  );

  // SEO JSON-LD Schemas
  const jsonLdData = useMemo(
    () => [
      {
        '@context': 'https://schema.org',
        '@type': 'EducationalOrganization',
        name: 'GRANDEC LMS',
        url: 'https://grandec.uz',
        logo: 'https://grandec.uz/grandec.png',
        description: "Ona tili va adabiyoti bo'yicha Milliy sertifikatga tayyorlovchi zamonaviy LMS va AI Esse platformasi.",
        sameAs: ['https://t.me/uz_essaygrader_bot'],
      },
      {
        '@context': 'https://schema.org',
        '@type': 'SoftwareApplication',
        name: 'GRANDEC',
        applicationCategory: 'EducationalApplication',
        operatingSystem: 'Web, Telegram TMA',
        offers: {
          '@type': 'Offer',
          price: '0',
          priceCurrency: 'UZS',
        },
      },
      {
        '@context': 'https://schema.org',
        '@type': 'FAQPage',
        mainEntity: [
          {
            '@type': 'Question',
            name: "Ona tili va adabiyotidan Milliy sertifikat nima?",
            acceptedAnswer: {
              '@type': 'Answer',
              text: "Milliy sertifikat — Bilim va malakalarni baholash agentligi (BMB) tomonidan beriladigan, abituriyentlarga OTM kirish imtihonlarida maksimal ball beruvchi rasmiy davlat hujjati.",
            },
          },
          {
            '@context': 'https://schema.org',
            '@type': 'Question',
            name: "AI Esse tekshiruvi qanday ishlaydi?",
            acceptedAnswer: {
              '@type': 'Answer',
              text: "Platformamizdagi sun'iy intellekt BMB ning rasmiy 12 ta baholash mezoni asosida inshoni 15 soniya ichida tahlil qilib, xatolar va ball bo'yicha batafsil tavsiyalar beradi.",
            },
          },
          {
            '@context': 'https://schema.org',
            '@type': 'Question',
            name: "1v1 Arena nima?",
            acceptedAnswer: {
              '@type': 'Answer',
              text: "1v1 Arena — ona tili va adabiyot bo'yicha boshqa o'quvchilar yoki AI bot bilan real vaqtda ELO reytingi uchun bilim bellashuvi.",
            },
          },
        ],
      },
    ],
    [],
  );

  return (
    <div className="landing" style={{ background: 'var(--bg)', minHeight: '100svh' }}>
      <SEO
        title="Ona tili va adabiyot LMS | Milliy sertifikat & AI Esse"
        description="Ona tili va adabiyoti bo'yicha Milliy sertifikatga tayyorlovchi zamonaviy LMS platformasi va AI Esse tahlil tizimi. 1v1 Arena, interaktiv testlar va rasmiy BMB mezonlari."
        canonical="/"
        jsonLd={jsonLdData}
      />

      <style>{`
        .landing-nav {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          z-index: 50;
          width: 100%;
          overflow-x: clip;
        }
        .landing-nav-bar {
          width: 100%;
          border-radius: 0;
          background: rgba(9, 13, 22, 0.85);
          backdrop-filter: blur(16px);
          -webkit-backdrop-filter: blur(16px);
          border-bottom: 1px solid rgba(148, 163, 184, 0.12);
        }
        .landing-nav-inner {
          margin: 0 auto;
          width: 100%;
          max-width: 72rem;
          padding: 0 1rem;
          height: 4.25rem;
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 0.75rem;
        }
        @media (min-width: 640px) { .landing-nav-inner { padding: 0 1.5rem; } }
        @media (min-width: 1024px) { .landing-nav-inner { padding: 0 2rem; } }
        
        .landing-links { display: none; }
        @media (min-width: 1024px) {
          .landing-links {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-size: 14px;
            font-weight: 600;
          }
        }
        
        .landing-cta {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          gap: 6px;
          min-height: 44px;
          padding: 10px 18px;
          font-size: 14px;
          font-weight: 700;
          color: #090d16;
          border-radius: 12px;
          text-decoration: none;
          white-space: nowrap;
          background: linear-gradient(135deg, #F59E0B, #FBBF24);
          box-shadow: 0 4px 18px rgba(245, 158, 11, 0.35);
          border: none;
          cursor: pointer;
        }
        .landing-cta:hover {
          background: linear-gradient(135deg, #FBBF24, #F59E0B);
          box-shadow: 0 6px 22px rgba(245, 158, 11, 0.45);
        }
        
        .landing-login {
          display: none;
          align-items: center;
          justify-content: center;
          min-height: 44px;
          font-size: 14px;
          font-weight: 600;
          padding: 10px 16px;
          border-radius: 12px;
          text-decoration: none;
          color: #94a3b8;
          transition: color 0.2s ease;
        }
        .landing-login:hover { color: #f8fafc; }
        @media (min-width: 640px) { .landing-login { display: inline-flex; } }
        
        .landing-burger {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          width: 44px;
          height: 44px;
          padding: 10px;
          border-radius: 12px;
          border: 1px solid rgba(148, 163, 184, 0.16);
          background: rgba(30, 41, 59, 0.5);
          cursor: pointer;
          color: #f8fafc;
          transition: background 0.2s ease;
        }
        .landing-burger:hover { background: rgba(30, 41, 59, 0.9); }
        @media (min-width: 1024px) { .landing-burger { display: none; } }
        
        /* Continuous scroll transformation (≥768px) */
        @media (min-width: 768px) {
          .landing-nav-bar {
            margin: calc(var(--nav-p, 0) * 10px) auto 0;
            width: calc(100% - var(--nav-p, 0) * clamp(0px, 6vw, 96px));
            border-radius: calc(var(--nav-p, 0) * 20px);
            border-left: 1px solid rgba(148, 163, 184, calc(var(--nav-p, 0) * 0.14));
            border-right: 1px solid rgba(148, 163, 184, calc(var(--nav-p, 0) * 0.14));
            box-shadow: 0 calc(var(--nav-p, 0) * 12px) calc(var(--nav-p, 0) * 36px) rgba(0, 0, 0, calc(var(--nav-p, 0) * 0.5));
          }
          .landing-nav-inner { height: calc(4.25rem - var(--nav-p, 0) * 0.5rem); }
        }
        
        /* Mobile Drawer */
        .drawer-overlay {
          position: fixed;
          inset: 0;
          z-index: 90;
          background: rgba(4, 7, 13, 0.75);
          backdrop-filter: blur(8px);
          -webkit-backdrop-filter: blur(8px);
          animation: fadeIn 0.25s ease;
        }
        .drawer-content {
          position: fixed;
          top: 0;
          right: 0;
          bottom: 0;
          width: 85%;
          max-width: 340px;
          z-index: 100;
          background: #0f172a;
          border-left: 1px solid rgba(148, 163, 184, 0.15);
          box-shadow: -10px 0 40px rgba(0, 0, 0, 0.8);
          display: flex;
          flex-direction: column;
          padding: 1.5rem;
          animation: slideInRight 0.3s cubic-bezier(0.16, 1, 0.3, 1);
        }
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
        @keyframes slideInRight { from { transform: translateX(100%); } to { transform: translateX(0); } }

        .drawer-link {
          display: flex;
          align-items: center;
          min-height: 48px;
          padding: 0.75rem 1rem;
          border-radius: 12px;
          font-size: 15px;
          font-weight: 600;
          color: #94a3b8;
          text-decoration: none;
          transition: all 0.2s ease;
        }
        .drawer-link:hover, .drawer-link:focus-visible {
          background: rgba(245, 158, 11, 0.12);
          color: #F59E0B;
        }

        /* Typography & Layout */
        .hero-h1 {
          font-size: clamp(2.25rem, 6vw, 3.75rem);
          line-height: 1.08;
          font-weight: 900;
          letter-spacing: -0.03em;
        }
        .grad-word {
          background: linear-gradient(135deg, #fef3c7 0%, #f59e0b 50%, #d97706 100%);
          -webkit-background-clip: text;
          background-clip: text;
          color: transparent;
        }
        .slide-h2 {
          font-size: clamp(1.75rem, 4vw, 2.35rem);
          line-height: 1.18;
          font-weight: 800;
          letter-spacing: -0.02em;
        }
        .slide-grid {
          display: grid;
          grid-template-columns: 1fr;
          gap: 2.25rem;
          align-items: center;
        }
        @media (min-width: 1024px) {
          .slide-grid {
            grid-template-columns: 1.05fr 0.95fr;
            gap: 3.5rem;
          }
        }
        .cta-row {
          display: flex;
          flex-direction: column;
          gap: 0.85rem;
          margin-top: 1.75rem;
        }
        @media (min-width: 480px) {
          .cta-row {
            flex-direction: row;
            flex-wrap: wrap;
            align-items: center;
          }
        }
        .ghost-cta {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          gap: 8px;
          min-height: 44px;
          padding: 12px 24px;
          font-size: 14px;
          font-weight: 700;
          border-radius: 14px;
          text-decoration: none;
          border: 1px solid rgba(148, 163, 184, 0.2);
          background: rgba(30, 41, 59, 0.4);
          color: #94a3b8;
          transition: all 0.2s ease;
        }
        .ghost-cta:hover {
          background: rgba(30, 41, 59, 0.8);
          color: #f8fafc;
          border-color: rgba(245, 158, 11, 0.4);
        }
        .dots {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 0.75rem;
          margin-top: 2rem;
        }
        .dot {
          width: 10px;
          height: 10px;
          min-width: 44px;
          min-height: 44px;
          border-radius: 999px;
          border: none;
          background: transparent;
          cursor: pointer;
          padding: 0;
          display: flex;
          align-items: center;
          justify-content: center;
        }
        .dot-inner {
          width: 9px;
          height: 9px;
          border-radius: 999px;
          background: rgba(148, 163, 184, 0.35);
          transition: all 0.3s ease;
        }
        .dot.on .dot-inner {
          width: 28px;
          background: linear-gradient(90deg, #F59E0B, #FBBF24);
          box-shadow: 0 0 12px rgba(245, 158, 11, 0.7);
        }
        .features-carousel {
          height: 480px;
        }
        @media (min-width: 640px) {
          .features-carousel {
            height: 510px;
          }
        }
        .feat-slide {
          height: 100%;
          padding: 30px 26px;
          display: flex;
          flex-direction: column;
        }
        .steps-grid {
          display: grid;
          grid-template-columns: 1fr;
          gap: 1.5rem;
        }
        @media (min-width: 768px) {
          .steps-grid {
            grid-template-columns: 1fr 1fr 1fr;
          }
        }
        .foot-grid {
          display: grid;
          grid-template-columns: 1fr;
          gap: 2.5rem;
        }
        @media (min-width: 768px) {
          .foot-grid {
            grid-template-columns: 1fr 1fr;
          }
        }
        @media (min-width: 1024px) {
          .foot-grid {
            grid-template-columns: repeat(4, 1fr);
          }
        }
        .news-form {
          display: flex;
          flex-direction: column;
          gap: 0.6rem;
        }
        @media (min-width: 420px) {
          .news-form {
            flex-direction: row;
          }
        }

        /* Micro-interaction option button */
        .interactive-opt-btn {
          display: flex;
          align-items: center;
          justify-content: space-between;
          width: 100%;
          min-height: 44px;
          padding: 10px 14px;
          border-radius: 12px;
          font-size: 13px;
          font-weight: 600;
          border: 1px solid rgba(148, 163, 184, 0.16);
          background: rgba(15, 23, 42, 0.7);
          color: #f8fafc;
          cursor: pointer;
          text-align: left;
          transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
        }
        .interactive-opt-btn:hover:not(:disabled) {
          border-color: rgba(245, 158, 11, 0.4);
          background: rgba(30, 41, 59, 0.6);
          transform: translateX(2px);
        }
        .interactive-opt-btn.is-correct {
          background: rgba(16, 185, 129, 0.2);
          border-color: #10B981;
          color: #34D399;
          box-shadow: 0 0 16px rgba(16, 185, 129, 0.2);
        }
        .interactive-opt-btn.is-wrong {
          background: rgba(244, 63, 94, 0.2);
          border-color: #F43F5E;
          color: #FB7185;
          box-shadow: 0 0 16px rgba(244, 63, 94, 0.2);
        }
      `}</style>

      {/* NAVBAR */}
      <nav ref={navRef} className="landing-nav" aria-label="Asosiy navigatsiya">
        <div className="landing-nav-bar">
          <div className="landing-nav-inner">
            <Link
              to="/"
              style={{ display: 'flex', alignItems: 'center', gap: 10, textDecoration: 'none', minWidth: 0 }}
              aria-label="GRANDEC LMS Bosh sahifasi"
            >
              <span style={{ position: 'relative', flexShrink: 0 }}>
                <img
                  src="/grandec.png"
                  alt="GRANDEC"
                  className="brand-badge"
                  style={{ width: 34, height: 34, padding: 0, objectFit: 'cover' }}
                />
              </span>
              <span style={{ lineHeight: 1.2, minWidth: 0 }}>
                <span
                  className="land-ink"
                  style={{
                    display: 'block',
                    fontSize: 16,
                    fontWeight: 800,
                    letterSpacing: '-0.01em',
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                  }}
                >
                  GRANDEC
                </span>
                <span style={{ display: 'block', fontSize: 9, fontWeight: 700, letterSpacing: '0.22em', color: '#F59E0B' }}>
                  LMS PLATFORM
                </span>
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

            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
              <LanguageSwitcher />

              {user ? (
                <Link
                  to={startTo}
                  className="landing-cta btn-glow"
                  title={user.full_name}
                  style={{ padding: '8px 14px 8px 8px', gap: 8 }}
                >
                  <span
                    aria-hidden="true"
                    style={{
                      width: 28,
                      height: 28,
                      borderRadius: 999,
                      flexShrink: 0,
                      fontSize: 11,
                      fontWeight: 900,
                      color: '#090d16',
                      display: 'inline-flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      background: 'rgba(9, 13, 22, 0.18)',
                    }}
                  >
                    {initials}
                  </span>
                  <span style={{ maxWidth: 120, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {user.full_name}
                  </span>
                </Link>
              ) : (
                <>
                  <Link to="/login" className="landing-login">
                    {t('login')}
                  </Link>
                  <Link to="/register" className="landing-cta btn-glow">
                    {t('start_free')}
                    <svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5" aria-hidden="true">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
                    </svg>
                  </Link>
                </>
              )}

              <button
                type="button"
                className="landing-burger"
                aria-label={mobileOpen ? "Menyuni yopish" : "Asosiy menyuni ochish"}
                aria-expanded={mobileOpen}
                onClick={() => setMobileOpen((v) => !v)}
              >
                {mobileOpen ? <XIcon size={22} /> : <MenuIcon size={22} />}
              </button>
            </div>
          </div>
        </div>
      </nav>

      {/* MOBILE DRAWER */}
      {mobileOpen && (
        <>
          <div
            className="drawer-overlay"
            onClick={() => setMobileOpen(false)}
            aria-hidden="true"
          />
          <div
            className="drawer-content"
            role="dialog"
            aria-modal="true"
            aria-label="Mobil navigatsiya menyusi"
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.5rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <img src="/grandec.png" alt="GRANDEC" style={{ width: 32, height: 32, objectFit: 'cover' }} />
                <span style={{ fontWeight: 800, fontSize: 16, color: '#f8fafc' }}>GRANDEC LMS</span>
              </div>
              <button
                type="button"
                className="landing-burger"
                aria-label="Menyuni yopish"
                onClick={() => setMobileOpen(false)}
              >
                <XIcon size={20} />
              </button>
            </div>

            <nav style={{ display: 'flex', flexDirection: 'column', gap: 6, flex: 1 }}>
              {sectionNav.map(([k, href]) => (
                <a
                  key={k}
                  href={href}
                  className="drawer-link"
                  onClick={() => setMobileOpen(false)}
                >
                  {t(k)}
                </a>
              ))}
            </nav>

            <div style={{ borderTop: '1px solid rgba(148, 163, 184, 0.15)', paddingTop: '1.25rem', display: 'flex', flexDirection: 'column', gap: 10 }}>
              {user ? (
                <Link
                  to={startTo}
                  className="landing-cta btn-glow"
                  onClick={() => setMobileOpen(false)}
                >
                  {user.full_name} →
                </Link>
              ) : (
                <>
                  <Link
                    to="/login"
                    className="ghost-cta"
                    onClick={() => setMobileOpen(false)}
                  >
                    {t('login')}
                  </Link>
                  <Link
                    to="/register"
                    className="landing-cta btn-glow"
                    onClick={() => setMobileOpen(false)}
                  >
                    {t('start_free')} →
                  </Link>
                </>
              )}
            </div>
          </div>
        </>
      )}

      {/* HERO SECTION */}
      <main id="main-content">
        <section id="carousel" style={{ position: 'relative', paddingTop: 76, overflow: 'hidden' }}>
          <div style={{ position: 'absolute', inset: 0 }} aria-hidden="true">
            <div className="hero-grid-bg" />
            <div className="hero-orb" style={{ width: 520, height: 520, background: '#F59E0B', top: -180, left: -100 }} />
            <div className="hero-orb" style={{ width: 440, height: 440, background: '#10B981', top: 60, right: -120 }} />
            <span className="float-letter f-dance" style={{ fontSize: 160, top: 56, left: '4%' }}>Oʻ</span>
            <span className="float-letter f-dance-2" style={{ fontSize: 130, top: 96, right: '6%' }}>A</span>
          </div>

          <div style={{ position: 'relative', margin: '0 auto', maxWidth: 72 * 16, padding: '36px 16px 20px', width: '100%' }}>
            {/* Eyebrow */}
            <div className="reveal in" style={{ textAlign: 'center', marginBottom: 28 }}>
              <span
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '6px 18px',
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
                {t('land_eyebrow')}
              </span>
            </div>

            {/* Main Headline */}
            <div style={{ textAlign: 'center', maxWidth: 58 * 16, margin: '0 auto 44px' }}>
              <h1 className="hero-h1 land-ink">
                <BlurText text={t('hero_title_1')} delay={60} as="span" style={{ justifyContent: 'center' }} />{' '}
                <BlurText
                  text={t('hero_title_2')}
                  delay={80}
                  as="span"
                  style={{ display: 'inline', textAlign: 'center' }}
                  wordClassName="grad-word"
                />
              </h1>
              <p
                className="land-muted"
                style={{ marginTop: 18, fontSize: 'clamp(1rem, 2vw, 1.15rem)', lineHeight: 1.7, textWrap: 'balance' }}
              >
                {t('land_subhead_1')} <b style={{ color: '#F59E0B' }}>{t('land_subhead_b1')}</b>{' '}
                {t('land_subhead_2')} <b style={{ color: '#10B981' }}>{t('land_subhead_b2')}</b>{' '}
                {t('land_subhead_3')}
              </p>
            </div>

            {/* Slide 0: Milliy Sertifikat Test Simulyatori */}
            {slide === 0 && (
              <div className="slide-grid">
                <div>
                  <span
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 8,
                      padding: '5px 14px',
                      borderRadius: 999,
                      fontSize: 11,
                      fontWeight: 700,
                      letterSpacing: '0.1em',
                      textTransform: 'uppercase',
                      background: 'rgba(245, 158, 11, 0.12)',
                      color: '#F59E0B',
                      border: '1px solid rgba(245, 158, 11, 0.28)',
                    }}
                  >
                    <ShieldCheckIcon size={14} /> {t('slide1_badge')}
                  </span>
                  <h2 className="slide-h2 land-ink" style={{ marginTop: 18 }}>
                    {t('slide1_h2_1')}
                    <br />
                    <span className="hero-title-gradient">{t('slide1_h2_2')}</span>
                  </h2>
                  <p className="land-muted" style={{ marginTop: 16, lineHeight: 1.7, maxWidth: 30 * 16 }}>
                    {t('slide1_p')}
                  </p>
                  <div className="cta-row">
                    <Link to={startTo} className="landing-cta btn-glow" style={{ padding: '12px 28px' }}>
                      {t('cta_start_course')} →
                    </Link>
                    <a href="#features" className="ghost-cta">
                      {t('cta_demo')}
                    </a>
                  </div>
                  <div
                    className="land-muted"
                    style={{ marginTop: 24, display: 'flex', flexWrap: 'wrap', gap: '8px 24px', fontSize: 13 }}
                  >
                    <span>
                      <span className="dot-mini" style={{ background: '#F59E0B' }} /> {t('meta_qbank')}
                    </span>
                    <span>
                      <span className="dot-mini" style={{ background: '#10B981' }} /> {t('meta_criteria')}
                    </span>
                    <span>
                      <span className="dot-mini" style={{ background: '#8B5CF6' }} /> {t('meta_cert')}
                    </span>
                  </div>
                </div>

                <div style={{ position: 'relative', minWidth: 0 }}>
                  <div className="lcard" style={{ borderRadius: 24, padding: 24 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <p style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.18em', color: '#F59E0B', margin: 0 }}>
                        {t('slide1_badge')}
                      </p>
                      <span style={{ fontSize: 11, fontWeight: 700, color: '#10B981', display: 'flex', alignItems: 'center', gap: 4 }}>
                        <CheckIcon size={14} /> BMB Standart
                      </span>
                    </div>
                    <p className="land-ink" style={{ fontSize: 16, fontWeight: 800, marginTop: 6, marginBottom: 16 }}>
                      {t('mock_sample_test')}
                    </p>

                    {[
                      [t('mock_read'), '8 / 10 ✓', 80, '#10B981'],
                      ['Grammatika va Morfologiya', '14 / 15 ✓', 93, '#F59E0B'],
                      [t('mock_lit'), '9 / 15', 60, '#38BDF8'],
                    ].map(([label, val, w, c]) => (
                      <div key={String(label)} style={{ marginTop: 14 }}>
                        <div
                          style={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            fontSize: 13,
                            fontWeight: 600,
                            color: '#e2e8f0',
                          }}
                        >
                          <span>{label}</span>
                          <span style={{ color: String(c), fontWeight: 700 }}>{val}</span>
                        </div>
                        <div style={{ height: 8, borderRadius: 999, background: 'rgba(30, 41, 59, 0.7)', marginTop: 6 }}>
                          <div
                            style={{
                              height: 8,
                              borderRadius: 999,
                              width: `${w}%`,
                              background: `linear-gradient(90deg, ${c}, ${c})`,
                              boxShadow: `0 0 10px ${c}55`,
                            }}
                          />
                        </div>
                      </div>
                    ))}

                    <div
                      style={{
                        marginTop: 22,
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        borderRadius: 16,
                        padding: '14px 18px',
                        background: 'linear-gradient(135deg, rgba(245, 158, 11, 0.12), rgba(16, 185, 129, 0.08))',
                        border: '1px solid rgba(245, 158, 11, 0.2)',
                      }}
                    >
                      <div>
                        <p style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.15em', color: '#F59E0B', margin: 0 }}>
                          {t('mock_score')}
                        </p>
                        <p className="land-ink" style={{ fontSize: 26, fontWeight: 900, margin: 0 }}>
                          78.3<span style={{ fontSize: 15, color: '#F59E0B' }}>%</span>
                        </p>
                      </div>
                      <span
                        style={{
                          padding: '6px 14px',
                          borderRadius: 12,
                          fontSize: 12,
                          fontWeight: 800,
                          color: '#090d16',
                          background: 'linear-gradient(135deg, #10B981, #34D399)',
                          boxShadow: '0 4px 14px rgba(16, 185, 129, 0.35)',
                        }}
                      >
                        A daraja · {t('mock_passed')}
                      </span>
                    </div>
                  </div>

                  <div
                    className="float-badge glass-card"
                    style={{
                      position: 'absolute',
                      top: -18,
                      left: -8,
                      display: 'flex',
                      alignItems: 'center',
                      gap: 8,
                      padding: '8px 16px',
                      borderRadius: 16,
                      fontSize: 12,
                      fontWeight: 700,
                      color: '#f8fafc',
                    }}
                  >
                    <AwardIcon size={16} /> {t('badge_exam_mode')}
                  </div>
                  <div
                    className="float-badge-2 glass-card"
                    style={{
                      position: 'absolute',
                      bottom: -18,
                      right: 14,
                      display: 'flex',
                      alignItems: 'center',
                      gap: 8,
                      padding: '8px 16px',
                      borderRadius: 16,
                      fontSize: 12,
                      fontWeight: 700,
                      color: '#f8fafc',
                    }}
                  >
                    <ClockIcon size={16} /> {t('badge_time')}
                  </div>
                </div>
              </div>
            )}

            {/* Slide 1: AI Esse — 12 Mezonli Baholash (Interactive Micro-Interaction) */}
            {slide === 1 && (
              <div className="slide-grid">
                <div>
                  <span
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 8,
                      padding: '5px 14px',
                      borderRadius: 999,
                      fontSize: 11,
                      fontWeight: 700,
                      letterSpacing: '0.1em',
                      textTransform: 'uppercase',
                      background: 'rgba(245, 158, 11, 0.12)',
                      color: '#F59E0B',
                      border: '1px solid rgba(245, 158, 11, 0.28)',
                    }}
                  >
                    <ZapIcon size={14} /> AI Esse · 12 Mezonli Tahlil
                  </span>
                  <h2 className="slide-h2 land-ink" style={{ marginTop: 18 }}>
                    {t('slide2_h2_1')}
                    <br />
                    <span className="hero-title-gradient">{t('slide2_h2_2')}</span>
                  </h2>
                  <p className="land-muted" style={{ marginTop: 16, lineHeight: 1.7, maxWidth: 30 * 16 }}>
                    {t('slide2_p')} Oʻquvchi insho yozganda BMB Davlat taʼlim standartlaridagi barcha 12 ta mezon boʻyicha bir necha soniyada batafsil tahlil va tavsiyalarga ega boʻladi.
                  </p>
                  <div className="cta-row">
                    <Link to={startTo} className="landing-cta btn-glow" style={{ padding: '12px 28px' }}>
                      {t('cta_write_essay')} →
                    </Link>
                    <button
                      type="button"
                      className="ghost-cta"
                      onClick={() => setShowAllCriteria((v) => !v)}
                      aria-label="12 mezonni to'liq ko'rish"
                    >
                      {showAllCriteria ? "Asosiy mezonlar" : "Barcha 12 mezon →"}
                    </button>
                  </div>
                </div>

                <div style={{ position: 'relative', minWidth: 0 }}>
                  <div className="lcard" style={{ borderRadius: 24, padding: 22 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <p style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.16em', color: '#F59E0B', margin: 0 }}>
                        {t('mock_ai_result')}
                      </p>
                      <span
                        style={{
                          fontSize: 11,
                          fontWeight: 700,
                          color: '#10B981',
                          background: 'rgba(16, 185, 129, 0.12)',
                          padding: '3px 8px',
                          borderRadius: 6,
                        }}
                      >
                        12 Mezon Faol
                      </span>
                    </div>
                    <p className="land-ink" style={{ fontSize: 15, fontWeight: 800, marginTop: 4, marginBottom: 14 }}>
                      {t('mock_essay_title')}
                    </p>

                    {/* Overall score indicator */}
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 16,
                        padding: '12px 16px',
                        borderRadius: 16,
                        background: 'rgba(30, 41, 59, 0.5)',
                        border: '1px solid rgba(148, 163, 184, 0.12)',
                        marginBottom: 16,
                      }}
                    >
                      <div style={{ textAlign: 'center' }}>
                        <p className="land-ink" style={{ fontSize: 28, fontWeight: 900, margin: 0, color: '#F59E0B' }}>
                          54.5
                        </p>
                        <p className="land-muted" style={{ fontSize: 10, fontWeight: 700, margin: 0 }}>
                          60 ballik tizim
                        </p>
                      </div>
                      <div style={{ flex: 1, borderLeft: '1px solid rgba(148, 163, 184, 0.14)', paddingLeft: 14 }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
                          <span className="land-muted">Umumiy foiz:</span>
                          <b style={{ color: '#10B981' }}>90.8% (A daraja)</b>
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginTop: 4 }}>
                          <span className="land-muted">Matn hajmi:</span>
                          <b style={{ color: '#f8fafc' }}>278 soʻz (Yetarli)</b>
                        </div>
                      </div>
                    </div>

                    {/* Criteria Selector / Hover list */}
                    <p style={{ fontSize: 11, fontWeight: 700, color: '#94a3b8', margin: '0 0 8px' }}>
                      Mezonni tanlang (jonli tahlil):
                    </p>
                    <div
                      style={{
                        display: 'grid',
                        gap: 6,
                        maxHeight: showAllCriteria ? 220 : 130,
                        overflowY: 'auto',
                        paddingRight: 4,
                      }}
                    >
                      {(showAllCriteria ? ESSAY_12_CRITERIA : ESSAY_12_CRITERIA.slice(0, 4)).map((crit) => {
                        const isSelected = selectedCriterion.id === crit.id;
                        return (
                          <div
                            key={crit.id}
                            onClick={() => setSelectedCriterion(crit)}
                            onMouseEnter={() => setSelectedCriterion(crit)}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'space-between',
                              padding: '8px 12px',
                              borderRadius: 10,
                              fontSize: 12,
                              cursor: 'pointer',
                              background: isSelected ? 'rgba(245, 158, 11, 0.15)' : 'rgba(15, 23, 42, 0.6)',
                              border: `1px solid ${isSelected ? 'rgba(245, 158, 11, 0.4)' : 'rgba(148, 163, 184, 0.1)'}`,
                              transition: 'all 0.2s ease',
                            }}
                          >
                            <span style={{ color: isSelected ? '#f8fafc' : '#cbd5e1', fontWeight: 600 }}>
                              {crit.id}. {crit.name}
                            </span>
                            <b style={{ color: isSelected ? '#F59E0B' : '#10B981', marginLeft: 8 }}>
                              {crit.score}
                            </b>
                          </div>
                        );
                      })}
                    </div>

                    {/* Interactive Feedback Box */}
                    <div
                      style={{
                        marginTop: 14,
                        borderRadius: 14,
                        padding: '12px 14px',
                        fontSize: 12,
                        background: 'rgba(245, 158, 11, 0.08)',
                        border: '1px solid rgba(245, 158, 11, 0.2)',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#F59E0B', fontWeight: 700, marginBottom: 4 }}>
                        <LightbulbIcon size={15} />
                        <span>{selectedCriterion.name}:</span>
                      </div>
                      <p style={{ margin: 0, color: '#cbd5e1', lineHeight: 1.5 }}>
                        {selectedCriterion.desc}
                      </p>
                    </div>
                  </div>

                  <div
                    className="float-badge glass-card"
                    style={{
                      position: 'absolute',
                      top: -18,
                      right: -8,
                      display: 'flex',
                      alignItems: 'center',
                      gap: 8,
                      padding: '8px 16px',
                      borderRadius: 16,
                      fontSize: 12,
                      fontWeight: 700,
                      color: '#f8fafc',
                    }}
                  >
                    <BotIcon size={16} /> BMB 12 Mezon
                  </div>
                  <div
                    className="float-badge-2 glass-card"
                    style={{
                      position: 'absolute',
                      bottom: -18,
                      left: 14,
                      display: 'flex',
                      alignItems: 'center',
                      gap: 8,
                      padding: '8px 16px',
                      borderRadius: 16,
                      fontSize: 12,
                      fontWeight: 700,
                      color: '#f8fafc',
                    }}
                  >
                    <ZapIcon size={16} /> 15s AI Tahlil
                  </div>
                </div>
              </div>
            )}

            {/* Slide 2: 1v1 Arena — Real-Time Playable Mini-Simulation! */}
            {slide === 2 && (
              <div className="slide-grid">
                <div>
                  <span
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 8,
                      padding: '5px 14px',
                      borderRadius: 999,
                      fontSize: 11,
                      fontWeight: 700,
                      letterSpacing: '0.1em',
                      textTransform: 'uppercase',
                      background: 'rgba(245, 158, 11, 0.12)',
                      color: '#F59E0B',
                      border: '1px solid rgba(245, 158, 11, 0.28)',
                    }}
                  >
                    <GamepadIcon size={14} /> {t('slide3_badge')} · Jonli Duel
                  </span>
                  <h2 className="slide-h2 land-ink" style={{ marginTop: 18 }}>
                    {t('slide3_h2_1')}
                    <br />
                    <span className="hero-title-gradient">{t('slide3_h2_2')}</span>
                  </h2>
                  <p className="land-muted" style={{ marginTop: 16, lineHeight: 1.7, maxWidth: 30 * 16 }}>
                    {t('slide3_p')} Oʻng tomondagi mini-oʻyinda variantlardan birini bosib koʻring va jonli bellashuvni hoziroq his eting!
                  </p>
                  <div className="cta-row">
                    <Link to={startTo} className="landing-cta btn-glow" style={{ padding: '12px 28px' }}>
                      {t('cta_arena')} →
                    </Link>
                    <span className="ghost-cta">
                      <FlameIcon size={15} /> {t('badge_10wins')}
                    </span>
                  </div>
                </div>

                <div style={{ position: 'relative', minWidth: 0 }}>
                  <div className="lcard" style={{ borderRadius: 24, padding: 22 }}>
                    {/* Header: SIZ vs AI ELO */}
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0, flex: 1 }}>
                        <span
                          style={{
                            width: 36,
                            height: 36,
                            borderRadius: 999,
                            flexShrink: 0,
                            fontSize: 12,
                            fontWeight: 900,
                            color: '#090d16',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            background: 'linear-gradient(135deg, #F59E0B, #FBBF24)',
                            boxShadow: '0 0 12px rgba(245, 158, 11, 0.35)',
                          }}
                        >
                          SIZ
                        </span>
                        <div style={{ minWidth: 0 }}>
                          <b className="land-ink" style={{ display: 'block', fontSize: 14 }}>
                            {t('mock_you')}
                          </b>
                          <small style={{ color: '#10B981', fontWeight: 800, fontSize: 10 }}>
                            ELO {arenaUserElo}
                          </small>
                        </div>
                      </div>

                      <div style={{ textAlign: 'center', padding: '4px 14px', borderRadius: 12, background: 'rgba(30, 41, 59, 0.6)' }}>
                        <b className="land-ink" style={{ fontSize: 16, letterSpacing: '0.05em' }}>
                          {arenaUserScore} : {arenaAiScore}
                        </b>
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0, flex: 1, justifyContent: 'flex-end' }}>
                        <div style={{ minWidth: 0, textAlign: 'right' }}>
                          <b className="land-ink" style={{ display: 'block', fontSize: 14 }}>
                            {t('mock_rival')}
                          </b>
                          <small style={{ color: '#F43F5E', fontWeight: 800, fontSize: 10 }}>
                            ELO 1195
                          </small>
                        </div>
                        <span
                          style={{
                            width: 36,
                            height: 36,
                            borderRadius: 999,
                            flexShrink: 0,
                            fontSize: 12,
                            fontWeight: 900,
                            color: '#090d16',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            background: 'linear-gradient(135deg, #8B5CF6, #A78BFA)',
                            boxShadow: '0 0 12px rgba(139, 92, 246, 0.35)',
                          }}
                        >
                          AI
                        </span>
                      </div>
                    </div>

                    {/* Question Card */}
                    <div
                      style={{
                        marginTop: 16,
                        borderRadius: 16,
                        padding: '14px 18px',
                        background: 'rgba(30, 41, 59, 0.5)',
                        border: '1px solid rgba(148, 163, 184, 0.12)',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                        <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: '0.15em', color: '#F59E0B' }}>
                          SAVOL {arenaQuestionIdx + 1} / {ARENA_QUESTIONS.length}
                        </span>
                        {arenaAiThinking ? (
                          <span style={{ fontSize: 10, color: '#38BDF8', fontWeight: 600 }}>
                            AI javob bermoqda...
                          </span>
                        ) : (
                          <span style={{ fontSize: 10, color: '#10B981', fontWeight: 600 }}>
                            AI javob berdi (2.2s)
                          </span>
                        )}
                      </div>
                      <p className="land-ink" style={{ fontSize: 14, fontWeight: 700, margin: 0, lineHeight: 1.5 }}>
                        {currentArenaQ.question}
                      </p>
                    </div>

                    {/* Interactive Answer Buttons */}
                    <div style={{ marginTop: 12, display: 'grid', gap: 8 }}>
                      {currentArenaQ.options.map((opt) => {
                        const isChosen = userSelectedOption === opt.key;
                        let extraClass = '';
                        if (arenaAnswered) {
                          if (opt.correct) extraClass = 'is-correct';
                          else if (isChosen && !opt.correct) extraClass = 'is-wrong';
                        }
                        return (
                          <button
                            key={opt.key}
                            type="button"
                            className={`interactive-opt-btn ${extraClass}`}
                            onClick={() => handleArenaAnswer(opt.key)}
                            disabled={arenaAnswered}
                            aria-label={`${opt.key} varianti: ${opt.text}`}
                          >
                            <span>
                              <b style={{ color: '#F59E0B', marginRight: 6 }}>{opt.key} ·</b>
                              {opt.text}
                            </span>
                            <span>
                              {arenaAnswered && (opt.correct ? '✓ Toʻgʻri' : isChosen ? '✗ Xato' : '')}
                            </span>
                          </button>
                        );
                      })}
                    </div>

                    {/* Next Question / Feedback */}
                    {arenaAnswered && (
                      <div
                        style={{
                          marginTop: 14,
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          padding: '10px 14px',
                          borderRadius: 12,
                          background: 'rgba(16, 185, 129, 0.1)',
                          border: '1px solid rgba(16, 185, 129, 0.25)',
                        }}
                      >
                        <span style={{ fontSize: 12, color: '#e2e8f0' }}>
                          {currentArenaQ.explanation}
                        </span>
                        <button
                          type="button"
                          className="landing-cta"
                          onClick={handleNextArenaQuestion}
                          style={{ padding: '6px 14px', fontSize: 12, minHeight: 36 }}
                        >
                          Keyingi savol →
                        </button>
                      </div>
                    )}
                  </div>

                  <div
                    className="float-badge glass-card"
                    style={{
                      position: 'absolute',
                      top: -18,
                      left: -8,
                      display: 'flex',
                      alignItems: 'center',
                      gap: 8,
                      padding: '8px 16px',
                      borderRadius: 16,
                      fontSize: 12,
                      fontWeight: 700,
                      color: '#f8fafc',
                    }}
                  >
                    <TrophyIcon size={16} /> {t('f_leaderboard')}
                  </div>
                  <div
                    className="float-badge-2 glass-card"
                    style={{
                      position: 'absolute',
                      bottom: -18,
                      right: 14,
                      display: 'flex',
                      alignItems: 'center',
                      gap: 8,
                      padding: '8px 16px',
                      borderRadius: 16,
                      fontSize: 12,
                      fontWeight: 700,
                      color: '#f8fafc',
                    }}
                  >
                    <BotIcon size={16} /> {t('f_bot_15s')}
                  </div>
                </div>
              </div>
            )}

            {/* Pagination Dots */}
            <div className="dots" role="tablist" aria-label="Hero slaydlari">
              {[0, 1, 2].map((i) => (
                <button
                  key={i}
                  type="button"
                  role="tab"
                  aria-selected={slide === i}
                  aria-label={`Slayd ${i + 1}`}
                  className={`dot${slide === i ? ' on' : ''}`}
                  onClick={() => setSlide(i)}
                >
                  <span className="dot-inner" />
                </button>
              ))}
            </div>
          </div>
        </section>

        {/* FEATURES SECTION (3D DEPTH CAROUSEL) */}
        <section id="features" style={{ padding: '64px 0' }}>
          <div style={{ margin: '0 auto', maxWidth: 72 * 16, padding: '0 16px', width: '100%' }}>
            <div style={{ textAlign: 'center', maxWidth: 44 * 16, margin: '0 auto 44px' }}>
              <span style={{ fontSize: 11, fontWeight: 900, letterSpacing: '0.25em', color: '#F59E0B' }}>
                {t('features_eyebrow')}
              </span>
              <h2 className="land-ink" style={{ marginTop: 12, fontSize: 'clamp(1.75rem, 4.5vw, 2.5rem)', fontWeight: 900 }}>
                {t('features_title_1')}{' '}
                <span className="hero-title-gradient">{t('features_title_2')}</span>{' '}
                {t('features_title_3')}
              </h2>
              <p className="land-muted" style={{ marginTop: 12, fontSize: '1rem', lineHeight: 1.6 }}>
                {t('features_subtitle')}
              </p>
            </div>

            <div className="features-carousel">
              <DepthCarousel
                items={featureSlides}
                cardWidth={290}
                cardHeight={370}
                radius={24}
                spread={75}
                tilt={16}
                depth={220}
                visibleCards={3}
                autoplay
                autoplayDelay={3600}
              />
            </div>
          </div>
        </section>

        {/* STATS SECTION */}
        <section id="stats" style={{ padding: '36px 0' }}>
          <div style={{ margin: '0 auto', maxWidth: 72 * 16, padding: '0 16px', width: '100%' }}>
            {stats && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 14, justifyContent: 'center', marginBottom: 24 }}>
                {[
                  { label: t('total_tests'), value: stats.totals.tests, Icon: FileTextIcon, color: '#F59E0B' },
                  { label: t('students'), value: stats.totals.students, Icon: TrophyIcon, color: '#10B981' },
                  { label: t('total_essays'), value: stats.totals.essays_graded, Icon: PenLineIcon, color: '#8B5CF6' },
                ].map((item) => (
                  <div
                    key={item.label}
                    className="glass-card lcard-hover"
                    style={{
                      borderRadius: 20,
                      padding: '16px 28px',
                      textAlign: 'center',
                      minWidth: 160,
                      display: 'flex',
                      alignItems: 'center',
                      gap: 14,
                    }}
                  >
                    <div
                      style={{
                        width: 44,
                        height: 44,
                        borderRadius: 14,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        background: `rgba(${item.color === '#F59E0B' ? '245,158,11' : item.color === '#10B981' ? '16,185,129' : '139,92,246'}, 0.12)`,
                        color: item.color,
                      }}
                    >
                      <item.Icon size={22} />
                    </div>
                    <div style={{ textAlign: 'left' }}>
                      <p className="land-ink" style={{ margin: 0, fontSize: 24, fontWeight: 900 }}>
                        {Number(item.value).toLocaleString()}
                      </p>
                      <p className="land-muted" style={{ margin: '2px 0 0', fontSize: 12, fontWeight: 600 }}>
                        {item.label}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}

            <div style={{ marginTop: 12 }}>
              <p
                style={{
                  fontSize: 12,
                  fontWeight: 900,
                  letterSpacing: '0.22em',
                  color: '#F59E0B',
                  margin: '0 0 12px',
                  textAlign: 'center',
                  textTransform: 'uppercase',
                }}
              >
                {t('an_platform_growth')}
              </p>
              <TrendChart data={trend} />
            </div>
          </div>
        </section>

        {/* HOW IT WORKS */}
        <section
          id="how"
          style={{
            padding: '64px 0',
            background: '#090d16',
            borderTop: '1px solid rgba(148, 163, 184, 0.1)',
            borderBottom: '1px solid rgba(148, 163, 184, 0.1)',
          }}
        >
          <div style={{ margin: '0 auto', maxWidth: 64 * 16, padding: '0 16px', width: '100%' }}>
            <div style={{ textAlign: 'center', maxWidth: 44 * 16, margin: '0 auto 48px' }}>
              <span style={{ fontSize: 11, fontWeight: 900, letterSpacing: '0.25em', color: '#F59E0B' }}>
                {t('how_eyebrow')}
              </span>
              <h2 className="land-ink" style={{ marginTop: 12, fontSize: 'clamp(1.75rem, 4.5vw, 2.5rem)', fontWeight: 900 }}>
                {t('how_title_1')}{' '}
                <span className="hero-title-gradient">{t('how_title_2')}</span>
              </h2>
            </div>

            <div className="steps-grid">
              {[
                [t('step1_title'), t('step1_desc'), '#F59E0B'],
                [t('step2_title'), t('step2_desc'), '#10B981'],
                [t('step3_title'), t('step3_desc'), '#8B5CF6'],
              ].map(([title, desc, c], i) => (
                <div
                  key={i}
                  className="glass-card lcard-hover"
                  style={{ borderRadius: 20, padding: '32px 24px', textAlign: 'center' }}
                >
                  <div
                    style={{
                      width: 60,
                      height: 60,
                      borderRadius: 20,
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
                  <h3 className="land-ink" style={{ fontSize: 18, fontWeight: 800, margin: '0 0 10px' }}>
                    {title}
                  </h3>
                  <p className="land-muted" style={{ fontSize: 14, lineHeight: 1.65, margin: '0 auto' }}>
                    {desc}
                  </p>
                </div>
              ))}
            </div>

            <div style={{ marginTop: 44, textAlign: 'center' }}>
              <Link to={startTo} className="landing-cta btn-glow" style={{ padding: '14px 36px', fontSize: 16 }}>
                {t('cta_free_account')} →
              </Link>
            </div>
          </div>
        </section>
      </main>

      {/* FOOTER */}
      <footer style={{ marginTop: 40 }}>
        <div style={{ height: 1, background: 'linear-gradient(90deg, rgba(245,158,11,.35), rgba(16,185,129,.2), transparent)' }} />
        <div className="land-foot-bg" style={{ position: 'relative', overflow: 'hidden' }}>
          <div style={{ margin: '0 auto', maxWidth: 72 * 16, padding: '64px 16px 40px', width: '100%', position: 'relative', zIndex: 1 }}>
            <div className="foot-grid">
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <img src="/grandec.png" alt="GRANDEC" style={{ width: 34, height: 34, objectFit: 'cover' }} />
                  <span style={{ lineHeight: 1.3 }}>
                    <b className="land-foot-ink" style={{ display: 'block', fontSize: 16 }}>GRANDEC</b>
                    <small style={{ fontSize: 9, fontWeight: 700, letterSpacing: '0.22em', color: '#F59E0B' }}>LMS PLATFORM</small>
                  </span>
                </div>
                <p className="land-foot-muted" style={{ fontSize: 14, lineHeight: 1.7, marginTop: 16 }}>
                  {t('foot_mission')}
                </p>
              </div>

              <div>
                <h4 style={{ fontSize: 12, fontWeight: 900, letterSpacing: '0.2em', color: '#F59E0B', margin: '0 0 20px', textTransform: 'uppercase' }}>
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
                <h4 style={{ fontSize: 12, fontWeight: 900, letterSpacing: '0.2em', color: '#F59E0B', margin: '0 0 20px', textTransform: 'uppercase' }}>
                  {t('foot_news')}
                </h4>
                <p className="land-foot-muted" style={{ fontSize: 14, lineHeight: 1.7, margin: '0 0 16px' }}>
                  {t('foot_newsletter_desc')}
                </p>
                {newsDone ? (
                  <p style={{ fontSize: 14, fontWeight: 600, color: '#10B981', margin: 0 }}>
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
                      aria-label="Email manzil"
                      className="newsletter-input"
                      style={{
                        flex: 1,
                        minWidth: 0,
                        minHeight: 44,
                        padding: '12px 16px',
                        borderRadius: 14,
                        fontSize: 14,
                      }}
                    />
                    <button type="submit" className="landing-cta btn-glow" style={{ flexShrink: 0 }}>
                      {t('foot_subscribe')}
                    </button>
                  </form>
                )}
                <p className="land-foot-muted" style={{ marginTop: 12, fontSize: 11 }}>
                  {t('foot_privacy_note')}
                </p>
              </div>

              <div>
                <h4 style={{ fontSize: 12, fontWeight: 900, letterSpacing: '0.2em', color: '#F59E0B', margin: '0 0 20px', textTransform: 'uppercase' }}>
                  {t('foot_contact')}
                </h4>
                <ul className="land-foot-muted" style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 16, fontSize: 14 }}>
                  <li style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <span
                      style={{
                        width: 38,
                        height: 38,
                        borderRadius: 12,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        flexShrink: 0,
                        color: '#F59E0B',
                        background: 'rgba(245, 158, 11, 0.1)',
                      }}
                    >
                      <BotIcon size={18} />
                    </span>
                    <span style={{ minWidth: 0 }}>
                      <b className="land-foot-ink" style={{ display: 'block', fontSize: 14 }}>Telegram bot</b>
                      <a href="https://t.me/uz_essaygrader_bot" target="_blank" rel="noreferrer" style={{ color: '#F59E0B', fontSize: 13 }}>
                        @uz_essaygrader_bot
                      </a>
                    </span>
                  </li>
                  <li style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <span
                      style={{
                        width: 38,
                        height: 38,
                        borderRadius: 12,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        flexShrink: 0,
                        color: '#F59E0B',
                        background: 'rgba(245, 158, 11, 0.1)',
                      }}
                    >
                      <ClockIcon size={18} />
                    </span>
                    <span style={{ minWidth: 0 }}>
                      <b className="land-foot-ink" style={{ display: 'block', fontSize: 14 }}>{t('foot_hours')}</b>
                      <span className="land-foot-muted" style={{ fontSize: 13 }}>{t('foot_hours_value')}</span>
                    </span>
                  </li>
                  <li style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <span
                      style={{
                        width: 38,
                        height: 38,
                        borderRadius: 12,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        flexShrink: 0,
                        color: '#F59E0B',
                        background: 'rgba(245, 158, 11, 0.1)',
                      }}
                    >
                      <MapPinIcon size={18} />
                    </span>
                    <span style={{ minWidth: 0 }}>
                      <b className="land-foot-ink" style={{ display: 'block', fontSize: 14 }}>{t('foot_online')}</b>
                      <span className="land-foot-muted" style={{ fontSize: 13 }}>{t('foot_online_value')}</span>
                    </span>
                  </li>
                </ul>
              </div>
            </div>

            <div
              className="land-foot-muted"
              style={{
                marginTop: 48,
                paddingTop: 24,
                borderTop: '1px solid rgba(148, 163, 184, 0.1)',
                display: 'flex',
                flexWrap: 'wrap',
                gap: '12px 24px',
                justifyContent: 'space-between',
                alignItems: 'center',
                fontSize: 12,
              }}
            >
              <div>
                <p style={{ margin: 0 }}>© 2026 GRANDEC · Barcha huquqlar himoyalangan.</p>
                <p style={{ margin: '6px 0 0', fontSize: 11, opacity: 0.75 }}>
                  {t('foot_website')} •{' '}
                  <a href="https://www.instagram.com/rozievkomiljon/" target="_blank" rel="noreferrer" style={{ color: '#F59E0B', fontWeight: 600 }}>
                    Komiljon Roziyev
                  </a>{' '}
                  {t('foot_created_by')}
                </p>
              </div>
              <div style={{ display: 'flex', gap: 20, alignItems: 'center' }}>
                <a href="/login" className="footer-link land-foot-muted" style={{ textDecoration: 'none' }}>{t('foot_privacy')}</a>
                <a href="/login" className="footer-link land-foot-muted" style={{ textDecoration: 'none' }}>{t('foot_terms')}</a>
                <span
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 8,
                    padding: '6px 14px',
                    borderRadius: 999,
                    border: '1px solid rgba(16, 185, 129, 0.3)',
                    background: 'rgba(16, 185, 129, 0.08)',
                    fontSize: 11,
                    fontWeight: 700,
                    color: '#34D399',
                  }}
                >
                  <span className="dot-mini" style={{ background: '#10B981', margin: 0 }} /> {t('foot_healthy')}
                </span>
              </div>
            </div>
          </div>

          {/* Oversized watermark */}
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
              fontFamily: "'Plus Jakarta Sans', Inter, system-ui, sans-serif",
              letterSpacing: '-0.02em',
              lineHeight: 0.8,
              whiteSpace: 'nowrap',
              color: 'rgba(255, 255, 255, 0.03)',
              fontSize: 'clamp(64px, 18.5vw, 260px)',
              marginTop: 10,
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
