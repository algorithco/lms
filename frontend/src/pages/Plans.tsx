import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useLang } from '../i18n/LangContext';
import { Billing } from '../lib/api';
import { isFreePlan, planEmoji, price } from '../lib/billingPanelGames';
import { BarChartIcon } from '../components/icons';

interface Plan {
  id: number;
  name: string;
  plan_type: string;
  description?: string;
  price_monthly: number | string;
  price_yearly: number | string;
  max_tests_per_day: number;
  max_essays_per_week: number;
  detailed_analytics: boolean;
  pdf_certificate: boolean;
  priority_support: boolean;
  unlimited_tests: boolean;
  unlimited_essays: boolean;
}

/** Per-plan_type feature bullets — parity with templates/payments/plans.html. */
function featuresFor(p: Plan, t: (k: string) => string): string[] {
  switch (p.plan_type) {
    case 'free':
      return [t('feat_free_1'), t('feat_free_2'), t('feat_free_3')];
    case 'starter':
      return [t('feat_starter_1'), t('feat_starter_2'), t('feat_starter_3')];
    case 'pro':
      return [t('feat_pro_1'), t('feat_pro_2'), t('feat_pro_3')];
    case 'premium':
      return [t('feat_premium_1'), t('feat_premium_2'), t('feat_premium_3'), t('feat_premium_4')];
    default: {
      const out: string[] = [];
      out.push(
        p.unlimited_tests
          ? t('sub_unlimited_tests')
          : `${t('sub_per_day_pre')} ${p.max_tests_per_day} ${t('sub_tests_unit')}`,
      );
      out.push(
        p.unlimited_essays
          ? t('sub_unlimited_essays')
          : `${t('sub_per_week_pre')} ${p.max_essays_per_week} ${t('sub_essays_unit')}`,
      );
      if (p.detailed_analytics) out.push(t('detailed_analytics'));
      if (p.pdf_certificate) out.push(t('sub_pdf_cert'));
      if (p.priority_support) out.push(t('sub_priority_support'));
      return out;
    }
  }
}

export default function Plans() {
  const { t } = useLang();
  const [plans, setPlans] = useState<Plan[]>([]);
  const [myPlanId, setMyPlanId] = useState<number | null>(null);
  // Current-subscription banner — same data as legacy plans.html
  // (GET /api/v1/billing/my/ → subscription.plan + days_remaining).
  const [mySub, setMySub] = useState<Record<string, unknown> | null>(null);
  const [myActive, setMyActive] = useState(false);
  // Session bridge status — GET /subscribe/api/status/ (Billing.status()).
  const [sessionPlan, setSessionPlan] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    Billing.plans()
      .then((r) => {
        setPlans(r.results as unknown as Plan[]);
        setMyPlanId(r.my_plan_id);
      })
      .catch((e: unknown) => setErr(e instanceof Error ? e.message : 'Failed.'));
    Billing.my()
      .then((r) => {
        if (r.subscription) {
          setMySub(r.subscription as Record<string, unknown>);
          setMyActive(String((r.subscription as Record<string, unknown>).status) === 'active');
        }
      })
      .catch(() => undefined);
    // Best-effort: session cookie may not exist for JWT-only logins.
    Billing.status()
      .then((s) => setSessionPlan(String((s as Record<string, unknown>).plan ?? '')))
      .catch(() => undefined);
  }, []);

  const myPlanName = (mySub?.plan as Record<string, unknown> | undefined)?.name;

  return (
    <div>
      <h1>{t('pay_plans_title')}</h1>
      <p className="muted">{t('pay_plans_subtitle')}</p>
      {err && <p className="error">{err}</p>}

      {/* Current subscription banner (legacy: user_subscription.is_active). */}
      {mySub && myActive && (
        <div className="card" style={{ marginBottom: 16 }}>
          <p className="muted small">{t('pay_current_sub')}</p>
          <p>
            <strong>{String(myPlanName ?? '')}</strong>
          </p>
          <p className="muted small">
            {Number(mySub.days_remaining ?? 0) > 0
              ? `${String(mySub.days_remaining)} ${t('pay_days_left')}`
              : t('pay_expired')}
            {sessionPlan ? ` · ${t('billing_session_title')}: ${sessionPlan}` : ''}
          </p>
          <Link className="btn sm" to="/my-subscription">
            {t('pay_manage')}
          </Link>
        </div>
      )}

      <div className="grid">
        {plans.map((p) => {
          const mine = myPlanId === p.id && myActive;
          const free = isFreePlan(p as unknown as Record<string, unknown>);
          const premium = p.plan_type === 'premium';
          const yearly = Number(p.price_yearly ?? 0);
          return (
            <div key={p.id} className="card">
              {premium && <span className="badge green">⭐ {t('pay_recommended')}</span>}
              <p style={{ fontSize: 28 }}>{planEmoji(p.plan_type)}</p>
              <strong>{String(p.name)}</strong>
              <p className="muted small">{String(p.description ?? '')}</p>
              {free ? (
                <>
                  <p className="stat-value">{t('pay_free_label')}</p>
                  <p className="muted small">{t('pay_free_forever')}</p>
                </>
              ) : (
                <>
                  <p className="stat-value">
                    {price(p.price_monthly)} <small className="muted">{t('pay_per_month')}</small>
                  </p>
                  {yearly > 0 && (
                    <p className="muted small">
                      {t('pay_yearly_prefix')} {price(p.price_yearly)} {t('pay_yearly_suffix')}
                    </p>
                  )}
                </>
              )}
              <ul className="muted small">
                {featuresFor(p, t).map((f, i) => (
                  <li key={i}>
                    {f.includes('tahlil') || f.includes('Tahlil') ? (
                      <span>
                        <BarChartIcon size={13} className="ico" /> {f}
                      </span>
                    ) : (
                      f
                    )}
                  </li>
                ))}
              </ul>
              {free ? (
                <span className="badge">{t('btn_current_plan')}</span>
              ) : mine ? (
                <span className="badge green">{t('btn_active')}</span>
              ) : (
                <Link className="btn primary sm" to={`/subscribe/${p.id}`}>
                  {t('btn_subscribe')}
                </Link>
              )}
            </div>
          );
        })}
      </div>
      <h2>{t('faq_title')}</h2>
      <div className="card">
        <p>
          <strong>{t('faq_payment_q')}</strong>
        </p>
        <p className="muted small">{t('faq_payment_a')}</p>
        <p>
          <strong>{t('faq_cancel_q')}</strong>
        </p>
        <p className="muted small">{t('faq_cancel_a')}</p>
        <p>
          <strong>{t('faq_premium_q')}</strong>
        </p>
        <p className="muted small">{t('faq_premium_a')}</p>
      </div>
    </div>
  );
}
