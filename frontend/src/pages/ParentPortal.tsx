import { useEffect, useMemo, useState } from 'react';
import { useLang } from '../i18n/LangContext';
import { School } from '../lib/api';
import { UsersIcon } from '../components/icons';
import type { ParentChild, ParentOverview } from '../lib/school';
import { errMessage, num } from '../lib/school';

export default function ParentPortal() {
  const { t } = useLang();
  const [children, setChildren] = useState<ParentChild[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    let alive = true;
    // GET /api/v1/school/parent/ — children with last-10 results each.
    School.parent()
      .then((r) => {
        if (alive) {
          setChildren(((r as unknown as ParentOverview).children ?? []) as ParentChild[]);
          setLoaded(true);
        }
      })
      .catch((e: unknown) => {
        if (alive) {
          setErr(errMessage(e));
          setLoaded(true);
        }
      });
    return () => {
      alive = false;
    };
  }, []);

  const totals = useMemo(() => {
    const all = children.flatMap((c) => c.results ?? []);
    const passedCount = all.filter((r) => r.is_passed).length;
    const avg =
      all.length > 0
        ? Math.round((all.reduce((a, r) => a + num(r.percentage, 0), 0) / all.length) * 10) / 10
        : 0;
    return { results: all.length, passed: passedCount, avg };
  }, [children]);

  if (!loaded && !err) return <p className="muted">{t('loading')}</p>;

  return (
    <div>
      <h1>
        <UsersIcon size={24} className="ico" /> {t('pp_title')}
      </h1>
      <p className="muted">{t('pp_subtitle')}</p>
      {err && <p className="error">{err}</p>}

      {loaded && children.length === 0 && !err ? (
        <div className="card">
          <h2>{t('pp_none_title')}</h2>
          <p className="muted">{t('pp_none_hint')}</p>
          <div className="card" style={{ background: '#eff6ff' }}>
            <p className="muted small">
              💡 <strong>{t('pp_how_title')}</strong>
              <br />
              {t('pp_how_text')}
            </p>
          </div>
        </div>
      ) : (
        <>
          {/* Summary stats — parity with parent_portal.html summary band. */}
          <div className="grid">
            <div className="card stat stat-gradient-blue">
              <span className="stat-label">{t('pp_children')}</span>
              <span className="stat-value">{children.length}</span>
            </div>
            <div className="card stat stat-gradient-green">
              <span className="stat-label">{t('pp_total_tests')}</span>
              <span className="stat-value">{totals.results}</span>
            </div>
            <div className="card stat stat-gradient-amber">
              <span className="stat-label">{t('passed')}</span>
              <span className="stat-value">{totals.passed}</span>
            </div>
            <div className="card stat stat-gradient-purple">
              <span className="stat-label">{t('average_score')}</span>
              <span className="stat-value">{totals.avg}%</span>
            </div>
          </div>

          {/* Per-child cards — each child's results/progress. */}
          <div className="grid" style={{ gridTemplateColumns: '1fr' }}>
            {children.map((c) => {
              const results = c.results ?? [];
              const passedCount = results.filter((r) => r.is_passed).length;
              const avg =
                results.length > 0
                  ? Math.round(
                      (results.reduce((a, r) => a + Number(r.percentage ?? 0), 0) / results.length) * 10,
                    ) / 10
                  : 0;
              return (
                <div key={c.id} className="card">
                  <div className="row" style={{ justifyContent: 'space-between' }}>
                    <div>
                      <strong>{c.name}</strong>
                      <p className="muted small">
                        {c.email}
                        {c.relationship ? ` · ${c.relationship}` : ''}
                      </p>
                    </div>
                    {!c.is_approved && <span className="badge amber">⏳ {t('pp_pending_approval')}</span>}
                  </div>

                  <div className="grid">
                    <div className="card stat">
                      <span className="stat-label">{t('pp_tests')}</span>
                      <span className="stat-value">{results.length}</span>
                    </div>
                    <div className="card stat">
                      <span className="stat-label">{t('passed')}</span>
                      <span className="stat-value">{passedCount}</span>
                    </div>
                    <div className="card stat">
                      <span className="stat-label">{t('average_score')}</span>
                      <span className="stat-value">{avg}%</span>
                    </div>
                  </div>

                  {results.length === 0 ? (
                    <p className="muted small">{t('pp_no_results')}</p>
                  ) : (
                    <>
                      <h3>📝 {t('pp_recent_tests')}</h3>
                      <div className="table-wrap">
                        <table className="data">
                          <thead>
                            <tr>
                              <th>{t('tests')}</th>
                              <th>{t('pp_percent')}</th>
                              <th>{t('status')}</th>
                              <th>{t('date')}</th>
                            </tr>
                          </thead>
                          <tbody>
{results.map((r) => (
                            <tr key={`${r.test}-${r.date}`}>
                                <td>{r.test}</td>
                                <td>
                                  <b className={r.is_passed ? '' : 'error'}>{r.percentage}%</b>
                                </td>
                                <td>
                                  <span className={`badge ${r.is_passed ? 'green' : 'rose'}`}>
                                    {r.is_passed ? `✅ ${t('passed')}` : `❌ ${t('failed')}`}
                                  </span>
                                </td>
                                <td className="muted small">
                                  {r.date ? r.date.slice(0, 16).replace('T', ' ') : '—'}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </>
                  )}
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
