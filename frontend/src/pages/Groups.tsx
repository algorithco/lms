import { useCallback, useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { useLang } from '../i18n/LangContext';
import { School, WhiteLabelApi } from '../lib/api';
import { FolderOpenIcon, SettingsIcon, UsersIcon, XIcon } from '../components/icons';
import type { GroupMember, SchoolGroup } from '../lib/school';
import { errMessage, getGroupDetail } from '../lib/school';

export default function Groups() {
  const { t } = useLang();
  const [groups, setGroups] = useState<SchoolGroup[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [name, setName] = useState('');
  const [desc, setDesc] = useState('');

  // White-Label B2B Branding Modal State
  const [brandingOpen, setBrandingOpen] = useState(false);
  const [centerName, setCenterName] = useState('');
  const [headerTitle, setHeaderTitle] = useState('');
  const [brandColor, setBrandColor] = useState('#1e3a8a');
  const [logoFile, setLogoFile] = useState<File | null>(null);
  const [stampFile, setStampFile] = useState<File | null>(null);
  const [currentLogoUrl, setCurrentLogoUrl] = useState<string | null>(null);
  const [currentStampUrl, setCurrentStampUrl] = useState<string | null>(null);
  const [savingBranding, setSavingBranding] = useState(false);

  // Inline edit state (PATCH /api/v1/school/groups/<id>/).
  const [editing, setEditing] = useState<number | null>(null);
  const [editName, setEditName] = useState('');
  const [editDesc, setEditDesc] = useState('');

  // Detail / members / analytics / attendance state.
  const [openGroup, setOpenGroup] = useState<number | null>(null);
  const [groupTabs, setGroupTabs] = useState<Record<number, 'members' | 'analytics' | 'attendance'>>({});
  const [groupAttendance, setGroupAttendance] = useState<Record<string, 'present' | 'absent' | 'late' | 'excused'>>({});
  const [analyticsData, setAnalyticsData] = useState<Record<number, import('../lib/api').GroupFullAnalyticsResponse>>({});
  const [analyticsLoading, setAnalyticsLoading] = useState<number | null>(null);
  const [search, setSearch] = useState('');
  const [found, setFound] = useState<GroupMember[]>([]);
  const [searching, setSearching] = useState(false);
  const [loadingGroups, setLoadingGroups] = useState(true);
  const searchTimer = useRef<number | null>(null);

  // Student join by invite code
  const [joinCode, setJoinCode] = useState('');
  const [joinBusy, setJoinBusy] = useState(false);

  const quickMarkStudent = async (
    groupId: number,
    studentId: number,
    status: 'present' | 'absent' | 'late' | 'excused',
    studentName: string,
  ) => {
    const key = `${groupId}_${studentId}`;
    setGroupAttendance((prev) => ({ ...prev, [key]: status }));
    try {
      const res = await School.attendanceQuickMark({
        group_id: groupId,
        student_id: studentId,
        status,
      });
      if (res.parent_alert_scheduled) {
        flash(`⚠️ ${studentName}: "Kelmadi" saqlandi. 15 daqiqadan so'ng ota-onaga Telegram orqali xabar boradi.`);
      } else {
        flash(`✓ ${studentName}: ${status === 'present' ? 'Keldi' : status === 'late' ? 'Kechikdi' : 'Sababli'} darhol saqlandi.`);
      }
    } catch (e2: unknown) {
      setErr(errMessage(e2));
    }
  };

  const load = useCallback(async () => {
    try {
      // GET /api/v1/school/groups/
      const list = (await School.groups()) as unknown as SchoolGroup[];
      setGroups(list);
    } catch (e: unknown) {
      setErr(errMessage(e));
    } finally {
      setLoadingGroups(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(
    () => () => {
      if (searchTimer.current !== null) window.clearTimeout(searchTimer.current);
    },
    [],
  );

  const flash = (msg: string) => {
    setOk(msg);
    setErr(null);
  };

  const handleJoin = async (e: FormEvent) => {
    e.preventDefault();
    if (!joinCode.trim()) return;
    setJoinBusy(true);
    setErr(null);
    setOk(null);
    try {
      const res = await School.joinGroup(joinCode.trim());
      flash(res.message || 'Guruhga muvaffaqiyatli qo‘shildingiz!');
      setJoinCode('');
      await load();
    } catch (e2: unknown) {
      setErr(errMessage(e2));
    } finally {
      setJoinBusy(false);
    }
  };

  const loadAnalytics = async (groupId: number) => {
    setAnalyticsLoading(groupId);
    try {
      const res = await School.groupAnalytics(groupId);
      setAnalyticsData((prev) => ({ ...prev, [groupId]: res }));
    } catch (e2: unknown) {
      setErr(errMessage(e2));
    } finally {
      setAnalyticsLoading(null);
    }
  };

  const copyCode = (code: string) => {
    void navigator.clipboard.writeText(code);
    flash(`Guruh taklif kodi nusxalandi: ${code}`);
  };

  const openBrandingModal = async () => {
    setBrandingOpen(true);
    try {
      const res = await WhiteLabelApi.get();
      setCenterName(res.center_name || '');
      setHeaderTitle(res.header_title || '');
      setBrandColor(res.brand_color || '#1e3a8a');
      setCurrentLogoUrl(res.center_logo_url || null);
      setCurrentStampUrl(res.stamp_signature_url || null);
    } catch {
      // fallback
    }
  };

  const saveBranding = async (e: FormEvent) => {
    e.preventDefault();
    setSavingBranding(true);
    try {
      const fd = new FormData();
      fd.append('center_name', centerName);
      fd.append('header_title', headerTitle);
      fd.append('brand_color', brandColor);
      if (logoFile) fd.append('center_logo', logoFile);
      if (stampFile) fd.append('stamp_signature', stampFile);
      const res = await WhiteLabelApi.update(fd);
      flash('Markaz brendi va hisobot sozlamalari muvaffaqiyatli saqlandi!');
      setCurrentLogoUrl(res.center_logo_url || null);
      setCurrentStampUrl(res.stamp_signature_url || null);
      setBrandingOpen(false);
    } catch (e2: unknown) {
      setErr(errMessage(e2));
    } finally {
      setSavingBranding(false);
    }
  };

  // POST /api/v1/school/groups/ — parity with group_form.html create.
  const create = async (e: FormEvent) => {
    e.preventDefault();
    setErr(null);
    setOk(null);
    try {
      await School.createGroup({ name: name.trim(), description: desc.trim() });
      setName('');
      setDesc('');
      flash(t('gf_created'));
      await load();
    } catch (e2: unknown) {
      setErr(errMessage(e2));
    }
  };

  const startEdit = (g: SchoolGroup) => {
    setOpenGroup(null);
    setEditing(g.id);
    setEditName(g.name);
    setEditDesc(g.description ?? '');
  };

  // PATCH /api/v1/school/groups/<id>/ — parity with group_form.html edit.
  const saveEdit = async (e: FormEvent) => {
    e.preventDefault();
    if (editing === null) return;
    try {
      await School.updateGroup(editing, { name: editName.trim(), description: editDesc.trim() });
      setEditing(null);
      flash(t('grp_updated'));
      await load();
    } catch (e2: unknown) {
      setErr(errMessage(e2));
    }
  };

  // DELETE /api/v1/school/groups/<id>/ — parity with group_confirm_delete.
  const remove = async (id: number) => {
    if (!window.confirm(t('panel_confirm_delete'))) return;
    try {
      await School.deleteGroup(id);
      if (openGroup === id) setOpenGroup(null);
      flash(t('grp_deleted'));
      await load();
    } catch (e2: unknown) {
      setErr(errMessage(e2));
    }
  };

  // GET /api/v1/school/groups/<id>/ via generic api() (typed client lacks it).
  const refreshOne = async (id: number) => {
    const fresh = await getGroupDetail(id);
    setGroups((prev) => prev.map((g) => (g.id === id ? fresh : g)));
  };

  // GET /api/v1/school/students/?q= — debounced member search.
  const onSearch = (qq: string) => {
    setSearch(qq);
    if (searchTimer.current !== null) window.clearTimeout(searchTimer.current);
    if (qq.trim().length < 2) {
      setFound([]);
      setSearching(false);
      return;
    }
    setSearching(true);
    searchTimer.current = window.setTimeout(async () => {
      try {
        const res = (await School.studentSearch(qq.trim())) as unknown as GroupMember[];
        setFound(res);
      } catch {
        setFound([]);
      } finally {
        setSearching(false);
      }
    }, 300);
  };

  // POST /api/v1/school/groups/<id>/members/ {add, remove}.
  const addMember = async (groupId: number, userId: number) => {
    try {
      await School.members(groupId, { add: [userId] });
      setFound((prev) => prev.filter((s) => s.id !== userId));
      flash(t('grp_member_added'));
      await refreshOne(groupId);
    } catch (e2: unknown) {
      setErr(errMessage(e2));
    }
  };

  const removeMember = async (groupId: number, userId: number) => {
    try {
      await School.members(groupId, { remove: [userId] });
      flash(t('grp_member_removed'));
      await refreshOne(groupId);
    } catch (e2: unknown) {
      setErr(errMessage(e2));
    }
  };

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12, marginBottom: 8 }}>
        <div>
          <h1 style={{ margin: 0 }}>
            <FolderOpenIcon size={24} className="ico" /> {t('groups')}
          </h1>
          <p className="muted small" style={{ margin: '4px 0 0' }}>{t('td_groups_hint')}</p>
        </div>
        <button
          type="button"
          onClick={openBrandingModal}
          className="btn sm"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
            background: 'rgba(99, 102, 241, 0.15)',
            borderColor: 'rgba(99, 102, 241, 0.35)',
            color: '#a5b4fc',
            fontWeight: 600,
          }}
        >
          <SettingsIcon size={14} />
          <span>🎨 Markaz brendi & muhri (White-Label)</span>
        </button>
      </div>
      {err && <p className="error">{err}</p>}
      {ok && <p className="badge green">{ok}</p>}

      {/* 2-column header: New Group + Join Group by Code */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 16 }}>
        {/* Create — parity with group_form.html (name + description). */}
        <form onSubmit={create} className="card form" style={{ maxWidth: '100%', margin: 0 }}>
          <h2>{t('gf_new_short')}</h2>
          <div className="row">
            <label>
              {t('gf_name_label')}
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder={t('gf_name_ph')}
                required
              />
            </label>
            <label>
              {t('gf_desc_label')}
              <input
                value={desc}
                onChange={(e) => setDesc(e.target.value)}
                placeholder={t('gf_desc_ph')}
              />
            </label>
          </div>
          <button className="btn primary sm" style={{ alignSelf: 'flex-start' }}>
            {t('gf_create')}
          </button>
        </form>

        {/* Join by invite code form */}
        <form onSubmit={handleJoin} className="card form" style={{ maxWidth: '100%', margin: 0 }}>
          <h2>🎯 Guruhga Taklif Kodi Orqali Qo‘shilish</h2>
          <p className="muted small">Ustoz taqdim etgan unikal guruh kodi (#GR-...) orqali darhol guruhga qo‘shiling:</p>
          <div className="row">
            <label style={{ flex: 1 }}>
              Taklif kodi:
              <input
                value={joinCode}
                onChange={(e) => setJoinCode(e.target.value)}
                placeholder="#GR-104 yoki GR-104"
                required
              />
            </label>
          </div>
          <button className="btn primary sm" disabled={joinBusy} style={{ alignSelf: 'flex-start' }}>
            {joinBusy ? 'Qo‘shilmoqda…' : '🚀 Guruhga qo‘shilish'}
          </button>
        </form>
      </div>

      {/* List — parity with group_list.html cards + empty state. */}
      {loadingGroups ? (
        <p className="muted" role="status" aria-live="polite">{t('loading')}</p>
      ) : groups.length === 0 ? (
        <div className="card" style={{ marginTop: 16 }}>
          <h3>{t('td_no_groups')}</h3>
          <p className="muted">{t('td_no_groups_hint')}</p>
        </div>
      ) : (
        <div className="grid" style={{ marginTop: 16 }}>
          {groups.map((g) => {
            const students = g.students ?? [];
            const open = openGroup === g.id;
            const isEditing = editing === g.id;
            const tab = groupTabs[g.id] ?? 'analytics';
            const analytics = analyticsData[g.id];
            const isLoadingAnalytics = analyticsLoading === g.id;

            return (
              <div key={g.id} className="card">
                {isEditing ? (
                  <form onSubmit={saveEdit} className="form">
                    <label>
                      {t('gf_name_label')}
                      <input value={editName} onChange={(e) => setEditName(e.target.value)} required />
                    </label>
                    <label>
                      {t('gf_desc_label')}
                      <input value={editDesc} onChange={(e) => setEditDesc(e.target.value)} />
                    </label>
                    <div className="row">
                      <button className="btn primary sm">{t('save')}</button>
                      <button type="button" className="btn sm ghost" onClick={() => setEditing(null)}>
                        {t('cancel')}
                      </button>
                    </div>
                  </form>
                ) : (
                  <>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
                      <strong>{g.name}</strong>
                      {g.invite_code && (
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                          <span
                            style={{
                              padding: '2px 8px',
                              borderRadius: '4px',
                              background: 'rgba(59, 130, 246, 0.12)',
                              color: '#3b82f6',
                              fontWeight: 700,
                              fontSize: '0.8rem',
                              border: '1px solid rgba(59, 130, 246, 0.3)',
                            }}
                          >
                            {g.invite_code}
                          </span>
                          <button
                            type="button"
                            className="btn sm ghost"
                            onClick={() => copyCode(g.invite_code!)}
                            title="Taklif kodini nusxalash"
                            style={{ padding: '2px 6px', fontSize: '0.75rem' }}
                          >
                            📋 Nusxa
                          </button>
                        </div>
                      )}
                    </div>
                    <p className="muted small">
                      <UsersIcon size={12} className="ico" /> {g.student_count ?? students.length} {t('an_talaba_full')}
                      {g.teacher_name ? ` · ${g.teacher_name}` : ''}
                    </p>
                    {g.description ? <p className="muted small">{g.description}</p> : null}
                    <div style={{display:'flex', marginLeft:'-8px'}} className="muted small" aria-hidden>
                      {students.slice(0, 5).map((s) => (
                        <span key={s.id} title={s.full_name} style={{marginLeft:'8px'}}>
                          {(s.first_name || s.full_name || '?').slice(0, 1)}·
                        </span>
                      ))}
                    </div>
                    <div className="row" style={{ marginTop: 10 }}>
                      <button
                        className="btn sm ghost"
                        onClick={() => {
                          setEditing(null);
                          const nextOpen = open ? null : g.id;
                          setOpenGroup(nextOpen);
                          if (nextOpen && !analyticsData[g.id]) {
                            void loadAnalytics(g.id);
                          }
                        }}
                      >
                        {open ? t('back') : 'Tahlil va A‘zolar'}
                      </button>
                      <button className="btn sm ghost" onClick={() => startEdit(g)}>
                        {t('edit')}
                      </button>
                      <button className="btn sm danger" onClick={() => remove(g.id)}>
                        {t('delete')}
                      </button>
                    </div>
                  </>
                )}

                {/* Detail — Tabs for Members and Analytics */}
                {open && !isEditing && (
                  <div style={{ marginTop: 14, borderTop: '1px solid rgba(255, 255, 255, 0.08)', paddingTop: 12 }}>
                    <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
                      <button
                        type="button"
                        className={`btn sm ${tab === 'analytics' ? 'primary' : 'ghost'}`}
                        onClick={() => {
                          setGroupTabs((prev) => ({ ...prev, [g.id]: 'analytics' }));
                          if (!analyticsData[g.id]) void loadAnalytics(g.id);
                        }}
                      >
                        📊 Monitoring & BMB
                      </button>
                      <button
                        type="button"
                        className={`btn sm ${tab === 'members' ? 'primary' : 'ghost'}`}
                        onClick={() => setGroupTabs((prev) => ({ ...prev, [g.id]: 'members' }))}
                      >
                        👥 A‘zolar ({students.length})
                      </button>
                      <button
                        type="button"
                        className={`btn sm ${tab === 'attendance' ? 'primary' : 'ghost'}`}
                        onClick={() => setGroupTabs((prev) => ({ ...prev, [g.id]: 'attendance' }))}
                      >
                        📅 1-Click Davomat
                      </button>
                    </div>

                    {tab === 'analytics' && (
                      <div>
                        {isLoadingAnalytics && <p className="muted small">Guruh tahlili yuklanmoqda…</p>}
                        {analytics && (
                          <div style={{ display: 'grid', gap: 12 }}>
                            {/* Export actions */}
                            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                              <a
                                href={School.exportExcelUrl(g.id)}
                                target="_blank"
                                rel="noreferrer"
                                className="btn sm"
                                style={{ display: 'inline-flex', alignItems: 'center', gap: 6, borderColor: '#10b981', color: '#10b981' }}
                              >
                                <span>📥</span> Excel (.xlsx)
                              </a>
                              <a
                                href={School.exportPdfUrl(g.id)}
                                target="_blank"
                                rel="noreferrer"
                                className="btn sm"
                                style={{ display: 'inline-flex', alignItems: 'center', gap: 6, borderColor: '#ef4444', color: '#ef4444' }}
                              >
                                <span>📄</span> PDF Hisobot
                              </a>
                              <a
                                href={WhiteLabelApi.monthlyReportPdfUrl(g.id)}
                                target="_blank"
                                rel="noreferrer"
                                className="btn sm"
                                style={{
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  gap: 6,
                                  background: 'rgba(99, 102, 241, 0.15)',
                                  borderColor: '#6366f1',
                                  color: '#818cf8',
                                  fontWeight: 600,
                                }}
                              >
                                <span>📑</span> Oylik A4 Hisobot (White-Label)
                              </a>
                            </div>

                            {/* Summary stats */}
                            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: 8 }}>
                              <div style={{ background: 'rgba(255, 255, 255, 0.03)', padding: '8px 10px', borderRadius: '6px' }}>
                                <span className="muted small">Testlar:</span>
                                <strong style={{ display: 'block', fontSize: '1.05rem' }}>{analytics.summary.total_tests_taken}</strong>
                              </div>
                              <div style={{ background: 'rgba(255, 255, 255, 0.03)', padding: '8px 10px', borderRadius: '6px' }}>
                                <span className="muted small">Esselar:</span>
                                <strong style={{ display: 'block', fontSize: '1.05rem' }}>{analytics.summary.total_essays_submitted}</strong>
                              </div>
                              <div style={{ background: 'rgba(255, 255, 255, 0.03)', padding: '8px 10px', borderRadius: '6px' }}>
                                <span className="muted small">O‘rtacha Test:</span>
                                <strong style={{ display: 'block', fontSize: '1.05rem', color: '#10b981' }}>{analytics.summary.average_test_percentage}%</strong>
                              </div>
                              <div style={{ background: 'rgba(255, 255, 255, 0.03)', padding: '8px 10px', borderRadius: '6px' }}>
                                <span className="muted small">O‘rtacha Esse:</span>
                                <strong style={{ display: 'block', fontSize: '1.05rem', color: '#f59e0b' }}>{analytics.summary.average_essay_score} / 20</strong>
                              </div>
                            </div>

                            {/* BMB distribution */}
                            <div>
                              <span className="muted small" style={{ fontWeight: 600 }}>BMB Sertifikat Taqsimoti:</span>
                              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 6 }}>
                                {Object.entries(analytics.summary.bmb_distribution).map(([gr, cnt]) => (
                                  <span
                                    key={gr}
                                    style={{
                                      padding: '2px 8px',
                                      borderRadius: '4px',
                                      fontSize: '0.78rem',
                                      fontWeight: 700,
                                      background: gr.startsWith('A') ? 'rgba(16, 185, 129, 0.15)' : gr.startsWith('B') ? 'rgba(59, 130, 246, 0.15)' : gr.startsWith('C') ? 'rgba(245, 158, 11, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                                      color: gr.startsWith('A') ? '#10b981' : gr.startsWith('B') ? '#3b82f6' : gr.startsWith('C') ? '#f59e0b' : '#ef4444',
                                    }}
                                  >
                                    {gr}: {cnt} ta
                                  </span>
                                ))}
                              </div>
                            </div>

                            {/* Student monitoring list */}
                            {analytics.students.length > 0 && (
                              <div style={{ overflowX: 'auto', marginTop: 4 }}>
                                <table className="data" style={{ fontSize: '0.82rem' }}>
                                  <thead>
                                    <tr>
                                      <th>Talaba</th>
                                      <th>Tarif</th>
                                      <th>To‘lov</th>
                                      <th>Testlar</th>
                                      <th>O‘rtacha</th>
                                      <th>BMB</th>
                                      <th>Esselar</th>
                                      <th>Oxirgi faollik</th>
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {analytics.students.map((st) => (
                                      <tr key={st.student_id}>
                                        <td><strong>{st.student_name}</strong></td>
                                        <td><span className="badge green" style={{ fontWeight: 600 }}>⭐ PRO (Faol)</span></td>
                                        <td>
                                          <span className={`badge ${st.tuition_status === 'paid' ? 'green' : st.tuition_status === 'overdue' ? 'rose' : 'amber'}`}>
                                            {st.tuition_label || 'Kutilmoqda'}
                                          </span>
                                        </td>
                                        <td>{st.tests_count}</td>
                                        <td>{st.avg_test_percentage}%</td>
                                        <td>
                                          <span className={`badge ${st.latest_test_grade.startsWith('A') ? 'green' : st.latest_test_grade.startsWith('B') ? 'blue' : 'rose'}`}>
                                            {st.latest_test_grade}
                                          </span>
                                        </td>
                                        <td>{st.essays_count} ta ({st.avg_essay_score} b.)</td>
                                        <td className="muted small">{st.last_active ? new Date(st.last_active).toLocaleDateString() : '—'}</td>
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

                    {tab === 'members' && (
                      <>
                        <h4 style={{ margin: '8px 0' }}>
                          {t('grp_members')} ({students.length})
                        </h4>
                        <ul className="muted small">
                          {students.map((s) => (
                            <li key={s.id}>
                              {s.full_name} ({s.email})
                              <button
                                className="btn sm ghost"
                                style={{ marginLeft: 8 }}
                                onClick={() => removeMember(g.id, s.id)}
                                aria-label={`${t('delete')} ${s.full_name}`}
                              >
                                <XIcon size={13} />
                              </button>
                            </li>
                          ))}
                          {students.length === 0 && <li>{t('gf_no_students')}</li>}
                        </ul>
                        <label className="small">
                          {t('gf_select_students')}
                          <input
                            value={search}
                            onChange={(e) => onSearch(e.target.value)}
                            placeholder={t('mt_search_ph')}
                          />
                        </label>
                        {search.trim().length >= 2 && (
                          <p className="muted small">
                            {searching ? t('loading') : `${found.length} ${t('an_talaba_full')}`}
                          </p>
                        )}
                        <ul className="muted small">
                          {found
                            .filter((s) => !students.some((m) => m.id === s.id))
                            .map((s) => (
                              <li key={s.id}>
                                {s.full_name} ({s.email})
                                <button
                                  className="btn sm ghost"
                                  style={{ marginLeft: 8 }}
                                  onClick={() => addMember(g.id, s.id)}
                                >
                                  + {t('grp_add')}
                                </button>
                              </li>
                            ))}
                        </ul>
                        {search.trim().length >= 2 && !searching && found.length === 0 && (
                          <p className="muted small">{t('grp_no_results')}</p>
                        )}
                      </>
                    )}

                    {tab === 'attendance' && (
                      <div style={{ marginTop: 8 }}>
                        {/* 1-Click Davomat Info Banner */}
                        <div
                          style={{
                            padding: '10px 14px',
                            borderRadius: 8,
                            background: 'rgba(59, 130, 246, 0.08)',
                            border: '1px solid rgba(59, 130, 246, 0.25)',
                            marginBottom: 12,
                            fontSize: '0.84rem',
                            color: '#93c5fd',
                            display: 'flex',
                            alignItems: 'center',
                            gap: 8,
                          }}
                        >
                          <span style={{ fontSize: '1.2rem' }}>⚡</span>
                          <span>
                            <strong>1-Click Davomat:</strong> O'quvchi yonidagi tugmani bosing — davomat darhol saqlanadi. Agar <strong>❌ Kelmadi</strong> tanlansa, 15 daqiqadan so'ng ota-onasining Telegram botiga avtomatik xabar yuboriladi.
                          </span>
                        </div>

                        {students.length === 0 ? (
                          <p className="muted small">Bu guruhda hali o'quvchilar yo'q.</p>
                        ) : (
                          <div className="table-wrap">
                            <table className="data" style={{ fontSize: '0.86rem' }}>
                              <thead>
                                <tr>
                                  <th>O'quvchi</th>
                                  <th>1-Click Davomat</th>
                                </tr>
                              </thead>
                              <tbody>
                                {students.map((s) => {
                                  const key = `${g.id}_${s.id}`;
                                  const curStatus = groupAttendance[key];
                                  return (
                                    <tr key={s.id}>
                                      <td>
                                        <strong>{s.full_name}</strong>
                                        <div className="muted small">{s.email}</div>
                                      </td>
                                      <td>
                                        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                                          <button
                                            type="button"
                                            className={`btn sm ${curStatus === 'present' ? 'primary' : 'ghost'}`}
                                            onClick={() => quickMarkStudent(g.id, s.id, 'present', s.full_name)}
                                            style={{ minHeight: 44, minWidth: 74, fontWeight: curStatus === 'present' ? 800 : 500 }}
                                          >
                                            ✅ Keldi
                                          </button>
                                          <button
                                            type="button"
                                            className={`btn sm ${curStatus === 'late' ? 'primary' : 'ghost'}`}
                                            onClick={() => quickMarkStudent(g.id, s.id, 'late', s.full_name)}
                                            style={{ minHeight: 44, minWidth: 74, fontWeight: curStatus === 'late' ? 800 : 500 }}
                                          >
                                            ⚠️ Kechikdi
                                          </button>
                                          <button
                                            type="button"
                                            className={`btn sm ${curStatus === 'absent' ? 'primary' : 'ghost'}`}
                                            onClick={() => quickMarkStudent(g.id, s.id, 'absent', s.full_name)}
                                            style={{ minHeight: 44, minWidth: 74, fontWeight: curStatus === 'absent' ? 800 : 500 }}
                                          >
                                            ❌ Kelmadi
                                          </button>
                                          <button
                                            type="button"
                                            className={`btn sm ${curStatus === 'excused' ? 'primary' : 'ghost'}`}
                                            onClick={() => quickMarkStudent(g.id, s.id, 'excused', s.full_name)}
                                            style={{ minHeight: 44, minWidth: 74, fontWeight: curStatus === 'excused' ? 800 : 500 }}
                                          >
                                            📝 Sababli
                                          </button>
                                        </div>
                                      </td>
                                    </tr>
                                  );
                                })}
                              </tbody>
                            </table>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* White-Label B2B Branding Modal */}
      {brandingOpen && (
        <div
          role="dialog"
          aria-modal="true"
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0, 0, 0, 0.75)',
            backdropFilter: 'blur(4px)',
            zIndex: 9999,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 16,
          }}
          onClick={() => setBrandingOpen(false)}
        >
          <div
            className="card"
            style={{
              maxWidth: 520,
              width: '100%',
              margin: 0,
              maxHeight: '90vh',
              overflowY: 'auto',
              background: 'var(--card)',
              border: '1px solid var(--border)',
              boxShadow: 'var(--card-shadow, 0 20px 40px rgba(0, 0, 0, 0.3))',
              borderRadius: 16,
              padding: 24,
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
              <h2 style={{ margin: 0, fontSize: '1.2rem', display: 'flex', alignItems: 'center', gap: 8 }}>
                <span>🎨</span> Markaz Brendi & White-Label Sozlamalari
              </h2>
              <button
                type="button"
                className="btn ghost sm"
                onClick={() => setBrandingOpen(false)}
                aria-label="Yopish"
              >
                <XIcon size={18} />
              </button>
            </div>
            <p className="muted small" style={{ marginBottom: 16 }}>
              Ushbu ma'lumotlar ota-onalar yig'ilishi va direktorlar uchun generatsiya qilinadigan rasmiy A4 Oylik PDF hisobotlarida to'liq aks etadi.
            </p>

            <form onSubmit={saveBranding} style={{ display: 'grid', gap: 14 }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, marginBottom: 4 }}>
                  O'quv markazi / Maktab nomi
                </label>
                <input
                  type="text"
                  value={centerName}
                  onChange={(e) => setCenterName(e.target.value)}
                  placeholder="Masalan: GRAND EDUCATION Karmana filiali"
                  required
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, marginBottom: 4 }}>
                  Hisobot bosh sarlavhasi (Header Title)
                </label>
                <input
                  type="text"
                  value={headerTitle}
                  onChange={(e) => setHeaderTitle(e.target.value)}
                  placeholder="Masalan: OYLIK AKADEMIK VA BMB DIAGNOSTIKA HISOBOTI"
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '80px 1fr', gap: 12, alignItems: 'center' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, marginBottom: 4 }}>
                    Brend rangi
                  </label>
                  <input
                    type="color"
                    value={brandColor}
                    onChange={(e) => setBrandColor(e.target.value)}
                    style={{ height: 40, width: '100%', padding: 2, cursor: 'pointer', borderRadius: 8 }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, marginBottom: 4 }}>
                    Rang kodi (HEX)
                  </label>
                  <input
                    type="text"
                    value={brandColor}
                    onChange={(e) => setBrandColor(e.target.value)}
                    placeholder="#1e3a8a"
                  />
                </div>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, marginBottom: 4 }}>
                  O'quv markazi logotipi (PNG / JPG)
                </label>
                {currentLogoUrl && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
                    <img src={currentLogoUrl} alt="Logo" style={{ height: 36, objectFit: 'contain' }} />
                    <span className="small muted">Joriy logotip yuklangan</span>
                  </div>
                )}
                <input
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  onChange={(e) => setLogoFile(e.target.files?.[0] || null)}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, marginBottom: 4 }}>
                  Rasmiy muhr yoki rahbar imzosi (Shaffof PNG tavsiya etiladi)
                </label>
                {currentStampUrl && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
                    <img src={currentStampUrl} alt="Muhr" style={{ height: 44, objectFit: 'contain' }} />
                    <span className="small muted">Joriy muhr yuklangan</span>
                  </div>
                )}
                <input
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  onChange={(e) => setStampFile(e.target.files?.[0] || null)}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 10 }}>
                <button
                  type="button"
                  className="btn ghost sm"
                  onClick={() => setBrandingOpen(false)}
                  disabled={savingBranding}
                >
                  Bekor qilish
                </button>
                <button
                  type="submit"
                  className="btn primary sm"
                  disabled={savingBranding}
                  style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
                >
                  {savingBranding ? 'Saqlanmoqda...' : '💾 Sozlamalarni saqlash'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
