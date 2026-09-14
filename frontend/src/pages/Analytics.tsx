import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useLang } from '../i18n/LangContext';
import { School } from '../lib/api';
import AnalyticsChart from '../components/AnalyticsChart';
import { TrendingUpIcon } from '../components/icons';
import type { AnalyticsData } from '../lib/school';
import { errMessage } from '../lib/school';

const RANGES = [7, 14, 30, 60, 90];

export default function Analytics() {
  const { t } = useLang();
  const [days, setDays] = useState(14);
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setData(null);
    setErr(null);
    // GET /api/v1/school/analytics/?days=<1..90>
    School.analytics(days)
      .then((r) => {
        if (alive) setData(r as unknown as AnalyticsData);
      })
      .catch((e: unknown) => {
        if (alive) setErr(errMessage(e));
      });
    return () => {
      alive = false;
    };
  }, [days]);

  const attempts = data?.totals.attempts ?? 0;
  const passed = data?.totals.passed ?? 0;
  const failed = Math.max(attempts - passed, 0);
  const passRate = attempts > 0 ? Math.round((passed / attempts) * 1000) / 10 : 0;
  const avgOfAvgs =
    data && data.avg_percentage.length > 0
      ? Math.round((data.avg_percentage.reduce((a, b) => a + b, 0) / data.avg_percentage.length) * 10) / 10
      : 0;

  if (!data && !err) return <p className="muted">{t('loading')}</p>;
  return (
    <div>
      <h1>
        <TrendingUpIcon size={24} className="ico" /> {t('analytics')}
      </h1>
      <Link to="/teacher" className="muted small">
        ← {t('teacher_dashboard')}
      </Link>
      {err && <p className="error">{err}</p>}

      {/* Day-range selector — backend clamps days to 1..90. */}
      <div className="toolbar" role="group" aria-label={t('analytics')}>
        {RANGES.map((d) => (
          <button
            key={d}
            className={`btn sm${days === d ? ' primary' : ''}`}
            onClick={() => setDays(d)}
            aria-pressed={days === d}
          >
            {d} {t('an_days_suffix')}
          </button>
        ))}
      </div>

      {data && (
        <>
          {/* Totals — parity with analytics.html summary cards for what the
              /analytics/ endpoint exposes (attempts + passed). */}
          <div className="grid">
            <div className="card stat stat-gradient-blue">
              <span className="stat-label">{t('an_total_submissions')}</span>
              <span className="stat-value">{attempts}</span>
              <span className="muted small">
                {t('an_last_days_prefix')} {days} {t('an_days_suffix')}
              </span>
            </div>
            <div className="card stat stat-gradient-green">
              <span className="stat-label">{t('passed_lbl')}</span>
              <span className="stat-value">{passed}</span>
              <span className="muted small">
                {t('failed_lbl')}: {failed}
              </span>
            </div>
            <div className="card stat stat-gradient-amber">
              <span className="stat-label">{t('pass_rate_title')}</span>
              <span className="stat-value">{passRate}%</span>
            </div>
            <div className="card stat stat-gradient-purple">
              <span className="stat-label">{t('average_score')}</span>
              <span className="stat-value">{avgOfAvgs}%</span>
            </div>
          </div>

          {/* Pass / fail split bar (derived from totals). */}
          <h2>
            ✅ {t('passed_lbl')} / {t('failed_lbl')}
          </h2>
          <div className="card">
            {attempts === 0 ? (
              <p className="muted">{t('an_no_data')}</p>
            ) : (
              <div
                style={{ display: 'flex', height: 18, borderRadius: 9, overflow: 'hidden' }}
                role="img"
                aria-label={`${t('passed_lbl')}: ${passed}, ${t('failed_lbl')}: ${failed}`}
              >
                <div style={{ width: `${passRate}%`, background: '#10b981' }} />
                <div style={{ width: `${100 - passRate}%`, background: '#fb7185' }} />
              </div>
            )}
          </div>

          {/* Daily chart via AnalyticsChart. */}
          <h2>📊 {t('an_daily_attempts')}</h2>
          <div className="card">
            {data.labels.length === 0 ? (
              <p className="muted">{t('an_no_data')}</p>
            ) : (
              <AnalyticsChart
                data={data.labels.map((label, i) => ({
                  date: label,
                  attempts: data.attempts[i] ?? 0,
                  avg: data.avg_percentage[i] ?? 0,
                }))}
                attemptsLabel={t('an_js_attempts')}
                avgLabel={t('an_js_avg_pct')}
              />
            )}
          </div>

          {/* Per-day table — same series as the chart, tabular form. */}
          <h2>{t('an_per_day')}</h2>
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>{t('date')}</th>
                  <th>{t('th_attempts')}</th>
                  <th>{t('average_score')}</th>
                </tr>
              </thead>
              <tbody>
                {[...data.labels]
                  .map((label, i) => ({ label, i }))
                  .reverse()
                  .map(({ label, i }) => (
                    <tr key={label}>
                      <td>{label}</td>
                      <td>{data.attempts[i] ?? 0}</td>
                      <td>{data.avg_percentage[i] ?? 0}%</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
