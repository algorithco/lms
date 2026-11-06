import React, { useEffect, useState } from 'react';
import { useLang } from '../i18n/LangContext';
import { api } from '../lib/api';
import { TrashIcon, UserIcon } from './icons';
import { Send, Copy, Check, Bell, BellOff, ShieldCheck } from 'lucide-react';

interface ParentRelation {
  id: number;
  parent_name?: string;
  parent_phone: string;
  parent_telegram_id: number | null;
  is_verified: boolean;
  notifications_enabled?: boolean;
  verification_code: string;
  weekly_report_enabled: boolean;
  instant_alerts_enabled: boolean;
  created_at: string;
}

export default function ParentMonitoringCard() {
  const { t } = useLang();
  const [relations, setRelations] = useState<ParentRelation[]>([]);
  const [deepLink, setDeepLink] = useState('');
  const [loading, setLoading] = useState(true);
  const [phoneInput, setPhoneInput] = useState('');
  const [nameInput, setNameInput] = useState('');
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const loadRelations = async () => {
    try {
      const res = await api.get<{ relations: ParentRelation[]; deep_link?: string }>('/parents/relation/');
      setRelations(res.relations || []);
      if (res.deep_link) {
        setDeepLink(res.deep_link);
      }
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadRelations();
  }, []);

  const handleCopyLink = () => {
    if (!deepLink) return;
    navigator.clipboard.writeText(deepLink);
    setCopied(true);
    setMessage('Telegram ulanish havolasi nusxalandi! Uni ota-onangizga yuboring.');
    setTimeout(() => setCopied(false), 3000);
  };

  const handleAddPhone = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!phoneInput.trim()) return;
    setSaving(true);
    setError(null);
    setMessage(null);

    try {
      const res = await api.post<{ message: string }>('/parents/relation/', {
        parent_phone: phoneInput.trim(),
        parent_name: nameInput.trim(),
      });
      setMessage(res.message);
      setPhoneInput('');
      setNameInput('');
      await loadRelations();
    } catch (err: unknown) {
      const respErr = err && typeof err === 'object' && 'response' in err
        ? (err as { response?: { data?: { error?: string } } }).response?.data?.error
        : null;
      setError(respErr || t('parent_error_generic'));
    } finally {
      setSaving(false);
    }
  };

  const handleToggle = async (
    relId: number,
    field: 'instant_alerts_enabled' | 'weekly_report_enabled' | 'notifications_enabled',
    currentVal: boolean
  ) => {
    try {
      await api.patch(`/parents/relation/${relId}/`, {
        [field]: !currentVal,
      });
      setRelations((prev) =>
        prev.map((r) => (r.id === relId ? { ...r, [field]: !currentVal } : r))
      );
    } catch {
      // ignore
    }
  };

  const handleDelete = async (relId: number) => {
    if (!confirm(t('parent_delete_confirm'))) return;
    try {
      await api.delete(`/parents/relation/${relId}/`);
      setRelations((prev) => prev.filter((r) => r.id !== relId));
    } catch {
      // ignore
    }
  };

  return (
    <div className="card" style={{ padding: 24, borderRadius: 16 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
        <div
          style={{
            width: 40,
            height: 40,
            borderRadius: 10,
            background: 'rgba(245, 158, 11, 0.15)',
            color: 'var(--accent)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <UserIcon size={22} />
        </div>
        <div>
          <h2 style={{ fontSize: 18, margin: 0, fontWeight: 800 }}>{t('parent_card_title')}</h2>
          <span className="muted small">
            {t('parent_card_subtitle')}
          </span>
        </div>
      </div>

      {/* Telegram 1-Click Deep Link Section */}
      {deepLink && (
        <div
          style={{
            background: 'linear-gradient(135deg, rgba(200, 146, 42, 0.12) 0%, rgba(200, 146, 42, 0.04) 100%)',
            border: '1px solid rgba(200, 146, 42, 0.3)',
            borderRadius: 12,
            padding: 16,
            marginBottom: 20,
            display: 'flex',
            flexDirection: 'column',
            gap: 12,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 10 }}>
            <div>
              <div style={{ fontWeight: 700, fontSize: 15, color: '#F59E0B', display: 'flex', alignItems: 'center', gap: 6 }}>
                <ShieldCheck size={18} />
                <span>👨‍👩‍👧 Ota-onani Telegramga ulash (1-klikda)</span>
              </div>
              <div className="muted small" style={{ marginTop: 2 }}>
                Ota-onangiz ushbu havola orqali botga kirishi bilan natijalaringiz unga avtomatik biriktiriladi.
              </div>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <a
                href={deepLink}
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 6,
                  padding: '8px 14px',
                  borderRadius: 8,
                  background: 'linear-gradient(135deg, #C8922A 0%, #D97706 100%)',
                  color: '#fff',
                  fontWeight: 600,
                  fontSize: 13,
                  textDecoration: 'none',
                  boxShadow: '0 2px 8px rgba(200, 146, 42, 0.3)',
                }}
              >
                <Send size={14} />
                <span>Telegramda ochish</span>
              </a>

              <button
                type="button"
                onClick={handleCopyLink}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 6,
                  padding: '8px 12px',
                  borderRadius: 8,
                  background: copied ? 'rgba(16, 185, 129, 0.2)' : 'var(--card-2, rgba(255,255,255,0.08))',
                  border: copied ? '1px solid #10B981' : '1px solid var(--border)',
                  color: copied ? '#10B981' : 'var(--text-primary)',
                  fontSize: 13,
                  fontWeight: 500,
                  cursor: 'pointer',
                }}
              >
                {copied ? <Check size={14} /> : <Copy size={14} />}
                <span>{copied ? 'Nusxalandi' : 'Nusxa olish'}</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {message && (
        <div
          style={{
            padding: '10px 14px',
            borderRadius: 10,
            background: 'rgba(16, 185, 129, 0.12)',
            border: '1px solid rgba(16, 185, 129, 0.3)',
            color: '#10b981',
            fontSize: 13,
            marginBottom: 16,
          }}
        >
          ✓ {message}
        </div>
      )}

      {error && (
        <div
          style={{
            padding: '10px 14px',
            borderRadius: 10,
            background: 'rgba(239, 68, 68, 0.12)',
            border: '1px solid rgba(239, 68, 68, 0.3)',
            color: '#ef4444',
            fontSize: 13,
            marginBottom: 16,
          }}
        >
          ⚠ {error}
        </div>
      )}

      {/* Linked Relations List */}
      {loading ? (
        <div className="muted small" style={{ padding: 12 }}>{t('parent_loading')}</div>
      ) : relations.length > 0 ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14, marginBottom: 20 }}>
          {relations.map((rel) => (
            <div
              key={rel.id}
              style={{
                border: '1px solid var(--border)',
                background: 'var(--card-2)',
                borderRadius: 12,
                padding: 16,
                display: 'flex',
                flexDirection: 'column',
                gap: 12,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <strong style={{ fontSize: 15 }}>
                      {rel.parent_name || rel.parent_phone}
                    </strong>
                    {rel.parent_name && rel.parent_phone && !rel.parent_phone.startsWith('tg:') && (
                      <span className="muted small">({rel.parent_phone})</span>
                    )}
                  </div>
                  <span className="muted small" style={{ display: 'block', marginTop: 2 }}>
                    {rel.is_verified ? (
                      <span style={{ color: '#10b981', fontWeight: 600 }}>{t('parent_linked')}</span>
                    ) : (
                      <span style={{ color: '#f59e0b', fontWeight: 600 }}>{t('parent_pending')}</span>
                    )}
                  </span>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  {!rel.is_verified && (
                    <div
                      style={{
                        padding: '4px 10px',
                        background: 'rgba(245, 158, 11, 0.15)',
                        border: '1px solid rgba(245, 158, 11, 0.3)',
                        borderRadius: 8,
                        fontSize: 12,
                        fontWeight: 700,
                        color: 'var(--accent-dark)',
                      }}
                    >
                      {t('parent_code_label')} <code>{rel.verification_code}</code>
                    </div>
                  )}

                  <button
                    type="button"
                    onClick={() => handleDelete(rel.id)}
                    style={{
                      border: 'none',
                      background: 'rgba(239, 68, 68, 0.1)',
                      color: '#ef4444',
                      padding: '6px 10px',
                      borderRadius: 8,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 4,
                      fontSize: 12,
                    }}
                  >
                    <TrashIcon size={14} />
                    <span>{t('parent_delete_btn')}</span>
                  </button>
                </div>
              </div>

              {/* Toggles */}
              {rel.is_verified && (
                <div
                  style={{
                    display: 'flex',
                    flexWrap: 'wrap',
                    gap: 16,
                    paddingTop: 8,
                    borderTop: '1px solid rgba(255,255,255,0.06)',
                  }}
                >
                  <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={rel.notifications_enabled !== false && rel.instant_alerts_enabled}
                      onChange={() =>
                        handleToggle(rel.id, 'instant_alerts_enabled', rel.instant_alerts_enabled)
                      }
                    />
                    <span>{rel.instant_alerts_enabled ? <Bell size={14} style={{ display: 'inline', verticalAlign: 'middle', marginRight: 4 }} /> : <BellOff size={14} style={{ display: 'inline', verticalAlign: 'middle', marginRight: 4 }} />} Tezkor imtihon xabarnomalari</span>
                  </label>

                  <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={rel.weekly_report_enabled}
                      onChange={() =>
                        handleToggle(rel.id, 'weekly_report_enabled', rel.weekly_report_enabled)
                      }
                    />
                    <span>Haftalik yakshanba hisoboti</span>
                  </label>
                </div>
              )}
            </div>
          ))}
        </div>
      ) : null}

      {/* Manual Phone / Name Form */}
      <form onSubmit={handleAddPhone} style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        <div style={{ fontSize: 13, fontWeight: 600 }}>Raqam orqali taklif qilish:</div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          <input
            type="text"
            placeholder="Ota-ona ismi (ixtiyoriy)"
            value={nameInput}
            onChange={(e) => setNameInput(e.target.value)}
            style={{
              flex: '1 1 180px',
              padding: '10px 14px',
              borderRadius: 10,
              border: '1px solid var(--border)',
              background: 'var(--card-2)',
              color: 'var(--text-primary)',
              fontSize: 14,
            }}
          />
          <input
            type="tel"
            placeholder="+998 90 123 45 67"
            value={phoneInput}
            onChange={(e) => setPhoneInput(e.target.value)}
            style={{
              flex: '1 1 200px',
              padding: '10px 14px',
              borderRadius: 10,
              border: '1px solid var(--border)',
              background: 'var(--card-2)',
              color: 'var(--text-primary)',
              fontSize: 14,
            }}
          />
          <button
            type="submit"
            disabled={saving || !phoneInput.trim()}
            className="btn btn-primary"
            style={{ padding: '10px 20px', borderRadius: 10, fontWeight: 600 }}
          >
            {saving ? '...' : t('save')}
          </button>
        </div>
      </form>
    </div>
  );
}
