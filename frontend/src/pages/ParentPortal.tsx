import { useEffect, useMemo, useState } from 'react';
import { useLang } from '../i18n/LangContext';
import { School, Tuition, type StudentAttendance, type TuitionOverview, type TuitionInvoice, type WeeklyReportRow } from '../lib/api';
import { UsersIcon } from '../components/icons';
import type { ParentChild, ParentOverview } from '../lib/school';
import { errMessage, num } from '../lib/school';

export default function ParentPortal() {
  const { t } = useLang();
  const [children, setChildren] = useState<ParentChild[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  /**
   * Attendance per child, keyed by student id.
   *
   * The endpoint only answers for a child this parent is approved for, so a
   * missing entry means "not permitted / no data" and nothing is rendered —
   * an empty placeholder must never imply that attendance data exists.
   */
  const [attendance, setAttendance] = useState<Record<number, StudentAttendance>>({});
  const [tuition, setTuition] = useState<Record<number, { overview: TuitionOverview; invoices: TuitionInvoice[] }>>({});
  const [weeklyReports, setWeeklyReports] = useState<WeeklyReportRow[]>([]);

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

  // Billing and weekly reports are supplementary; each endpoint restricts
  // results to this parent's verified children.
  useEffect(() => {
    let alive = true;
    Tuition.children().then(({ children: rows }) => {
      if (!alive) return;
      setTuition(Object.fromEntries(rows.map((row) => [
        row.student_id,
        { overview: row, invoices: row.invoice_rows ?? row.invoices ?? [] },
      ])));
    }).catch(() => { /* finance is optional when no verified child invoice exists */ });
    School.myWeeklyReports().then(({ results }) => {
      if (alive) setWeeklyReports(results);
    }).catch(() => { /* retain the existing parent portal if no reports exist */ });
    return () => { alive = false; };
  }, []);

  // Attendance is supplementary: a failure here must not break the portal.
  // One call covering every approved child. The per-student endpoint
  // (school/attendance/students/<id>/) is teacher/admin-only, so asking it as
  // a parent was refused with 403 and this block could never render for the
  // very role the page exists for.
  useEffect(() => {
    let alive = true;
    School.parentAttendance()
      .then(({ children: rows }) => {
        if (!alive) return;
        const next: Record<number, StudentAttendance> = {};
        for (const row of rows ?? []) {
          if (Number.isFinite(row.student_id)) next[row.student_id] = row;
        }
        setAttendance(next);
      })
      .catch(() => {
        /* no approved child / no data — the block stays hidden */
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

                  {tuition[c.id] && (tuition[c.id].invoices.length > 0 || (tuition[c.id].overview.outstanding_uzs ?? 0) > 0) && (
                    <section className="card" aria-label="Kurs to'lovlari">
                      <h3>💳 {t('tuition_title')}</h3>
                      <p className="muted small">{t('tuition_confirmed')}: {Number(tuition[c.id].overview.confirmed_paid_uzs ?? 0).toLocaleString()} so'm · {t('tuition_outstanding')}: {Number(tuition[c.id].overview.outstanding_uzs ?? 0).toLocaleString()} so'm</p>
                      <div className="table-wrap">
                        <table className="data">
                          <thead><tr><th>{t('tuition_period')}</th><th>{t('tuition_status')}</th><th>{t('tuition_amount')}</th><th>{t('tuition_paid')}</th><th>{t('tuition_outstanding')}</th><th>{t('tuition_deadline')}</th></tr></thead>
                          <tbody>{tuition[c.id].invoices.map((invoice) => (
                            <tr key={invoice.id}>
                              <td>{invoice.period_label}</td>
                              <td>{invoice.status_label}{invoice.awaiting_confirmation ? ` · ${t('tuition_pending')}` : ''}</td>
                              <td>{Number(invoice.amount_due_uzs).toLocaleString()} so'm</td>
                              <td>{Number(invoice.paid_amount_uzs).toLocaleString()} so'm</td>
                              <td>{Number(invoice.balance_uzs).toLocaleString()} so'm</td>
                              <td>{invoice.due_date}</td>
                            </tr>
                          ))}</tbody>
                        </table>
                      </div>
                    </section>
                  )}
                  {weeklyReports.filter((report) => report.student_id === c.id).map((report) => (
                    <section key={report.id} className="card" aria-label="Haftalik hisobot">
                      <h3>📊 {t('weekly_reports_title')} · {report.period_label}</h3>
                      <p className="muted small">{t('weekly_attendance')}: {String((report.summary.attendance as Record<string, unknown> | undefined)?.attendance_percentage ?? '—')}% · {t('weekly_essays')}: {String((report.summary.essays as Record<string, unknown> | undefined)?.graded ?? 0)} · {t('weekly_tests')}: {String((report.summary.tests as Record<string, unknown> | undefined)?.completed_attempts ?? 0)}</p>
                    </section>
                  ))}
                  {attendance[c.id] &&
                    (attendance[c.id].marked_records ?? 0) > 0 && (
                      <div className="card">
                        <div className="row" style={{ justifyContent: 'space-between' }}>
                          <strong>{t('attendance_student_history')}</strong>
                          <span className="muted small">
                            {t('attendance_percentage')}:{' '}
                            <b>
                              {attendance[c.id].attendance_percentage !== null
                                ? `${attendance[c.id].attendance_percentage}%`
                                : '—'}
                            </b>
                          </span>
                        </div>
                        <p className="muted small">
                          {t('attendance_present')}: {attendance[c.id].present} ·{' '}
                          {t('attendance_late')}: {attendance[c.id].late} ·{' '}
                          {t('attendance_absent')}: {attendance[c.id].absent} ·{' '}
                          {t('attendance_excused')}: {attendance[c.id].excused}
                        </p>
                        {(attendance[c.id].recent ?? []).length > 0 && (
                          <div className="table-wrap">
                            <table className="data">
                              <thead>
                                <tr>
                                  <th>{t('date')}</th>
                                  <th>{t('attendance_group')}</th>
                                  <th>{t('status')}</th>
                                </tr>
                              </thead>
                              <tbody>
                                {(attendance[c.id].recent ?? []).slice(0, 5).map((rec, i) => (
                                  <tr key={`${rec.date}-${rec.time}-${i}`}>
                                    <td className="muted small">
                                      {rec.date}
                                      {rec.time && rec.time !== '—' ? ` · ${rec.time}` : ''}
                                    </td>
                                    <td>{rec.group}</td>
                                    <td>
                                      <span
                                        className={`badge ${
                                          rec.status === 'present'
                                            ? 'green'
                                            : rec.status === 'late'
                                              ? 'amber'
                                              : 'rose'
                                        }`}
                                      >
                                        {rec.status_label}
                                        {rec.status === 'late' && rec.late_minutes > 0
                                          ? ` (${rec.late_minutes} ${t('minutes')})`
                                          : ''}
                                      </span>
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        )}
                      </div>
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
