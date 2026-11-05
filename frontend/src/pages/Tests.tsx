import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { AlertTriangle, BarChart3, Clock, FileText, Lock, PlayCircle, Plus, RotateCcw, Search, SlidersHorizontal } from 'lucide-react';
import LimitExceededModal from '../components/LimitExceededModal';
import MockCodeCard from '../components/MockCodeCard';
import { useAuth } from '../auth/AuthContext';
import { useLang } from '../i18n/LangContext';
import { Billing, DashboardApi, MockTests, type ApiError, type BillingEntitlement } from '../lib/api';
import { listTestsPage, type TestListItem } from '../lib/testing';
import { paywallSubject, type PaywallSubject } from '../lib/paywall';
import { listState } from '../lib/listState';
import { useSubject } from '../lib/useSubject';
import { useVisualViewport } from '../lib/useVisualViewport';

const PAGE_SIZE = 20;

type Category = 'all' | 'milliy' | 'adabiyot' | 'attestatsiya' | 'ielts' | 'multilevel';

interface MyStatus {
  state: 'none' | 'in_progress' | 'done';
  route?: string;
  result_id?: number;
  percentage?: number;
  correct?: number;
  total?: number;
}

type Item = TestListItem & { section_names?: string[]; my_status?: MyStatus };

const lower = (v: unknown) => String(v ?? '').toLowerCase();
const isEnglishTest = (i: Item) =>
  lower(i.subject) === 'english' || /ielts|multi-level|cefr/.test(lower(i.title) + lower(i.course_title) + lower(i.mock_code));
const isIelts = (i: Item) => /ielts/.test(lower(i.title) + lower(i.course_title) + lower(i.mock_code) + lower(i.exam_type));
const isMultiLevel = (i: Item) => lower(i.exam_type) === 'cefr_multilevel' || /multi-level|cefr/.test(lower(i.title) + lower(i.course_title));
const isAttest = (i: Item) =>
  ['#mock-attest2026', 'mock-attest2026'].includes(lower(i.mock_code)) || i.category_slug === 'attestatsiya' || lower(i.title).includes('attestatsiya');
const isAdabiyot = (i: Item) => /adabiyot|mumtoz/.test(lower(i.title) + lower(i.course_title));
const isMilliy = (i: Item) => i.category_slug === 'milliy-sertifikat' || /milliy|bmb/.test(lower(i.title) + lower(i.course_title));
// Paywall rule kept exactly as before this redesign (BMB mock #4 / attestation / "#mock" titles need a plan).
const isMock4 = (i: Item) => lower(i.mock_code) === '#mock-bmb04' || /mock #4|mock 4/.test(lower(i.title));
const isDiagnostic = (i: Item) =>
  ['#mock-bmb-diagnostic', 'mock-bmb-diagnostic', '#mock-shukurov', 'mock-shukurov'].includes(lower(i.mock_code)) ||
  /shukurov|bmb rasmiy mock|diagnostic/.test(lower(i.title));

const CATEGORIES: Record<'uzbek' | 'english', Category[]> = {
  uzbek: ['all', 'milliy', 'adabiyot', 'attestatsiya'],
  english: ['all', 'ielts', 'multilevel'],
};

