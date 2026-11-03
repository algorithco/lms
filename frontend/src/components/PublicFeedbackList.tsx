import { MessageSquare, Star } from 'lucide-react';
import { useTranslation } from '../i18n/useTranslation';
import type { PublicFeedbackItem } from '../lib/api';

interface Props {
  items: PublicFeedbackItem[];
  loading: boolean;
  onOpen: () => void;
}

const KNOWN_CATS = ['praise', 'suggestion', 'bug', 'feedback'];

function initialsOf(name: string): string {
  const parts = (name || '').trim().split(/\s+/).filter(Boolean);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return (parts[0] || '?').slice(0, 2).toUpperCase();
}

export default function PublicFeedbackList({ items, loading, onOpen }: Props) {
  const { t } = useTranslation();

  const openBtn = (
    <button type="button" className="ui-btn ui-btn--primary" onClick={onOpen}>
      <MessageSquare size={18} aria-hidden="true" />
      <span>{t('feedback_open_btn')}</span>
    </button>
  );

  if (loading) return null;

  if (items.length === 0) {
    return (
      <div className="fb-empty">
        <div className="fb-empty__icon" aria-hidden="true">
          <MessageSquare size={28} />
        </div>
        <h3 className="fb-empty__title">{t('feedback_empty_title')}</h3>
        <p className="fb-empty__desc">{t('feedback_empty_desc')}</p>
        {openBtn}
      </div>
    );
  }

  return (
    <>
      <div className="fb-cta">{openBtn}</div>
      <div className="fb-grid">
        {items.map((item) => (
          <figure key={item.id} className="fb-card">
            <div className="fb-card__top">
              <div className="fb-card__stars" role="img" aria-label={`${item.rating || 5}/5`}>
                {[1, 2, 3, 4, 5].map((s) => (
                  <Star
                    key={s}
                    size={16}
                    aria-hidden="true"
                    fill={s <= (item.rating || 5) ? 'currentColor' : 'none'}
                    className={s <= (item.rating || 5) ? 'is-on' : 'is-off'}
                  />
                ))}
              </div>
              <span className="fb-card__badge">{t(`feedback_cat_${KNOWN_CATS.includes((item.category || '').toLowerCase()) ? item.category.toLowerCase() : 'feedback'}`)}</span>
            </div>
            <blockquote className="fb-card__quote">“{item.message}”</blockquote>
            <figcaption className="fb-card__author">
              <span className="fb-card__avatar" aria-hidden="true">{initialsOf(item.name)}</span>
              <span className="fb-card__who">
                <b>{item.name}</b>
                <small>{item.role || t('feedback_role_default')} · {item.created_at}</small>
              </span>
            </figcaption>
          </figure>
        ))}
      </div>
    </>
  );
}
