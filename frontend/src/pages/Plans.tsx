import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { AlertTriangle, Check, Crown, Rocket, Sparkles, Zap } from 'lucide-react';
import { useLang } from '../i18n/LangContext';
import { Billing, type BillingPlan } from '../lib/api';
import { formatPrice, planLines } from '../lib/planFeatures';
import UsageLimits from '../components/UsageLimits';

interface MySub {
  plan?: { id?: number; name?: string; plan_type?: string } | null;
  days_remaining?: number;
  is_active?: boolean;
  status?: string;
}

const ICONS: Record<string, typeof Zap> = { starter: Zap, start: Zap, pro: Rocket, premium: Crown };

/**
 * /plans and /subscribe. Every price and limit on the cards is the plan row
 * from GET /api/v1/billing/plans/; the current plan comes from /billing/my/.
 */
export default function Plans() {
  const { t } = useLang();
  const [plans, setPlans] = useState<BillingPlan[] | null>(null);
  const [myPlanId, setMyPlanId] = useState<number | null>(null);
  const [mySub, setMySub] = useState<MySub | null>(null);
  const [failed, setFailed] = useState(false);

  const fetchAll = useCallback(() => {
    Billing.plans()
      .then((r) => {
        // Cheapest first: the cards read as a ladder whatever order the rows were saved in.
        const price = (p: BillingPlan) => Number(p.price_uzs ?? p.price_monthly ?? 0);
        setPlans(r.results.filter((p) => price(p) > 0).sort((a, b) => price(a) - price(b)));
        setMyPlanId(r.my_plan_id);
      })
      .catch(() => setFailed(true));
    Billing.my()
      .then((r) => setMySub((r.subscription as MySub | null) ?? null))
      .catch(() => setMySub(null));
  }, []);

  useEffect(fetchAll, [fetchAll]);

  const retry = () => {
    setFailed(false);
    setPlans(null);
    fetchAll();
  };

  const active = Boolean(mySub && (mySub.is_active ?? mySub.status === 'active'));
  const days = Number(mySub?.days_remaining ?? 0);

  return (
    <div className="pl">
      <header className="pl-head">
        <h1>{t('pay_plans_title')}</h1>
        <p className="muted">{t('pl_subtitle')}</p>
      </header>

      <UsageLimits showManage={false} />

      {active && mySub?.plan && (
        <section className="ui-card pl-current" aria-label={t('pay_current_sub')}>
          <span className="ic-chip">
            <Crown size={18} aria-hidden="true" />
          </span>
          <div className="pl-current__text">
            <small>{t('pay_current_sub')}</small>
            <strong>{mySub.plan.name}</strong>
            <span>{days > 0 ? t('pl_days_left').replace('{n}', String(days)) : t('pay_expired')}</span>
          </div>
          <Link className="ui-btn ui-btn--sm" to="/my-subscription">
            {t('pay_manage')}
          </Link>
        </section>
      )}

      {failed ? (
        <div className="ui-state ui-state--error" role="alert">
          <span className="ic-chip ic-chip--danger">
            <AlertTriangle size={22} aria-hidden="true" />
          </span>
          <p>{t('pl_load_error')}</p>
          <button type="button" className="ui-btn" onClick={retry}>
            {t('pl_retry')}
          </button>
        </div>
      ) : plans === null ? (
        <div className="pl-grid" aria-busy="true">
          {[0, 1, 2].map((i) => (
            <div key={i} className="ui-card pl-card">
              <span className="ui-skel" style={{ width: 40, height: 40 }} />
              <span className="ui-skel ui-skel-line" style={{ width: '50%' }} />
              <span className="ui-skel ui-skel-line" style={{ width: '70%', height: 28 }} />
              <span className="ui-skel ui-skel-line" />
              <span className="ui-skel ui-skel-line" />
            </div>
          ))}
        </div>
      ) : plans.length === 0 ? (
        <div className="ui-state">
          <span className="ic-chip ic-chip--muted">
            <Sparkles size={22} aria-hidden="true" />
          </span>
          <p>{t('pl_empty')}</p>
        </div>
      ) : (
        <div className="pl-grid">
          {plans.map((p) => {
            const Icon = ICONS[p.plan_type] ?? Sparkles;
            const featured = p.plan_type === 'pro';
            const mine = active && (myPlanId === p.id || mySub?.plan?.id === p.id);
            return (
              <article key={p.id} className={`ui-card pl-card${featured ? ' is-featured' : ''}${mine ? ' is-mine' : ''}`}>
                {featured && <span className="pl-card__badge">{t('pl_recommended')}</span>}
                <span className="ic-chip">
                  <Icon size={18} aria-hidden="true" />
                </span>
                <h2 className="pl-card__name">{p.name}</h2>
                <p className="pl-card__price">
                  <b>{formatPrice(p.price_uzs ?? p.price_monthly)}</b> <span>{t('pay_per_month')}</span>
                </p>
                <ul className="pl-card__lines">
                  {planLines(p).map((l) => (
                    <li key={l.key}>
                      <Check size={16} aria-hidden="true" />
                      <span>{l.n === undefined ? t(l.key) : t(l.key).replace('{n}', String(l.n))}</span>
                    </li>
                  ))}
                </ul>
                {mine ? (
                  <span className="pl-card__mine">
                    <Check size={16} aria-hidden="true" /> {t('pl_your_plan')}
                  </span>
                ) : (
                  <Link
                    className={`ui-btn ui-btn--block${featured ? ' ui-btn--primary' : ''}`}
                    to={`/checkout?plan=${encodeURIComponent(p.plan_type)}`}
                  >
                    {t(active ? 'pl_switch_cta' : 'pl_pay_cta')}
                  </Link>
                )}
              </article>
            );
          })}
        </div>
      )}

      <p className="pl-note muted">{t('pl_pay_note')}</p>

      <section className="ui-card pl-faq">
        <h2>{t('faq_title')}</h2>
        {(['payment', 'cancel', 'premium'] as const).map((k) => (
          <details key={k}>
            <summary>{t(`faq_${k}_q`)}</summary>
            <p>{t(`faq_${k}_a`)}</p>
          </details>
        ))}
      </section>
    </div>
  );
}
