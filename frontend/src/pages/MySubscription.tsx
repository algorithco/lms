import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useLang } from '../i18n/LangContext';
import { Billing } from '../lib/api';
import { formatDateTime, num, paymentStatusKey, str } from '../lib/billingPanelGames';

/**
 * My subscription — parity with templates/payments/my_subscription.html.
 * Backend: GET /api/v1/billing/my/ → { subscription, history[:10] }
 * plus session GET /subscribe/api/status/ → { has_subscription, plan,
 * plan_name, expires_at, days_remaining, features }.
 */
export default function MySubscription() {
  const { t } = useLang();
  const [sub, setSub] = useState<Record<string, unknown> | null>(null);
  const [history, setHistory] = useState<Record<string, unknown>[]>([]);
  const [session, setSession] = useState<Record<string, unknown> | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [loading, setLoading] = useState(true);

  const load = () =>
    Billing.my()
      .then((r) => {
        setSub((r.subscription ?? null) as Record<string, unknown> | null);
        setHistory((r.history ?? []) as Record<string, unknown>[]);
      })
      .catch((e: unknown) => setErr(e instanceof Error ? e.message : 'Failed.'))
      .finally(() => setLoading(false));

  useEffect(() => {
    load();
    // Best-effort session bridge (JWT-only logins have no session cookie).
    Billing.status()
      .then((s) => setSession(s as unknown as Record<string, unknown>))
      .catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const cancel = async () => {
    try {
      await Billing.cancel();
      setConfirming(false);
      load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : 'Failed.');
    }
  };

  const plan = (sub?.plan ?? {}) as Record<string, unknown>;
  const active = str(sub?.status) === 'active';
  const days = num(sub?.days_remaining, 0);
  const sessionFeatures = (session?.features ?? {}) as Record<string, unknown>;

  if (loading) return <p className="muted">{t('loading')}</p>;

  return (
    <div>
      <h1>{t('sub_my_title')}</h1>
      <p className="muted">{t('sub_my_subtitle')}</p>
      {err && <p className="error">{err}</p>}

      {!sub ? (
        <div className="card">
          <p>
            <strong>{t('sub_none_title')}</strong>
          </p>
          <p className="muted small">{t('sub_none_hint')}</p>
          <Link className="btn primary sm" to="/subscribe">
            {t('sub_plans_cta')}
          </Link>
        </div>
      ) : (
        <>
          <div className="card">
            <p className="muted small">{t('sub_current')}</p>
            <p>
              <strong>{str(plan.name)}</strong>{' '}
              <span className={`badge ${active ? 'green' : ''}`}>{str(sub.status)}</span>
            </p>
            <p className="muted small">
              {days > 0 ? `${days} ${t('sub_days_left')}` : t('sub_expired')}
              {sub.expires_at ? ` · ${t('sub_expires_at')}: ${formatDateTime(sub.expires_at)}` : ''}
            </p>
            <p className="muted small">
              {t('sub_payment_method')}: <b>{str(sub.payment_method) || t('sub_free')}</b>
            </p>
            {/* Feature breakdown — mirrors my_subscription.html feature grid. */}
            <p className="muted small" style={{ marginTop: 8 }}>
              {t('sub_your_features')}
            </p>
            <ul className="muted small">
              <li>
                ✅{' '}
                {plan.unlimited_tests
                  ? t('sub_unlimited_tests')
                  : `${t('sub_per_day_pre')} ${str(plan.max_tests_per_day ?? '—')} ${t('sub_tests_unit')}`}
              </li>
              <li>
                ✅{' '}
                {plan.unlimited_essays
                  ? t('sub_unlimited_essays')
                  : `${t('sub_per_week_pre')} ${str(plan.max_essays_per_week ?? '—')} ${t('sub_essays_unit')}`}
              </li>
              {plan.detailed_analytics ? <li>✅ {t('detailed_analytics')}</li> : null}
              {plan.pdf_certificate ? <li>✅ {t('sub_pdf_cert')}</li> : null}
              {plan.priority_support ? <li>✅ {t('sub_priority_support')}</li> : null}
            </ul>
            {active ? (
              !confirming ? (
                <button className="btn danger sm" onClick={() => setConfirming(true)}>
                  {t('sub_cancel')}
                </button>
              ) : (
                <div>
                  <p className="muted small">{t('sub_cancel_confirm')}</p>
                  <div className="row">
                    <button className="btn danger sm" onClick={cancel}>
                      {t('confirm')}
                    </button>
                    <button className="btn sm" onClick={() => setConfirming(false)}>
                      {t('back')}
                    </button>
                  </div>
                </div>
              )
            ) : null}
          </div>

          {/* Session bridge status — GET /subscribe/api/status/. */}
          <div className="card" style={{ marginTop: 12 }}>
            <p className="muted small">{t('billing_session_title')}</p>
            {session ? (
              <p className="muted small">
                {session.has_subscription ? t('billing_session_active') : t('billing_session_free')}
                {session.plan_name ? ` · ${str(session.plan_name)}` : ''}
                {session.days_remaining !== undefined
                  ? ` · ${str(session.days_remaining)} ${t('sub_days_left')}`
                  : ''}
                {Object.keys(sessionFeatures).length > 0 && (
                  <>
                    {' · '}
                    {str(sessionFeatures.unlimited_tests)
                      ? t('sub_unlimited_tests')
                      : `${t('sub_per_day_pre')} ${str(sessionFeatures.max_tests_per_day ?? '—')} ${t('sub_tests_unit')}`}
                  </>
                )}
              </p>
            ) : (
              <p className="muted small">{t('sub_session_unavailable')}</p>
            )}
          </div>
        </>
      )}

      <h2>{t('sub_history_title')}</h2>
      {history.length === 0 ? (
        <p className="muted">{t('sub_no_payments')}</p>
      ) : (
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>{t('pay_plan_label')}</th>
                <th>{t('pay_total')}</th>
                <th>{t('sub_payment_method')}</th>
                <th>{t('status')}</th>
              </tr>
            </thead>
            <tbody>
              {history.map((h: Record<string, unknown>) => {
                const key = paymentStatusKey(h.status);
                const rowKey = h.id ?? h.created_at ?? `${str(h.plan_name)}-${str(h.amount)}-${str(h.status)}`;
                return (
                  <tr key={String(rowKey)}>
                    <td>
                      {str(h.plan_name)}
                      <br />
                      <small className="muted">{formatDateTime(h.created_at)}</small>
                    </td>
                    <td>
                      {str(h.amount)} {str(h.currency)}
                    </td>
                    <td>{str(h.payment_method)}</td>
                    <td>
                      <span className="badge">{key ? t(key) : str(h.status)}</span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
