import { useEffect, useMemo, useState } from 'react';
import type { FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';
import { Mic, Headphones, Play, Pause } from 'lucide-react';
import { useAuth } from '../auth/AuthContext';
import { useLang } from '../i18n/LangContext';
import { useTheme } from '../theme/ThemeContext';
import { School, landingFor } from '../lib/api';
import TrendChart from '../components/TrendChart';
import HowItWorks from '../components/HowItWorks';
import SEO from '../components/SEO';
import LanguageSwitcher from '../components/LanguageSwitcher';
import UserNavDropdown from '../components/UserNavDropdown';
import confetti from 'canvas-confetti';
import {
  BotIcon,
  CheckIcon,
  ClockIcon,
  FileTextIcon,
  LightbulbIcon,
  MapPinIcon,
  MenuIcon,
  MoonIcon,
  PenLineIcon,
  SunIcon,
  SwordsIcon,
  TrophyIcon,
  XIcon,
} from '../components/icons';

// ---------------------------------------------------------------------------
// 12 BMB Milliy Sertifikat Essay Assessment Criteria (Uzbek Track)
// ---------------------------------------------------------------------------
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

// Interactive CBT Sample Question (Uzbek Track)
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

// ---------------------------------------------------------------------------
// 4 Official IELTS Writing Criteria (English Track)
// ---------------------------------------------------------------------------
interface IeltsCriterionData {
  id: number;
  name: string;
  code: string;
  score: string;
  band: number;
  desc: string;
  advice: string;
  highlights: string[];
}

const IELTS_4_CRITERIA: IeltsCriterionData[] = [
  {
    id: 1,
    name: 'Task Response',
    code: 'TR',
    score: '7.5 / 9.0',
    band: 7.5,
    desc: 'Barcha savol qismlari toʻliq va teran ochilgan. Asosiy argumentlar aniq keltirilib, izchil pozitsiya saqlangan.',
    advice: '2-asosiy qismda yana bitta empirik dalil (misol) keltirilsa, ball 8.0+ darajaga koʻtariladi.',
    highlights: ['Well-developed position', 'Relevant arguments', 'Clear thesis statement'],
  },
  {
    id: 2,
    name: 'Coherence & Cohesion',
    code: 'CC',
    score: '7.0 / 9.0',
    band: 7.0,
    desc: 'Paragraflar mantiqan toʻgʻri taqsimlangan. Fikrlar ketma-ketligi silliq va bogʻlovchi vositalar oʻrinli qoʻllangan.',
    advice: 'Paragraflararo oʻtishda faqat "Moreover", "Furthermore" bilan cheklanmay, murakkab jumlalar bilan bogʻlang.',
    highlights: ['Logical sequencing', 'Clear central topic', 'Diverse cohesive devices'],
  },
  {
    id: 3,
    name: 'Lexical Resource',
    code: 'LR',
    score: '8.0 / 9.0',
    band: 8.0,
    desc: 'Keng va murakkab akademik soʻz boyligi hamda tabiiy kollokatsiyalar (soʻz birikmalari) muvaffaqiyatli ishlatilgan.',
    advice: '"paradigm shift", "pedagogical efficacy", "heuristic adaptability" kabi Band 8+ soʻzlar oʻrinli tanlangan.',
    highlights: ['Sophisticated collocations', 'Precise academic vocabulary', 'Natural phrasing'],
  },
  {
    id: 4,
    name: 'Grammatical Range & Accuracy',
    code: 'GRA',
    score: '7.5 / 9.0',
    band: 7.5,
    desc: 'Murakkab ergash gaplar, inversion va passiv konstruksiyalardan yuqori aniqlikda foydalanilgan.',
    advice: 'Kollektiv otlar va nisbiy olmoshlar moslashuvidagi 1 ta kichik punktuatsion holatga eʼtibor qarating.',
    highlights: ['Wide syntactic variety', 'Complex sentence structures', 'High accuracy rate'],
  },
];

// Interactive Speaking Sample (English Track)
interface SpeakingDemoData {
  part: string;
  topic: string;
  overallBand: number;
  scores: {
    fluency: number;
    pronunciation: number;
    lexical: number;
    grammar: number;
  };
  duration: string;
  transcript: string;
  highlightWords: string[];
  aiFeedback: string;
}

const SPEAKING_DEMO: SpeakingDemoData = {
  part: 'Part 2: Long Turn (Cue Card)',
  topic: 'Describe an educational journey that significantly influenced your life',
  overallBand: 7.5,
  scores: {
    fluency: 8.0,
    pronunciation: 7.0,
    lexical: 8.0,
    grammar: 7.5,
  },
  duration: '0:42 / 1:30',
  transcript:
    'When I first commenced my studies in modern pedagogy, I realized the profound transformative power of interactive learning paradigms. It not only broadened my cognitive horizon, but also inspired me to persevere in rigorous academic research...',
  highlightWords: ['commenced', 'profound transformative power', 'cognitive horizon', 'persevere'],
  aiFeedback:
    "💡 'commenced' va 'cognitive horizon' kabi ifodalar Lexical Resource ballini 8.0 ga chiqardi. Talaffuzda intonatsiya tabiiy, Band 8.0 darajasidagi ravonlik saqlangan.",
};

// Interactive Cambridge CBT Question (English Track)
interface EnglishCbtQuestion {
  section: string;
  question: string;
  options: { key: string; text: string; correct: boolean }[];
  explanation: string;
}

const ENGLISH_CBT_QUESTION: EnglishCbtQuestion = {
  section: 'Academic Reading — Passage 2',
  question:
    'According to cognitive psychologists, what is the primary neurobiological advantage of spaced repetition in memory consolidation?',
  options: [
    { key: 'A', text: 'Accelerating superficial cramming before high-stakes exams', correct: false },
    { key: 'B', text: 'Strengthening synaptic neural pathways through timed retrieval intervals', correct: true },
    { key: 'C', text: 'Completely eliminating mental fatigue during prolonged study sessions', correct: false },
    { key: 'D', text: 'Minimizing the total number of vocabulary items required for fluency', correct: false },
  ],
  explanation:
    "To'g'ri javob: B. Tadqiqotlarga ko'ra, oraliq takrorlash (spaced repetition) neyronlar orasidagi sinaptik bog'lanishlarni mustahkamlaydi va ma'lumotni qisqa muddatli xotiradan uzoq muddatli xotiraga o'tkazishni ta'minlaydi.",
};

export default function Landing() {
  const { t } = useLang();
  const { user, openAuthModal } = useAuth();
  const { resolvedTheme, setTheme } = useTheme();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);

  // -------------------------------------------------------------------------
  // DUAL-TRACK SUBJECT STATE (Uzbek vs English)
  // -------------------------------------------------------------------------
  const [landingSubject, setLandingSubject] = useState<'uzbek' | 'english'>(() => {
    const saved = localStorage.getItem('landing_subject') || localStorage.getItem('lms_subject');
    return saved === 'english' ? 'english' : 'uzbek';
  });

  const handleSubjectSwitch = (sub: 'uzbek' | 'english') => {
    if (sub === landingSubject) return;
    setLandingSubject(sub);
    localStorage.setItem('landing_subject', sub);
    localStorage.setItem('lms_subject', sub);
    window.dispatchEvent(new CustomEvent('subject-changed', { detail: sub }));
  };

  // Hero interactive demo widget modes
  const [demoTabUzbek, setDemoTabUzbek] = useState<'essay' | 'test'>('essay');
  const [selectedCritUzbek, setSelectedCritUzbek] = useState<CriterionData>(ESSAY_12_CRITERIA[0]);
  const [selectedOptionKeyUzbek, setSelectedOptionKeyUzbek] = useState<string | null>(null);

  const [demoTabEnglish, setDemoTabEnglish] = useState<'writing' | 'speaking' | 'cbt'>('writing');
  const [selectedCritEnglish, setSelectedCritEnglish] = useState<IeltsCriterionData>(IELTS_4_CRITERIA[0]);
  const [selectedOptionKeyEnglish, setSelectedOptionKeyEnglish] = useState<string | null>(null);
  const [isSpeakingPlaying, setIsSpeakingPlaying] = useState<boolean>(false);

  // Live platform stats
  const [stats, setStats] = useState<{
    totals: { tests: number; students: number; essays_graded: number };
  } | null>(null);

  // Newsletter
  const [newsEmail, setNewsEmail] = useState('');
  const [newsDone, setNewsDone] = useState(false);

  const startTo = user ? landingFor(user) : '/register';

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

  const handleCbtOptionClickUzbek = (key: string) => {
    setSelectedOptionKeyUzbek(key);
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

  const handleCbtOptionClickEnglish = (key: string) => {
    setSelectedOptionKeyEnglish(key);
    if (key === 'B') {
      try {
        confetti({
          particleCount: 40,
          spread: 60,
          origin: { y: 0.65 },
          colors: ['#38BDF8', '#10B981', '#F59E0B'],
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
          landingSubject === 'english'
            ? 'IELTS & Multi-level LMS | AI Writing & Speaking Simulator'
            : 'Ona tili va adabiyot LMS | Milliy sertifikat & AI Esse'
        }
        description={
          landingSubject === 'english'
            ? "IELTS Band 1.0–9.0 va CEFR Multi-level bo'yicha AI Writing tahlili, AI Speaking simulyatori va Cambridge CBT testlari — GRAND EDUCATION."
            : "Ona tili va adabiyotidan Milliy sertifikatga tayyorlovchi LMS platformasi — GRAND EDUCATION (grandec.uz). 12 mezonli AI Esse tahlili, Fast CBT simulyatori va 1v1 Arena."
        }
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
          background: 'var(--topbar-bg)',
          backdropFilter: 'blur(16px)',
          WebkitBackdropFilter: 'blur(16px)',
          borderBottom: '1px solid var(--border)',
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
                  color: 'var(--ink)',
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
                  color: 'var(--muted)',
                  textDecoration: 'none',
                  transition: 'all 0.2s ease',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.color = 'var(--ink)';
                  e.currentTarget.style.background = 'var(--dropdown-hover)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.color = 'var(--muted)';
                  e.currentTarget.style.background = 'transparent';
                }}
              >
                {t(k)}
              </a>
            ))}
          </div>

          {/* Right Area: Language Switcher, Theme Switcher & Auth / User Dropdown */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
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
                    background: 'var(--card-2)',
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
              </>
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
                border: '1px solid var(--border)',
                background: 'var(--card-2)',
                color: 'var(--ink)',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                transition: 'all 0.2s ease',
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
                <span style={{ fontWeight: 900, fontSize: 16, color: 'var(--ink)' }}>GRAND EDUCATION</span>
              </div>
              <button
                type="button"
                onClick={() => setMobileOpen(false)}
                style={{
                  background: 'none',
                  border: 'none',
                  color: 'var(--muted)',
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
                    color: 'var(--muted)',
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
        <section id="hero" style={{ padding: '36px 20px 60px' }}>
          <div
            style={{
              margin: '0 auto',
              maxWidth: 1200,
            }}
          >
            {/* DUAL-TRACK SEGMENTED PILL SWITCHER */}
            <div style={{ display: 'flex', justifyContent: 'flex-start', marginBottom: 28 }}>
              <div
                role="group"
                aria-label="Asosiy yo'nalishni tanlang"
                className="hero-subject-switcher"
              >
                {/* 🇺🇿 Ona tili */}
                <button
                  type="button"
                  onClick={() => handleSubjectSwitch('uzbek')}
                  className={`hero-switcher-btn ${landingSubject === 'uzbek' ? 'active' : ''}`}
                  aria-pressed={landingSubject === 'uzbek'}
                >
                  <span style={{ fontSize: 18 }}>🇺🇿</span>
                  <span>Ona tili va Adabiyot</span>
                  <span className="switcher-subtag">Milliy sertifikat</span>
                </button>

                {/* 🇬🇧 English */}
                <button
                  type="button"
                  onClick={() => handleSubjectSwitch('english')}
                  className={`hero-switcher-btn ${landingSubject === 'english' ? 'active' : ''}`}
                  aria-pressed={landingSubject === 'english'}
                >
                  <span style={{ fontSize: 18 }}>🇬🇧</span>
                  <span>English (IELTS & Multi-level)</span>
                  <span className="switcher-subtag">Band 1–9</span>
                </button>
              </div>
            </div>

            {/* HERO GRID */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr',
                gap: 44,
                alignItems: 'center',
              }}
              className="hero-grid"
            >
              {/* Left Column: Headlines & 1-Click CTAs */}
              <AnimatePresence mode="wait">
                <motion.div
                  key={landingSubject}
                  initial={{ opacity: 0, y: 16 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -16 }}
                  transition={{ duration: 0.24, ease: 'easeOut' }}
                >
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
                        background:
                          landingSubject === 'english'
                            ? 'rgba(56, 189, 248, 0.12)'
                            : 'rgba(245, 158, 11, 0.1)',
                        color: landingSubject === 'english' ? '#38BDF8' : '#F59E0B',
                        border:
                          landingSubject === 'english'
                            ? '1px solid rgba(56, 189, 248, 0.3)'
                            : '1px solid rgba(245, 158, 11, 0.25)',
                        boxShadow:
                          landingSubject === 'english'
                            ? '0 0 20px rgba(56, 189, 248, 0.15)'
                            : '0 0 20px rgba(245, 158, 11, 0.1)',
                      }}
                    >
                      <span
                        style={{
                          width: 8,
                          height: 8,
                          borderRadius: 999,
                          background: landingSubject === 'english' ? '#38BDF8' : '#10B981',
                          boxShadow: `0 0 10px ${landingSubject === 'english' ? '#38BDF8' : '#10B981'}`,
                        }}
                      />
                      {landingSubject === 'english'
                        ? '🎯 IELTS Band 1.0–9.0 · CEFR Multi-level (B2/C1)'
                        : '⭐️ Milliy sertifikat & Attestatsiya 2026 (Yangi format)'}
                    </span>
                  </div>

                  {/* Main Headline */}
                  <h1
                    style={{
                      fontSize: 'clamp(2.3rem, 4.8vw, 3.8rem)',
                      lineHeight: 1.12,
                      fontWeight: 900,
                      letterSpacing: '-0.03em',
                      color: 'var(--ink)',
                      margin: '0 0 20px',
                    }}
                  >
                    {landingSubject === 'english' ? (
                      <>
                        IELTS va Multi-level imtihonlariga{' '}
                        <span className="hero-title-gradient">AI bilan tayyorlaning</span>
                      </>
                    ) : (
                      <>
                        Milliy sertifikatga{' '}
                        <span className="hero-title-gradient">AI bilan tayyorlaning</span>
                      </>
                    )}
                  </h1>

                  {/* Subhead */}
                  <p
                    style={{
                      fontSize: 'clamp(1.05rem, 1.8vw, 1.18rem)',
                      lineHeight: 1.7,
                      color: 'var(--muted)',
                      maxWidth: 540,
                      margin: '0 0 32px',
                    }}
                  >
                    {landingSubject === 'english'
                      ? 'Rasmiy 4 ta mezon boʻyicha Writing Task 1 & 2 AI baholash, interaktiv Speaking trenajyori va toʻliq CBT Reading & Listening simulyatori.'
                      : 'BMB Davlat standarti asosidagi 12 ta mezonli AI Esse tahlili, Fast CBT test simulyatori va jonli 1v1 Arena bellashuvlari.'}
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
                      onClick={() => handleAction(landingSubject === 'english' ? '/speaking' : '/essays')}
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
                      <span>{t('hero_cta_start_free')}</span>
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
                        color: 'var(--ink)',
                        background: 'var(--card-2)',
                        border: '1px solid var(--border)',
                        cursor: 'pointer',
                        backdropFilter: 'blur(12px)',
                        transition: 'all 0.2s ease',
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.borderColor = 'var(--accent)';
                        e.currentTarget.style.background = 'var(--dropdown-hover)';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.borderColor = 'var(--border)';
                        e.currentTarget.style.background = 'var(--card-2)';
                      }}
                    >
                      <span>{t('hero_cta_login_1click')}</span>
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
                    {landingSubject === 'english' ? (
                      <>
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                          <CheckIcon size={16} style={{ color: '#10B981' }} />
                          Instant Band Score (1.0–9.0)
                        </span>
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                          <CheckIcon size={16} style={{ color: '#F59E0B' }} />
                          4 ta rasmiy IELTS mezoni
                        </span>
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                          <CheckIcon size={16} style={{ color: '#38BDF8' }} />
                          AI Speaking & Audio tahlil
                        </span>
                      </>
                    ) : (
                      <>
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                          <CheckIcon size={16} className="text-emerald" style={{ color: '#10B981' }} />
                          {t('trust_ai_speed')}
                        </span>
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                          <CheckIcon size={16} className="text-amber" style={{ color: '#F59E0B' }} />
                          {t('trust_bmb_criteria')}
                        </span>
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                          <CheckIcon size={16} className="text-purple" style={{ color: '#8B5CF6' }} />
                          {t('trust_elo_arena')}
                        </span>
                      </>
                    )}
                  </div>
                </motion.div>
              </AnimatePresence>

              {/* Right Column: High-End Interactive Demo Widget */}
              <div>
                <AnimatePresence mode="wait">
                  <motion.div
                    key={landingSubject}
                    initial={{ opacity: 0, scale: 0.98 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.98 }}
                    transition={{ duration: 0.22, ease: 'easeOut' }}
                    className="glass-card lcard-hover demo-card"
                    style={{
                      borderRadius: 24,
                      padding: 24,
                      backdropFilter: 'blur(16px)',
                    }}
                  >
                    {/* ----------------------------------------------------------------- */}
                    {/* UZBEK TRACK DEMO WIDGET */}
                    {/* ----------------------------------------------------------------- */}
                    {landingSubject === 'uzbek' && (
                      <div>
                        {/* Segmented Demo Tabs */}
                        <div
                          className="demo-tabs-wrap"
                          style={{
                            display: 'flex',
                            background: 'var(--card-2)',
                            borderRadius: 14,
                            padding: 4,
                            marginBottom: 20,
                            border: '1px solid var(--border)',
                          }}
                        >
                          <button
                            type="button"
                            onClick={() => setDemoTabUzbek('essay')}
                            style={{
                              flex: 1,
                              padding: '10px 14px',
                              borderRadius: 10,
                              fontSize: 13,
                              fontWeight: 800,
                              border: 'none',
                              cursor: 'pointer',
                              transition: 'all 0.2s ease',
                              background: demoTabUzbek === 'essay' ? 'rgba(245, 158, 11, 0.18)' : 'transparent',
                              color: demoTabUzbek === 'essay' ? '#F59E0B' : 'var(--muted)',
                              boxShadow: demoTabUzbek === 'essay' ? '0 0 12px rgba(245, 158, 11, 0.2)' : 'none',
                            }}
                          >
                            ✍️ AI Esse (12 Mezon)
                          </button>
                          <button
                            type="button"
                            onClick={() => setDemoTabUzbek('test')}
                            style={{
                              flex: 1,
                              padding: '10px 14px',
                              borderRadius: 10,
                              fontSize: 13,
                              fontWeight: 800,
                              border: 'none',
                              cursor: 'pointer',
                              transition: 'all 0.2s ease',
                              background: demoTabUzbek === 'test' ? 'rgba(16, 185, 129, 0.18)' : 'transparent',
                              color: demoTabUzbek === 'test' ? '#10B981' : 'var(--muted)',
                              boxShadow: demoTabUzbek === 'test' ? '0 0 12px rgba(16, 185, 129, 0.2)' : 'none',
                            }}
                          >
                            📚 Fast CBT Test
                          </button>
                        </div>

                        {/* TAB 1: AI ESSE DEMO */}
                        {demoTabUzbek === 'essay' && (
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
                                  Namuna Esse Tahlili
                                </span>
                                <h4 style={{ margin: '4px 0 0', fontSize: 15, fontWeight: 800, color: 'var(--ink)' }}>
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
                                A Daraja (90.8%)
                              </span>
                            </div>

                            {/* Score summary bar */}
                            <div
                              className="demo-score-box"
                              style={{
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'space-between',
                                padding: '12px 16px',
                                borderRadius: 14,
                                background: 'var(--card-2)',
                                border: '1px solid rgba(245, 158, 11, 0.25)',
                                marginBottom: 16,
                              }}
                            >
                              <div>
                                <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--muted)' }}>Umumiy BMB Ball</span>
                                <div style={{ fontSize: 22, fontWeight: 900, color: 'var(--ink)' }}>
                                  54.5 <span style={{ fontSize: 14, color: '#F59E0B' }}>/ 60</span>
                                </div>
                              </div>
                              <div style={{ textAlign: 'right' }}>
                                <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--muted)' }}>Matn Hajmi</span>
                                <div style={{ fontSize: 14, fontWeight: 800, color: '#10B981' }}>278 ta soʻz</div>
                              </div>
                            </div>

                            {/* Criteria Selector Chips */}
                            <p style={{ fontSize: 11, fontWeight: 700, color: 'var(--muted)', margin: '0 0 8px' }}>
                              Mezonni tanlang va tavsiyalarni koʻring:
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
                                const isSel = selectedCritUzbek.id === crit.id;
                                return (
                                  <button
                                    key={crit.id}
                                    type="button"
                                    onClick={() => setSelectedCritUzbek(crit)}
                                    style={{
                                      padding: '6px 10px',
                                      borderRadius: 8,
                                      fontSize: 11,
                                      fontWeight: 700,
                                      cursor: 'pointer',
                                      border: `1px solid ${isSel ? 'rgba(245, 158, 11, 0.5)' : 'var(--border)'}`,
                                      background: isSel ? 'rgba(245, 158, 11, 0.18)' : 'var(--card-2)',
                                      color: isSel ? '#F59E0B' : 'var(--ink-soft)',
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
                              className="active-critique-box"
                              style={{
                                padding: '14px',
                                borderRadius: 14,
                                background: 'var(--card-2)',
                                border: '1px solid rgba(245, 158, 11, 0.25)',
                                marginBottom: 16,
                              }}
                            >
                              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                                <b style={{ fontSize: 13, color: '#F59E0B' }}>
                                  {selectedCritUzbek.id}. {selectedCritUzbek.name}
                                </b>
                                <span style={{ fontSize: 12, fontWeight: 800, color: '#10B981' }}>{selectedCritUzbek.score}</span>
                              </div>
                              <p style={{ fontSize: 12, color: 'var(--ink-soft)', margin: '0 0 6px', lineHeight: 1.5 }}>
                                {selectedCritUzbek.desc}
                              </p>
                              <div
                                style={{
                                  fontSize: 11,
                                  color: 'var(--muted)',
                                  background: 'rgba(245, 158, 11, 0.08)',
                                  padding: '6px 10px',
                                  borderRadius: 8,
                                  display: 'flex',
                                  alignItems: 'center',
                                  gap: 6,
                                }}
                              >
                                <LightbulbIcon size={14} style={{ color: '#F59E0B', flexShrink: 0 }} />
                                <span>{selectedCritUzbek.advice}</span>
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
                              ✍️ Oʻz essemni tahlil qilish →
                            </button>
                          </div>
                        )}

                        {/* TAB 2: FAST CBT TEST DEMO */}
                        {demoTabUzbek === 'test' && (
                          <div>
                            <div
                              style={{
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'space-between',
                                fontSize: 12,
                                fontWeight: 700,
                                color: 'var(--muted)',
                                marginBottom: 12,
                              }}
                            >
                              <span style={{ color: '#10B981' }}>Savol 1 / 1</span>
                              <span>⏱ 00:45</span>
                            </div>

                            <h4 style={{ fontSize: 15, fontWeight: 800, color: 'var(--ink)', margin: '0 0 16px', lineHeight: 1.5 }}>
                              {CBT_QUESTION.question}
                            </h4>

                            {/* Choices */}
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 16 }}>
                              {CBT_QUESTION.options.map((opt) => {
                                const isChosen = selectedOptionKeyUzbek === opt.key;
                                const isCorrect = opt.correct;
                                const showCorrectState = selectedOptionKeyUzbek !== null && isCorrect;
                                const showWrongState = isChosen && !isCorrect;

                                return (
                                  <button
                                    key={opt.key}
                                    type="button"
                                    onClick={() => handleCbtOptionClickUzbek(opt.key)}
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
                                        : 'var(--card-2)',
                                      border: `1px solid ${
                                        showCorrectState
                                          ? '#10B981'
                                          : showWrongState
                                          ? '#ef4444'
                                          : 'var(--border)'
                                      }`,
                                      color: showCorrectState
                                        ? '#34D399'
                                        : showWrongState
                                        ? '#f87171'
                                        : 'var(--ink)',
                                    }}
                                  >
                                    <span>
                                      <b>{opt.key})</b> {opt.text}
                                    </span>
                                    {showCorrectState && <span>✓ Toʻgʻri</span>}
                                    {showWrongState && <span>✕ Xato</span>}
                                  </button>
                                );
                              })}
                            </div>

                            {/* Explanation */}
                            {selectedOptionKeyUzbek && (
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
                                <b style={{ color: '#10B981', display: 'block', marginBottom: 4 }}>💡 Ilmiy tahlil:</b>
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
                              Toʻliq testni boshlash →
                            </button>
                          </div>
                        )}
                      </div>
                    )}

                    {/* ----------------------------------------------------------------- */}
                    {/* ENGLISH TRACK DEMO WIDGET */}
                    {/* ----------------------------------------------------------------- */}
                    {landingSubject === 'english' && (
                      <div>
                        {/* Segmented Demo Tabs: Writing | Speaking | CBT */}
                        <div
                          className="demo-tabs-wrap"
                          style={{
                            display: 'flex',
                            background: 'var(--card-2)',
                            borderRadius: 14,
                            padding: 4,
                            marginBottom: 20,
                            border: '1px solid var(--border)',
                          }}
                        >
                          <button
                            type="button"
                            onClick={() => setDemoTabEnglish('writing')}
                            style={{
                              flex: 1,
                              padding: '10px 8px',
                              borderRadius: 10,
                              fontSize: 12,
                              fontWeight: 800,
                              border: 'none',
                              cursor: 'pointer',
                              transition: 'all 0.2s ease',
                              background: demoTabEnglish === 'writing' ? 'rgba(245, 158, 11, 0.18)' : 'transparent',
                              color: demoTabEnglish === 'writing' ? '#F59E0B' : 'var(--muted)',
                              boxShadow: demoTabEnglish === 'writing' ? '0 0 12px rgba(245, 158, 11, 0.2)' : 'none',
                            }}
                          >
                            ✍️ IELTS Writing
                          </button>
                          <button
                            type="button"
                            onClick={() => setDemoTabEnglish('speaking')}
                            style={{
                              flex: 1,
                              padding: '10px 8px',
                              borderRadius: 10,
                              fontSize: 12,
                              fontWeight: 800,
                              border: 'none',
                              cursor: 'pointer',
                              transition: 'all 0.2s ease',
                              background: demoTabEnglish === 'speaking' ? 'rgba(56, 189, 248, 0.18)' : 'transparent',
                              color: demoTabEnglish === 'speaking' ? '#38BDF8' : 'var(--muted)',
                              boxShadow: demoTabEnglish === 'speaking' ? '0 0 12px rgba(56, 189, 248, 0.2)' : 'none',
                            }}
                          >
                            🎙 AI Speaking
                          </button>
                          <button
                            type="button"
                            onClick={() => setDemoTabEnglish('cbt')}
                            style={{
                              flex: 1,
                              padding: '10px 8px',
                              borderRadius: 10,
                              fontSize: 12,
                              fontWeight: 800,
                              border: 'none',
                              cursor: 'pointer',
                              transition: 'all 0.2s ease',
                              background: demoTabEnglish === 'cbt' ? 'rgba(16, 185, 129, 0.18)' : 'transparent',
                              color: demoTabEnglish === 'cbt' ? '#10B981' : 'var(--muted)',
                              boxShadow: demoTabEnglish === 'cbt' ? '0 0 12px rgba(16, 185, 129, 0.2)' : 'none',
                            }}
                          >
                            🎧 CBT Reading
                          </button>
                        </div>

                        {/* TAB 1: IELTS WRITING AI */}
                        {demoTabEnglish === 'writing' && (
                          <div>
                            {/* Topic Header */}
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
                                  Academic Task 2
                                </span>
                                <h4 style={{ margin: '4px 0 0', fontSize: 14, fontWeight: 800, color: 'var(--ink)' }}>
                                  The impact of AI on traditional education systems
                                </h4>
                              </div>
                              <span
                                style={{
                                  padding: '4px 10px',
                                  borderRadius: 8,
                                  fontSize: 11,
                                  fontWeight: 800,
                                  background: 'rgba(245, 158, 11, 0.15)',
                                  color: '#F59E0B',
                                  border: '1px solid rgba(245, 158, 11, 0.3)',
                                  whiteSpace: 'nowrap',
                                }}
                              >
                                Band 7.5 (C1)
                              </span>
                            </div>

                            {/* Score summary bar */}
                            <div
                              className="demo-score-box"
                              style={{
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'space-between',
                                padding: '12px 16px',
                                borderRadius: 14,
                                background: 'var(--card-2)',
                                border: '1px solid rgba(245, 158, 11, 0.25)',
                                marginBottom: 16,
                              }}
                            >
                              <div>
                                <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--muted)' }}>Overall Band Score</span>
                                <div style={{ fontSize: 22, fontWeight: 900, color: '#F59E0B' }}>
                                  7.5 <span style={{ fontSize: 13, color: 'var(--muted)' }}>/ 9.0</span>
                                </div>
                              </div>
                              <div style={{ textAlign: 'right' }}>
                                <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--muted)' }}>Word Count</span>
                                <div style={{ fontSize: 14, fontWeight: 800, color: '#10B981' }}>284 words</div>
                              </div>
                            </div>

                            {/* 4 Official IELTS Criteria Chips */}
                            <p style={{ fontSize: 11, fontWeight: 700, color: 'var(--muted)', margin: '0 0 8px' }}>
                              Rasmiy 4 ta baholash mezonini koʻring:
                            </p>
                            <div
                              style={{
                                display: 'grid',
                                gridTemplateColumns: 'repeat(2, 1fr)',
                                gap: 6,
                                marginBottom: 14,
                              }}
                            >
                              {IELTS_4_CRITERIA.map((crit) => {
                                const isSel = selectedCritEnglish.id === crit.id;
                                return (
                                  <button
                                    key={crit.id}
                                    type="button"
                                    onClick={() => setSelectedCritEnglish(crit)}
                                    style={{
                                      padding: '8px 10px',
                                      borderRadius: 10,
                                      fontSize: 11,
                                      fontWeight: 700,
                                      cursor: 'pointer',
                                      display: 'flex',
                                      alignItems: 'center',
                                      justifyContent: 'space-between',
                                      border: `1px solid ${isSel ? 'rgba(245, 158, 11, 0.6)' : 'var(--border)'}`,
                                      background: isSel ? 'rgba(245, 158, 11, 0.18)' : 'var(--card-2)',
                                      color: isSel ? '#F59E0B' : 'var(--ink-soft)',
                                      transition: 'all 0.15s ease',
                                    }}
                                  >
                                    <span>{crit.code}</span>
                                    <b>{crit.score}</b>
                                  </button>
                                );
                              })}
                            </div>

                            {/* Active Criterion Box */}
                            <div
                              className="active-critique-box"
                              style={{
                                padding: '14px',
                                borderRadius: 14,
                                background: 'var(--card-2)',
                                border: '1px solid rgba(245, 158, 11, 0.25)',
                                marginBottom: 16,
                              }}
                            >
                              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                                <b style={{ fontSize: 13, color: '#F59E0B' }}>
                                  {selectedCritEnglish.name} ({selectedCritEnglish.code})
                                </b>
                                <span style={{ fontSize: 12, fontWeight: 800, color: '#10B981' }}>{selectedCritEnglish.score}</span>
                              </div>
                              <p style={{ fontSize: 12, color: 'var(--ink-soft)', margin: '0 0 8px', lineHeight: 1.5 }}>
                                {selectedCritEnglish.desc}
                              </p>

                              {/* Highlights badges */}
                              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 8 }}>
                                {selectedCritEnglish.highlights.map((h) => (
                                  <span
                                    key={h}
                                    style={{
                                      fontSize: 10,
                                      fontWeight: 700,
                                      padding: '2px 8px',
                                      borderRadius: 6,
                                      background: 'rgba(56, 189, 248, 0.12)',
                                      color: '#38BDF8',
                                      border: '1px solid rgba(56, 189, 248, 0.25)',
                                    }}
                                  >
                                    ✓ {h}
                                  </span>
                                ))}
                              </div>

                              <div
                                style={{
                                  fontSize: 11,
                                  color: 'var(--muted)',
                                  background: 'rgba(245, 158, 11, 0.08)',
                                  padding: '6px 10px',
                                  borderRadius: 8,
                                  display: 'flex',
                                  alignItems: 'center',
                                  gap: 6,
                                }}
                              >
                                <LightbulbIcon size={14} style={{ color: '#F59E0B', flexShrink: 0 }} />
                                <span>{selectedCritEnglish.advice}</span>
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
                            >
                              ✍️ IELTS Writing tahlil qilish →
                            </button>
                          </div>
                        )}

                        {/* TAB 2: AI SPEAKING SIMULATOR */}
                        {demoTabEnglish === 'speaking' && (
                          <div>
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
                                <span style={{ fontSize: 11, fontWeight: 700, color: '#38BDF8', textTransform: 'uppercase' }}>
                                  {SPEAKING_DEMO.part}
                                </span>
                                <h4 style={{ margin: '4px 0 0', fontSize: 14, fontWeight: 800, color: 'var(--ink)' }}>
                                  {SPEAKING_DEMO.topic}
                                </h4>
                              </div>
                              <span
                                style={{
                                  padding: '4px 10px',
                                  borderRadius: 8,
                                  fontSize: 11,
                                  fontWeight: 800,
                                  background: 'rgba(56, 189, 248, 0.15)',
                                  color: '#38BDF8',
                                  border: '1px solid rgba(56, 189, 248, 0.3)',
                                  whiteSpace: 'nowrap',
                                }}
                              >
                                Band {SPEAKING_DEMO.overallBand}
                              </span>
                            </div>

                            {/* Audio waveform simulator */}
                            <div
                              style={{
                                padding: '14px 16px',
                                borderRadius: 14,
                                background: 'var(--card-2)',
                                border: '1px solid rgba(56, 189, 248, 0.25)',
                                marginBottom: 14,
                              }}
                            >
                              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
                                <button
                                  type="button"
                                  onClick={() => setIsSpeakingPlaying((p) => !p)}
                                  style={{
                                    display: 'inline-flex',
                                    alignItems: 'center',
                                    gap: 6,
                                    padding: '6px 12px',
                                    borderRadius: 10,
                                    background: isSpeakingPlaying ? '#38BDF8' : 'rgba(56, 189, 248, 0.15)',
                                    color: isSpeakingPlaying ? '#090D16' : '#38BDF8',
                                    border: '1px solid rgba(56, 189, 248, 0.35)',
                                    cursor: 'pointer',
                                    fontSize: 12,
                                    fontWeight: 800,
                                    transition: 'all 0.2s ease',
                                  }}
                                >
                                  {isSpeakingPlaying ? <Pause size={14} /> : <Play size={14} />}
                                  <span>{isSpeakingPlaying ? "To'xtatish" : "Eshitish"}</span>
                                </button>
                                <span style={{ fontSize: 12, fontWeight: 700, color: '#38BDF8' }}>
                                  {SPEAKING_DEMO.duration}
                                </span>
                              </div>

                              {/* Equalizer bars */}
                              <div
                                style={{
                                  display: 'flex',
                                  alignItems: 'center',
                                  justifyContent: 'space-between',
                                  height: 32,
                                  gap: 3,
                                  padding: '0 4px',
                                }}
                              >
                                {[18, 24, 12, 28, 32, 20, 26, 30, 16, 22, 28, 14, 26, 32, 20, 15, 25, 29, 18].map(
                                  (h, idx) => (
                                    <div
                                      key={idx}
                                      className={`waveform-bar ${isSpeakingPlaying ? 'playing' : ''}`}
                                      style={{
                                        height: isSpeakingPlaying ? undefined : `${h * 0.75}px`,
                                        animationDelay: `${idx * 0.05}s`,
                                      }}
                                    />
                                  ),
                                )}
                              </div>
                            </div>

                            {/* 4-Criteria Score Grid */}
                            <div
                              style={{
                                display: 'grid',
                                gridTemplateColumns: 'repeat(4, 1fr)',
                                gap: 6,
                                marginBottom: 12,
                                textAlign: 'center',
                              }}
                            >
                              {[
                                { label: 'Fluency', val: SPEAKING_DEMO.scores.fluency, color: '#34D399' },
                                { label: 'Pronun.', val: SPEAKING_DEMO.scores.pronunciation, color: '#F59E0B' },
                                { label: 'Lexical', val: SPEAKING_DEMO.scores.lexical, color: '#38BDF8' },
                                { label: 'Grammar', val: SPEAKING_DEMO.scores.grammar, color: '#A78BFA' },
                              ].map((item) => (
                                <div
                                  key={item.label}
                                  style={{
                                    padding: '8px 4px',
                                    borderRadius: 10,
                                    background: 'var(--card-2)',
                                    border: '1px solid var(--border)',
                                  }}
                                >
                                  <div style={{ fontSize: 10, color: 'var(--muted)', fontWeight: 700 }}>{item.label}</div>
                                  <div style={{ fontSize: 15, fontWeight: 900, color: item.color, marginTop: 2 }}>
                                    {item.val.toFixed(1)}
                                  </div>
                                </div>
                              ))}
                            </div>

                            {/* AI Transcription & Feedback */}
                            <div
                              style={{
                                padding: '12px 14px',
                                borderRadius: 12,
                                background: 'rgba(56, 189, 248, 0.08)',
                                border: '1px solid rgba(56, 189, 248, 0.25)',
                                fontSize: 12,
                                color: 'var(--ink-soft)',
                                lineHeight: 1.5,
                                marginBottom: 16,
                              }}
                            >
                              <div style={{ fontSize: 11, fontWeight: 800, color: '#38BDF8', marginBottom: 4 }}>
                                🎙 AI Transkripsiya (Excerpt):
                              </div>
                              <p style={{ margin: '0 0 6px', fontStyle: 'italic', color: '#cbd5e1' }}>
                                "{SPEAKING_DEMO.transcript.slice(0, 160)}..."
                              </p>
                              <div style={{ fontSize: 11, color: '#94a3b8' }}>
                                {SPEAKING_DEMO.aiFeedback}
                              </div>
                            </div>

                            <button
                              type="button"
                              onClick={() => handleAction('/speaking')}
                              style={{
                                width: '100%',
                                padding: '11px',
                                borderRadius: 12,
                                background: 'rgba(56, 189, 248, 0.15)',
                                border: '1px solid rgba(56, 189, 248, 0.35)',
                                color: '#38BDF8',
                                fontSize: 13,
                                fontWeight: 800,
                                cursor: 'pointer',
                                transition: 'all 0.2s ease',
                              }}
                            >
                              🎙 Speaking trenajyorni sinash →
                            </button>
                          </div>
                        )}

                        {/* TAB 3: CBT READING & LISTENING */}
                        {demoTabEnglish === 'cbt' && (
                          <div>
                            <div
                              style={{
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'space-between',
                                fontSize: 12,
                                fontWeight: 700,
                                color: 'var(--muted)',
                                marginBottom: 12,
                              }}
                            >
                              <span style={{ color: '#10B981' }}>{ENGLISH_CBT_QUESTION.section}</span>
                              <span>⏱ 00:55</span>
                            </div>

                            <h4 style={{ fontSize: 14, fontWeight: 800, color: 'var(--ink)', margin: '0 0 16px', lineHeight: 1.5 }}>
                              {ENGLISH_CBT_QUESTION.question}
                            </h4>

                            {/* Choices */}
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 16 }}>
                              {ENGLISH_CBT_QUESTION.options.map((opt) => {
                                const isChosen = selectedOptionKeyEnglish === opt.key;
                                const isCorrect = opt.correct;
                                const showCorrectState = selectedOptionKeyEnglish !== null && isCorrect;
                                const showWrongState = isChosen && !isCorrect;

                                return (
                                  <button
                                    key={opt.key}
                                    type="button"
                                    onClick={() => handleCbtOptionClickEnglish(opt.key)}
                                    style={{
                                      display: 'flex',
                                      alignItems: 'center',
                                      justifyContent: 'space-between',
                                      width: '100%',
                                      padding: '10px 12px',
                                      borderRadius: 12,
                                      fontSize: 12,
                                      fontWeight: 700,
                                      cursor: 'pointer',
                                      textAlign: 'left',
                                      transition: 'all 0.2s ease',
                                      background: showCorrectState
                                        ? 'rgba(16, 185, 129, 0.2)'
                                        : showWrongState
                                        ? 'rgba(239, 68, 68, 0.2)'
                                        : 'var(--card-2)',
                                      border: `1px solid ${
                                        showCorrectState
                                          ? '#10B981'
                                          : showWrongState
                                          ? '#ef4444'
                                          : 'var(--border)'
                                      }`,
                                      color: showCorrectState
                                        ? '#34D399'
                                        : showWrongState
                                        ? '#f87171'
                                        : 'var(--ink)',
                                    }}
                                  >
                                    <span>
                                      <b>{opt.key})</b> {opt.text}
                                    </span>
                                    {showCorrectState && <span>✓ Correct</span>}
                                    {showWrongState && <span>✕ Incorrect</span>}
                                  </button>
                                );
                              })}
                            </div>

                            {/* Explanation */}
                            {selectedOptionKeyEnglish && (
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
                                <b style={{ color: '#10B981', display: 'block', marginBottom: 4 }}>💡 Key Explanation:</b>
                                {ENGLISH_CBT_QUESTION.explanation}
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
                              🎧 Cambridge CBT testini boshlash →
                            </button>
                          </div>
                        )}
                      </div>
                    )}
                  </motion.div>
                </AnimatePresence>
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
                {landingSubject === 'english' ? 'CAMBRIDGE & CEFR ECOSYSTEM' : t('features_main_eyebrow')}
              </span>
              <h2
                style={{
                  fontSize: 'clamp(1.8rem, 3.5vw, 2.5rem)',
                  fontWeight: 900,
                  color: 'var(--ink)',
                  margin: '12px 0',
                }}
              >
                {landingSubject === 'english' ? (
                  <>
                    IELTS & Multi-level imkoniyatlari{' '}
                    <span className="hero-title-gradient">bitta platformada</span>
                  </>
                ) : (
                  <>
                    {t('features_main_title_1')}{' '}
                    <span className="hero-title-gradient">{t('features_main_title_2')}</span>
                  </>
                )}
              </h2>
              <p style={{ fontSize: 15, color: 'var(--muted)', lineHeight: 1.6, margin: 0 }}>
                {landingSubject === 'english'
                  ? 'IELTS Band 7.5+ va Multi-level C1 darajasiga erishish uchun eng soʻnggi AI texnologiyalari.'
                  : t('features_main_subtitle')}
              </p>
            </div>

            {/* 3 Core Direction Cards Grid */}
            <AnimatePresence mode="wait">
              <motion.div
                key={landingSubject}
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
                {landingSubject === 'uzbek' ? (
                  <>
                    {/* Uzbek Card 1: AI Esse */}
                    <div
                      className="glass-card lcard-hover"
                      style={{
                        borderRadius: 24,
                        padding: '32px 28px',
                        display: 'flex',
                        flexDirection: 'column',
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
                          {t('feature_card_essay_badge')}
                        </span>
                      </div>

                      <h3 style={{ fontSize: 20, fontWeight: 900, color: 'var(--ink)', margin: '0 0 10px' }}>
                        {t('feature_card_essay_title')}
                      </h3>
                      <p style={{ fontSize: 14, color: 'var(--muted)', lineHeight: 1.65, margin: '0 0 20px', flex: 1 }}>
                        {t('feature_card_essay_desc')}
                      </p>

                      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 24, fontSize: 13, color: 'var(--ink-soft)' }}>
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
                      >
                        {t('feature_card_essay_action')}
                      </button>
                    </div>

                    {/* Uzbek Card 2: CBT Tests */}
                    <div
                      className="glass-card lcard-hover"
                      style={{
                        borderRadius: 24,
                        padding: '32px 28px',
                        display: 'flex',
                        flexDirection: 'column',
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
                          {t('feature_card_cbt_badge')}
                        </span>
                      </div>

                      <h3 style={{ fontSize: 20, fontWeight: 900, color: 'var(--ink)', margin: '0 0 10px' }}>
                        {t('feature_card_cbt_title')}
                      </h3>
                      <p style={{ fontSize: 14, color: 'var(--muted)', lineHeight: 1.65, margin: '0 0 20px', flex: 1 }}>
                        {t('feature_card_cbt_desc')}
                      </p>

                      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 24, fontSize: 13, color: 'var(--ink-soft)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#10B981' }} />
                          <span>{t('feature_card_cbt_bullet1')}</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#10B981' }} />
                          <span>{t('feature_card_cbt_bullet2')}</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#10B981' }} />
                          <span>{t('feature_card_cbt_bullet3')}</span>
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
                      >
                        {t('feature_card_cbt_action')}
                      </button>
                    </div>

                    {/* Uzbek Card 3: 1v1 Arena */}
                    <div
                      className="glass-card lcard-hover"
                      style={{
                        borderRadius: 24,
                        padding: '32px 28px',
                        display: 'flex',
                        flexDirection: 'column',
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
                          {t('feature_card_arena_badge')}
                        </span>
                      </div>

                      <h3 style={{ fontSize: 20, fontWeight: 900, color: 'var(--ink)', margin: '0 0 10px' }}>
                        {t('feature_card_arena_title')}
                      </h3>
                      <p style={{ fontSize: 14, color: 'var(--muted)', lineHeight: 1.65, margin: '0 0 20px', flex: 1 }}>
                        {t('feature_card_arena_desc')}
                      </p>

                      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 24, fontSize: 13, color: 'var(--ink-soft)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#A78BFA' }} />
                          <span>{t('feature_card_arena_bullet1')}</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#A78BFA' }} />
                          <span>{t('feature_card_arena_bullet2')}</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#A78BFA' }} />
                          <span>{t('feature_card_arena_bullet3')}</span>
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
                      >
                        {t('feature_card_arena_action')}
                      </button>
                    </div>
                  </>
                ) : (
                  <>
                    {/* English Card 1: IELTS Writing AI Grader */}
                    <div
                      className="glass-card lcard-hover"
                      style={{
                        borderRadius: 24,
                        padding: '32px 28px',
                        display: 'flex',
                        flexDirection: 'column',
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
                          IELTS Band 1.0–9.0
                        </span>
                      </div>

                      <h3 style={{ fontSize: 20, fontWeight: 900, color: 'var(--ink)', margin: '0 0 10px' }}>
                        IELTS Writing AI Grader (Task 1 & 2)
                      </h3>
                      <p style={{ fontSize: 14, color: 'var(--muted)', lineHeight: 1.65, margin: '0 0 20px', flex: 1 }}>
                        Rasmiy 4 ta mezon (TR, CC, LR, GRA) boʻyicha 15 soniyada toʻliq ekspertiza, ilgʻor akademik sinonimlar va aniq Band Score.
                      </p>

                      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 24, fontSize: 13, color: 'var(--ink-soft)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#F59E0B' }} />
                          <span>Task 1 (Grafik/Jadval) va Task 2 tahlili</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#F59E0B' }} />
                          <span>Band 8+ akademik kollokatsiyalar taklifi</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#F59E0B' }} />
                          <span>CEFR darajasi (B2, C1, C2) muvofiqligi</span>
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
                      >
                        Writing topshirish →
                      </button>
                    </div>

                    {/* English Card 2: AI Speaking Simulator */}
                    <div
                      className="glass-card lcard-hover"
                      style={{
                        borderRadius: 24,
                        padding: '32px 28px',
                        display: 'flex',
                        flexDirection: 'column',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
                        <div
                          style={{
                            width: 52,
                            height: 52,
                            borderRadius: 16,
                            background: 'rgba(56, 189, 248, 0.12)',
                            border: '1px solid rgba(56, 189, 248, 0.28)',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            color: '#38BDF8',
                            boxShadow: '0 0 20px rgba(56, 189, 248, 0.15)',
                          }}
                        >
                          <Mic size={26} />
                        </div>
                        <span
                          style={{
                            padding: '4px 10px',
                            borderRadius: 999,
                            fontSize: 11,
                            fontWeight: 800,
                            background: 'rgba(56, 189, 248, 0.15)',
                            color: '#38BDF8',
                            border: '1px solid rgba(56, 189, 248, 0.3)',
                          }}
                        >
                          Gemini Multimodal Speech AI
                        </span>
                      </div>

                      <h3 style={{ fontSize: 20, fontWeight: 900, color: 'var(--ink)', margin: '0 0 10px' }}>
                        AI Speaking Simulyatori
                      </h3>
                      <p style={{ fontSize: 14, color: 'var(--muted)', lineHeight: 1.65, margin: '0 0 20px', flex: 1 }}>
                        Part 1, Part 2 (Cue Card 1 daqiqa tayyorgarlik) va Part 3 savollariga ovozli javob bering. Talaffuz va ravonlik tahlili.
                      </p>

                      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 24, fontSize: 13, color: 'var(--ink-soft)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#38BDF8' }} />
                          <span>Jonli audio toʻlqin va aniq transkripsiya</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#38BDF8' }} />
                          <span>Talaffuz (Pronunciation) va ravonlik bahosi</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#38BDF8' }} />
                          <span>Grammatik tahrirlar va Band 8+ sinonimlar</span>
                        </div>
                      </div>

                      <button
                        type="button"
                        onClick={() => handleAction('/speaking')}
                        style={{
                          width: '100%',
                          padding: '12px',
                          borderRadius: 12,
                          background: 'rgba(56, 189, 248, 0.15)',
                          border: '1px solid rgba(56, 189, 248, 0.35)',
                          color: '#38BDF8',
                          fontWeight: 800,
                          fontSize: 14,
                          cursor: 'pointer',
                          transition: 'all 0.2s ease',
                        }}
                      >
                        Speakingni sinash →
                      </button>
                    </div>

                    {/* English Card 3: Cambridge CBT Reading & Listening */}
                    <div
                      className="glass-card lcard-hover"
                      style={{
                        borderRadius: 24,
                        padding: '32px 28px',
                        display: 'flex',
                        flexDirection: 'column',
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
                          <Headphones size={26} />
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
                          Cambridge CBT Standard
                        </span>
                      </div>

                      <h3 style={{ fontSize: 20, fontWeight: 900, color: 'var(--ink)', margin: '0 0 10px' }}>
                        CBT Reading & Listening
                      </h3>
                      <p style={{ fontSize: 14, color: 'var(--muted)', lineHeight: 1.65, margin: '0 0 20px', flex: 1 }}>
                        Rasmiy British Council va IDP kompyuterlashtirilgan formati. Audio boshqaruvi, interaktiv savollar va lahzalik aniq Band.
                      </p>

                      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 24, fontSize: 13, color: 'var(--ink-soft)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#10B981' }} />
                          <span>Haqiqiy Cambridge test formatlari</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#10B981' }} />
                          <span>Audio pleer va interaktiv skript matni</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <CheckIcon size={16} style={{ color: '#10B981' }} />
                          <span>Tezkor xatolar ustida ishlash rejimi</span>
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
                      >
                        CBT Testni boshlash →
                      </button>
                    </div>
                  </>
                )}
              </motion.div>
            </AnimatePresence>
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
                      <p style={{ margin: 0, fontSize: 22, fontWeight: 900, color: 'var(--ink)' }}>
                        {Number(item.value).toLocaleString()}
                      </p>
                      <p style={{ margin: '2px 0 0', fontSize: 12, fontWeight: 600, color: 'var(--muted)' }}>
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
        <HowItWorks />
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
                    <b style={{ display: 'block', fontSize: 16, color: 'var(--ink)' }}>GRAND EDUCATION</b>
                    <small style={{ fontSize: 9, fontWeight: 700, letterSpacing: '0.2em', color: '#F59E0B' }}>
                      LMS PLATFORM
                    </small>
                  </div>
                </div>
                <p style={{ fontSize: 14, lineHeight: 1.7, color: 'var(--muted)', marginTop: 16 }}>
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
                      <a href={href} style={{ color: 'var(--muted)', textDecoration: 'none' }}>
                        {t(k)}
                      </a>
                    </li>
                  ))}
                  <li>
                    <button
                      type="button"
                      onClick={() => openAuthModal('login')}
                      style={{ background: 'none', border: 'none', color: 'var(--muted)', cursor: 'pointer', padding: 0, fontSize: 14 }}
                    >
                      {t('login')}
                    </button>
                  </li>
                  <li>
                    <button
                      type="button"
                      onClick={() => openAuthModal('register')}
                      style={{ background: 'none', border: 'none', color: 'var(--muted)', cursor: 'pointer', padding: 0, fontSize: 14 }}
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
                <p style={{ fontSize: 14, lineHeight: 1.7, color: 'var(--muted)', margin: '0 0 14px' }}>
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
                        background: 'var(--card-2)',
                        border: '1px solid var(--border)',
                        color: 'var(--ink)',
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
                  <li style={{ display: 'flex', alignItems: 'center', gap: 10, color: 'var(--muted)' }}>
                    <ClockIcon size={18} style={{ color: '#F59E0B' }} />
                    <span>{t('foot_ai_24_7')}</span>
                  </li>
                  <li style={{ display: 'flex', alignItems: 'center', gap: 10, color: 'var(--muted)' }}>
                    <MapPinIcon size={18} style={{ color: '#F59E0B' }} />
                    <span>{t('foot_location')}</span>
                  </li>
                </ul>
              </div>
            </div>

            <div
              style={{
                marginTop: 44,
                paddingTop: 24,
                borderTop: '1px solid var(--border)',
                display: 'flex',
                flexWrap: 'wrap',
                justifyContent: 'space-between',
                gap: 12,
                fontSize: 13,
                color: 'var(--muted)',
              }}
            >
              <span>© {new Date().getFullYear()} GRAND EDUCATION (grandec.uz). {t('foot_rights')}</span>
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
        @keyframes wavePulse {
          0%, 100% { height: 6px; }
          50% { height: 26px; }
        }
        .waveform-bar {
          width: 4px;
          border-radius: 999px;
          background: #38BDF8;
          transition: height 0.15s ease;
        }
        .waveform-bar.playing {
          animation: wavePulse 0.8s ease-in-out infinite;
        }
        .hero-subject-switcher {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          background: var(--card-2);
          padding: 6px;
          border-radius: 18px;
          border: 1px solid var(--border);
          box-shadow: 0 8px 32px rgba(0, 0, 0, 0.25);
          backdrop-filter: blur(12px);
          -webkit-backdrop-filter: blur(12px);
        }
        .hero-switcher-btn {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          padding: 10px 18px;
          border-radius: 14px;
          border: 1px solid transparent;
          cursor: pointer;
          font-size: 14px;
          font-weight: 700;
          color: var(--muted);
          background: transparent;
          transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
        }
        .hero-switcher-btn:hover {
          color: var(--ink);
          background: rgba(255, 255, 255, 0.04);
        }
        .hero-switcher-btn.active {
          background: linear-gradient(135deg, #F59E0B, #FBBF24);
          color: #090D16;
          font-weight: 800;
          box-shadow: 0 4px 16px rgba(245, 158, 11, 0.35);
        }
        .switcher-subtag {
          font-size: 11px;
          font-weight: 800;
          padding: 2px 7px;
          border-radius: 6px;
          background: rgba(0, 0, 0, 0.12);
          color: inherit;
          opacity: 0.9;
        }
        .hero-switcher-btn:not(.active) .switcher-subtag {
          background: rgba(255, 255, 255, 0.08);
          color: var(--muted);
        }
        @media (max-width: 640px) {
          .hero-subject-switcher {
            width: 100%;
            flex-direction: column;
            gap: 4px;
          }
          .hero-switcher-btn {
            width: 100%;
            justify-content: center;
            padding: 10px 14px;
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
