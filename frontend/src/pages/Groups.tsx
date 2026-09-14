import { useCallback, useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { useLang } from '../i18n/LangContext';
import { School } from '../lib/api';
import { FolderOpenIcon, XIcon } from '../components/icons';
import type { GroupMember, SchoolGroup } from '../lib/school';
import { errMessage, getGroupDetail } from '../lib/school';

export default function Groups() {
  const { t } = useLang();
  const [groups, setGroups] = useState<SchoolGroup[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [name, setName] = useState('');
  const [desc, setDesc] = useState('');

  // Inline edit state (PATCH /api/v1/school/groups/<id>/).
  const [editing, setEditing] = useState<number | null>(null);
  const [editName, setEditName] = useState('');
  const [editDesc, setEditDesc] = useState('');

  // Detail / members state.
  const [openGroup, setOpenGroup] = useState<number | null>(null);
  const [search, setSearch] = useState('');
  const [found, setFound] = useState<GroupMember[]>([]);
  const [searching, setSearching] = useState(false);
  const searchTimer = useRef<number | null>(null);

  const load = useCallback(async () => {
    try {
      // GET /api/v1/school/groups/
      const list = (await School.groups()) as unknown as SchoolGroup[];
      setGroups(list);
    } catch (e: unknown) {
      setErr(errMessage(e));
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
      await School.updateGroup(editing, { name: editName.trim(), description: editDesc });
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
      <h1>
        <FolderOpenIcon size={24} className="ico" /> {t('groups')}
      </h1>
      <p className="muted small">{t('td_groups_hint')}</p>
      {err && <p className="error">{err}</p>}
      {ok && <p className="badge green">{ok}</p>}

      {/* Create — parity with group_form.html (name + description). */}
      <form onSubmit={create} className="card form" style={{ maxWidth: '100%' }}>
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

      {/* List — parity with group_list.html cards + empty state. */}
      {groups.length === 0 ? (
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
                    <strong>{g.name}</strong>
                    <p className="muted small">
                      👥 {g.student_count ?? students.length} {t('an_talaba_full')}
                      {g.teacher_name ? ` · ${g.teacher_name}` : ''}
                    </p>
                    {g.description ? <p className="muted small">{g.description}</p> : null}
                    <div className="flex -space-x-2 muted small" aria-hidden>
                      {students.slice(0, 5).map((s) => (
                        <span key={s.id} title={s.full_name}>
                          {(s.first_name || s.full_name || '?').slice(0, 1)}·
                        </span>
                      ))}
                    </div>
                    <div className="row">
                      <button
                        className="btn sm ghost"
                        onClick={() => {
                          setEditing(null);
                          setOpenGroup(open ? null : g.id);
                        }}
                      >
                        {open ? t('back') : t('details')}
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

                {/* Detail — parity with group_detail.html member section. */}
                {open && !isEditing && (
                  <>
                    <h3>
                      {t('grp_members')} ({students.length})
                    </h3>
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
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
