import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useLang } from '../i18n/LangContext';
import { FeedbackApi, type AdminFeedbackItem, type AdminFeedbackList } from '../lib/api';

const STATUSES = ['new', 'seen', 'in_progress', 'resolved'] as const;
const CATEGORIES = ['feedback', 'suggestion', 'bug', 'praise'] as const;

/** Admin inbox: filter, read context, set status, reply, choose what shows on the landing page. */
export default function PanelFeedback() {
  const { t } = useLang();
  const [filters, setFilters] = useState({ category: '', status: '', rating: '', q: '' });
  const [page, setPage] = useState(1);
  const [data, setData] = useState<AdminFeedbackList | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState<number | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    const params: Record<string, string> = { page: String(page) };
    Object.entries(filters).forEach(([k, v]) => v && (params[k] = v));
    FeedbackApi.adminList(params)
      .then((d) => {
        setData(d);
        setError(null);
      })
      .catch(() => setError(t('fbi_err_load')))
      .finally(() => setLoading(false));
  }, [filters, page, t]);

  useEffect(load, [load]);

  const update = async (item: AdminFeedbackItem, patch: Parameters<typeof FeedbackApi.adminUpdate>[1]) => {
    try {
      const next = await FeedbackApi.adminUpdate(item.id, patch);
      setData((d) => (d ? { ...d, results: d.results.map((r) => (r.id === next.id ? next : r)) } : d));
    } catch {
      setError(patch.is_published ? t('fbi_err_consent') : t('fbi_err_save'));
    }
  };

  const setFilter = (key: keyof typeof filters, value: string) => {
    setPage(1);
    setFilters((f) => ({ ...f, [key]: value }));
  };
  const pages = data ? Math.max(1, Math.ceil(data.count / data.page_size)) : 1;

  return (
    <div className="fbi">
      <p className="muted small">
        <Link to="/panel">← {t('panel_back')}</Link>
      </p>
      <h1>{t('fbi_title')}</h1>

      {data && (
        <div className="fbi-stats">
          <span className="badge blue">{t('fbi_total')}: {data.stats.total}</span>
          <span className="badge amber">{t('fbi_avg')}: {data.stats.average_rating}</span>
          {STATUSES.map((s) => (
            <span key={s} className="badge">{t(`fbi_status_${s}`)}: {data.stats.by_status[s] ?? 0}</span>
          ))}
        </div>
      )}

      <div className="fbi-filters card">
        <select aria-label={t('feedback_category')} value={filters.category} onChange={(e) => setFilter('category', e.target.value)}>
          <option value="">{t('fbi_all_categories')}</option>
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>{t(`feedback_cat_${c}`)}</option>
          ))}
        </select>
        <select aria-label={t('fbi_status')} value={filters.status} onChange={(e) => setFilter('status', e.target.value)}>
          <option value="">{t('fbi_all_statuses')}</option>
          {STATUSES.map((s) => (
            <option key={s} value={s}>{t(`fbi_status_${s}`)}</option>
          ))}
        </select>
        <select aria-label={t('feedback_rating')} value={filters.rating} onChange={(e) => setFilter('rating', e.target.value)}>
          <option value="">{t('fbi_all_ratings')}</option>
          {[1, 2, 3, 4, 5].map((n) => (
            <option key={n} value={n}>{'★'.repeat(n)}</option>
          ))}
        </select>
        <input type="search" placeholder={t('fbi_search')} value={filters.q} onChange={(e) => setFilter('q', e.target.value)} />
      </div>

      {error && <p className="error" role="alert">{error}</p>}
      {loading && !data && <p className="muted">{t('loading')}</p>}
      {data && data.results.length === 0 && (
        <div className="card fbi-empty">
          <p><strong>{t('fbi_empty_title')}</strong></p>
          <p className="muted small">{t('fbi_empty_text')}</p>
        </div>
      )}

      <div className="fbi-list">
        {data?.results.map((item) => (
          <article key={item.id} className={`card fbi-item${item.rating <= 2 || item.category === 'bug' ? ' urgent' : ''}`}>
            <header>
              <span className="fbi-stars" aria-label={`${item.rating} / 5`}>{'★'.repeat(item.rating)}{'☆'.repeat(5 - item.rating)}</span>
              <span className="badge">{t(`feedback_cat_${item.category}`)}</span>
              <span className="muted small">{item.name || t('fbi_guest')} · {new Date(item.created_at).toLocaleString()}</span>
            </header>
            <p className="fbi-message">{item.message}</p>
            <button type="button" className="btn ghost sm" onClick={() => setOpen(open === item.id ? null : item.id)}>
              {open === item.id ? t('fbi_hide_context') : t('fbi_show_context')}
            </button>
            {open === item.id && (
              <dl className="fbi-context">
                {Object.entries(item.context).map(([k, v]) => (
                  <div key={k}>
                    <dt>{k}</dt>
                    <dd>{v}</dd>
                  </div>
                ))}
              </dl>
            )}
            <div className="fbi-controls">
              <label>
                <span className="muted small">{t('fbi_status')}</span>
                <select value={item.status} onChange={(e) => update(item, { status: e.target.value })}>
                  {STATUSES.map((s) => (
                    <option key={s} value={s}>{t(`fbi_status_${s}`)}</option>
                  ))}
                </select>
              </label>
              <label className="fbi-publish">
                <input
                  type="checkbox"
                  checked={item.is_published}
                  disabled={!item.consent_public}
                  onChange={(e) => update(item, { is_published: e.target.checked })}
                />
                <span>{item.consent_public ? t('fbi_publish') : t('fbi_no_consent')}</span>
              </label>
            </div>
            <ReplyBox item={item} onSave={(reply) => update(item, { admin_reply: reply })} />
          </article>
        ))}
      </div>

      {data && pages > 1 && (
        <div className="toolbar">
          <button className="btn sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>←</button>
          <span className="muted small">{page} / {pages}</span>
          <button className="btn sm" disabled={page >= pages} onClick={() => setPage((p) => p + 1)}>→</button>
        </div>
      )}
    </div>
  );
}

function ReplyBox({ item, onSave }: { item: AdminFeedbackItem; onSave: (reply: string) => void }) {
  const { t } = useLang();
  const [reply, setReply] = useState(item.admin_reply);
  return (
    <div className="fbi-reply">
      <textarea rows={2} value={reply} maxLength={2000} placeholder={t('fbi_reply_ph')} onChange={(e) => setReply(e.target.value)} aria-label={t('fbi_reply')} />
      <button type="button" className="btn primary sm" disabled={reply.trim() === item.admin_reply.trim()} onClick={() => onSave(reply)}>
        {t('fbi_reply_send')}
      </button>
      {item.replied_at && <span className="muted small">{t('fbi_replied')}: {new Date(item.replied_at).toLocaleString()}</span>}
    </div>
  );
}
