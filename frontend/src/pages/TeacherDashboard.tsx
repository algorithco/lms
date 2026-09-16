import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useLang } from '../i18n/LangContext';
import { School } from '../lib/api';
import AnalyticsChart from '../components/AnalyticsChart';
import { UsersIcon } from '../components/icons';
import type {
  AnalyticsData,
  EssayBoard,
  GroupMember,
  RecentResult,
  SchoolGroup,
  TeacherOverview,
} from '../lib/school';
import { errMessage } from '../lib/school';

export default function TeacherDashboard() {
  const { t } = useLang();
  const [data, setData] = useState<TeacherOverview | null>(null);
  const [activity, setActivity] = useState<AnalyticsData | null>(null);
  const [board, setBoard] = useState<EssayBoard | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    // GET /api/v1/school/teacher/ — groups, student_count,
    // published_tests, active_topics, recent_results.
    School.teacher()
      .then((r) => {
        if (alive) { setData(r as unknown as TeacherOverview); setLoading(false); }
      })
      .catch((e: unknown) => {
        if (alive) { setErr(errMessage(e)); setLoading(false); }
      });
    // GET /api/v1/school/analytics/?days=14 — activity strip for the dashboard.
    School.analytics(14)
      .then((r) => {
        if (alive) setActivity(r as unknown as AnalyticsData);
      })
      .catch(() => {
        /* activity is supplementary — dashboard works without it */
      });
    // GET /api/v1/school/essay-leaderboard/ — essay totals + top writers.
    School.essayLeaderboard()
      .then((r) => {
        if (alive) setBoard(r as unknown as EssayBoard);
      })
      .catch(() => {
        /* supplementary */
      });
    return () => {
      alive = false;
    };
  }, []);

  const groups: SchoolGroup[] = data?.groups ?? [];
  const recent: RecentResult[] = data?.recent_results ?? [];

  // Aggregate unique students across the teacher's groups (students lists).
  const students: GroupMember[] = useMemo(() => {
    const seen = new Map<number, GroupMember>();
    for (const g of groups) {
      for (const s of g.students ?? []) seen.set(s.id, s);
    }
    return [...seen.values()].sort((a, b) => a.full_name.localeCompare(b.full_name));
  }, [groups]);

  if (loading && !err) return <p className="muted" role="status" aria-live="polite">{t('loading')}</p>;

  return (
    <div>
      <h1>
        <UsersIcon size={24} className="ico" /> {t('teacher_dashboard')}
      </h1>
      {err && <p className="error" role="alert">{err}</p>}

      {/* Stat cards — parity with teacher_dashboard.html stat cards that the
          /teacher/ endpoint exposes (students, published tests, essay topics). */}
      <div className="grid">
        <div className="card stat stat-gradient-blue">
          <span className="stat-label">{t('students_count')}</span>
          <span className="stat-value">{data ? data.student_count : '…'}</span>
          <span className="muted small">{t('active_students_hint')}</span>
        </div>
        <div className="card stat stat-gradient-green">
          <span className="stat-label">{t('groups')}</span>
          <span className="stat-value">{groups.length}</span>
          <Link to="/groups">{t('view_all')} →</Link>
        </div>
        <div className="card stat stat-gradient-amber">
          <span className="stat-label">{t('stat_tests_created')}</span>
          <span className="stat-value">{data ? data.published_tests : '…'}</span>
          <span className="muted small">{t('active_status')}</span>
        </div>
        <div className="card stat stat-gradient-purple">
          <span className="stat-label">{t('essay_topics')}</span>
          <span className="stat-value">{data ? data.active_topics : '…'}</span>
          <Link to="/essays">{t('view_all')} →</Link>
        </div>
      </div>

      {/* Analytics quick link — mirrors the legacy detailed-analytics banner. */}
      <Link to="/analytics" className="card" style={{ display: 'block', marginTop: 16 }}>
        <strong><UsersIcon size={14} className="ico" /> {t('detailed_analytics')}</strong>
        <p className="muted small">{t('detailed_analytics_hint')}</p>
      </Link>

      {/* Recent activity (last 14 days) from /analytics/. */}
      {activity && activity.labels.length > 0 && (
        <>
          <h2>{t('td_activity')}</h2>
          <div className="card">
            <AnalyticsChart
              data={activity.labels.map((label, i) => ({
                date: label,
                attempts: activity.attempts[i] ?? 0,
                avg: activity.avg_percentage[i] ?? 0,
              }))}
            />
          </div>
        </>
      )}

      {/* Groups + students lists — parity with group_list.html cards. */}
      <h2>{t('groups')}</h2>
      {groups.length === 0 ? (
        <div className="card">
          <p className="muted">{t('td_no_groups_hint')}</p>
          <Link className="btn primary sm" to="/groups">
            {t('gf_new_short')}
          </Link>
        </div>
      ) : (
        <div className="grid">
          {groups.map((g) => (
            <div key={g.id} className="card">
              <strong>{g.name}</strong>
              {g.description ? <p className="muted small">{g.description}</p> : null}
              <p className="muted small">
                <UsersIcon size={12} className="ico" /> {g.student_count ?? (g.students ?? []).length} {t('an_talaba_full')}
              </p>
              <ul className="muted small">
                {(g.students ?? []).slice(0, 5).map((s) => (
                  <li key={s.id}>
                    {s.full_name} ({s.email})
                  </li>
                ))}
              </ul>
              {(g.students ?? []).length > 5 && (
                <p className="muted small">+{(g.students ?? []).length - 5} …</p>
              )}
              <Link to="/groups">{t('details')} →</Link>
            </div>
          ))}
        </div>
      )}

      {/* Full students list across groups. */}
      <h2>
        {t('td_students_list')} ({students.length})
      </h2>
      {students.length === 0 ? (
        <p className="muted">{t('gf_no_students')}</p>
      ) : (
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>{t('th_student')}</th>
                <th>{t('th_email')}</th>
                <th>{t('groups')}</th>
              </tr>
            </thead>
            <tbody>
              {students.map((s) => (
                <tr key={s.id}>
                  <td>{s.full_name}</td>
                  <td>{s.email}</td>
                  <td>
                    {groups
                      .filter((g) => (g.students ?? []).some((m) => m.id === s.id))
                      .map((g) => g.name)
                      .join(', ')}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Submissions — recent_results from /teacher/. */}
      <h2>{t('recent_student_results')}</h2>
      <p className="muted small">{t('latest_submissions_hint')}</p>
      {recent.length === 0 ? (
        <p className="muted">{t('no_student_results_hint')}</p>
      ) : (
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>{t('th_student')}</th>
                <th>{t('th_test_name')}</th>
                <th>{t('score')}</th>
                <th>{t('status')}</th>
                <th>{t('date')}</th>
              </tr>
            </thead>
            <tbody>
              {recent.map((r) => (
                <tr key={`${r.student}-${r.test}-${r.date}`}>
                  <td>{r.student}</td>
                  <td>{r.test}</td>
                  <td>{r.percentage}%</td>
                  <td>
                    <span className={`badge ${r.is_passed ? 'green' : 'rose'}`}>
                      {r.is_passed ? t('status_passed') : t('status_failed')}
                    </span>
                  </td>
                  <td className="muted small">{r.date ? r.date.slice(0, 16).replace('T', ' ') : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Essay queue links — essay UI lives in other streams; link out. */}      <h2>{t('teacher_queue')}</h2>
      <div className="grid">
        <div className="card">
          <strong>{t('essay_topics')}</strong>
          <p className="muted small">{t('td_queue_hint')}</p>
          <Link className="btn primary sm" to="/teacher/essays">
            {t('td_open_queue')} →
          </Link>
        </div>
        <div className="card">
          <strong>{t('lb_essay_title')}</strong>
          <p className="muted small">
            {board ? `${board.total_essays} ${t('lb_total_essays')} · ${board.total_students} ${t('lb_graded_students')}` : t('loading')}
          </p>
          <Link className="btn sm" to="/essay-leaderboard">
            {t('view_all')} →
          </Link>
        </div>
      </div>
      {board && board.podium.length > 0 && (
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>{t('lb_rank')}</th>
                <th>{t('lb_student')}</th>
                <th>{t('lb_best_score')}</th>
                <th>{t('lb_essays_col')}</th>
              </tr>
            </thead>
            <tbody>
              {board.podium.map((e) => (
                <tr key={e.student_id}>
                  <td>{e.rank}</td>
                  <td>{e.name}</td>
                  <td>
                    {e.best_score} <span className="muted small">({e.converted_score} / 75)</span>
                  </td>
                  <td>{e.essay_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
