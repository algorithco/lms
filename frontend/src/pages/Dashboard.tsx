import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { useLang } from '../i18n/LangContext';
import { AuthExpiredError, Certificates, Results, Tests } from '../lib/api';
import { num, type CertListItem, type ResultListItem, type TestListItem } from '../lib/testing';
import {
  AwardIcon,
  ClockIcon,
  FileTextIcon,
  TrophyIcon,
} from '../components/icons';

interface Stats {
  total_tests_taken?: number;
  total_passed?: number;
  total_failed?: number;
  average_percentage?: number;
  best_percentage?: number;
  total_time_spent_seconds?: number;
}

export default function Dashboard() {
  const { user } = useAuth();
  const { t } = useLang();
  const navigate = useNavigate();
  const [stats, setStats] = useState<Stats | null>(null);
  const [available, setAvailable] = useState<TestListItem[]>([]);
  const [testCount, setTestCount] = useState<number | null>(null);
  const [certs, setCerts] = useState<CertListItem[]>([]);
  const [certCount, setCertCount] = useState<number | null>(null);
  const [recent, setRecent] = useState<ResultListItem[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const results = await Promise.allSettled([
          Results.stats(),
          Tests.list(),
          Certificates.mine(),
          Results.mine(),
        ]);
        if (cancelled) return;
        for (const item of results) {
          if (item.status === 'rejected' && item.reason instanceof AuthExpiredError) {
            navigate('/login');
            return;
          }
        }
        const [sR, tR, cRes, rRes] = results;
        const s = sR.status === 'fulfilled' ? (sR.value as unknown as Stats) : null;
        const tlist = tR.status === 'fulfilled' ? (tR.value as unknown as { count: number; results: TestListItem[] }) : null;
        const cVal = cRes.status === 'fulfilled' ? (cRes.value as unknown as { count: number; results: CertListItem[] }) : null;
        const rVal = rRes.status === 'fulfilled' ? (rRes.value as unknown as { results: ResultListItem[] }) : null;
        const failed = results.filter((x) => x.status === 'rejected');
        if (failed.length > 0 && !s && !tlist && !cVal && !rVal) {
          const first = failed[0] as PromiseRejectedResult;
          throw first.reason as Error;
        }
        if (failed.length > 0) {
          const msgs = failed.map((x) => (x as PromiseRejectedResult).reason?.message ?? '').filter(Boolean);
          if (msgs.length) setErr(msgs[0]);
        }
        setStats(s ?? null);
        setTestCount(tlist ? tlist.count : null);
        setAvailable(((tlist?.results ?? []) as TestListItem[]).slice(0, 6));
        setCertCount(cVal ? cVal.count : null);
        setCerts(((cVal?.results ?? []) as CertListItem[]).slice(0, 3));
        setRecent(((rVal?.results ?? []) as ResultListItem[]).slice(0, 5));
      } catch (e) {
        if (!cancelled) {
          if (e instanceof AuthExpiredError) navigate('/login');
          else setErr(e instanceof Error ? e.message : t('err_retry_js'));
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [t, navigate, tick]);

  const avg = stats ? num(stats.average_percentage, 0) : null;

  return (
    <div>
      <h1>
        {t('welcome')}, {user?.full_name}
      </h1>
      {err && (
        <p className="error" role="alert">
          {err}{' '}
          <button className="btn sm ghost" onClick={() => { setErr(null); setLoading(true); setTick((x) => x + 1); }}>
            {t('retry')}
          </button>
        </p>
      )}
      {loading && <p className="muted" role="status" aria-live="polite">{t('loading')}</p>}

      {/* Stat cards — parity with legacy student_dashboard.html. */}
      <div className="grid">
        <div className="card stat stat-gradient-blue">
          <span className="stat-label">
            <FileTextIcon size={13} className="ico" /> {t('stat_tests_taken')}
          </span>
          <span className="stat-value">
            {stats ? num(stats.total_tests_taken, 0) : '…'}
          </span>
          <span className="muted small">{t('stat_sub_total_hint')}</span>
          <Link to="/tests">{t('tests')} →</Link>
        </div>
        <div className="card stat stat-gradient-green">
          <span className="stat-label">
            <TrophyIcon size={13} className="ico" /> {t('stat_tests_passed')}
          </span>
          <span className="stat-value">
            {stats ? num(stats.total_passed, 0) : '…'}
          </span>
          <span className="muted small">
            {stats
              ? `${num(stats.total_passed, 0)}/${num(stats.total_tests_taken, 0)} ${t('stat_successfully')}`
              : t('hint_take_test')}
          </span>
          <Link to="/results">{t('my_results')} →</Link>
        </div>
        <div className="card stat stat-gradient-amber">
          <span className="stat-label">
            <TrophyIcon size={13} className="ico" /> {t('average_score')}
          </span>
          <span className="stat-value">{avg === null ? '…' : `${avg}%`}</span>
          <span className="muted small">
            {avg === null
              ? ''
              : avg >= 70
                ? t('perf_excellent')
                : avg >= 50
                  ? t('perf_not_bad')
                  : t('perf_more_effort')}
          </span>
          <Link to="/results">{t('recent_results')} →</Link>
        </div>
        <div className="card stat stat-gradient-purple">
          <span className="stat-label">
            <AwardIcon size={13} className="ico" /> {t('certificates')}
          </span>
          <span className="stat-value">{certCount ?? '…'}</span>
          <span className="muted small">
            {t('count_certificates')} · {t('download_pdf_hint')}
          </span>
          <Link to="/certificates">{t('my_certificates')} →</Link>
        </div>
      </div>

      {/* Available tests preview (legacy: first 6 active tests). */}
      <h2>{t('available_tests')}</h2>
      <p className="muted">{t('available_tests_hint')}</p>
      {available.length === 0 ? (
        <div className="card">
          <h3>{t('no_tests_title')}</h3>
          <p className="muted">{t('no_tests_hint')}</p>
          <Link className="btn primary" to="/tests">
            {t('view_tests')}
          </Link>
        </div>
      ) : (
        <div className="grid">
          {available.map((item) => (
            <Link key={item.id} to={`/tests/${item.id}`} className="card link-card">
              <div className="toolbar" style={{ marginBottom: 8 }}>
                <span className="badge blue">{t(`difficulty_${item.difficulty ?? ''}`) !== `difficulty_${item.difficulty ?? ''}` ? t(`difficulty_${item.difficulty ?? ''}`) : String(item.difficulty ?? '—')}</span>
                {(item.time_limit_minutes ?? 0) > 0 && (
                  <span className="badge amber">
                    <ClockIcon size={12} className="ico" /> {item.time_limit_minutes}{' '}
                    {t('minutes_suffix')}
                  </span>
                )}
              </div>
              <strong>{String(item.title ?? `Test #${item.id}`)}</strong>
              <span className="muted small">
                {num(item.total_questions, 0)} {t('questions_suffix')} ·{' '}
                {t('pass_suffix')}: {num(item.pass_percentage, 0)}%
              </span>
            </Link>
          ))}
        </div>
      )}
      <p className="muted small">
        <Link to="/tests">
          {t('view_all')} → ({testCount ?? '…'})
        </Link>
      </p>

      {/* Recent results (legacy: last 5, linked to detail). */}
      <h2>{t('recent_results')}</h2>
      {recent.length === 0 ? (
        <div className="card">
          <h3>{t('no_results_title')}</h3>
          <p className="muted">{t('no_results_hint')}</p>
          <Link className="btn primary" to="/tests">
            {t('view_tests')}
          </Link>
        </div>
      ) : (
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>{t('th_test_name')}</th>
                <th>{t('score')}</th>
                <th>{t('status')}</th>
              </tr>
            </thead>
            <tbody>
              {recent.map((r) => (
                <tr key={r.id}>
                  <td>
                    <Link to={`/results/${r.id}`}>
                      {String(r.test_title ?? r.test ?? `#${r.id}`)}
                    </Link>
                    <div className="muted small">{String(r.course_title ?? '')}</div>
                  </td>
                  <td>{num(r.percentage, 0)}%</td>
                  <td>
                    <span className={`badge ${r.is_passed ? 'green' : 'rose'}`}>
                      {r.is_passed ? t('status_passed') : t('status_failed')}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Certificates preview (legacy: quick certificates block). */}
      {certs.length > 0 && (
        <>
          <h2>{t('my_certificates')}</h2>
          <p className="muted">{t('my_certificates_hint')}</p>
          <div className="grid">
            {certs.map((c) => (
              <Link key={c.id} to="/certificates" className="card link-card">
                <span className="stat-label">
                  <AwardIcon size={13} className="ico" />{' '}
                  {String(c.certificate_number ?? '')}
                </span>
                <strong>
                  {String(c.course_title ?? c.test_title ?? `#${c.id}`)}
                </strong>
                <span className="muted small">
                  {num(c.percentage, 0)}% · {String(c.status ?? '')}
                </span>
              </Link>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
