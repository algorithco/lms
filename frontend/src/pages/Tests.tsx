import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useLang } from '../i18n/LangContext';
import { api, type Paginated } from '../lib/api';
import { listTestsPage, num, type TestListItem } from '../lib/testing';
import { CheckIcon, ClockIcon, HashIcon } from '../components/icons';

const PAGE_SIZE = 20;

export default function Tests() {
  const { t } = useLang();
  const [tests, setTests] = useState<TestListItem[]>([]);
  const [count, setCount] = useState(0);
  const [page, setPage] = useState(1);
  const [hasNext, setHasNext] = useState(false);
  const [hasPrev, setHasPrev] = useState(false);
  const [query, setQuery] = useState('');
  const [difficulty, setDifficulty] = useState('');
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setErr(null);
    listTestsPage(page)
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
  }, [page]);

  // Backend TestListView exposes no search/filter params, so search +
  // difficulty filter run client-side over the loaded page (parity with
  // legacy templates/web/test_list.html filterTests() behaviour).
  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    return tests.filter((item) => {
      const title = String(item.title ?? '').toLowerCase();
      const course = String(item.course_title ?? '').toLowerCase();
      const matchSearch = !q || title.includes(q) || course.includes(q);
      const matchDiff = !difficulty || String(item.difficulty ?? '') === difficulty;
      return matchSearch && matchDiff;
    });
  }, [tests, query, difficulty]);

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
        {visible.map((item) => (
          <Link key={item.id} to={`/tests/${item.id}`} className="card link-card">
            <div className="toolbar" style={{ marginBottom: 8 }}>
              <span className="badge blue">{String(item.difficulty ?? '—')}</span>
              {(item.time_limit_minutes ?? 0) > 0 && (
                <span className="badge amber">
                  <ClockIcon size={12} className="ico" /> {item.time_limit_minutes} {t('minutes_suffix')}
                </span>
              )}
            </div>
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
        ))}
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
