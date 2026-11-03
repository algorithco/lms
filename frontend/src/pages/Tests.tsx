import MockCodeCard from '../components/MockCodeCard';
import TestCatalog from '../components/TestCatalog';
import { useEffect, useMemo, useState } from 'react';
import LimitExceededModal from '../components/LimitExceededModal';
import { useAuth } from '../auth/AuthContext';
import { Link, useNavigate } from 'react-router-dom';
import { useLang } from '../i18n/LangContext';
import { api, MockTests, Billing, type BillingEntitlement, type Paginated } from '../lib/api';
import { listTestsPage, num, type TestListItem } from '../lib/testing';
import { paywallSubject, type PaywallSubject } from '../lib/paywall';
import { ClockIcon, HashIcon } from '../components/icons';

const PAGE_SIZE = 20;

function getCleanTestTitle(rawTitle: string | null | undefined, subject?: string): string {
  if (!rawTitle) return subject === 'english' ? 'English CBT Mock Exam' : 'Ona tili va Adabiyot — Rasmiy BMB Diagnostika';
  let s = String(rawTitle).trim();
  s = s.replace(/#?MOCK-[A-Z0-9_-]+/gi, '').trim();
  s = s.replace(/^[-–—:() ]+|[-–—:() ]+$/g, '').trim();
  if (!s) return subject === 'english' ? 'English CBT Mock Exam' : 'Ona tili va Adabiyot — Rasmiy BMB Diagnostika';
  return s;
}

export default function Tests() {
  const { t } = useLang();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [entitlement, setEntitlement] = useState<BillingEntitlement | null>(null);
  const [limitModalOpen, setLimitModalOpen] = useState(false);
  const [limitModalMsg, setLimitModalMsg] = useState<string | undefined>();
  const [limitSubject, setLimitSubject] = useState<PaywallSubject | undefined>();

  useEffect(() => {
    Billing.entitlement().then(setEntitlement).catch(() => setEntitlement(null));
  }, []);

  const isFreeUser = user?.role === 'student' && (!entitlement || (!entitlement.is_paid && !entitlement.is_sponsored && entitlement.source !== 'override'));
  const isTeacherOrAdmin = user?.role === 'admin' || user?.role === 'teacher' || user?.role === 'center_admin';
  const [tests, setTests] = useState<TestListItem[]>([]);
  const [count, setCount] = useState(0);
  const [page, setPage] = useState(1);
  const [hasNext, setHasNext] = useState(false);
  const [hasPrev, setHasPrev] = useState(false);
  const [query, setQuery] = useState('');
  const [difficulty, setDifficulty] = useState('');
  const [categoryFilter, setCategoryFilter] = useState<'all' | 'milliy' | 'adabiyot' | 'attestatsiya' | 'arena' | 'ielts' | 'multilevel'>('all');
  const [catalogSubject, setCatalogSubject] = useState<'all' | 'ona_tili' | 'adabiyot' | 'english' | 'attestatsiya'>('all');
  const [activeSub, setActiveSub] = useState<'uzbek' | 'english'>(() => {
    return (localStorage.getItem('lms_subject') as 'uzbek' | 'english') || 'uzbek';
  });
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // Quick Mock Join
  const [mockBusy, setMockBusy] = useState(false);
  const [mockErr, setMockErr] = useState<string | null>(null);

  const formatMockError = (e2: unknown): string => {
    if (e2 instanceof Error) {
      try {
        const parsed = JSON.parse(e2.message);
        if (parsed && typeof parsed.error === 'string') return parsed.error;
        if (parsed && typeof parsed.detail === 'string') return parsed.detail;
      } catch {
        // Not a JSON string
      }
      return e2.message;
    }
    return t('mockcode_not_found');
  };

  const executeJoin = async (code: string) => {
    const raw = code.trim();
    if (!raw) {
      setMockErr(t('mockcode_empty'));
      return;
    }
    setMockBusy(true);
    setMockErr(null);
    try {
      const res = await MockTests.join(raw);
      if (res && res.attempt_id) {
        navigate(`/take/${res.attempt_id}`);
      } else if (res && res.test_id) {
        navigate(`/tests/${res.test_id}`);
      }
    } catch (e2) {
      setMockErr(formatMockError(e2));
    } finally {
      setMockBusy(false);
    }
  };

  const [subjectTick, setSubjectTick] = useState(0);

  useEffect(() => {
    const handler = (e: Event) => {
      const customEvent = e as CustomEvent<'uzbek' | 'english'>;
      const next = customEvent.detail || (localStorage.getItem('lms_subject') as 'uzbek' | 'english') || 'uzbek';
      setActiveSub(next);
      setCategoryFilter('all');
      setPage(1);
      setSubjectTick((v) => v + 1);
    };
    window.addEventListener('subject-changed', handler);
    return () => window.removeEventListener('subject-changed', handler);
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setErr(null);
    listTestsPage(page, activeSub)
      .then((p: Paginated<TestListItem>) => {
        if (cancelled) return;
        setTests(p.results ?? []);
        setCount(p.count ?? (p.results ?? []).length);
        setHasNext(Boolean(p.next));
        setHasPrev(Boolean(p.previous));
      })
      .catch((e: unknown) => {
        if (!cancelled) setErr(e instanceof Error ? e.message : t('err_retry_js'));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, activeSub, subjectTick]);

  const isEnglishTest = (item: TestListItem) => {
    const title = String(item.title ?? '').toLowerCase();
    const course = String(item.course_title ?? '').toLowerCase();
    const mock = String(item.mock_code ?? '').toLowerCase();
    const subj = String((item as Record<string, unknown>).subject ?? '').toLowerCase();
    return (
      subj === 'english' ||
      title.includes('ielts') ||
      title.includes('multi-level') ||
      title.includes('cefr') ||
      course.includes('ielts') ||
      mock.includes('ielts')
    );
  };

  const isIeltsTest = (item: TestListItem) => {
    const title = String(item.title ?? '').toLowerCase();
    const course = String(item.course_title ?? '').toLowerCase();
    const mock = String(item.mock_code ?? '').toLowerCase();
    return title.includes('ielts') || course.includes('ielts') || mock.includes('ielts');
  };

  const isMultiLevelTest = (item: TestListItem) => {
    const title = String(item.title ?? '').toLowerCase();
    const course = String(item.course_title ?? '').toLowerCase();
    return title.includes('multi-level') || title.includes('cefr') || course.includes('multi-level');
  };

  const isMockAttest = (item: TestListItem) =>
    item.mock_code === '#MOCK-ATTEST2026' ||
    item.mock_code === 'MOCK-ATTEST2026' ||
    item.category_slug === 'attestatsiya' ||
    String(item.title ?? '').toLowerCase().includes('attestatsiya');

  const isMock4 = (item: TestListItem) =>
    item.mock_code === '#MOCK-BMB04' ||
    String(item.title ?? '').toLowerCase().includes('mock #4') ||
    String(item.title ?? '').toLowerCase().includes('mock 4');

  const isMockBmbDiag = (item: TestListItem) =>
    item.mock_code === '#MOCK-BMB-DIAGNOSTIC' ||
    item.mock_code === 'MOCK-BMB-DIAGNOSTIC' ||
    item.mock_code === '#MOCK-SHUKUROV' ||
    item.mock_code === 'MOCK-SHUKUROV' ||
    String(item.title ?? '').toLowerCase().includes('shukurov') ||
    String(item.title ?? '').toLowerCase().includes('bmb rasmiy mock');

  const isAdabiyotTest = (item: TestListItem) => {
    const title = String(item.title ?? '').toLowerCase();
    const course = String(item.course_title ?? '').toLowerCase();
    return title.includes('adabiyot') || course.includes('adabiyot') || title.includes('15') || title.includes('mumtoz');
  };

  // Client-side search and category filtering
  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    const filtered = tests.filter((item) => {
      const title = String(item.title ?? '').toLowerCase();
      const course = String(item.course_title ?? '').toLowerCase();
      const matchSearch = !q || title.includes(q) || course.includes(q);
      const matchDiff = !difficulty || String(item.difficulty ?? '') === difficulty;
      if (!matchSearch || !matchDiff) return false;

      // Strict subject segregation
      const isEng = isEnglishTest(item);
      if (activeSub === 'uzbek' && isEng) return false;
      if (activeSub === 'english' && !isEng) return false;

      if (activeSub === 'english') {
        if (categoryFilter === 'ielts') return isIeltsTest(item);
        if (categoryFilter === 'multilevel') return isMultiLevelTest(item);
        return true;
      }

      if (categoryFilter === 'adabiyot') {
        return isAdabiyotTest(item);
      }
      if (categoryFilter === 'attestatsiya') {
        return isMockAttest(item);
      }
      if (categoryFilter === 'milliy') {
        return (
          isMock4(item) ||
          isMockBmbDiag(item) ||
          item.category_slug === 'milliy-sertifikat' ||
          title.includes('milliy') ||
          course.includes('milliy')
        );
      }
      if (categoryFilter === 'arena') {
        return false;
      }
      return true;
    });

    return [...filtered].sort((a, b) => {
      const aWeight = isMockAttest(a) ? 3 : isMockBmbDiag(a) ? 2 : isMock4(a) ? 1 : 0;
      const bWeight = isMockAttest(b) ? 3 : isMockBmbDiag(b) ? 2 : isMock4(b) ? 1 : 0;
      return bWeight - aWeight;
    });
  }, [tests, query, difficulty, categoryFilter, activeSub]);

  const totalPages = Math.max(1, Math.ceil(count / PAGE_SIZE));
  const handleCatalogSelect = (track: 'ona_tili' | 'adabiyot' | 'english' | 'attestatsiya') => {
    if (catalogSubject === track) {
      setCatalogSubject('all');
      setCategoryFilter('all');
      setQuery('');
      return;
    }
    setCatalogSubject(track);
    if (track === 'ona_tili') {
      setActiveSub('uzbek');
      setCategoryFilter('milliy');
      setQuery('');
      localStorage.setItem('lms_subject', 'uzbek');
      window.dispatchEvent(new CustomEvent('subject-changed', { detail: 'uzbek' }));
    } else if (track === 'adabiyot') {
      setActiveSub('uzbek');
      setCategoryFilter('adabiyot');
      setQuery('');
      localStorage.setItem('lms_subject', 'uzbek');
      window.dispatchEvent(new CustomEvent('subject-changed', { detail: 'uzbek' }));
    } else if (track === 'english') {
      setActiveSub('english');
      setCategoryFilter('all');
      setQuery('');
      localStorage.setItem('lms_subject', 'english');
      window.dispatchEvent(new CustomEvent('subject-changed', { detail: 'english' }));
    } else if (track === 'attestatsiya') {
      setActiveSub('uzbek');
      setCategoryFilter('attestatsiya');
      setQuery('');
      localStorage.setItem('lms_subject', 'uzbek');
      window.dispatchEvent(new CustomEvent('subject-changed', { detail: 'uzbek' }));
    }
  };


  const retry = async () => {
    setErr(null);
    setLoading(true);
    try {
      const p = await api<Paginated<TestListItem>>(`/api/tests/?page=${page}`);
      setTests(p.results ?? []);
      setCount(p.count ?? 0);
      setHasNext(Boolean(p.next));
      setHasPrev(Boolean(p.previous));
    } catch (e) {
      setErr(e instanceof Error ? e.message : t('err_retry_js'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12, marginBottom: 12 }}>
        <div>
          <h1 style={{ margin: 0 }}>
            {t('tests')}{err ? '' : ` (${count})`}
          </h1>
          <p className="muted" style={{ margin: '4px 0 0' }}>{t('available_tests_hint')}</p>
        </div>
        {isTeacherOrAdmin && (
          <Link
            to="/tests/create"
            style={{
              background: 'linear-gradient(135deg, #F59E0B 0%, #D97706 100%)',
              color: '#FFFFFF',
              fontWeight: 800,
              fontSize: 13.5,
              padding: '10px 18px',
              borderRadius: 12,
              textDecoration: 'none',
              display: 'inline-flex',
              alignItems: 'center',
              gap: 8,
              boxShadow: '0 4px 14px rgba(217, 119, 6, 0.3)',
            }}
          >
            <span>✍️</span> + Yangi test yaratish (Smart Paste)
          </Link>
        )}
      </div>

      <TestCatalog
        selected={catalogSubject}
        onSelect={handleCatalogSelect}
        onClear={() => {
          setCatalogSubject('all');
          setCategoryFilter('all');
          setQuery('');
        }}
      />

      <MockCodeCard
        subject={activeSub}
        busy={mockBusy}
        error={mockErr}
        onJoin={(code) => void executeJoin(code)}
        onEdit={() => mockErr && setMockErr(null)}
      />

      {/* 🏷 Toifalar Bo'limi (Category Filter) */}
      <div
        style={{
          display: 'flex',
          gap: 8,
          marginBottom: 16,
          flexWrap: 'wrap',
          alignItems: 'center',
        }}
      >
        {activeSub === 'english' ? (
          <>
            <button
              type="button"
              className={`btn sm ${categoryFilter === 'all' ? 'primary' : 'ghost'}`}
              onClick={() => setCategoryFilter('all')}
              style={{ borderRadius: 20, padding: '6px 16px', fontWeight: 700 }}
            >
              🌐 All Tests
            </button>
            <button
              type="button"
              className={`btn sm ${categoryFilter === 'ielts' ? 'primary' : 'ghost'}`}
              onClick={() => setCategoryFilter('ielts')}
              style={{
                borderRadius: 20,
                padding: '6px 16px',
                fontWeight: 700,
                borderColor: categoryFilter === 'ielts' ? '#f59e0b' : undefined,
                background: categoryFilter === 'ielts' ? 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)' : undefined,
                color: categoryFilter === 'ielts' ? '#0f172a' : undefined,
                boxShadow: categoryFilter === 'ielts' ? '0 0 12px rgba(245, 158, 11, 0.4)' : undefined,
              }}
            >
              🎓 IELTS (Academic & General)
            </button>
            <button
              type="button"
              className={`btn sm ${categoryFilter === 'multilevel' ? 'primary' : 'ghost'}`}
              onClick={() => setCategoryFilter('multilevel')}
              style={{
                borderRadius: 20,
                padding: '6px 16px',
                fontWeight: 700,
                borderColor: categoryFilter === 'multilevel' ? '#10b981' : undefined,
                background: categoryFilter === 'multilevel' ? 'linear-gradient(135deg, #10b981 0%, #059669 100%)' : undefined,
                color: categoryFilter === 'multilevel' ? '#0f172a' : undefined,
                boxShadow: categoryFilter === 'multilevel' ? '0 0 12px rgba(16, 185, 129, 0.4)' : undefined,
              }}
            >
              🎯 CEFR Multi-level (B2/C1)
            </button>
          </>
        ) : (
          <>
            <button
              type="button"
              className={`btn sm ${categoryFilter === 'all' ? 'primary' : 'ghost'}`}
              onClick={() => setCategoryFilter('all')}
              style={{ borderRadius: 20, padding: '6px 16px', fontWeight: 700 }}
            >
              🌐 Barchasi
            </button>
            <button
              type="button"
              className={`btn sm ${categoryFilter === 'milliy' ? 'primary' : 'ghost'}`}
              onClick={() => setCategoryFilter('milliy')}
              style={{ borderRadius: 20, padding: '6px 16px', fontWeight: 700 }}
            >
              📜 Milliy Sertifikat
            </button>
            <button
              type="button"
              className={`btn sm ${categoryFilter === 'attestatsiya' ? 'primary' : 'ghost'}`}
              onClick={() => setCategoryFilter('attestatsiya')}
              style={{
                borderRadius: 20,
                padding: '6px 16px',
                fontWeight: 700,
                borderColor: categoryFilter === 'attestatsiya' ? '#8b5cf6' : undefined,
                background: categoryFilter === 'attestatsiya' ? 'linear-gradient(135deg, #8b5cf6 0%, #6d28d9 100%)' : undefined,
                color: categoryFilter === 'attestatsiya' ? '#fff' : undefined,
                boxShadow: categoryFilter === 'attestatsiya' ? '0 0 12px rgba(139, 92, 246, 0.4)' : undefined,
              }}
            >
              🎓 Attestatsiya (Ustozlar uchun)
            </button>
            <button
              type="button"
              className={`btn sm ${categoryFilter === 'arena' ? 'primary' : 'ghost'}`}
              onClick={() => setCategoryFilter('arena')}
              style={{
                borderRadius: 20,
                padding: '6px 16px',
                fontWeight: 700,
                borderColor: categoryFilter === 'arena' ? '#f59e0b' : undefined,
                background: categoryFilter === 'arena' ? 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)' : undefined,
                color: categoryFilter === 'arena' ? '#111' : undefined,
                boxShadow: categoryFilter === 'arena' ? '0 0 12px rgba(245, 158, 11, 0.4)' : undefined,
              }}
            >
              ⚔️ 1v1 Arena
            </button>
          </>
        )}
      </div>

      {categoryFilter === 'arena' && (
        <div
          className="card"
          style={{
            background: 'radial-gradient(circle at top right, rgba(245, 158, 11, 0.15) 0%, rgba(15, 23, 42, 0.8) 100%)',
            border: '1.5px solid rgba(245, 158, 11, 0.6)',
            borderRadius: '16px',
            padding: '24px',
            marginBottom: '20px',
            textAlign: 'center',
          }}
        >
          <span style={{ fontSize: '3rem', display: 'block', marginBottom: '8px' }}>⚔️</span>
          <h2 style={{ color: '#f59e0b', margin: '0 0 8px' }}>1v1 Real-Vaqt Bilimlar Arenasi</h2>
          <p className="muted" style={{ maxWidth: 600, margin: '0 auto 16px', fontSize: '0.95rem' }}>
            Boshqa o‘qituvchilar va abituriyentlar bilan real-vaqt rejimida 1v1 tezkor test jangida bellashing, tajriba to‘plang va milliy reytingingizni oshiring!
          </p>
          <button
            type="button"
            className="btn primary"
            style={{
              background: 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)',
              color: '#111',
              fontWeight: 800,
              padding: '10px 24px',
              borderRadius: '10px',
              fontSize: '1rem',
            }}
            onClick={() => navigate('/arena')}
          >
            🚀 Arenaga kirish va duel boshlash →
          </button>
        </div>
      )}

      <div className="toolbar" style={{ marginBottom: 16 }}>
        <input
          type="search"
          placeholder={t('test_search_ph')}
          aria-label={t('search')}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <select
          aria-label={t('difficulty')}
          value={difficulty}
          onChange={(e) => setDifficulty(e.target.value)}
        >
          <option value="">{t('test_filter_all_diff')}</option>
          <option value="easy">Oson</option>
          <option value="medium">O&apos;rtacha</option>
          <option value="hard">Qiyin</option>
        </select>
      </div>

      {loading && <p className="muted">{t('loading')}</p>}
      {err && (
        <p className="error">
          {err}{' '}
          <button className="btn sm ghost" onClick={retry}>
            {t('essay_error_retry')}
          </button>
        </p>
      )}

      {!loading && !err && tests.length === 0 && (
        <div
          className="card"
          style={{
            padding: '48px 24px',
            textAlign: 'center',
            maxWidth: 620,
            margin: '36px auto',
            borderRadius: 24,
            background: 'linear-gradient(180deg, rgba(30, 41, 59, 0.45) 0%, rgba(15, 23, 42, 0.6) 100%)',
            border: '1px solid rgba(148, 163, 184, 0.15)',
            boxShadow: '0 20px 40px -15px rgba(0, 0, 0, 0.4)',
          }}
        >
          <div
            style={{
              width: 76,
              height: 76,
              margin: '0 auto 18px',
              borderRadius: '50%',
              background: 'linear-gradient(135deg, rgba(2, 132, 199, 0.15), rgba(56, 189, 248, 0.05))',
              border: '2px solid rgba(56, 189, 248, 0.35)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 34,
              boxShadow: '0 0 25px rgba(56, 189, 248, 0.2)',
            }}
          >
            {activeSub === 'english' ? '🎧' : '📚'}
          </div>
          <h3
            style={{
              fontSize: '20px',
              fontWeight: 800,
              margin: '0 0 8px',
              color: 'var(--ink, #f8fafc)',
            }}
          >
            {activeSub === 'english' ? '🎧 CBT Reading & Listening Testlar' : (t('no_tests_title') || 'Testlar mavjud emas')}
          </h3>
          <p
            className="muted"
            style={{
              fontSize: '14px',
              lineHeight: 1.6,
              maxWidth: 480,
              margin: '0 auto 20px',
              color: '#94a3b8',
            }}
          >
            {activeSub === 'english'
              ? 'Hozircha ochiq CBT testlar tayyorlanmoqda. Yuqoridagi "English CBT Mock & Exam Access" maydoniga o\'qituvchingiz bergan test kodini kiritib testni boshlashingiz mumkin.'
              : (t('no_tests_hint') || "Ayni paytda faol testlar topilmadi. Tez orada yangi testlar joylanadi.")}
          </p>
          <button
            type="button"
            className="btn"
            onClick={() => void retry()}
            style={{
              padding: '10px 24px',
              borderRadius: 12,
              fontWeight: 600,
              fontSize: 14,
            }}
          >
            🔄 Qayta yuklash
          </button>
        </div>
      )}

      {!loading && !err && tests.length > 0 && visible.length === 0 && (
        <div
          className="card"
          style={{
            padding: '36px 20px',
            textAlign: 'center',
            maxWidth: 520,
            margin: '28px auto',
            borderRadius: 18,
            background: 'rgba(30, 41, 59, 0.35)',
            border: '1px solid rgba(148, 163, 184, 0.12)',
          }}
        >
          <div style={{ fontSize: 32, marginBottom: 12 }}>🔍</div>
          <h4 style={{ margin: '0 0 6px', fontSize: '16px', fontWeight: 700, color: 'var(--ink, #f8fafc)' }}>
            Mos keluvchi testlar topilmadi
          </h4>
          <p className="muted" style={{ margin: '0 0 16px', fontSize: '14px', color: '#94a3b8' }}>
            {t('test_no_match') || "Qidiruv yoki filtr mezonlariga mos keladigan test mavjud emas."}
          </p>
          <button
            type="button"
            className="btn"
            onClick={() => {
              setQuery('');
              setCategoryFilter('all');
            }}
            style={{
              padding: '8px 20px',
              borderRadius: 10,
              fontSize: '13px',
              fontWeight: 600,
            }}
          >
            Filtrni tozalash
          </button>
        </div>
      )}

      <div className="grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '20px' }}>
        {visible.map((item) => {
          const isAttest = isMockAttest(item);
          const isBmbDiag = isMockBmbDiag(item);
          const isM4 = isMock4(item);
          const cleanTitle = getCleanTestTitle(item.title, item.subject);
          const isDiagnostic = isBmbDiag || (item.title && item.title.toLowerCase().includes('diagnostic'));
          const isLocked = isFreeUser && !isDiagnostic && (isAttest || isM4 || (item.title && item.title.toLowerCase().includes('#mock')));
          const timeLimit = item.time_limit_minutes && item.time_limit_minutes > 0 ? item.time_limit_minutes : 180;
          const questionsCount = num(item.total_questions, 45);
          const passPct = num(item.pass_percentage, 60);

          return (
            <Link
              key={item.id}
              to={`/tests/${item.id}`}
              onClick={(e) => {
                if (isLocked) {
                  e.preventDefault();
                  setLimitModalMsg(t('paywall_reason_mock_locked'));
                  setLimitSubject(paywallSubject(item));
                  setLimitModalOpen(true);
                }
              }}
              className="card link-card"
              style={{
                borderRadius: '18px',
                background: 'var(--card)',
                border: isAttest
                  ? '1.5px solid rgba(139, 92, 246, 0.4)'
                  : isBmbDiag
                  ? '1.5px solid rgba(217, 119, 6, 0.4)'
                  : isM4
                  ? '1.5px solid rgba(16, 185, 129, 0.4)'
                  : '1px solid var(--border)',
                boxShadow: isAttest
                  ? '0 6px 22px rgba(139, 92, 246, 0.07)'
                  : isBmbDiag
                  ? '0 6px 22px rgba(217, 119, 6, 0.07)'
                  : 'var(--card-shadow)',
                padding: '22px',
                display: 'flex',
                flexDirection: 'column',
                gap: 12,
                transition: 'all 0.2s ease',
              }}
            >
              {/* Top Tags: Subject & Category */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                <span
                  style={{
                    background: item.subject === 'english' ? 'rgba(2, 132, 199, 0.1)' : 'rgba(5, 150, 105, 0.1)',
                    color: item.subject === 'english' ? '#0284C7' : '#059669',
                    fontSize: '0.74rem',
                    fontWeight: 800,
                    padding: '3px 10px',
                    borderRadius: '999px',
                  }}
                >
                  {item.subject === 'english' ? 'Ingliz tili' : 'Ona tili va Adabiyot'}
                </span>

                {isAttest ? (
                  <span
                    style={{
                      background: 'rgba(139, 92, 246, 0.12)',
                      color: '#7C3AED',
                      fontSize: '0.74rem',
                      fontWeight: 800,
                      padding: '3px 10px',
                      borderRadius: '999px',
                    }}
                  >
                    🎓 Attestatsiya
                  </span>
                ) : isBmbDiag || isM4 ? (
                  <span
                    style={{
                      background: 'rgba(217, 119, 6, 0.12)',
                      color: '#B45309',
                      fontSize: '0.74rem',
                      fontWeight: 800,
                      padding: '3px 10px',
                      borderRadius: '999px',
                    }}
                  >
                    🔥 Rasmiy BMB
                  </span>
                ) : null}

                {isLocked ? (
                  <span
                    style={{
                      background: 'rgba(239, 68, 68, 0.12)',
                      color: '#DC2626',
                      fontSize: '0.74rem',
                      fontWeight: 800,
                      padding: '3px 10px',
                      borderRadius: '999px',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 4,
                    }}
                  >
                    <span>🔒 Qulflangan (Faqat obunachilar uchun)</span>
                  </span>
                ) : isDiagnostic ? (
                  <span
                    style={{
                      background: 'rgba(16, 185, 129, 0.12)',
                      color: '#059669',
                      fontSize: '0.74rem',
                      fontWeight: 800,
                      padding: '3px 10px',
                      borderRadius: '999px',
                    }}
                  >
                    ✅ 1 ta Bepul Sinov
                  </span>
                ) : null}

                {item.audio_url && (
                  <span style={{ background: 'rgba(59, 130, 246, 0.1)', color: '#2563EB', padding: '3px 8px', borderRadius: '6px', fontSize: '0.72rem', fontWeight: 700 }}>
                    🎧 Audio
                  </span>
                )}
              </div>

              {/* Title */}
              <strong style={{ fontSize: '1.08rem', color: 'var(--ink)', lineHeight: 1.35, fontWeight: 800 }}>
                {cleanTitle}
              </strong>

              {item.description && (
                <span style={{ fontSize: '0.84rem', color: 'var(--muted)', lineHeight: 1.5 }}>
                  {String(item.description).slice(0, 110)}
                </span>
              )}

              {/* Metadata Badges: Duration, Questions, Pass mark */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginTop: 4 }}>
                <span
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 5,
                    fontSize: '0.76rem',
                    fontWeight: 700,
                    color: '#B45309',
                    background: 'rgba(245, 158, 11, 0.1)',
                    padding: '3px 9px',
                    borderRadius: '8px',
                  }}
                >
                  <ClockIcon size={12} /> {timeLimit} daqiqa
                </span>

                <span
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 5,
                    fontSize: '0.76rem',
                    fontWeight: 700,
                    color: 'var(--ink-soft)',
                    background: 'var(--card-2)',
                    padding: '3px 9px',
                    borderRadius: '8px',
                  }}
                >
                  <HashIcon size={12} /> {t('omr_questions_count').replace('{n}', String(questionsCount))}
                </span>

                <span
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 5,
                    fontSize: '0.76rem',
                    fontWeight: 700,
                    color: '#059669',
                    background: 'rgba(16, 185, 129, 0.1)',
                    padding: '3px 9px',
                    borderRadius: '8px',
                  }}
                >
                  🎯{' '}
                  {item.cefr_scale
                    ? t('cefr_pass_rule')
                        .replace('{level}', item.cefr_scale.level)
                        .replace('{min}', String(item.cefr_scale.min))
                        .replace('{max}', String(item.cefr_scale.scale_max))
                    : `${t('test_pass_mark')}: ${passPct}%`}
                </span>
              </div>

              {/* Bottom Action Button */}
              <div style={{ marginTop: 'auto', paddingTop: 10 }}>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <div
                    style={{
                      flex: 1,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: 6,
                      padding: '10px 14px',
                      borderRadius: '12px',
                      color: '#FFFFFF',
                      fontWeight: 800,
                      fontSize: '0.85rem',
                      background: isLocked ? '#64748B' : 'linear-gradient(135deg, #F59E0B, #D97706)',
                      boxShadow: isLocked ? 'none' : '0 4px 14px rgba(217, 119, 6, 0.25)',
                    }}
                  >
                    <span>{isLocked ? '🔒 Qulflangan (Tarif kerak)' : 'Testni boshlash →'}</span>
                  </div>
                  {isTeacherOrAdmin && (
                    <button
                      type="button"
                      onClick={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        navigate(`/tests/${item.id}/gradebook`);
                      }}
                      title="Natijalar vedomostini ko'rish"
                      style={{
                        padding: '10px 14px',
                        borderRadius: '12px',
                        background: 'rgba(245, 158, 11, 0.15)',
                        border: '1px solid rgba(245, 158, 11, 0.4)',
                        color: '#D97706',
                        fontWeight: 800,
                        fontSize: '0.82rem',
                        cursor: 'pointer',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 4,
                        whiteSpace: 'nowrap',
                      }}
                    >
                      <span>📊</span> Vedomost
                    </button>
                  )}
                </div>
              </div>
            </Link>
          );
        })}
      </div>

      <LimitExceededModal
        isOpen={limitModalOpen}
        onClose={() => setLimitModalOpen(false)}
        message={limitModalMsg}
        feature="test"
        subject={limitSubject}
      />

      {(hasNext || hasPrev) && (
        <div className="toolbar" style={{ marginTop: 16 }}>
          <button
            className="btn sm"
            disabled={!hasPrev}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
          >
            ← {t('back')}
          </button>
          <span className="muted small">
            {page} / {totalPages}
          </span>
          <button
            className="btn sm"
            disabled={!hasNext}
            onClick={() => setPage((p) => p + 1)}
          >
            {t('next')} →
          </button>
        </div>
      )}
    </div>
  );
}
