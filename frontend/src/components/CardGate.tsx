import { Link } from 'react-router-dom';
import { useLang } from '../i18n/LangContext';
import type { CardStatus } from '../lib/useCardInfo';

/** What to show instead of the card number until the server has released it. */
export default function CardGate({ status, onRetry }: { status: CardStatus; onRetry: () => void }) {
  const { t } = useLang();
  if (status === 'loading') return <span className="muted small">{t('loading')}</span>;
  if (status === 'login') {
    return (
      <span className="card-gate">
        {t('pay_card_login')} <Link to="/login">{t('login')}</Link>
      </span>
    );
  }
  return (
    <span className="card-gate">
      {t('pay_card_error')}{' '}
      <button type="button" className="btn sm" onClick={onRetry}>
        {t('error_retry')}
      </button>
    </span>
  );
}
