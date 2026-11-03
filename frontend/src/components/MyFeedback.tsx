import { useEffect, useState } from 'react';
import { useLang } from '../i18n/LangContext';
import { FeedbackApi, type MyFeedbackItem } from '../lib/api';

/** "Mening fikrlarim": what the signed-in user sent, its status and any admin reply. */
export default function MyFeedback() {
  const { t } = useLang();
  const [items, setItems] = useState<MyFeedbackItem[] | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    FeedbackApi.mine()
      .then((d) => setItems(d.results))
      .catch(() => setFailed(true));
  }, []);

  return (
    <section className="card myfb" aria-labelledby="myfb-title">
      <h2 id="myfb-title">{t('myfb_title')}</h2>
      {failed && <p className="muted small">{t('myfb_err')}</p>}
      {!failed && items === null && <p className="muted small">{t('loading')}</p>}
      {items && items.length === 0 && <p className="muted small">{t('myfb_empty')}</p>}
      <ul>
        {items?.map((f) => (
          <li key={f.id}>
            <div className="myfb-head">
              <span className="fbi-stars" aria-label={`${f.rating} / 5`}>{'★'.repeat(f.rating)}{'☆'.repeat(5 - f.rating)}</span>
              <span className="badge">{t(`fbi_status_${f.status}`)}</span>
              <span className="muted small">{new Date(f.created_at).toLocaleDateString()}</span>
            </div>
            <p>{f.message}</p>
            {f.admin_reply && (
              <blockquote>
                <strong>{t('myfb_reply')}</strong>
                <span>{f.admin_reply}</span>
              </blockquote>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
