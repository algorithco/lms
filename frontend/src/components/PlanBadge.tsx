import { Link } from 'react-router-dom';
import { Crown } from 'lucide-react';
import { useLang } from '../i18n/LangContext';
import { daysLeft, useEntitlement, useTier } from '../lib/useTier';

interface Props {
  /** chip = one pill (header); card = pill plus the real term and allowance (sidebar). */
  variant?: 'chip' | 'card';
  onNavigate?: () => void;
}

/** The one place the plan is shown. Label from /me; term and limits from the entitlement. */
export default function PlanBadge({ variant = 'chip', onNavigate }: Props) {
  const { t } = useLang();
  const tier = useTier();
  const ent = useEntitlement();

  const label = tier.isAdmin ? t('tier_admin') : tier.isPaid ? tier.code : t('tier_free');
  const days = !tier.isAdmin && tier.isPaid ? daysLeft(ent?.expires_at) : null;
  const test = ent?.test;
  const details: string[] = [];
  if (tier.isAdmin) {
    details.push(t('tier_admin_note'));
  } else if (tier.isPaid) {
    if (days !== null) details.push(t('tier_days_left').replace('{n}', String(days)));
    if (test) {
      details.push(
        test.unlimited
          ? t('tier_tests_unlimited')
          : test.limit != null
            ? t('tier_tests_used').replace('{used}', String(test.used)).replace('{limit}', String(test.limit))
            : '',
      );
    }
  }

  const pill = (
    <span className={`plan-pill${tier.isPaid ? ' is-paid' : ''}`}>
      {tier.isPaid && <Crown size={14} aria-hidden="true" />}
      <span>
        {t('tier_label')}: <b>{label}</b>
      </span>
    </span>
  );

  if (variant === 'chip') {
    return (
      <span className="plan-chip">
        {pill}
        {!tier.isPaid && (
          <Link to="/subscribe" className="ui-btn ui-btn--sm" onClick={onNavigate}>
            {t('tier_upgrade')}
          </Link>
        )}
      </span>
    );
  }

  return (
    <div className="plan-card">
      {pill}
      {details.filter(Boolean).map((d) => (
        <p key={d}>{d}</p>
      ))}
      {!tier.isPaid && !tier.isAdmin && (
        <>
          <p>{t('tier_free_note')}</p>
          <Link to="/subscribe" className="ui-btn ui-btn--primary ui-btn--sm" onClick={onNavigate}>
            {t('tier_upgrade')}
          </Link>
        </>
      )}
    </div>
  );
}
