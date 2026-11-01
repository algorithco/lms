import { useCallback, useEffect, useState } from 'react';
import { useLang } from '../i18n/LangContext';
import { Auth, Panel } from '../lib/api';
import { formatDate, str } from '../lib/billingPanelGames';

/**
 * Users admin — parity with templates/panel/user_list.html.
 * Backend: GET /api/v1/panel/users/?q=&role=&status=&joined=
 * (joined: today/7d/30d), POST .../role/ (role), POST .../block/ (toggle),
 * POST .../grant-subscription/ (grant PRO/Premium).
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
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Grant Subscription Modal State
  const [grantModalUser, setGrantModalUser] = useState<Record<string, unknown> | null>(null);
  const [grantPlanType, setGrantPlanType] = useState<'pro' | 'premium'>('pro');
  const [grantDays, setGrantDays] = useState<number>(30);
  const [grantLoading, setGrantLoading] = useState<boolean>(false);

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

  const handleGrant = async () => {
    if (!grantModalUser) return;
    setGrantLoading(true);
    try {
      const res = await Panel.grantSubscription(grantModalUser.id as number, grantPlanType, grantDays);
      setSuccessMsg(res.message);
      setGrantModalUser(null);
      setErr(null);
      load();
      setTimeout(() => setSuccessMsg(null), 6000);
    } catch (e) {
      setErr(e instanceof Error ? e.message : 'Obuna berishda xatolik yuz berdi.');
    } finally {
      setGrantLoading(false);
    }
  };

  return (
    <div>
      <h1>{t('users')}</h1>
      <p className="muted">{t('panel_users_by_role')}</p>
      {err && <p className="error">{err}</p>}
      {successMsg && (
        <div style={{ padding: '12px 16px', background: '#dcfce7', color: '#166534', borderRadius: '10px', marginBottom: '14px', fontWeight: 600, border: '1px solid #86efac' }}>
          ✓ {successMsg}
        </div>
      )}
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
                <th>Obuna (Tarif)</th>
                <th>{t('status_header')}</th>
                <th>{t('date')}</th>
                <th>{t('actions')}</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => {
                const isMe = meId !== null && Number(u.id) === meId;
                const blocked = !u.is_active;
                const planStr = str(u.plan || 'free').toLowerCase();
                const hasPro = Boolean(u.has_pro || planStr === 'pro' || planStr === 'premium');
                const expDate = str(u.subscription_expires_at);

                return (
                  <tr key={str(u.id)}>
                    <td>
                      {(() => {
                        const fn = str(u.full_name).trim();
                        const em = str(u.email).trim();
                        if (fn && fn !== em) return fn;
                        if (em.startsWith('tg_') || em.includes('@tma')) return `Foydalanuvchi #${u.id}`;
                        return em || `Foydalanuvchi #${u.id}`;
                      })()}
                      {isMe && (
                        <>
                          {' '}
                          <span className="badge">{t('panel_you')}</span>
                        </>
                      )}
                    </td>
                    <td>
                      {str(u.email).startsWith('tg_') || str(u.email).includes('@tma') ? (
                        <span
                          className="badge"
                          style={{
                            background: 'rgba(56, 189, 248, 0.12)',
                            color: '#0284c7',
                            border: '1px solid rgba(56, 189, 248, 0.3)',
                            fontSize: '0.75rem',
                            fontWeight: 700,
                          }}
                        >
                          📱 Telegram SSO
                        </span>
                      ) : (
                        <small className="muted">{str(u.email)}</small>
                      )}
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
                      {str(u.role) === 'admin' ? (
                        <span className="badge" style={{ background: '#fef3c7', color: '#b45309', fontWeight: 700 }}>
                          👑 Admin
                        </span>
                      ) : hasPro ? (
                        <div>
                          <span className="badge" style={{ background: '#dcfce7', color: '#15803d', fontWeight: 700 }}>
                            ⭐ {planStr.toUpperCase()}
                          </span>
                          {expDate && (
                            <div style={{ fontSize: '11px', color: '#64748b', marginTop: '2px' }}>
                              {expDate} gacha
                            </div>
                          )}
                        </div>
                      ) : (
                        <span className="badge muted">Free</span>
                      )}
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
                      <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                        <button
                          className="btn sm"
                          style={{ background: '#f59e0b', color: '#fff', border: 'none', fontWeight: 600, fontSize: '11px', padding: '4px 8px', borderRadius: '6px', cursor: 'pointer' }}
                          onClick={() => {
                            setGrantModalUser(u);
                            setGrantPlanType('pro');
                            setGrantDays(30);
                            setErr(null);
                          }}
                          title="Foydalanuvchiga bepul obuna berish"
                        >
                          ⭐ PRO Berish
                        </button>
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
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Grant Subscription Modal */}
      {grantModalUser && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(15, 23, 42, 0.6)',
            backdropFilter: 'blur(4px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 9999,
            padding: '16px',
          }}
          onClick={() => setGrantModalUser(null)}
        >
          <div
            style={{
              background: '#ffffff',
              borderRadius: '16px',
              padding: '24px',
              width: '100%',
              maxWidth: '440px',
              boxShadow: '0 20px 25px -5px rgba(0,0,0,0.2)',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3 style={{ margin: '0 0 8px 0', fontSize: '18px', fontWeight: 700, color: '#0f172a' }}>
              ⭐ Bepul Obuna Biriktirish
            </h3>
            <p style={{ margin: '0 0 16px 0', fontSize: '14px', color: '#64748b' }}>
              <strong>{str(grantModalUser.full_name) || str(grantModalUser.email) || `ID #${grantModalUser.id}`}</strong> uchun cheksiz ruxsat taqdim etish:
            </p>

            <div style={{ marginBottom: '14px' }}>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: '#475569', marginBottom: '6px' }}>
                Obuna Rejasi
              </label>
              <select
                value={grantPlanType}
                onChange={(e) => setGrantPlanType(e.target.value as 'pro' | 'premium')}
                style={{ width: '100%', padding: '8px 12px', borderRadius: '8px', border: '1px solid #cbd5e1', fontSize: '14px' }}
              >
                <option value="pro">⭐ PRO — Cheksiz testlar, kunlik 50 AI, Mock testlar</option>
                <option value="premium">💎 PREMIUM — Mutlaq to'liq ruxsat, ustoz vositalari</option>
              </select>
            </div>

            <div style={{ marginBottom: '20px' }}>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: '#475569', marginBottom: '6px' }}>
                Obuna Muddati
              </label>
              <select
                value={grantDays}
                onChange={(e) => setGrantDays(Number(e.target.value))}
                style={{ width: '100%', padding: '8px 12px', borderRadius: '8px', border: '1px solid #cbd5e1', fontSize: '14px' }}
              >
                <option value={30}>📅 1 Oy (30 kun)</option>
                <option value={90}>📅 3 Oy (90 kun)</option>
                <option value={180}>📅 6 Oy (180 kun)</option>
                <option value={365}>🎉 1 Yil (365 kun)</option>
              </select>
            </div>

            <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end' }}>
              <button
                className="btn"
                style={{ background: '#f1f5f9', color: '#475569', border: 'none', padding: '8px 16px', borderRadius: '8px', cursor: 'pointer' }}
                onClick={() => setGrantModalUser(null)}
                disabled={grantLoading}
              >
                Bekor qilish
              </button>
              <button
                className="btn"
                style={{ background: '#0284c7', color: '#ffffff', border: 'none', fontWeight: 600, padding: '8px 16px', borderRadius: '8px', cursor: 'pointer' }}
                onClick={handleGrant}
                disabled={grantLoading}
              >
                {grantLoading ? 'Yuklanmoqda...' : 'Tasdiqlash va Berish'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
