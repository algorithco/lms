import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useLang } from '../i18n/LangContext';
import { api, MockTests, type Paginated } from '../lib/api';
import { listTestsPage, num, type TestListItem } from '../lib/testing';
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
  const [tests, setTests] = useState<TestListItem[]>([]);
  const [count, setCount] = useState(0);
  const [page, setPage] = useState(1);
  const [hasNext, setHasNext] = useState(false);
  const [hasPrev, setHasPrev] = useState(false);
  const [query, setQuery] = useState('');
  const [difficulty, setDifficulty] = useState('');
  const [categoryFilter, setCategoryFilter] = useState<'all' | 'milliy' | 'attestatsiya' | 'arena' | 'ielts' | 'multilevel'>('all');
  const [activeSub, setActiveSub] = useState<'uzbek' | 'english'>(() => {
    return (localStorage.getItem('lms_subject') as 'uzbek' | 'english') || 'uzbek';
  });
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // Quick Mock Join
  const [mockCode, setMockCode] = useState('');
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
    return 'Mock test topilmadi yoki kod noto‘g‘ri.';
  };

  const executeJoin = async (overrideCode?: string) => {
    const raw = (overrideCode ?? mockCode).trim();
    if (!raw) {
      setMockErr("Iltimos, Mock test kodini kiriting (masalan: #MOCK-ATTEST2026)");
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

  const joinMock = (e: React.FormEvent) => {
    e.preventDefault();
    executeJoin();
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
      <h1>
        {t('tests')} ({count})
      </h1>
      <p className="muted">{t('available_tests_hint')}</p>

      {/* 🎯 Mock Testga Kod Bilan Qo'shilish */}
      {activeSub === 'english' ? (
        <div
          className="card"
          style={{
            margin: '16px 0 20px',
            background: '#FFFFFF',
            border: '1px solid rgba(226, 232, 240, 0.95)',
            boxShadow: '0 4px 20px rgba(0, 0, 0, 0.04)',
            borderRadius: '16px',
            padding: '18px 22px',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
            <div>
              <strong style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '1rem', color: '#38bdf8' }}>
                <span>🎯</span> English CBT Mock & Exam Access
              </strong>
              <p className="muted small" style={{ margin: '4px 0 0' }}>
                Enter your instructor's test code or practice code to begin:
              </p>
            </div>
            <form onSubmit={joinMock} style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
              <input
                type="text"
                value={mockCode}
                onChange={(e) => {
                  setMockCode(e.target.value);
                  if (mockErr) setMockErr(null);
                }}
                placeholder="#IELTS-CBT-01"
                required
                style={{
                  width: '180px',
                  fontWeight: 700,
                  textTransform: 'uppercase',
                  letterSpacing: '1px',
                }}
              />
              <button className="btn primary sm" disabled={mockBusy}>
                {mockBusy ? 'Connecting…' : '🚀 Start Exam'}
              </button>
            </form>
          </div>
          {mockErr && (
            <div
              style={{
                marginTop: 12,
                padding: '10px 14px',
                borderRadius: 8,
                background: 'rgba(239, 68, 68, 0.12)',
                border: '1px solid rgba(239, 68, 68, 0.3)',
                color: '#f87171',
                fontSize: 13,
                fontWeight: 600,
                display: 'flex',
                alignItems: 'center',
                gap: 8,
              }}
            >
              <span>⚠️</span>
              <span>{mockErr}</span>
            </div>
          )}
        </div>
      ) : (
        <div
          className="card"
          style={{
            margin: '16px 0 20px',
            background: '#FFFFFF',
            border: '1px solid rgba(226, 232, 240, 0.95)',
            boxShadow: '0 4px 20px rgba(0, 0, 0, 0.04)',
            borderRadius: '16px',
            padding: '18px 22px',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
            <div>
              <strong style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '1rem', color: '#059669' }}>
                <span>🎯</span> Rasmiy Mock Testga Qo‘shilish
              </strong>
              <p className="muted small" style={{ margin: '4px 0 0' }}>
                Ustozingiz bergan maxsus test kodini kiriting yoki rasmiy imtihonga 1-klikda kiring:
              </p>
              <div style={{ marginTop: 10, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <button
                  type="button"
                  className="btn sm"
                  style={{
                    background: 'rgba(139, 92, 246, 0.08)',
                    border: '1px solid rgba(139, 92, 246, 0.3)',
                    color: '#6D28D9',
                    fontWeight: 800,
                    fontSize: '0.82rem',
                    padding: '6px 14px',
                    borderRadius: '10px',
                    cursor: 'pointer',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 6,
                    transition: 'all 0.2s ease',
                  }}
                  disabled={mockBusy}
                  onClick={() => {
                    setMockCode('#MOCK-ATTEST2026');
                    executeJoin('#MOCK-ATTEST2026');
                  }}
                >
                  🎓 Attestatsiya Diagnostika 2026 →
                </button>
                <button
                  type="button"
                  className="btn sm"
                  style={{
                    background: 'rgba(217, 119, 6, 0.08)',
                    border: '1px solid rgba(217, 119, 6, 0.3)',
                    color: '#B45309',
                    fontWeight: 800,
                    fontSize: '0.82rem',
                    padding: '6px 14px',
                    borderRadius: '10px',
                    cursor: 'pointer',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 6,
                    transition: 'all 0.2s ease',
                  }}
                  disabled={mockBusy}
                  onClick={() => {
                    setMockCode('#MOCK-BMB-DIAGNOSTIC');
                    executeJoin('#MOCK-BMB-DIAGNOSTIC');
                  }}
                >
                  🔥 Ona tili va Adabiyot — Rasmiy BMB Diagnostika →
                </button>
                <button
                  type="button"
                  className="btn sm"
                  style={{
                    background: 'rgba(5, 150, 105, 0.08)',
                    border: '1px solid rgba(5, 150, 105, 0.3)',
                    color: '#059669',
                    fontWeight: 800,
                    fontSize: '0.82rem',
                    padding: '6px 14px',
                    borderRadius: '10px',
                    cursor: 'pointer',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 6,
                    transition: 'all 0.2s ease',
                  }}
                  disabled={mockBusy}
                  onClick={() => {
                    setMockCode('#MOCK-BMB04');
                    executeJoin('#MOCK-BMB04');
                  }}
                >
                  ⭐️ BMB Rasmiy 3 soatlik Mock Test →
                </button>
              </div>
            </div>
            <form onSubmit={joinMock} style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
              <input
                type="text"
                value={mockCode}
                onChange={(e) => {
                  setMockCode(e.target.value);
                  if (mockErr) setMockErr(null);
                }}
                placeholder="#MOCK-BMB-DIAGNOSTIC"
                required
                style={{
                  width: '180px',
                  fontWeight: 700,
                  textTransform: 'uppercase',
                  letterSpacing: '1px',
                }}
              />
              <button className="btn primary sm" disabled={mockBusy}>
                {mockBusy ? 'Ulanmoqda…' : '🚀 Testni boshlash'}
              </button>
            </form>
          </div>
          {mockErr && (
            <div
              style={{
                marginTop: 12,
                padding: '10px 14px',
                borderRadius: 8,
                background: 'rgba(239, 68, 68, 0.12)',
                border: '1px solid rgba(239, 68, 68, 0.3)',
                color: '#f87171',
                fontSize: 13,
                fontWeight: 600,
                display: 'flex',
                alignItems: 'center',
                gap: 8,
              }}
            >
              <span>⚠️</span>
              <span>{mockErr}</span>
            </div>
          )}
        </div>
      )}

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
        <div className="card" style={{ padding: '28px 20px', textAlign: 'center' }}>
          <h3>{activeSub === 'english' ? '🎧 CBT Reading & Listening Testlar' : t('no_tests_title')}</h3>
          <p className="muted" style={{ maxWidth: 520, margin: '8px auto 0' }}>
            {activeSub === 'english'
              ? 'Hozircha ochiq CBT testlar tayyorlanmoqda. Yuqoridagi "English CBT Mock & Exam Access" maydoniga o\'qituvchingiz bergan test kodini kiritib testni boshlashingiz mumkin.'
              : t('no_tests_hint')}
          </p>
        </div>
      )}

      {!loading && !err && tests.length > 0 && visible.length === 0 && (
        <div className="card" style={{ padding: '24px 20px', textAlign: 'center' }}>
          <p className="muted">{t('test_no_match')}</p>
        </div>
      )}

      <div className="grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '20px' }}>
        {visible.map((item) => {
          const isAttest = isMockAttest(item);
          const isBmbDiag = isMockBmbDiag(item);
          const isM4 = isMock4(item);
          const cleanTitle = getCleanTestTitle(item.title, item.subject);
          const timeLimit = item.time_limit_minutes && item.time_limit_minutes > 0 ? item.time_limit_minutes : 180;
          const questionsCount = num(item.total_questions, 45);
          const passPct = num(item.pass_percentage, 60);

          return (
            <Link
              key={item.id}
              to={`/tests/${item.id}`}
              className="card link-card"
              style={{
                borderRadius: '18px',
                background: '#FFFFFF',
                border: isAttest
                  ? '1.5px solid rgba(139, 92, 246, 0.35)'
                  : isBmbDiag
                  ? '1.5px solid rgba(217, 119, 6, 0.35)'
                  : isM4
                  ? '1.5px solid rgba(16, 185, 129, 0.35)'
                  : '1px solid rgba(226, 232, 240, 0.95)',
                boxShadow: isAttest
                  ? '0 6px 22px rgba(139, 92, 246, 0.07)'
                  : isBmbDiag
                  ? '0 6px 22px rgba(217, 119, 6, 0.07)'
                  : '0 4px 18px rgba(0, 0, 0, 0.04)',
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
                  {item.subject === 'english' ? '🇬🇧 Ingliz tili' : '🇺🇿 Ona tili va Adabiyot'}
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

                {item.audio_url && (
                  <span style={{ background: 'rgba(59, 130, 246, 0.1)', color: '#2563EB', padding: '3px 8px', borderRadius: '6px', fontSize: '0.72rem', fontWeight: 700 }}>
                    🎧 Audio
                  </span>
                )}
              </div>

              {/* Title */}
              <strong style={{ fontSize: '1.08rem', color: '#0F172A', lineHeight: 1.35, fontWeight: 800 }}>
                {cleanTitle}
              </strong>

              {item.description && (
                <span style={{ fontSize: '0.84rem', color: '#64748B', lineHeight: 1.5 }}>
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
                    color: '#475569',
                    background: '#F1F5F9',
                    padding: '3px 9px',
                    borderRadius: '8px',
                  }}
                >
                  <HashIcon size={12} /> {questionsCount} ta savol
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
                  🎯 O\'tish bali: {passPct}%
                </span>
              </div>

              {/* Bottom Action Button */}
              <div style={{ marginTop: 'auto', paddingTop: 10 }}>
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: 6,
                    padding: '10px 16px',
                    borderRadius: '12px',
                    background: 'linear-gradient(135deg, #F59E0B, #D97706)',
                    color: '#FFFFFF',
                    fontWeight: 800,
                    fontSize: '0.85rem',
                    boxShadow: '0 4px 14px rgba(217, 119, 6, 0.25)',
                  }}
                >
                  <span>Testni boshlash →</span>
                </div>
              </div>
            </Link>
          );
        })}
      </div>

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
