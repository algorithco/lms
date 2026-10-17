import React, { useEffect, useState } from 'react';
import { useLang } from '../i18n/LangContext';
import { api } from '../lib/api';
import { TrashIcon, UserIcon } from './icons';

interface ParentRelation {
  id: number;
  parent_phone: string;
  parent_telegram_id: number | null;
  is_verified: boolean;
  verification_code: string;
  weekly_report_enabled: boolean;
  instant_alerts_enabled: boolean;
  created_at: string;
}

export default function ParentMonitoringCard() {
  const { t } = useLang();
  const [relations, setRelations] = useState<ParentRelation[]>([]);
  const [loading, setLoading] = useState(true);
  const [phoneInput, setPhoneInput] = useState('');
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadRelations = async () => {
    try {
      const res = await api.get<{ relations: ParentRelation[] }>('/parents/relation/');
      setRelations(res.relations || []);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadRelations();
  }, []);

  const handleAddPhone = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!phoneInput.trim()) return;
    setSaving(true);
    setError(null);
    setMessage(null);

    try {
      const res = await api.post<{ message: string }>('/parents/relation/', {
        parent_phone: phoneInput.trim(),
      });
      setMessage(res.message);
      setPhoneInput('');
      await loadRelations();
    } catch (err: any) {
      setError(err?.response?.data?.error || t('parent_error_generic'));
    } finally {
      setSaving(false);
    }
  };

  const handleToggle = async (relId: number, field: 'instant_alerts_enabled' | 'weekly_report_enabled', currentVal: boolean) => {
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
                  <strong style={{ fontSize: 15, display: 'block' }}>{rel.parent_phone}</strong>
                  <span className="muted small">
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
                    {t('parent_delete_btn')}
                  </button>
                </div>
              </div>

              {!rel.is_verified && (
                <div
                  style={{
                    background: 'rgba(245, 158, 11, 0.08)',
                    borderRadius: 8,
                    padding: '8px 12px',
                    fontSize: 12,
                    color: 'var(--ink)',
                  }}
                >
                  💡 <strong>{t('parent_connect_tip_prefix')}</strong> Telegramda <code>@grandec_bot</code> ga kirib,{' '}
                  <strong>{rel.verification_code}</strong> {t('parent_connect_tip_body')}
                </div>
              )}

              {/* Toggles */}
              <div
                style={{
                  display: 'flex',
                  gap: 16,
                  flexWrap: 'wrap',
                  borderTop: '1px solid var(--border)',
                  paddingTop: 10,
                }}
              >
                <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={rel.instant_alerts_enabled}
                    onChange={() => handleToggle(rel.id, 'instant_alerts_enabled', rel.instant_alerts_enabled)}
                  />
                  <span>{t('parent_instant_alerts')}</span>
                </label>

                <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={rel.weekly_report_enabled}
                    onChange={() => handleToggle(rel.id, 'weekly_report_enabled', rel.weekly_report_enabled)}
                  />
                  <span>{t('parent_weekly_reports')}</span>
                </label>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div
          style={{
            border: '1px dashed var(--border)',
            borderRadius: 12,
            padding: 20,
            textAlign: 'center',
            marginBottom: 20,
          }}
        >
          <span className="muted small" style={{ display: 'block', marginBottom: 6 }}>
            {t('parent_no_relations')}
          </span>
          <span className="muted small">
            {t('parent_no_relations_sub')}
          </span>
        </div>
      )}

      {/* Add New Parent Phone Form */}
      <form onSubmit={handleAddPhone} style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
        <input
          type="text"
          placeholder={t('parent_phone_placeholder')}
          value={phoneInput}
          onChange={(e) => setPhoneInput(e.target.value)}
          style={{
            flex: 1,
            minWidth: 240,
            padding: '10px 14px',
            borderRadius: 10,
            border: '1px solid var(--border)',
            background: 'var(--card)',
            color: 'var(--ink)',
            fontSize: 14,
          }}
        />
        <button
          type="submit"
          disabled={saving}
          className="btn primary btn-glow"
          style={{ padding: '10px 18px', fontSize: 13, fontWeight: 700 }}
        >
          {saving ? t('parent_saving') : t('parent_add_btn')}
        </button>
      </form>
    </div>
  );
}
