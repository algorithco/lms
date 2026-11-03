import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useLang } from '../i18n/LangContext';
import { Billing } from '../lib/api';
import { formatDateTime, num, paymentStatusKey, str } from '../lib/billingPanelGames';
import UsageLimits from '../components/UsageLimits';

/**
 * My subscription. Backend: GET /api/v1/billing/my/ → { subscription, history[:10] }.
 * Limits come only from <UsageLimits /> (GET /api/v1/billing/entitlement/),
 * the same numbers the server enforces — never from plan marketing fields.
 */
export default function MySubscription() {
  const { t } = useLang();
  const [sub, setSub] = useState<Record<string, unknown> | null>(null);
  const [history, setHistory] = useState<Record<string, unknown>[]>([]);
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
  // is_active also checks the expiry date; status alone may lag until the expiry job.
  const active = sub?.is_active === true;
  const days = num(sub?.days_remaining, 0);
  const method = str(sub?.payment_method);

  if (loading) return <p className="muted">{t('loading')}</p>;

  return (
    <div>
      <h1>{t('sub_my_title')}</h1>
      <p className="muted">{t('sub_my_subtitle')}</p>
      {err && <p className="error">{err}</p>}

      {/* Live plan + remaining usage (server-calculated, quietly hidden on error). */}
      <UsageLimits />

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
              <span className={`badge ${active ? 'green' : ''}`}>
                {t(active ? 'sub_status_active' : 'sub_status_inactive')}
              </span>
              {sub.is_trial ? <span className="badge amber">{t('sub_status_trial')}</span> : null}
            </p>
            <p className="muted small">
              {active && days > 0 ? `${days} ${t('sub_days_left')}` : active ? '' : t('sub_expired')}
              {sub.expires_at ? ` · ${t('sub_expires_at')}: ${formatDateTime(sub.expires_at)}` : ''}
            </p>
            <p className="muted small">
              {t('sub_payment_method')}: <b>{method ? t(`sub_pm_${method}`, method) : '—'}</b>
            </p>
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
