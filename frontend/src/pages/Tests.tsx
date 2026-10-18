import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useLang } from '../i18n/LangContext';
import { api, MockTests, type Paginated } from '../lib/api';
import { listTestsPage, num, type TestListItem } from '../lib/testing';
import { CheckIcon, ClockIcon, HashIcon } from '../components/icons';

const PAGE_SIZE = 20;

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
  const [categoryFilter, setCategoryFilter] = useState<'all' | 'milliy' | 'attestatsiya' | 'arena'>('all');
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
    const handler = () => {
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
    const activeSub = (localStorage.getItem('lms_subject') as 'uzbek' | 'english') || 'uzbek';
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
  }, [page, subjectTick]);

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
  }, [tests, query, difficulty, categoryFilter]);

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
      <div
        className="card"
        style={{
          margin: '16px 0 20px',
          background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.08) 0%, rgba(59, 130, 246, 0.06) 100%)',
          border: '1px solid rgba(16, 185, 129, 0.35)',
          borderRadius: '12px',
          padding: '16px 20px',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
          <div>
            <strong style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '1rem', color: '#10b981' }}>
              <span>🎯</span> Mock Testga Kod Bilan Qo‘shilish
            </strong>
            <p className="muted small" style={{ margin: '4px 0 0' }}>
              Ustoz bergan <strong>#MOCK-...</strong> kodini kiriting yoki rasmiy imtihonga 1-klikda kiring:
            </p>
            <div style={{ marginTop: 8, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              <button
                type="button"
                className="btn sm"
                style={{
                  background: 'rgba(139, 92, 246, 0.15)',
                  border: '1px solid #8b5cf6',
                  color: '#a78bfa',
                  fontWeight: 700,
                  fontSize: '0.8rem',
                  padding: '4px 12px',
                  borderRadius: '8px',
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
                🎓 #MOCK-ATTEST2026 (Attestatsiya Diagnostika 2026) →
              </button>
              <button
                type="button"
                className="btn sm"
                style={{
                  background: 'rgba(245, 158, 11, 0.15)',
                  border: '1px solid #f59e0b',
                  color: '#f59e0b',
                  fontWeight: 700,
                  fontSize: '0.8rem',
                  padding: '4px 12px',
                  borderRadius: '8px',
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
                🔥 #MOCK-BMB-DIAGNOSTIC (BMB Rasmiy Mock Test) →
              </button>
              <button
                type="button"
                className="btn sm"
                style={{
                  background: 'rgba(16, 185, 129, 0.15)',
                  border: '1px solid #10b981',
                  color: '#10b981',
                  fontWeight: 700,
                  fontSize: '0.8rem',
                  padding: '4px 12px',
                  borderRadius: '8px',
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
                ⭐️ #MOCK-BMB04 (3 soatlik to‘liq BMB Mock #4) →
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
        <div className="card">
          <h3>{t('no_tests_title')}</h3>
          <p className="muted">{t('no_tests_hint')}</p>
        </div>
      )}

      {!loading && !err && tests.length > 0 && visible.length === 0 && (
        <div className="card">
          <p className="muted">{t('test_no_match')}</p>
        </div>
      )}

      <div className="grid">
        {visible.map((item) => {
          const isAttest = isMockAttest(item);
          const isBmbDiag = isMockBmbDiag(item);
          const isM4 = isMock4(item);
          const isHighlight = isAttest || isBmbDiag || isM4;
          return (
            <Link
              key={item.id}
              to={`/tests/${item.id}`}
              className="card link-card"
              style={
                isAttest
                  ? {
                      border: '1.5px solid rgba(139, 92, 246, 0.75)',
                      background: 'radial-gradient(circle at top right, rgba(139, 92, 246, 0.12) 0%, rgba(15, 23, 42, 0.6) 100%)',
                      boxShadow: '0 4px 20px rgba(139, 92, 246, 0.2)',
                    }
                  : isBmbDiag
                  ? {
                      border: '1.5px solid rgba(245, 158, 11, 0.7)',
                      background: 'radial-gradient(circle at top right, rgba(245, 158, 11, 0.1) 0%, rgba(15, 23, 42, 0.6) 100%)',
                      boxShadow: '0 4px 20px rgba(245, 158, 11, 0.15)',
                    }
                  : isM4
                  ? {
                      border: '1.5px solid rgba(16, 185, 129, 0.7)',
                      background: 'radial-gradient(circle at top right, rgba(16, 185, 129, 0.08) 0%, rgba(15, 23, 42, 0.6) 100%)',
                      boxShadow: '0 4px 20px rgba(16, 185, 129, 0.12)',
                    }
                  : undefined
              }
            >
              {isHighlight ? (
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8, flexWrap: 'wrap' }}>
                  <span
                    style={{
                      background: isAttest
                        ? 'linear-gradient(135deg, #8b5cf6 0%, #6d28d9 100%)'
                        : isBmbDiag
                        ? 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)'
                        : 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
                      color: '#ffffff',
                      fontWeight: 700,
                      fontSize: '0.75rem',
                      padding: '3px 10px',
                      borderRadius: '9999px',
                      boxShadow: isAttest
                        ? '0 2px 8px rgba(139, 92, 246, 0.4)'
                        : isBmbDiag
                        ? '0 2px 8px rgba(245, 158, 11, 0.4)'
                        : '0 2px 8px rgba(16, 185, 129, 0.4)',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 4,
                    }}
                  >
                    {isAttest
                      ? '🎓 Rasmiy Attestatsiya Diagnostika 2026'
                      : isBmbDiag
                      ? '🔥 BMB Rasmiy Mock Test'
                      : '⭐️ BMB Rasmiy Mock #4 (Tekin)'}
                  </span>
                  <span className="badge amber">
                    <ClockIcon size={12} className="ico" /> {item.time_limit_minutes ?? 100} {t('minutes_suffix')}
                  </span>
                  <span className="badge blue">Qiyin (Hard)</span>
                  {item.is_strict_mode && (
                    <span style={{ background: 'rgba(239, 68, 68, 0.15)', color: '#ef4444', border: '1px solid rgba(239, 68, 68, 0.3)', padding: '2px 8px', borderRadius: '6px', fontSize: '0.72rem', fontWeight: 700, display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                      🔒 Strict Exam
                    </span>
                  )}
                  {item.audio_url && (
                    <span style={{ background: 'rgba(59, 130, 246, 0.15)', color: '#60a5fa', border: '1px solid rgba(59, 130, 246, 0.3)', padding: '2px 8px', borderRadius: '6px', fontSize: '0.72rem', fontWeight: 700, display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                      🎧 Audio Listening
                    </span>
                  )}
                  {item.subject === 'english' && (
                    <span style={{ background: 'rgba(99, 102, 241, 0.15)', color: '#818cf8', border: '1px solid rgba(99, 102, 241, 0.3)', padding: '2px 8px', borderRadius: '6px', fontSize: '0.72rem', fontWeight: 700, display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                      🇬🇧 English
                    </span>
                  )}
                </div>
              ) : (
                <div className="toolbar" style={{ marginBottom: 8, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  <span className="badge blue">{String(item.difficulty ?? '—')}</span>
                  {item.is_strict_mode && (
                    <span style={{ background: 'rgba(239, 68, 68, 0.15)', color: '#ef4444', border: '1px solid rgba(239, 68, 68, 0.3)', padding: '2px 8px', borderRadius: '6px', fontSize: '0.72rem', fontWeight: 700, display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                      🔒 Strict Exam
                    </span>
                  )}
                  {item.audio_url && (
                    <span style={{ background: 'rgba(59, 130, 246, 0.15)', color: '#60a5fa', border: '1px solid rgba(59, 130, 246, 0.3)', padding: '2px 8px', borderRadius: '6px', fontSize: '0.72rem', fontWeight: 700, display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                      🎧 Audio
                    </span>
                  )}
                  {item.subject === 'english' && (
                    <span style={{ background: 'rgba(99, 102, 241, 0.15)', color: '#818cf8', border: '1px solid rgba(99, 102, 241, 0.3)', padding: '2px 8px', borderRadius: '6px', fontSize: '0.72rem', fontWeight: 700, display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                      🇬🇧 English
                    </span>
                  )}
                  {(item.time_limit_minutes ?? 0) > 0 && (
                    <span className="badge amber">
                      <ClockIcon size={12} className="ico" /> {item.time_limit_minutes} {t('minutes_suffix')}
                    </span>
                  )}
                </div>
              )}
              <strong>{String(item.title ?? `Test #${item.id}`)}</strong>
              {item.description && (
                <span className="muted small">{String(item.description).slice(0, 120)}</span>
              )}
              <span className="muted small">
                <HashIcon size={12} className="ico" /> {num(item.total_questions, 0)} {t('questions_suffix')}
                {' · '}
                {t('pass_suffix')}: {num(item.pass_percentage, 0)}%
                {' · '}
                {t('th_attempts')}: {num(item.max_attempts, 0) === 0 ? '∞' : num(item.max_attempts, 0)}
              </span>
              {item.course_title && (
                <span className="muted small">
                  <CheckIcon size={12} className="ico" /> {String(item.course_title)}
                </span>
              )}
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