function cleanTitle(raw: string | undefined): string {
  return String(raw ?? '')
    .replace(/#?MOCK-[A-Z0-9_-]+/gi, '')
    .replace(/^[-–—:() ]+|[-–—:() ]+$/g, '')
    .trim();
}

function SkeletonCard() {
  return (
    <div className="ui-card tl-card" aria-hidden="true">
      <div className="ui-skel ui-skel-line" style={{ width: '70%', height: 16 }} />
      <div className="ui-skel ui-skel-line" style={{ width: '45%' }} />
      <div className="ui-skel" style={{ height: 44, marginTop: 12, borderRadius: 12 }} />
    </div>
  );
}

/** Tests: resume → join with a code → the subject's tests (chips, search, filter sheet). */
export default function Tests() {
  const { t } = useLang();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const { user } = useAuth();
  const subject = useSubject();

  const practiceSkill = searchParams.get('skill') || '';
  const practiceType = searchParams.get('type') || '';
  const practiceMode = searchParams.get('mode') || '';
  const isPracticeActive = Boolean(practiceMode === 'practice' || practiceSkill || practiceType);

  const [entitlement, setEntitlement] = useState<BillingEntitlement | null>(null);
  const [tests, setTests] = useState<Item[]>([]);
  const [count, setCount] = useState<number | null>(null);
  const [page, setPage] = useState(1);
  const [hasNext, setHasNext] = useState(false);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [reload, setReload] = useState(0);
  const [resume, setResume] = useState<{ title: string; route: string } | null>(null);
  const [category, setCategory] = useState<Category>('all');
  const [query, setQuery] = useState('');
  const [difficulty, setDifficulty] = useState('');
  const [filterOpen, setFilterOpen] = useState(false);
  const [mockBusy, setMockBusy] = useState(false);
  const [mockErr, setMockErr] = useState<string | null>(null);
  const [limitOpen, setLimitOpen] = useState(false);
  const [limitSubject, setLimitSubject] = useState<PaywallSubject | undefined>();
  useVisualViewport(filterOpen);

  const isStudent = user?.role === 'student';
  const isStaff = user?.role === 'admin' || user?.role === 'teacher' || user?.role === 'center_admin';
  const isFreeUser =
    isStudent && (!entitlement || (!entitlement.is_paid && !entitlement.is_sponsored && entitlement.source !== 'override'));

  useEffect(() => {
    Billing.entitlement().then(setEntitlement).catch(() => setEntitlement(null));
  }, []);

  // A new subject starts the list from the top.
  useEffect(() => {
    setCategory('all');
    setPage(1);
  }, [subject]);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setErr(null);
    listTestsPage(page, subject)
      .then((p) => {
        if (!alive) return;
        setTests((p.results ?? []) as Item[]);
        setCount(p.count ?? (p.results ?? []).length);
        setHasNext(Boolean(p.next));
      })
      .catch((e: unknown) => {
        if (!alive) return;
        setTests([]);
        setCount(null);
        setErr(e instanceof Error ? e.message : t('err_retry_js'));
      })
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, [page, subject, reload, t]);

  // Same source as the dashboard: the one unfinished attempt of this subject.
  useEffect(() => {
    if (!isStudent) return;
    let alive = true;
    DashboardApi.get(subject)
      .then((d) => alive && setResume(d.resume ? { title: d.resume.title, route: d.resume.route } : null))
      .catch(() => alive && setResume(null));
    return () => {
      alive = false;
    };
  }, [subject, isStudent]);

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    const filtered = tests.filter((i) => {
      if (q && !(lower(i.title).includes(q) || lower(i.course_title).includes(q))) return false;
      if (difficulty && String(i.difficulty ?? '') !== difficulty) return false;
      if ((subject === 'english') !== isEnglishTest(i)) return false;
      switch (category) {
        case 'ielts':
          return isIelts(i);
        case 'multilevel':
          return isMultiLevel(i);
        case 'adabiyot':
          return isAdabiyot(i);
        case 'attestatsiya':
          return isAttest(i);
        case 'milliy':
          return isMilliy(i) || isMock4(i) || isDiagnostic(i);
        default:
          return true;
      }
    });

    if (!isPracticeActive) return filtered;

    const sk = practiceSkill.trim().toLowerCase();
    const tp = practiceType.trim().toLowerCase();
    const scoreItem = (i: Item): number => {
      const hay = `${lower(i.title)} ${lower(i.course_title)} ${(i.section_names || []).map(lower).join(' ')} ${lower(i.category_slug)}`;
      let pts = 0;
      if (sk && hay.includes(sk)) pts += 2;
      if (tp && hay.includes(tp)) pts += 2;
      if (i.my_status?.state !== 'done') pts += 1;
      return pts;
    };
    const exactMatches = filtered.filter((i) => scoreItem(i) >= 2);
    if (exactMatches.length > 0) {
      return [...exactMatches].sort((a, b) => scoreItem(b) - scoreItem(a));
    }
    return [...filtered].sort((a, b) => scoreItem(b) - scoreItem(a));
  }, [tests, query, difficulty, subject, category, isPracticeActive, practiceSkill, practiceType]);

  const join = useCallback(
    async (code: string) => {
      const raw = code.trim();
      if (!raw) {
        setMockErr(t('mockcode_empty'));
        return;
      }
      setMockBusy(true);
      setMockErr(null);
      try {
        const res = await MockTests.join(raw);
        if (res?.attempt_id) navigate(`/take/${res.attempt_id}`);
        else if (res?.test_id) navigate(`/tests/${res.test_id}`);
      } catch (e) {
        const detail = (e as ApiError)?.detail;
        setMockErr(typeof detail === 'string' && detail ? detail : t('mockcode_not_found'));
      } finally {
        setMockBusy(false);
      }
    },
    [navigate, t],
  );

  const statusChip = (s: MyStatus | undefined) => {
    if (s?.state === 'in_progress') return <span className="tl-status is-progress">{t('tl_status_progress')}</span>;
    if (s?.state === 'done') {
      return (
        <span className="tl-status is-done">
          {t('tl_status_done')}
          {s.total ? ` · ${s.correct}/${s.total}` : ''}
        </span>
      );
    }
    return <span className="tl-status">{t('tl_status_none')}</span>;
  };

  const action = (i: Item) => {
    const locked = isFreeUser && !isDiagnostic(i) && (isAttest(i) || isMock4(i) || lower(i.title).includes('#mock'));
    if (locked) {
      return (
        <button
          type="button"
          className="ui-btn ui-btn--block"
          onClick={() => {
            setLimitSubject(paywallSubject(i));
            setLimitOpen(true);
          }}
        >
          <Lock size={16} aria-hidden="true" /> {t('tl_locked')}
        </button>
      );
    }
    const s = i.my_status;
    if (s?.state === 'in_progress' && s.route) {
      return (
        <Link to={s.route} className="ui-btn ui-btn--primary ui-btn--block">
          <PlayCircle size={18} aria-hidden="true" /> {t('tl_resume')}
        </Link>
      );
    }
    if (s?.state === 'done' && s.result_id) {
      return (
        <Link to={`/results/${s.result_id}`} className="ui-btn ui-btn--block">
          <BarChart3 size={18} aria-hidden="true" /> {t('tl_view_result')}
        </Link>
      );
    }
    return (
      <Link to={`/tests/${i.id}`} className="ui-btn ui-btn--primary ui-btn--block">
        {t('tl_start')}
      </Link>
    );
  };

  const meta = (i: Item) => {
    const parts: string[] = [];
    if (i.section_names?.length) parts.push(i.section_names.join(' · '));
    else if (i.total_questions) parts.push(t('tl_questions').replace('{n}', String(i.total_questions)));
    return parts.join(' · ');
  };

  const totalPages = count != null ? Math.max(1, Math.ceil(count / PAGE_SIZE)) : 1;
  const filtersOn = (difficulty ? 1 : 0) + (query ? 1 : 0);

  const view = listState({ loading, error: err, total: tests.length, visible: visible.length });

  return (
    <div className="tl" data-state={view}>
      <div className="tl-head">
        <h1>
          {t('tests')}
          {!loading && !err && count != null && <span className="tl-count"> ({count})</span>}
        </h1>
        {isStaff && (
          <Link to="/tests/create" className="ui-btn ui-btn--sm">
            <Plus size={16} aria-hidden="true" /> {t('tl_create')}
          </Link>
        )}
      </div>

      {isPracticeActive && (
        <div
          role="status"
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 12,
            padding: '14px 18px',
            borderRadius: 16,
            background: 'linear-gradient(135deg, rgba(200, 146, 42, 0.14), rgba(59, 130, 246, 0.12))',
            border: '1.5px solid #C8922A',
            color: 'var(--text-primary, var(--ink))',
          }}
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <strong style={{ fontSize: 15, fontWeight: 800 }}>
              🎯 Zaif qism mashqi: {[
                practiceSkill ? t(`omr_section_${practiceSkill}`, practiceSkill) : '',
                practiceType ? t(`rv_type_${practiceType}`, practiceType) : '',
              ]
                .filter(Boolean)
                .join(' — ') || 'Shaxsiy mashq rejimi'}
            </strong>
            <span style={{ fontSize: 12.5, color: 'var(--text-secondary, var(--muted))' }}>
              Zaif mavzularingizni mustahkamlash uchun tavsiya etilgan testlar saralandi
            </span>
          </div>
          <button
            type="button"
            className="ui-btn ui-btn--sm"
            onClick={() => setSearchParams({})}
            style={{
              borderColor: '#C8922A',
              fontWeight: 800,
            }}
          >
            Filtrni tozalash ✕
          </button>
        </div>
      )}

      {resume && (
        <Link to={resume.route} className="ui-card tl-resume">
          <span className="ic-chip">
            <PlayCircle size={18} aria-hidden="true" />
          </span>
          <span className="tl-resume__text">
            <b>{t('tl_resume')}</b>
            <span className="clamp-1">{resume.title}</span>
          </span>
        </Link>
      )}

      <MockCodeCard subject={subject} busy={mockBusy} error={mockErr} onJoin={(c) => void join(c)} onEdit={() => mockErr && setMockErr(null)} />

      <div className="ui-chip-row" role="group" aria-label={t('catalog_title')}>
        {CATEGORIES[subject].map((c) => (
          <button key={c} type="button" className={`ui-chip${category === c ? ' is-on' : ''}`} aria-pressed={category === c} onClick={() => setCategory(c)}>
            {t(`tl_cat_${c}`)}
          </button>
        ))}
      </div>

      <div className="tl-tools">
        <label className="ui-search">
          <Search size={18} aria-hidden="true" />
          <input
            type="search"
            className="ui-input"
            placeholder={t('test_search_ph')}
            aria-label={t('search')}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            enterKeyHint="search"
          />
        </label>
        <button type="button" className="ui-btn tl-filter-btn" onClick={() => setFilterOpen(true)} aria-label={t('tl_filters')}>
          <SlidersHorizontal size={18} aria-hidden="true" />
          {filtersOn > 0 && difficulty && <b className="fbi-filter-count">1</b>}
        </button>
      </div>

      {view === 'loading' && (
        <div className="tl-grid" aria-busy="true" aria-label={t('loading')}>
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
        </div>
      )}

      {view === 'error' && (
        <div className="ui-state ui-state--error" role="alert">
          <span className="ic-chip ic-chip--danger">
            <AlertTriangle size={24} aria-hidden="true" />
          </span>
          <h3>{t('tl_error_title')}</h3>
          <p>{err}</p>
          <button type="button" className="ui-btn ui-btn--primary" onClick={() => setReload((n) => n + 1)}>
            <RotateCcw size={16} aria-hidden="true" /> {t('error_retry')}
          </button>
        </div>
      )}

      {view === 'empty' && (
        <div className="ui-state">
          <span className="ic-chip ic-chip--muted">
            <FileText size={24} aria-hidden="true" />
          </span>
          <h3>{t('tl_empty_title')}</h3>
          <p>{t(subject === 'english' ? 'tl_empty_english' : 'tl_empty_uzbek')}</p>
        </div>
      )}

      {view === 'no_match' && (
        <div className="ui-state">
          <span className="ic-chip ic-chip--muted">
            <Search size={24} aria-hidden="true" />
          </span>
          <h3>{t('tl_nomatch_title')}</h3>
          <button
            type="button"
            className="ui-btn"
            onClick={() => {
              setQuery('');
              setDifficulty('');
              setCategory('all');
            }}
          >
            {t('tl_clear_filters')}
          </button>
        </div>
      )}

      {view === 'list' && (
        <div className="tl-grid">
          {visible.map((i) => (
            <article key={i.id} className="ui-card tl-card">
              <div className="tl-card__top">
                <Link to={`/tests/${i.id}`} className="tl-card__title clamp-2">
                  {cleanTitle(i.title) || t('tl_untitled')}
                </Link>
                {statusChip(i.my_status)}
              </div>
              <p className="tl-card__meta">
                {meta(i) && <span className="clamp-1">{meta(i)}</span>}
                {i.time_limit_minutes ? (
                  <span className="tl-card__time">
                    <Clock size={14} aria-hidden="true" /> {t('tl_minutes').replace('{n}', String(i.time_limit_minutes))}
                  </span>
                ) : null}
              </p>
              <div className="tl-card__actions">
                {action(i)}
                {isStaff && (
                  <Link to={`/tests/${i.id}/gradebook`} className="ui-btn ui-btn--sm" aria-label={t('tl_gradebook')}>
                    <BarChart3 size={16} aria-hidden="true" />
                  </Link>
                )}
              </div>
            </article>
          ))}
        </div>
      )}

      {!loading && !err && (page > 1 || hasNext) && (
        <div className="tl-pager">
          <button type="button" className="ui-btn" disabled={page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))}>
            {t('back')}
          </button>
          <span>
            {page} / {totalPages}
          </span>
          <button type="button" className="ui-btn" disabled={!hasNext} onClick={() => setPage((p) => p + 1)}>
            {t('next')}
          </button>
        </div>
      )}

      {filterOpen && (
        <div className="sheet-backdrop" onMouseDown={(e) => e.target === e.currentTarget && setFilterOpen(false)}>
          <div className="sheet" role="dialog" aria-modal="true" aria-label={t('tl_filters')}>
            <div className="sheet__grip" aria-hidden="true" />
            <h2 className="sheet__title">{t('tl_filters')}</h2>
            <div className="sheet__body">
              <span className="sheet__label">{t('difficulty')}</span>
              <div className="ui-chip-row" role="group" aria-label={t('difficulty')}>
                {['', 'easy', 'medium', 'hard'].map((d) => (
                  <button key={d || 'any'} type="button" className={`ui-chip${difficulty === d ? ' is-on' : ''}`} aria-pressed={difficulty === d} onClick={() => setDifficulty(d)}>
                    {t(d ? `tl_diff_${d}` : 'tl_diff_any')}
                  </button>
                ))}
              </div>
            </div>
            <div className="sheet__actions">
              <button type="button" className="ui-btn ui-btn--primary" onClick={() => setFilterOpen(false)}>
                {t('fbi_apply')}
              </button>
            </div>
          </div>
        </div>
      )}

      <LimitExceededModal
        isOpen={limitOpen}
        onClose={() => setLimitOpen(false)}
        message={t('paywall_reason_mock_locked')}
        feature="test"
        subject={limitSubject}
      />
    </div>
  );
}
