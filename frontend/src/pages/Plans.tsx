import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useLang } from '../i18n/LangContext';
import { Billing } from '../lib/api';
import UsageLimits from '../components/UsageLimits';

interface Plan {
  id: number;
  name?: string;
  plan_type: string;
  price_monthly: number | string;
  is_public?: boolean;
}

const PUBLIC_PLANS: {
  plan_type: 'starter' | 'pro' | 'premium';
  name: string;
  defaultPrice: number;
  emoji: string;
  badgeUz?: string | null;
  badgeRu?: string | null;
  badgeEn?: string | null;
  featuresUz: string[];
  featuresRu: string[];
  featuresEn: string[];
}[] = [
  {
    plan_type: 'starter',
    name: 'START / STARTER',
    defaultPrice: 15000,
    emoji: '⚡',
    badgeUz: null,
    badgeRu: null,
    badgeEn: null,
    featuresUz: [
      'Kuniga 5 ta test',
      'Haftasiga 8 ta esse',
      '5 Rasmli esse/hafta',
      '3 Matnli esse/hafta',
      'Matnli esselar orasida 5 soat',
    ],
    featuresRu: [
      '5 тестов в день',
      '8 эссе в неделю',
      '5 фото эссе / неделю',
      '3 текстовых эссе / неделю',
      '5 часов между текстовыми эссе',
    ],
    featuresEn: [
      '5 tests per day',
      '8 essays per week',
      '5 photo essays / week',
      '3 text essays / week',
      '5 hours cooldown between text essays',
    ],
  },
  {
    plan_type: 'pro',
    name: 'PRO',
    defaultPrice: 49000,
    emoji: '🚀',
    badgeUz: '⭐ Eng ommabop / Tavsiya etiladi',
    badgeRu: '⭐ Самый популярный / Рекомендуется',
    badgeEn: '⭐ Most Popular / Recommended',
    featuresUz: [
      'Kuniga 1 ta rasmiy Mock test',
      'Haftasiga 15 ta esse baholash',
      'Barcha CBT va Mock testlar',
      "Kunlik 50 ta AI repetitor so'rovi & Tahlil",
      'Qisqa kutish vaqti (cooldownsiz)',
    ],
    featuresRu: [
      '1 официальный Mock тест в день',
      '15 оценок эссе в неделю',
      'Все CBT и Mock тесты',
      '50 запросов к AI-репетитору в день & Аналитика',
      'Короткое время ожидания (без кулдауна)',
    ],
    featuresEn: [
      '1 official Mock test per day',
      '15 essay assessments per week',
      'All CBT and Mock tests',
      '50 AI tutor requests per day & Analytics',
      'Short waiting time (no cooldown)',
    ],
  },
  {
    plan_type: 'premium',
    name: 'PREMIUM',
    defaultPrice: 60000,
    emoji: '👑',
    badgeUz: null,
    badgeRu: null,
    badgeEn: null,
    featuresUz: [
      'Cheksiz rasmli va matnli esse baholash (12 mezon)',
      'Cheksiz barcha CBT, Mock testlar va 1v1 Arena',
      '24/7 Cheksiz AI repetitor ("Nega bu xato?")',
      'Rasmiy PDF Sertifikat & Ustoz tekshiruvi',
      "Hech qanday cheklov va cooldown yo'q",
    ],
    featuresRu: [
      'Безлимитная оценка фото и текстовых эссе (12 критериев)',
      'Все CBT, Mock тесты и 1v1 Арена',
      '24/7 Безлимитный AI репетитор ("Почему эта ошибка?")',
      'Официальный PDF Сертификат & Проверка учителем',
      'Без каких-либо ограничений и кулдауна',
    ],
    featuresEn: [
      'Unlimited photo and text essay grading (12 criteria)',
      'All CBT, Mock tests and 1v1 Arena',
      '24/7 Unlimited AI tutor ("Why is this wrong?")',
      'Official PDF Certificate & Teacher review',
      'No restrictions and no cooldown',
    ],
  },
];

export default function Plans() {
  const { t, lang } = useLang();
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
  const myPlanType = (mySub?.plan as Record<string, unknown> | undefined)?.plan_type;

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
        className="grid grid-cols-1 md:grid-cols-3 gap-6"
        style={{
          display: 'grid',
          gap: 24,
          marginBottom: 32,
        }}
      >
        {PUBLIC_PLANS.map((p) => {
          const apiPlan = plans.find((ap) => ap.plan_type === p.plan_type);
          const priceMonthly = apiPlan ? Number(apiPlan.price_monthly) : p.defaultPrice;
          const mine = myActive && (myPlanType === p.plan_type || (apiPlan && myPlanId === apiPlan.id));
          const isPro = p.plan_type === 'pro';
          const isPremium = p.plan_type === 'premium';
          const features = lang === 'ru' ? p.featuresRu : lang === 'en' ? p.featuresEn : p.featuresUz;
          const badgeText = isPro
            ? (lang === 'ru' ? p.badgeRu : lang === 'en' ? p.badgeEn : p.badgeUz)
            : null;

          return (
            <div
              key={p.plan_type}
              className={`card ${isPro ? 'border-amber-500/80 shadow-lg' : ''}`}
              style={{
                display: 'flex',
                flexDirection: 'column',
                position: 'relative',
                padding: 24,
                borderRadius: 16,
                border: isPro
                  ? '2px solid rgba(245, 158, 11, 0.8)'
                  : isPremium
                  ? '1px solid rgba(16, 185, 129, 0.4)'
                  : '1px solid var(--border)',
                boxShadow: isPro ? '0 0 20px rgba(245, 158, 11, 0.3)' : undefined,
                background: isPro
                  ? 'rgba(245, 158, 11, 0.05)'
                  : isPremium
                  ? 'rgba(16, 185, 129, 0.04)'
                  : 'var(--card-2)',
              }}
            >
              {badgeText && (
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
                  {badgeText}
                </span>
              )}
              <p style={{ fontSize: 32, margin: '4px 0 8px' }}>{p.emoji}</p>
              <strong style={{ fontSize: 20 }}>{p.name}</strong>

              <p className="stat-value" style={{ margin: '8px 0 16px', fontSize: 24, color: 'var(--ink)' }}>
                {priceMonthly.toLocaleString()}{' '}
                <span style={{ fontSize: 14, color: 'var(--muted)', fontWeight: 500 }}>{t('pay_per_month')}</span>
              </p>

              <ul className="muted small" style={{ flex: 1, paddingLeft: 18, margin: '0 0 20px', lineHeight: 1.7 }}>
                {features.map((f, i) => (
                  <li key={i} style={{ marginBottom: 6 }}>
                    {f}
                  </li>
                ))}
              </ul>

              {mine ? (
                <span className="badge green" style={{ textAlign: 'center', padding: '8px 16px', marginTop: 'auto', fontWeight: 700 }}>
                  {t('btn_active')}
                </span>
              ) : (
                <Link
                  className={`btn sm ${isPro ? 'primary btn-glow' : ''}`}
                  style={{
                    textAlign: 'center',
                    textDecoration: 'none',
                    fontWeight: 700,
                    marginTop: 'auto',
                    background: isPro ? 'linear-gradient(135deg, #f59e0b, #d97706)' : undefined,
                    color: isPro ? '#fff' : undefined,
                  }}
                  to={`/checkout?plan=${p.plan_type}`}
                >
                  {lang === 'ru' ? 'Оплатить и загрузить чек →' : lang === 'en' ? 'Pay & Upload Receipt →' : "To'lov qilish & Chek yuklash →"}
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
