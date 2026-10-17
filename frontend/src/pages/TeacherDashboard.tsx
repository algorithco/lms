import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { useLang } from '../i18n/LangContext';
import {
  MockTests,
  type MockLeaderboardResponse,
  type MockTestCreateResponse,
  School,
  type WeeklyReportRow,
} from '../lib/api';
import AnalyticsChart from '../components/AnalyticsChart';
import AttendancePanel from '../components/AttendancePanel';
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
  const [weeklyReports, setWeeklyReports] = useState<WeeklyReportRow[]>([]);

  // Quick Mock Creator state
  const [mockTitle, setMockTitle] = useState('');
  const [mockKeys, setMockKeys] = useState('');
  const [mockTime, setMockTime] = useState(60);
  const [mockBusy, setMockBusy] = useState(false);
  const [mockCreated, setMockCreated] = useState<MockTestCreateResponse | null>(null);
  const [mockErr, setMockErr] = useState<string | null>(null);
  const [copiedMock, setCopiedMock] = useState(false);

  // Quick Mock Leaderboard View
  const [activeMockId, setActiveMockId] = useState<number | null>(null);
  const [leaderboardData, setLeaderboardData] = useState<MockLeaderboardResponse | null>(null);
  const [leaderboardLoading, setLeaderboardLoading] = useState(false);
  const [leaderboardErr, setLeaderboardErr] = useState<string | null>(null);

  const createQuickMock = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!mockKeys.trim()) return;
    setMockBusy(true);
    setMockErr(null);
    setMockCreated(null);
    try {
      const res = await MockTests.create({
        title: mockTitle.trim() || undefined,
        keys: mockKeys.trim(),
        time_limit: mockTime,
      });
      setMockCreated(res);
      setMockKeys('');
      setMockTitle('');
    } catch (e2) {
      setMockErr(e2 instanceof Error ? e2.message : 'Mock test yaratishda xatolik yuz berdi.');
    } finally {
      setMockBusy(false);
    }
  };

  const viewMockLeaderboard = async (testId: number) => {
    setActiveMockId(testId);
    setLeaderboardLoading(true);
    setLeaderboardErr(null);
    try {
      const res = await MockTests.leaderboard(testId);
      setLeaderboardData(res);
    } catch (e2) {
      setLeaderboardErr(e2 instanceof Error ? e2.message : 'Reytingni yuklab bo‘lmadi.');
    } finally {
      setLeaderboardLoading(false);
    }
  };

  const copyMockCode = (code: string) => {
    void navigator.clipboard.writeText(code);
    setCopiedMock(true);
    setTimeout(() => setCopiedMock(false), 2500);
  };

  useEffect(() => {
    let alive = true;
    School.weeklyReports().then(({ results }) => {
      if (alive) setWeeklyReports(results);
    }).catch(() => { /* report archive is supplementary */ });
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

      {/* 🚀 Tezkor Mock Test Yaratish & BMB Reyting */}
      <div
        className="card"
        style={{
          marginTop: 18,
          background: 'linear-gradient(135deg, rgba(59, 130, 246, 0.05) 0%, rgba(16, 185, 129, 0.05) 100%)',
          border: '1px solid rgba(59, 130, 246, 0.25)',
          borderRadius: '14px',
          padding: '20px',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
          <div>
            <h2 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: 8 }}>
              <span>🚀</span> Tezkor Mock Test Yaratish (1-soniyada kalitlar orqali)
            </h2>
            <p className="muted small" style={{ margin: '4px 0 0' }}>
              Qog‘ozdagi yoki PDF variantdagi test kalitlarini (masalan, <code>1a2b3c...40b</code>) tashlang — tizim avtomatik 40 talik Mock sessiya yaratib, <strong>#MOCK-...</strong> unikal kod beradi!
            </p>
          </div>
        </div>

        <form onSubmit={createQuickMock} style={{ marginTop: 16 }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 12 }}>
            <label className="small">
              Mock Test Nomi (ixtiyoriy):
              <input
                value={mockTitle}
                onChange={(e) => setMockTitle(e.target.value)}
                placeholder="Milliy Sertifikat Mock Test #1"
              />
            </label>
            <label className="small">
              Vaqt chegarasi (daqiqa):
              <input
                type="number"
                min="5"
                max="300"
                value={mockTime}
                onChange={(e) => setMockTime(Number(e.target.value))}
              />
            </label>
          </div>

          <label className="small" style={{ marginTop: 10, display: 'block' }}>
            To‘g‘ri javoblar kaliti:
            <textarea
              rows={2}
              value={mockKeys}
              onChange={(e) => setMockKeys(e.target.value)}
              placeholder="Masalan: 1a2b3c4d5a...40b yoki 1:A, 2:B, 3:C... yoki ABCDABCD..."
              required
              style={{ fontFamily: 'monospace', fontSize: '0.9rem', marginTop: 4 }}
            />
          </label>

          <div style={{ display: 'flex', gap: 10, alignItems: 'center', marginTop: 12, flexWrap: 'wrap' }}>
            <button className="btn primary sm" disabled={mockBusy}>
              {mockBusy ? 'Yaratilmoqda…' : '⚡ 1-soniyada Mock Test Yaratish'}
            </button>
            {mockErr && <span className="error small">{mockErr}</span>}
          </div>
        </form>

        {/* Mock Created Success Banner */}
        {mockCreated && (
          <div
            style={{
              marginTop: 16,
              background: 'rgba(16, 185, 129, 0.08)',
              border: '1px solid rgba(16, 185, 129, 0.3)',
              borderRadius: '10px',
              padding: '14px',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10 }}>
              <div>
                <strong style={{ color: '#10b981', display: 'block', fontSize: '1rem' }}>
                  🎉 Mock Test Muvaffaqiyatli Yaratildi!
                </strong>
                <p style={{ margin: '4px 0 0', fontSize: '0.88rem' }}>
                  {mockCreated.title} · {mockCreated.questions_count} ta savol · {mockCreated.time_limit} daqiqa
                </p>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span
                  style={{
                    padding: '4px 12px',
                    borderRadius: '6px',
                    background: 'rgba(16, 185, 129, 0.2)',
                    color: '#10b981',
                    fontWeight: 800,
                    fontSize: '1.05rem',
                    letterSpacing: '0.5px',
                  }}
                >
                  {mockCreated.mock_code}
                </span>
                <button
                  type="button"
                  className="btn sm"
                  onClick={() => copyMockCode(mockCreated.mock_code)}
                >
                  {copiedMock ? '✓ Nusxalandi' : '📋 Kodni nusxalash'}
                </button>
                <button
                  type="button"
                  className="btn sm ghost"
                  onClick={() => viewMockLeaderboard(mockCreated.test_id)}
                >
                  🏆 Reytingni ko‘rish
                </button>
              </div>
            </div>
            <p className="muted small" style={{ margin: '8px 0 0' }}>
              💡 O‘quvchilaringiz ushbu kodni saytda yoki Telegram botda (@grandec_bot) kiritib, 1 bosishda testni boshlashlari mumkin!
            </p>
          </div>
        )}

        {/* Mock Leaderboard Modal/Panel */}
        {activeMockId && (
          <div style={{ marginTop: 18, borderTop: '1px solid rgba(255, 255, 255, 0.08)', paddingTop: 14 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
              <h3 style={{ margin: 0 }}>
                🏆 Guruh Mock Reytingi & BMB Darajalari
              </h3>
              <button
                type="button"
                className="btn sm ghost"
                onClick={() => {
                  setActiveMockId(null);
                  setLeaderboardData(null);
                }}
              >
                ✕ Yopish
              </button>
            </div>

            {leaderboardLoading && <p className="muted small">Reyting hisoblanmoqda…</p>}
            {leaderboardErr && <p className="error small">{leaderboardErr}</p>}
            {leaderboardData && (
              <div>
                <p className="muted small" style={{ marginBottom: 10 }}>
                  <strong>{leaderboardData.title}</strong> ({leaderboardData.mock_code}) · Jami qatnashchilar: {leaderboardData.total_participants} ta
                </p>

                {/* BMB Grade summary pill strip */}
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 14 }}>
                  {Object.entries(leaderboardData.bmb_summary).map(([gr, count]) => (
                    <span
                      key={gr}
                      style={{
                        padding: '3px 8px',
                        borderRadius: '4px',
                        fontSize: '0.8rem',
                        fontWeight: 700,
                        background: gr.startsWith('A') ? 'rgba(16, 185, 129, 0.15)' : gr.startsWith('B') ? 'rgba(59, 130, 246, 0.15)' : gr.startsWith('C') ? 'rgba(245, 158, 11, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                        color: gr.startsWith('A') ? '#10b981' : gr.startsWith('B') ? '#3b82f6' : gr.startsWith('C') ? '#f59e0b' : '#ef4444',
                      }}
                    >
                      {gr}: {count} ta
                    </span>
                  ))}
                </div>

                {leaderboardData.leaderboard.length === 0 ? (
                  <p className="muted small">Hozircha hech kim ushbu mock testni yakunlamadi.</p>
                ) : (
                  <div style={{ overflowX: 'auto' }}>
                    <table className="data" style={{ fontSize: '0.84rem' }}>
                      <thead>
                        <tr>
                          <th>O‘rin</th>
                          <th>O‘quvchi</th>
                          <th>Ball</th>
                          <th>Foiz</th>
                          <th>BMB Daraja</th>
                          <th>Vaqt</th>
                        </tr>
                      </thead>
                      <tbody>
                        {leaderboardData.leaderboard.map((item) => (
                          <tr key={item.rank}>
                            <td><strong>#{item.rank}</strong></td>
                            <td>{item.student_name}</td>
                            <td>{item.score} / {item.max_score}</td>
                            <td><strong>{item.percentage}%</strong></td>
                            <td>
                              <span className={`badge ${item.bmb_grade.startsWith('A') ? 'green' : item.bmb_grade.startsWith('B') ? 'blue' : 'rose'}`}>
                                {item.bmb_grade} ({item.bmb_title})
                              </span>
                            </td>
                            <td className="muted small">{item.date ? new Date(item.date).toLocaleDateString() : '—'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
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

      {weeklyReports.length > 0 && (
        <section className="card" aria-label="Weekly reports">
          <h2>📊 {t('weekly_group_reports_title')}</h2>
          {weeklyReports.map((report) => <article key={report.id}>
            <h3>{report.group_name} · {report.period_label} · v{report.version}</h3>
            <p className="muted small">{report.text.replace(/\*/g, '')}</p>
          </article>)}
        </section>
      )}

      {/* Attendance workspace — group roster, 4-way marking, finalization. */}
      <h2>{t('attendance_title')}</h2>
      <AttendancePanel />

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
                <th>Tarif</th>
                <th>Testlar</th>
                <th>Esselar</th>
                <th>{t('groups')}</th>
              </tr>
            </thead>
            <tbody>
              {students.map((s) => (
                <tr key={s.id}>
                  <td><strong>{s.full_name}</strong></td>
                  <td>{s.email}</td>
                  <td>
                    <span className="badge green" style={{ fontWeight: 600 }}>
                      {s.pro_status_label ?? '⭐ PRO (Faol)'}
                    </span>
                  </td>
                  <td>{s.tests_count ?? 0} ta</td>
                  <td>{s.essays_count ?? 0} ta</td>
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
