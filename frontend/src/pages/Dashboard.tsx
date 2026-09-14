import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { useLang } from '../i18n/LangContext';
import { Certificates, Results, Tests } from '../lib/api';
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
  const [stats, setStats] = useState<Stats | null>(null);
  const [available, setAvailable] = useState<TestListItem[]>([]);
  const [testCount, setTestCount] = useState<number | null>(null);
  const [certs, setCerts] = useState<CertListItem[]>([]);
  const [certCount, setCertCount] = useState<number | null>(null);
  const [recent, setRecent] = useState<ResultListItem[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [s, tlist, c, r] = await Promise.all([
          Results.stats().catch(() => null),
          Tests.list().catch(() => null),
          Certificates.mine().catch(() => null),
          Results.mine().catch(() => null),
        ]);
        if (cancelled) return;
        setStats((s ?? null) as Stats | null);
        setTestCount(tlist ? tlist.count : null);
        setAvailable(((tlist?.results ?? []) as TestListItem[]).slice(0, 6));
        setCertCount(c ? c.count : null);
        setCerts(((c?.results ?? []) as CertListItem[]).slice(0, 3));
        setRecent(((r?.results ?? []) as ResultListItem[]).slice(0, 5));
      } catch (e) {
        if (!cancelled) setErr(e instanceof Error ? e.message : t('err_retry_js'));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const avg = stats ? num(stats.average_percentage, 0) : null;

  return (
    <div>
      <h1>
        {t('welcome')}, {user?.full_name}
      </h1>
      {err && <p className="error">{err}</p>}
      {loading && <p className="muted">{t('loading')}</p>}

      {/* Stat cards — parity with legacy student_dashboard.html. */}
      <div className="grid">
        <div className="card stat stat-gradient-blue">
          <span className="stat-label">
            <FileTextIcon size={13} className="ico" /> {t('stat_tests_taken')}
          </span>
          <span className="stat-value">
            {stats ? Number(stats.total_tests_taken ?? 0) : '…'}
          </span>
          <span className="muted small">{t('stat_sub_total_hint')}</span>
          <Link to="/tests">{t('tests')} →</Link>
        </div>
        <div className="card stat stat-gradient-green">
          <span className="stat-label">
            <TrophyIcon size={13} className="ico" /> {t('stat_tests_passed')}
          </span>
          <span className="stat-value">
            {stats ? Number(stats.total_passed ?? 0) : '…'}
          </span>
          <span className="muted small">
            {stats
              ? `${Number(stats.total_passed ?? 0)}/${Number(stats.total_tests_taken ?? 0)} ${t('stat_successfully')}`
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
                <span className="badge blue">{String(item.difficulty ?? '—')}</span>
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
                    <Link to="/results">
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
