import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useLang } from '../i18n/LangContext';
import { Billing, type BillingEntitlement, type UsageBucket } from '../lib/api';

/**
 * Small usage/plan widget for the student dashboard and subscription pages.
 *
 * Renders only real server-calculated values from
 * GET /api/v1/billing/entitlement/ — never hard-coded limits. The widget is
 * unobtrusive by design: while loading, on error, or for signed-out users it
 * renders nothing rather than blocking the page.
 */

function bucketLine(
  label: string,
  bucket: UsageBucket | undefined,
  t: (k: string) => string,
  fallbackValue?: string,
): string {
  if (bucket && bucket.unlimited) return `${label}: ${t('usage_unlimited')}`;
  if (bucket && typeof bucket.remaining === 'number' && typeof bucket.limit === 'number') {
    return `${label}: ${bucket.remaining}/${bucket.limit} ${t('usage_remaining')}`;
  }
  if (fallbackValue) return `${label}: ${fallbackValue}`;
  return `${label}: ${t('usage_unlimited')}`;
}

/** Local clock time of the cooldown deadline, e.g. "14:30". */
function clockTime(iso: string | null): string {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function planLabel(e: BillingEntitlement, t: (k: string) => string): string {
  if (e.is_sponsored || e.source === 'sponsored') return t('usage_sponsored');
  if (e.source === 'override') return t('usage_admin_override');
  if (!e.is_paid || e.source === 'default' || e.plan_name === 'Bepul') return t('pay_free_label');
  return e.plan_name || String(e.plan_type ?? '') || t('usage_plan');
}

export default function UsageLimits({ showManage = true }: { showManage?: boolean }) {
  const { t } = useLang();
  const [ent, setEnt] = useState<BillingEntitlement | null>(null);

  useEffect(() => {
    let cancelled = false;
    Billing.entitlement()
      .then((data) => {
        if (!cancelled) setEnt(data);
      })
      .catch(() => {
        // Quietly hidden: the widget must never break the host page.
        if (!cancelled) setEnt(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (!ent) return null;

  const sponsored = ent.is_sponsored || ent.source === 'sponsored';
  const isFreePlan = !ent.is_paid && !sponsored && ent.source !== 'override';
  const cooldown = Number(ent.text_cooldown_seconds ?? 0);
  const cooldownAt = cooldown > 0 ? clockTime(ent.text_cooldown_until) : '';

  return (
    <div className="card" style={{ marginBottom: 16 }}>
      <p className="muted small">
        {t('usage_plan')}: <strong>{planLabel(ent, t)}</strong>
      </p>
      <ul className="muted small">
        <li>
          {isFreePlan
            ? `${t('usage_text_essay')}: ${t('usage_text_essay_free_val')}`
            : bucketLine(t('usage_text_essay'), ent.text_essay, t, t('usage_text_essay_free_val'))}
        </li>
        <li>
          {isFreePlan
            ? `${t('usage_image_essay')}: ${t('usage_image_essay_free_val')}`
            : bucketLine(t('usage_image_essay'), ent.image_essay, t, t('usage_image_essay_free_val'))}
        </li>
        <li>
          {isFreePlan
            ? `${t('usage_tests')}: ${t('usage_test_free_val')}`
            : bucketLine(t('usage_tests'), ent.test, t, t('usage_test_free_val'))}
        </li>
        <li>
          {`${t('usage_ai_tutor')}: ${isFreePlan ? t('usage_ai_tutor_free_val') : t('usage_unlimited')}`}
        </li>
        {cooldownAt && (
          <li>
            {t('usage_next_essay')}: <b>{cooldownAt}</b>
          </li>
        )}
      </ul>
      {sponsored && <p className="muted small">{t('usage_no_payment_required')}</p>}
      {showManage && (
        <Link className="btn sm" to="/my-subscription">
          {t('pay_manage')}
        </Link>
      )}
    </div>
  );
}
