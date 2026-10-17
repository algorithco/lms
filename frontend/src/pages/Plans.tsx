import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useLang } from '../i18n/LangContext';
import { Billing } from '../lib/api';
import { isFreePlan, planEmoji, price } from '../lib/billingPanelGames';
import { BarChartIcon } from '../components/icons';
import UsageLimits from '../components/UsageLimits';

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
  // Commercial plan configuration (apps/payments/models.py SubscriptionPlan).
  image_essay_weekly_limit?: number | null;
  text_essay_weekly_limit?: number | null;
  text_essay_cooldown_hours?: number | null;
  test_limit?: number | null;
  is_unlimited_image_essays?: boolean;
  is_unlimited_text_essays?: boolean;
  is_unlimited_tests?: boolean;
  is_public?: boolean;
}

/**
 * Quota bullets derived from the plan's REAL configuration — nothing is
 * invented. A null limit with the matching unlimited flag unset means the
 * administrator has not configured that bucket, so no bullet is shown.
 */
function quotaFeatures(p: Plan, t: (k: string) => string): string[] {
  const out: string[] = [];
  if (p.is_unlimited_image_essays) {
    out.push(`${t('usage_image_essay')}: ${t('usage_unlimited')}`);
  } else if (typeof p.image_essay_weekly_limit === 'number') {
    out.push(`${p.image_essay_weekly_limit} ${t('usage_image_essay')}${t('usage_per_week')}`);
  }
  if (p.is_unlimited_text_essays) {
    out.push(`${t('usage_text_essay')}: ${t('usage_unlimited')}`);
  } else if (typeof p.text_essay_weekly_limit === 'number') {
    out.push(`${p.text_essay_weekly_limit} ${t('usage_text_essay')}${t('usage_per_week')}`);
  }
  if (typeof p.text_essay_cooldown_hours === 'number' && p.text_essay_cooldown_hours > 0) {
    out.push(`${t('usage_text_cooldown_prefix')} ${p.text_essay_cooldown_hours} ${t('usage_hours')}`);
  }
  if (p.is_unlimited_tests) {
    out.push(`${t('usage_tests')}: ${t('usage_unlimited')}`);
  } else if (typeof p.test_limit === 'number') {
    out.push(`${p.test_limit} ${t('usage_tests')}${t('usage_per_week')}`);
  }
  return out;
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

  // Never show the store a plan that administrators have hidden, nor the
  // sponsored tier (it is granted, not purchased).
  const planOrder: Record<string, number> = {
    free: 0,
    starter: 1,
    start: 1,
    pro: 2,
    premium: 3,
  };
  const visiblePlans = plans
    .filter((p) => p.is_public !== false && p.plan_type !== 'teacher_sponsored')
    .sort((a, b) => (planOrder[a.plan_type] ?? 99) - (planOrder[b.plan_type] ?? 99));

  return (
    <div>
      <h1>{t('pay_plans_title')}</h1>
      <p className="muted">{t('pay_plans_subtitle')}</p>
      {err && <p className="error">{err}</p>}

      <div
        className="card"
        style={{
          background: 'linear-gradient(135deg, rgba(245, 158, 11, 0.1), rgba(16, 185, 129, 0.05))',
          border: '1px solid rgba(245, 158, 11, 0.25)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 16,
          padding: '16px 20px',
          borderRadius: 12,
          flexWrap: 'wrap',
          gap: 12,
        }}
      >
        <div>
          <strong style={{ fontSize: 16, color: '#fbbf24', display: 'block', marginBottom: 4 }}>
            💳 Karta orqali tezkor to'lov va chek yuklash
          </strong>
          <span className="muted small">
            Starter (15 000 so'm), Pro (49 000 so'm) yoki Premium (60 000 so'm) tariflari uchun chekni yuklab, 5-15 daqiqada obunani faollashtiring.
          </span>
        </div>
        <Link to="/checkout" className="btn primary sm btn-glow" style={{ textDecoration: 'none', fontWeight: 700 }}>
          To'lov qilish & Chek yuklash →
        </Link>
      </div>

      {/* Current plan + live remaining usage for this student. */}
      <UsageLimits />

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

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
          gap: 20,
          marginBottom: 32,
        }}
      >
        {visiblePlans.map((p) => {
          const mine = myPlanId === p.id && myActive;
          const free = isFreePlan(p as unknown as Record<string, unknown>);
          const pro = p.plan_type === 'pro';
          const premium = p.plan_type === 'premium';
          const yearly = Number(p.price_yearly ?? 0);
          return (
            <div
              key={p.id}
              className="card"
              style={{
                display: 'flex',
                flexDirection: 'column',
                position: 'relative',
                border: pro
                  ? '2px solid rgba(245, 158, 11, 0.6)'
                  : premium
                  ? '1px solid rgba(16, 185, 129, 0.4)'
                  : '1px solid rgba(255, 255, 255, 0.1)',
                background: pro ? 'rgba(245, 158, 11, 0.04)' : undefined,
              }}
            >
              {pro && (
                <span
                  style={{
                    position: 'absolute',
                    top: -12,
                    right: 16,
                    background: 'linear-gradient(135deg, #f59e0b, #d97706)',
                    color: '#fff',
                    fontSize: 11,
                    fontWeight: 700,
                    padding: '3px 10px',
                    borderRadius: 20,
                    boxShadow: '0 2px 8px rgba(245, 158, 11, 0.4)',
                  }}
                >
                  ⭐ Eng ommabop / Tavsiya etiladi
                </span>
              )}
              {premium && (
                <span
                  style={{
                    position: 'absolute',
                    top: -12,
                    right: 16,
                    background: 'linear-gradient(135deg, #10b981, #059669)',
                    color: '#fff',
                    fontSize: 11,
                    fontWeight: 700,
                    padding: '3px 10px',
                    borderRadius: 20,
                  }}
                >
                  👑 Premium VIP
                </span>
              )}
              <p style={{ fontSize: 32, margin: '4px 0 8px' }}>{planEmoji(p.plan_type)}</p>
              <strong style={{ fontSize: 20 }}>{String(p.name)}</strong>
              <p className="muted small" style={{ minHeight: 38 }}>
                {String(p.description ?? '')}
              </p>
              {free ? (
                <>
                  <p className="stat-value">{t('pay_free_label')}</p>
                  <p className="muted small">{t('pay_free_forever')}</p>
                </>
              ) : (
                <>
                  <p className="stat-value" style={{ margin: '8px 0 16px' }}>
                    {price(p.price_monthly)} <small className="muted">{t('pay_per_month')}</small>
                  </p>
                  {yearly > 0 && (
                    <p className="muted small">
                      {t('pay_yearly_prefix')} {price(p.price_yearly)} {t('pay_yearly_suffix')}
                    </p>
                  )}
                </>
              )}
              <ul className="muted small" style={{ flex: 1, marginBottom: 20 }}>
                {[...featuresFor(p, t), ...quotaFeatures(p, t)].map((f, i) => (
                  <li key={i} style={{ marginBottom: 6 }}>
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
                <Link
                  className="btn primary sm btn-glow"
                  style={{ textAlign: 'center', textDecoration: 'none', fontWeight: 700, marginTop: 'auto' }}
                  to={`/checkout?plan=${p.plan_type}`}
                >
                  To'lov qilish & Chek yuklash →
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
