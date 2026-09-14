import { useCallback, useEffect, useState } from 'react';
import { useLang } from '../i18n/LangContext';
import { Auth, Panel } from '../lib/api';
import { formatDate, str } from '../lib/billingPanelGames';

/**
 * Users admin — parity with templates/panel/user_list.html.
 * Backend: GET /api/v1/panel/users/?q=&role=&status=&joined=
 * (joined: today/7d/30d), POST .../role/ (role), POST .../block/ (toggle).
 * Self-demote/self-block are rejected by the API — surfaced as errors.
 */
export default function PanelUsers() {
  const { t } = useLang();
  const [users, setUsers] = useState<Record<string, unknown>[]>([]);
  const [roles, setRoles] = useState<{ value: string; label: string }[]>([]);
  const [q, setQ] = useState('');
  const [role, setRole] = useState('');
  const [status, setStatus] = useState('');
  const [joined, setJoined] = useState('');
  const [meId, setMeId] = useState<number | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    Auth.me()
      .then((me) => setMeId(me.id))
      .catch(() => undefined);
  }, []);

  const load = useCallback(() => {
    const params: Record<string, string> = {};
    if (q) params.q = q;
    if (role) params.role = role;
    if (status) params.status = status;
    if (joined) params.joined = joined;
    Panel.users(params)
      .then((r) => {
        setUsers(r.results as unknown as Record<string, unknown>[]);
        setRoles(r.roles);
        setErr(null);
      })
      .catch((e: unknown) => setErr(e instanceof Error ? e.message : 'Failed.'));
  }, [q, role, status, joined]);

  useEffect(() => {
    const id = setTimeout(load, 300);
    return () => clearTimeout(id);
  }, [load]);

  const setR = async (id: number | string, r: string) => {
    try {
      await Panel.setRole(id, r);
      setErr(null);
      load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : t('panel_msg_invalid_role'));
    }
  };

  const toggle = async (id: number | string, blocked: boolean) => {
    if (!window.confirm(blocked ? t('panel_confirm_unblock') : t('panel_confirm_block'))) return;
    try {
      await Panel.toggleBlock(id);
      setErr(null);
      load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : 'Failed.');
    }
  };

  return (
    <div>
      <h1>{t('users')}</h1>
      <p className="muted">{t('panel_users_by_role')}</p>
      {err && <p className="error">{err}</p>}
      <div className="toolbar">
        <input placeholder={t('panel_search_users')} value={q} onChange={(e) => setQ(e.target.value)} />
        <select value={role} onChange={(e) => setRole(e.target.value)}>
          <option value="">
            {t('all')} · {t('role')}
          </option>
          {roles.map((r) => (
            <option key={r.value} value={r.value}>
              {r.label}
            </option>
          ))}
        </select>
        <select value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">
            {t('all')} · {t('status_header')}
          </option>
          <option value="active">{t('panel_active')}</option>
          <option value="blocked">{t('panel_blocked')}</option>
        </select>
        <select value={joined} onChange={(e) => setJoined(e.target.value)}>
          <option value="">{t('panel_joined')}</option>
          <option value="today">{t('panel_joined_today')}</option>
          <option value="7d">{t('panel_joined_7d')}</option>
          <option value="30d">{t('panel_joined_30d')}</option>
        </select>
      </div>
      {users.length === 0 ? (
        <p className="muted">{t('panel_no_users')}</p>
      ) : (
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>{t('th_student')}</th>
                <th>{t('email')}</th>
                <th>{t('role')}</th>
                <th>{t('status_header')}</th>
                <th>{t('date')}</th>
                <th>{t('actions')}</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => {
                const isMe = meId !== null && Number(u.id) === meId;
                const blocked = !u.is_active;
                return (
                  <tr key={str(u.id)}>
                    <td>
                      {str(u.full_name) || str(u.email)}
                      {isMe && (
                        <>
                          {' '}
                          <span className="badge">{t('panel_you')}</span>
                        </>
                      )}
                    </td>
                    <td>
                      <small className="muted">{str(u.email)}</small>
                    </td>
                    <td>
                      <select
                        value={str(u.role)}
                        onChange={(e) => setR(u.id as number, e.target.value)}
                        aria-label="role"
                      >
                        {roles.map((r) => (
                          <option key={r.value} value={r.value}>
                            {r.label}
                          </option>
                        ))}
                      </select>
                    </td>
                    <td>
                      <span className={`badge ${u.is_active ? 'green' : 'rose'}`}>
                        {u.is_active ? t('panel_active') : t('panel_blocked')}
                      </span>
                    </td>
                    <td>
                      <small className="muted">{formatDate(u.date_joined)}</small>
                    </td>
                    <td>
                      {isMe ? (
                        <span className="muted small">—</span>
                      ) : (
                        <button
                          className="btn sm danger"
                          onClick={() => toggle(u.id as number, blocked)}
                        >
                          {blocked ? t('panel_unblock') : t('panel_block')}
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
