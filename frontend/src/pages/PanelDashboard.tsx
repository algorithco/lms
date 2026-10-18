import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useLang } from '../i18n/LangContext';
import {
  Panel,
  type PanelDashboardResponse,
  type PanelGroupItem,
  type PanelTeacherItem,
  type PanelAttendanceItem,
} from '../lib/api';
import { num, str } from '../lib/billingPanelGames';
import {
  CheckIcon,
  CopyIcon,
  CreditCardIcon,
  DownloadIcon,
  FileTextIcon,
  FolderOpenIcon,
  PenLineIcon,
  ScrollTextIcon,
  ShieldCheckIcon,
  TargetIcon,
  UsersIcon,
  XIcon,
} from '../components/icons';

/**
 * Admin control panel home — deliberately distinct from the student
 * Dashboard: admin hero banner, platform-wide live stats, quick actions
 * for every management area, then inventory tables.
 * Backend: GET /api/v1/panel/dashboard/ → { tests{...}, questions,
 * essay_topics, users{...}, new_users_today, attempts{total,today},
 * essays{total,awaiting_review}, pending_payments, active_subscriptions,
 * role_breakdown[], recent_tests[], recent_topics[] }.
 */
export default function PanelDashboard() {
  const { t } = useLang();
  const [d, setD] = useState<PanelDashboardResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);

  // Groups, Teachers, and Attendance Management
  const [groups, setGroups] = useState<PanelGroupItem[]>([]);
  const [teachers, setTeachers] = useState<PanelTeacherItem[]>([]);
  const [attendance, setAttendance] = useState<PanelAttendanceItem[]>([]);
  const [groupsLoading, setGroupsLoading] = useState(false);

  // Group Create Modal State
  const [isGroupModalOpen, setIsGroupModalOpen] = useState(false);
  const [groupName, setGroupName] = useState('');
  const [groupSubject, setGroupSubject] = useState<'uzbek' | 'english'>('uzbek');
  const [groupTeacherId, setGroupTeacherId] = useState<number | ''>('');
  const [groupMonthlyFee, setGroupMonthlyFee] = useState(400000);
  const [creatingGroup, setCreatingGroup] = useState(false);
  const [groupSuccessMsg, setGroupSuccessMsg] = useState<string | null>(null);
  const [groupErrorMsg, setGroupErrorMsg] = useState<string | null>(null);
  const [copiedCode, setCopiedCode] = useState<string | null>(null);

  const loadGroupsAndAttendance = () => {
    setGroupsLoading(true);
    Promise.allSettled([
      Panel.groups(),
      Panel.teachers(),
      Panel.attendance(),
    ]).then(([gRes, tRes, aRes]) => {
      if (gRes.status === 'fulfilled') setGroups(gRes.value.results || []);
      if (tRes.status === 'fulfilled') {
        const tList = tRes.value.results || [];
        setTeachers(tList);
        if (tList.length > 0) {
          setGroupTeacherId((prev) => (prev ? prev : tList[0].id));
        }
      }
      if (aRes.status === 'fulfilled') setAttendance(aRes.value.results || []);
      setGroupsLoading(false);
    });
  };

  useEffect(() => {
    loadGroupsAndAttendance();
  }, []);

  const handleCreateGroup = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!groupName.trim()) {
      setGroupErrorMsg('Iltimos, guruh nomini kiriting.');
      return;
    }
    if (!groupTeacherId) {
      setGroupErrorMsg('Iltimos, ustozni tanlang.');
      return;
    }
    setCreatingGroup(true);
    setGroupErrorMsg(null);
    setGroupSuccessMsg(null);
    try {
      const res = await Panel.createGroup({
        name: groupName.trim(),
        subject: groupSubject,
        teacher_id: Number(groupTeacherId),
        monthly_fee: groupMonthlyFee,
      });
      setGroupSuccessMsg(res.message || `Guruh muvaffaqiyatli ochildi! Taklif kodi: #${res.invite_code}`);
      setGroupName('');
      loadGroupsAndAttendance();
    } catch (createErr) {
      setGroupErrorMsg(createErr instanceof Error ? createErr.message : 'Guruh yaratishda xatolik yuz berdi.');
    } finally {
      setCreatingGroup(false);
    }
  };

  const handleCopyCode = (code: string) => {
    navigator.clipboard.writeText(code);
    setCopiedCode(code);
    setTimeout(() => setCopiedCode(null), 2500);
  };

  useEffect(() => {
    Panel.dashboard()
      .then((r) => setD(r))
      .catch((e: unknown) => setErr(e instanceof Error ? e.message : 'Failed.'));
  }, []);

  if (err) return <p className="error" role="alert">{err}</p>;
  if (!d) return <p className="muted" role="status" aria-live="polite">{t('loading')}</p>;

  const tests = d.tests ?? { total: 0, published: 0, draft: 0, archived: 0 };
  const users = d.users ?? { total: 0, active: 0, blocked: 0 };
  const attempts = d.attempts ?? { total: 0, today: 0 };
  const essays = d.essays ?? { total: 0, pending_ai: 0, awaiting_review: 0 };
  const roles = (d.role_breakdown ?? []).filter((r) => r && typeof r.key === 'string');
  const recentTests = (d.recent_tests ?? []).slice(0, 5);
  const recentTopics = (d.recent_topics ?? []).slice(0, 5);

  return (
    <div>
      <div className="card admin-hero">
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span className="admin-hero-badge">
            <ShieldCheckIcon size={28} className="ico" />
          </span>
          <div>
            <h1 style={{ margin: 0 }}>{t('panel_dashboard')}</h1>
            <p className="muted" style={{ margin: '4px 0 0' }}>
              {t('panel_admin_hero_sub')}
            </p>
          </div>
        </div>
        <div className="admin-hero-stats">
          <div>
            <span className="stat-value">{num(attempts.today)}</span>
            <span className="stat-label">{t('panel_attempts_today')}</span>
          </div>
          <div>
            <span className="stat-value">{num(d.new_users_today)}</span>
            <span className="stat-label">{t('panel_new_users')}</span>
          </div>
          <div>
            <span className="stat-value">{num(essays.pending_ai)}</span>
            <span className="stat-label">{t('panel_essays_pending_ai')}</span>
          </div>
          <div>
            <span className="stat-value">{num(essays.awaiting_review)}</span>
            <span className="stat-label">{t('panel_essays_awaiting_review')}</span>
          </div>
          <div>
            <span className="stat-value">{num(d.pending_payments)}</span>
            <span className="stat-label">{t('panel_payments_pending')}</span>
          </div>
        </div>
      </div>

      <h2>{t('panel_quick_actions')}</h2>
      <div className="grid">
        <Link className="card stat admin-action" to="/panel/tests/new">
          <span className="stat-label"><FileTextIcon size={15} className="ico" /> {t('panel_action_new_test')}</span>
          <span className="muted small">{t('panel_action_new_test_hint')}</span>
        </Link>
        <Link className="card stat admin-action" to="/panel/topics">
          <span className="stat-label"><PenLineIcon size={15} className="ico" /> {t('panel_action_new_topic')}</span>
          <span className="muted small">{t('panel_action_new_topic_hint')}</span>
        </Link>
        <Link className="card stat admin-action" to="/teacher/essays">
          <span className="stat-label"><ScrollTextIcon size={15} className="ico" /> {t('panel_action_review_essays')}</span>
          <span className="muted small">
            {t('panel_essays_pending')}: {num(essays.awaiting_review)}
          </span>
        </Link>
        <Link className="card stat admin-action" to="/panel/tuition">
          <span className="stat-label"><CreditCardIcon size={15} className="ico" /> {t('tuition_title')}</span>
          <span className="muted small">
            {t('panel_payments_pending')}: {num(d.pending_payments)} · {t('tuition_admin_sub')}
          </span>
        </Link>
        <Link className="card stat admin-action" to="/panel/users">
          <span className="stat-label"><UsersIcon size={15} className="ico" /> {t('panel_action_manage_users')}</span>
          <span className="muted small">
            {t('panel_active')}: {num(users.active)} · {t('panel_blocked')}: {num(users.blocked)}
          </span>
        </Link>
        <button
          type="button"
          className="card stat admin-action"
          style={{ cursor: 'pointer', textAlign: 'left', background: 'rgba(245, 158, 11, 0.08)', border: '1px solid rgba(245, 158, 11, 0.35)' }}
          onClick={() => {
            setIsGroupModalOpen(true);
            setGroupSuccessMsg(null);
            setGroupErrorMsg(null);
          }}
        >
          <span className="stat-label" style={{ color: '#f59e0b', fontWeight: 700 }}>
            <FolderOpenIcon size={15} className="ico" /> ➕ Yangi Guruh Ochish
          </span>
          <span className="muted small">Ustoz biriktirish va #GR-XXX taklif kodi yaratish</span>
        </button>
      </div>

      <h2>{t('panel_platform')}</h2>
      <div className="grid grid-4-xl">
        <div className="card stat admin-stat-gradient-blue">
          <span className="stat-label">{t('tests')}</span>
          <span className="stat-value">{num(tests.total)}</span>
          <span className="muted small">
            {t('status_published')}: {num(tests.published)} · {t('status_draft')}:{' '}
            {num(tests.draft)} · {t('status_archived')}: {num(tests.archived)}
          </span>
          <Link to="/panel/tests">{t('view_all')} →</Link>
        </div>
        <div className="card stat admin-stat-gradient-green">
          <span className="stat-label">{t('questions')}</span>
          <span className="stat-value">{num(d.questions)}</span>
          <span className="muted small">{t('panel_all_questions_hint')}</span>
        </div>
        <div className="card stat admin-stat-gradient-amber">
          <span className="stat-label">{t('essay_topics')}</span>
          <span className="stat-value">{num(d.essay_topics)}</span>
          <span className="muted small">
            {t('panel_essays_total')}: {num(essays.total)}
          </span>
          <Link to="/panel/topics">{t('view_all')} →</Link>
        </div>
        <div className="card stat admin-stat-gradient-purple">
          <span className="stat-label">{t('users')}</span>
          <span className="stat-value">{num(users.total)}</span>
          <span className="muted small">
            {t('panel_active')}: {num(users.active)} · {t('panel_blocked')}: {num(users.blocked)}
          </span>
          <Link to="/panel/users">{t('view_all')} →</Link>
        </div>
        <div className="card stat admin-stat-gradient-green">
          <span className="stat-label"><TargetIcon size={15} className="ico" /> {t('panel_attempts_total')}</span>
          <span className="stat-value">{num(attempts.total)}</span>
          <span className="muted small">
            {t('panel_attempts_today')}: {num(attempts.today)}
          </span>
          <Link to="/analytics">{t('view_all')} →</Link>
        </div>
        <div className="card stat admin-stat-gradient-purple">
          <span className="stat-label"><CreditCardIcon size={15} className="ico" /> {t('panel_subscriptions')}</span>
          <span className="stat-value">{num(d.active_subscriptions)}</span>
          <span className="muted small">
            {t('panel_payments_pending')}: {num(d.pending_payments)}
          </span>
        </div>
      </div>

      {/* Smart Onboarding Audience Segmentation & Cohort Analytics */}
      {d.cohort_analytics && (
        <section style={{ marginTop: 24, marginBottom: 24 }}>
          <h2>🎯 Auditoriya Segmentatsiyasi va Kogorta Analitikasi</h2>
          <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 16 }}>
            {/* Audience Segmentation Card */}
            <div className="card" style={{ padding: '20px' }}>
              <h3 style={{ fontSize: '1rem', fontWeight: 800, marginBottom: 14, display: 'flex', alignItems: 'center', gap: 8 }}>
                <span>👥 Imtihon yo'nalishlari bo'yicha taqsimot</span>
              </h3>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                {/* National Certificate */}
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.88rem', fontWeight: 700, marginBottom: 6 }}>
                    <span style={{ color: '#10B981' }}>🎓 Milliy sertifikat (Abituriyentlar)</span>
                    <span>
                      {d.cohort_analytics.segmentation.national_certificate.count} nafar (
                      {d.cohort_analytics.segmentation.national_certificate.percentage}%)
                    </span>
                  </div>
                  <div style={{ height: 10, background: 'rgba(255, 255, 255, 0.08)', borderRadius: 5, overflow: 'hidden' }}>
                    <div
                      style={{
                        width: `${Math.min(100, Math.max(0, d.cohort_analytics.segmentation.national_certificate.percentage))}%`,
                        height: '100%',
                        background: '#10B981',
                        borderRadius: 5,
                      }}
                    />
                  </div>
                </div>

                {/* Attestation */}
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.88rem', fontWeight: 700, marginBottom: 6 }}>
                    <span style={{ color: '#3B82F6' }}>👨‍🏫 Attestatsiya 2026 (O'qituvchilar)</span>
                    <span>
                      {d.cohort_analytics.segmentation.attestation.count} nafar (
                      {d.cohort_analytics.segmentation.attestation.percentage}%)
                    </span>
                  </div>
                  <div style={{ height: 10, background: 'rgba(255, 255, 255, 0.08)', borderRadius: 5, overflow: 'hidden' }}>
                    <div
                      style={{
                        width: `${Math.min(100, Math.max(0, d.cohort_analytics.segmentation.attestation.percentage))}%`,
                        height: '100%',
                        background: '#3B82F6',
                        borderRadius: 5,
                      }}
                    />
                  </div>
                </div>

                <div
                  style={{
                    marginTop: 8,
                    padding: '10px 14px',
                    borderRadius: 10,
                    background: 'rgba(255, 255, 255, 0.03)',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                  }}
                >
                  <span style={{ fontSize: '0.82rem', color: 'var(--ink-muted)' }}>
                    Boshlang'ich placement test o'rtacha bali:
                  </span>
                  <strong style={{ color: '#F59E0B', fontSize: '1.05rem' }}>
                    {d.cohort_analytics.avg_placement_score} / 5.0
                  </strong>
                </div>
              </div>
            </div>

            {/* Timeline Breakdown Card */}
            <div className="card" style={{ padding: '20px' }}>
              <h3 style={{ fontSize: '1rem', fontWeight: 800, marginBottom: 14, display: 'flex', alignItems: 'center', gap: 8 }}>
                <span>⏱ Tayyorgarlik muddatlari bo'yicha taqsimot</span>
              </h3>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10, marginTop: 10 }}>
                <div
                  style={{
                    padding: '14px 10px',
                    borderRadius: 12,
                    background: 'rgba(244, 63, 94, 0.1)',
                    border: '1px solid rgba(244, 63, 94, 0.25)',
                    textAlign: 'center',
                  }}
                >
                  <span style={{ fontSize: '0.74rem', color: '#fda4af', fontWeight: 600 }}>1 oylik shoshilinch</span>
                  <div style={{ fontSize: '1.35rem', fontWeight: 900, color: '#f43f5e', marginTop: 4 }}>
                    {d.cohort_analytics.timeline_breakdown.months_1.count}
                  </div>
                </div>

                <div
                  style={{
                    padding: '14px 10px',
                    borderRadius: 12,
                    background: 'rgba(245, 158, 11, 0.1)',
                    border: '1px solid rgba(245, 158, 11, 0.25)',
                    textAlign: 'center',
                  }}
                >
                  <span style={{ fontSize: '0.74rem', color: '#fde68a', fontWeight: 600 }}>3 oylik standart</span>
                  <div style={{ fontSize: '1.35rem', fontWeight: 900, color: '#f59e0b', marginTop: 4 }}>
                    {d.cohort_analytics.timeline_breakdown.months_3.count}
                  </div>
                </div>

                <div
                  style={{
                    padding: '14px 10px',
                    borderRadius: 12,
                    background: 'rgba(16, 185, 129, 0.1)',
                    border: '1px solid rgba(16, 185, 129, 0.25)',
                    textAlign: 'center',
                  }}
                >
                  <span style={{ fontSize: '0.74rem', color: '#a7f3d0', fontWeight: 600 }}>6 oylik uzoq muddatli</span>
                  <div style={{ fontSize: '1.35rem', fontWeight: 900, color: '#10B981', marginTop: 4 }}>
                    {d.cohort_analytics.timeline_breakdown.months_6.count}
                  </div>
                </div>
              </div>

              <div style={{ marginTop: 16, fontSize: '0.8rem', color: 'var(--ink-muted)' }}>
                Jami onboardingdan o'tgan o'quvchilar: <strong>{d.cohort_analytics.total_onboarded} nafar</strong>
              </div>
            </div>
          </div>
        </section>
      )}

      <h2>{t('panel_users_by_role')}</h2>
      <div className="grid">
        {roles.map((r) => (
          <div key={r.key} className="card stat">
            <span className="stat-label">{t(`role_${r.key}`) !== `role_${r.key}` ? t(`role_${r.key}`) : r.key}</span>
            <span className="stat-value">{r.count}</span>
          </div>
        ))}
      </div>

      {/* 👥 Guruhlar va Davomat Monitoringi Section */}
      <section style={{ marginTop: 32, marginBottom: 32 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12, marginBottom: 16 }}>
          <div>
            <h2 style={{ margin: 0, display: 'flex', alignItems: 'center', gap: 8 }}>
              <span>👥</span> Guruhlar va Davomat Monitoringi
            </h2>
            <p className="muted small" style={{ margin: '4px 0 0' }}>
              Barcha faol guruhlar ro'yxati, ustozlar, taklif kodlari va so'nggi darslar davomat ko'rsatkichlari.
            </p>
          </div>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            <a
              href="/api/v1/panel/attendance/export/"
              download
              className="btn sm"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                background: 'rgba(16, 185, 129, 0.15)',
                color: '#10b981',
                border: '1px solid rgba(16, 185, 129, 0.4)',
                fontWeight: 700,
                textDecoration: 'none',
              }}
            >
              <DownloadIcon size={14} />
              <span>📥 Oylik Davomat Hisoboti (Excel)</span>
            </a>
            <button
              type="button"
              className="btn primary sm"
              style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontWeight: 700 }}
              onClick={() => {
                setIsGroupModalOpen(true);
                setGroupSuccessMsg(null);
                setGroupErrorMsg(null);
              }}
            >
              <span>➕ Yangi Guruh Qo'shish</span>
            </button>
          </div>
        </div>

        {groupsLoading ? (
          <p className="muted">Guruhlar yuklanmoqda…</p>
        ) : groups.length === 0 ? (
          <div className="card" style={{ textAlign: 'center', padding: '32px 20px' }}>
            <span style={{ fontSize: '2.5rem' }}>👥</span>
            <h3>Hozircha o'quv guruhlari mavjud emas</h3>
            <p className="muted" style={{ maxWidth: 440, margin: '8px auto 16px' }}>
              O'quv markazingiz yoki repetitorlik yo'nalishingiz uchun yangi guruh oching va o'quvchilarga taklif kodini bering.
            </p>
            <button
              type="button"
              className="btn primary sm"
              onClick={() => setIsGroupModalOpen(true)}
            >
              ➕ Birinchi guruhni ochish
            </button>
          </div>
        ) : (
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>Guruh nomi</th>
                  <th>Fan</th>
                  <th>Ustoz</th>
                  <th>Taklif kodi</th>
                  <th>O'quvchilar</th>
                  <th>Davomat ko'rsatkichi</th>
                  <th>So'nggi darslar</th>
                  <th>Oylik to'lov</th>
                </tr>
              </thead>
              <tbody>
                {groups.map((g) => {
                  const att = attendance.find((a) => a.group_id === g.id);
                  const isEng = g.subject === 'english';
                  return (
                    <tr key={g.id}>
                      <td>
                        <strong>{g.name}</strong>
                      </td>
                      <td>
                        <span className={`badge ${isEng ? 'blue' : 'amber'}`}>
                          {isEng ? '🇬🇧 English' : '🇺🇿 Ona tili'}
                        </span>
                      </td>
                      <td>
                        <div>
                          <strong>{g.teacher_name}</strong>
                          <span className="muted small" style={{ display: 'block' }}>{g.teacher_email}</span>
                        </div>
                      </td>
                      <td>
                        <button
                          type="button"
                          className="badge"
                          style={{
                            cursor: 'pointer',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 4,
                            background: copiedCode === g.invite_code ? 'rgba(16, 185, 129, 0.2)' : 'rgba(245, 158, 11, 0.15)',
                            borderColor: copiedCode === g.invite_code ? '#10b981' : 'rgba(245, 158, 11, 0.4)',
                            color: copiedCode === g.invite_code ? '#10b981' : '#f59e0b',
                            fontWeight: 800,
                            letterSpacing: '0.5px',
                          }}
                          onClick={() => handleCopyCode(g.invite_code)}
                          title="Nusxa olish uchun bosing"
                        >
                          {copiedCode === g.invite_code ? <CheckIcon size={12} /> : <CopyIcon size={12} />}
                          <span>#{g.invite_code}</span>
                        </button>
                      </td>
                      <td>
                        <span style={{ fontWeight: 700 }}>{g.student_count} nafar</span>
                      </td>
                      <td>
                        {att ? (
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <div style={{ width: 60, height: 6, background: 'rgba(255,255,255,0.1)', borderRadius: 3, overflow: 'hidden' }}>
                              <div
                                style={{
                                  width: `${Math.min(100, Math.max(0, att.attendance_rate))}%`,
                                  height: '100%',
                                  background: att.attendance_rate >= 80 ? '#10b981' : att.attendance_rate >= 60 ? '#f59e0b' : '#ef4444',
                                  borderRadius: 3,
                                }}
                              />
                            </div>
                            <span style={{ fontWeight: 800, fontSize: '0.85rem' }}>{att.attendance_rate}%</span>
                          </div>
                        ) : (
                          <span className="muted small">—</span>
                        )}
                      </td>
                      <td>
                        {att && att.recent_sessions && att.recent_sessions.length > 0 ? (
                          <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                            {att.recent_sessions.map((s) => (
                              <span
                                key={s.id}
                                style={{
                                  fontSize: '0.72rem',
                                  padding: '2px 6px',
                                  borderRadius: 6,
                                  background: 'rgba(255,255,255,0.06)',
                                  border: '1px solid rgba(255,255,255,0.1)',
                                }}
                                title={`${s.lesson_date}: ${s.present} keldi, ${s.late} kech, ${s.absent} kelmadi`}
                              >
                                {s.lesson_date.slice(0, 5)}: 🟢{s.present} 🔴{s.absent}
                              </span>
                            ))}
                          </div>
                        ) : (
                          <span className="muted small">0 ta dars</span>
                        )}
                      </td>
                      <td>
                        <span style={{ fontWeight: 700, color: 'var(--ink)' }}>
                          {Number(g.monthly_fee || 400000).toLocaleString()} so'm
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Yangi Guruh Ochish Modal Oynasi */}
      {isGroupModalOpen && (
        <div
          role="dialog"
          aria-modal="true"
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0, 0, 0, 0.75)',
            backdropFilter: 'blur(4px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 9999,
            padding: 16,
          }}
          onClick={(e) => {
            if (e.target === e.currentTarget) setIsGroupModalOpen(false);
          }}
        >
          <div
            className="card"
            style={{
              width: '100%',
              maxWidth: 520,
              background: 'var(--card, #1e293b)',
              border: '1px solid var(--border, #334155)',
              borderRadius: 16,
              padding: 24,
              boxShadow: '0 20px 40px rgba(0,0,0,0.5)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
              <h3 style={{ margin: 0, fontSize: '1.2rem', fontWeight: 800 }}>
                ➕ Yangi O'quv Guruhi Ochish
              </h3>
              <button
                type="button"
                className="btn ghost sm"
                style={{ padding: 4 }}
                onClick={() => setIsGroupModalOpen(false)}
              >
                <XIcon size={18} />
              </button>
            </div>

            {groupSuccessMsg && (
              <div
                style={{
                  background: 'rgba(16, 185, 129, 0.15)',
                  border: '1px solid rgba(16, 185, 129, 0.4)',
                  color: '#10b981',
                  padding: '12px 16px',
                  borderRadius: 10,
                  marginBottom: 16,
                  fontWeight: 600,
                  fontSize: '0.9rem',
                }}
              >
                ✅ {groupSuccessMsg}
              </div>
            )}

            {groupErrorMsg && (
              <div
                style={{
                  background: 'rgba(239, 68, 68, 0.15)',
                  border: '1px solid rgba(239, 68, 68, 0.4)',
                  color: '#f87171',
                  padding: '12px 16px',
                  borderRadius: 10,
                  marginBottom: 16,
                  fontWeight: 600,
                  fontSize: '0.9rem',
                }}
              >
                ⚠️ {groupErrorMsg}
              </div>
            )}

            <form onSubmit={handleCreateGroup}>
              {/* Guruh nomi */}
              <div style={{ marginBottom: 16 }}>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 700, marginBottom: 6 }}>
                  Guruh nomi <span style={{ color: '#f43f5e' }}>*</span>
                </label>
                <input
                  type="text"
                  required
                  placeholder="Masalan: IELTS Target Band 7.5 (Ertalabki)"
                  value={groupName}
                  onChange={(e) => setGroupName(e.target.value)}
                  style={{ width: '100%' }}
                />
              </div>

              {/* Fan yo'nalishi (Segmented Switcher) */}
              <div style={{ marginBottom: 16 }}>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 700, marginBottom: 6 }}>
                  Fan yo'nalishi <span style={{ color: '#f43f5e' }}>*</span>
                </label>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                  <button
                    type="button"
                    onClick={() => setGroupSubject('uzbek')}
                    style={{
                      padding: '10px 14px',
                      borderRadius: 10,
                      border: groupSubject === 'uzbek' ? '2px solid #f59e0b' : '1px solid var(--border)',
                      background: groupSubject === 'uzbek' ? 'rgba(245, 158, 11, 0.15)' : 'transparent',
                      color: groupSubject === 'uzbek' ? '#f59e0b' : 'var(--ink)',
                      fontWeight: 700,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: 8,
                      transition: 'all 0.15s ease',
                    }}
                  >
                    <span>🇺🇿</span>
                    <span>Ona tili</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setGroupSubject('english')}
                    style={{
                      padding: '10px 14px',
                      borderRadius: 10,
                      border: groupSubject === 'english' ? '2px solid #3b82f6' : '1px solid var(--border)',
                      background: groupSubject === 'english' ? 'rgba(59, 130, 246, 0.15)' : 'transparent',
                      color: groupSubject === 'english' ? '#38bdf8' : 'var(--ink)',
                      fontWeight: 700,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: 8,
                      transition: 'all 0.15s ease',
                    }}
                  >
                    <span>🇬🇧</span>
                    <span>English (IELTS)</span>
                  </button>
                </div>
              </div>

              {/* Ustoz biriktirish (Teacher dropdown) */}
              <div style={{ marginBottom: 16 }}>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 700, marginBottom: 6 }}>
                  Guruhga mas'ul ustoz <span style={{ color: '#f43f5e' }}>*</span>
                </label>
                <select
                  required
                  value={groupTeacherId}
                  onChange={(e) => setGroupTeacherId(Number(e.target.value))}
                  style={{ width: '100%' }}
                >
                  <option value="">Ustozni tanlang...</option>
                  {teachers.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.full_name} ({t.email}) — {t.role}
                    </option>
                  ))}
                </select>
              </div>

              {/* Oylik to'lov summasi */}
              <div style={{ marginBottom: 24 }}>
                <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 700, marginBottom: 6 }}>
                  Oylik to'lov summasi (so'm)
                </label>
                <input
                  type="number"
                  min="0"
                  step="10000"
                  placeholder="400000"
                  value={groupMonthlyFee}
                  onChange={(e) => setGroupMonthlyFee(Number(e.target.value))}
                  style={{ width: '100%' }}
                />
                <span className="muted small" style={{ display: 'block', marginTop: 4 }}>
                  Taklif kodi (#GR-XXX) yaratilgach, o'quvchilar ushbu kod orqali guruhga qo'shiladi.
                </span>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
                <button
                  type="button"
                  className="btn ghost sm"
                  onClick={() => setIsGroupModalOpen(false)}
                >
                  Bekor qilish
                </button>
                <button
                  type="submit"
                  className="btn primary sm"
                  disabled={creatingGroup}
                  style={{ fontWeight: 800 }}
                >
                  {creatingGroup ? 'Yaratilmoqda…' : '🚀 Guruhni ochish va kod biriktirish'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      <h2>{t('panel_recent_tests')}</h2>
      {recentTests.length === 0 ? (
        <p className="muted">{t('no_tests_yet')}</p>
      ) : (
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>{t('th_test_name')}</th>
                <th>{t('th_course')}</th>
                <th>{t('th_questions')}</th>
                <th>{t('status')}</th>
              </tr>
            </thead>
            <tbody>
              {recentTests.map((x) => (
                <tr key={str(x.id)}>
                  <td>
                    <Link to={`/panel/tests/${str(x.id)}/questions`}>{str(x.title)}</Link>
                  </td>
                  <td>{str(x.course_title)}</td>
                  <td>{str(x.q_count ?? '', '—')}</td>
                  <td>
                    <span className="badge">{str(x.status)}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h2>{t('panel_recent_topics')}</h2>
      {recentTopics.length === 0 ? (
        <div className="card">
          <p>
            <strong>{t('panel_no_topics')}</strong>
          </p>
          <p className="muted small">{t('panel_no_topics_hint')}</p>
          <Link className="btn primary sm" to="/panel/topics">
            {t('panel_new_topic')}
          </Link>
        </div>
      ) : (
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>{t('th_topic')}</th>
                <th>{t('panel_category')}</th>
                <th>{t('words')}</th>
              </tr>
            </thead>
            <tbody>
              {recentTopics.map((x) => (
                <tr key={str(x.id)}>
                  <td>{str(x.title)}</td>
                  <td>
                    <span className="badge">{str(x.category)}</span>
                  </td>
                  <td className="muted small">
                    {str(x.word_limit_min)}-{str(x.word_limit_max)} {t('words')}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
