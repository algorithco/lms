import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useLang } from '../i18n/LangContext';
import { Billing } from '../lib/api';
import { planEmoji, price, str } from '../lib/billingPanelGames';
import { BotIcon, CopyIcon, CreditCardIcon } from '../components/icons';

/**
 * Manual card-transfer flow — parity with templates/payments/subscribe.html.
 * Backend: GET /api/v1/billing/subscribe/<plan_id>/ →
 * { plan, card_number, card_bank, card_holder, admin_username, bot_name, free }.
 */
export default function Subscribe() {
  const { planId = '' } = useParams();
  const { t } = useLang();
  const [info, setInfo] = useState<Record<string, unknown> | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    Billing.subscribeInfo(planId)
      .then((r) => setInfo(r as unknown as Record<string, unknown>))
      .catch((e: unknown) => setErr(e instanceof Error ? e.message : 'Failed.'));
  }, [planId]);

  const copy = async (text: string) => {
    const legacyCopy = (v: string) => {
      const ta = document.createElement('textarea');
      ta.value = v;
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.select();
      try {
        document.execCommand('copy');
        setCopied(true);
        setTimeout(() => setCopied(false), 1800);
      } catch {
        /* unavailable */
      }
      document.body.removeChild(ta);
    };
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      legacyCopy(text);
    }
  };

  if (err) {
    return (
      <div>
        <p className="error">{err}</p>
        <p>
          <Link to="/subscribe">{t('pay_back_to_plans')}</Link>
        </p>
      </div>
    );
  }
  if (!info) return <p className="muted">{t('loading')}</p>;

  const plan = (info.plan ?? {}) as Record<string, unknown>;
  const planType = str(plan.plan_type);
  const admin = str(info.admin_username);

  return (
    <div>
      <p>
        <Link to="/subscribe">← {t('pay_back_to_plans')}</Link>
      </p>
      <h1>
        <CreditCardIcon size={24} className="ico" /> {t('pay_checkout_title')}
      </h1>

      {/* Plan summary (legacy header + summary box). */}
      <div className="card" style={{ textAlign: 'center', marginBottom: 12 }}>
        <p style={{ fontSize: 40 }}>{planEmoji(planType)}</p>
        <h2>{str(plan.name)}</h2>
        <p className="muted small">{str(plan.description)}</p>
        <p className="stat-value">
          {price(plan.price_monthly)} <small className="muted">{t('pay_per_month')}</small>
        </p>
      </div>
      <div className="card" style={{ marginBottom: 12 }}>
        <p className="muted small">
          {t('pay_plan_label')} <b>{str(plan.name)}</b>
        </p>
        <p className="muted small">
          {t('pay_period_label')} <b>{t('pay_30_days')}</b>
        </p>
        <p>
          {t('pay_total')} <b>{price(plan.price_monthly)}</b>
        </p>
      </div>

      {info.free ? (
        <p className="muted">{t('pay_msg_free_plan')}</p>
      ) : (
        <>
          {/* Step 1 — card transfer. */}
          <div className="card">
            <h2>{t('pay_step1_title')}</h2>
            <p className="muted small">{t('pay_step1_text')}</p>
            <p className="muted small">{t('pay_card_label')}</p>
            <p className="stat-value" style={{ userSelect: 'all' }}>
              {str(info.card_number)}
            </p>
            <p className="muted small">
              {t('pay_card_holder')}: <b>{str(info.card_holder)}</b> · {t('pay_bank')}:{' '}
              <b>{str(info.card_bank)}</b>
            </p>
            <div className="row">
              <button className="btn sm" onClick={() => copy(str(info.card_number))}>
                <CopyIcon size={14} className="ico" /> {t('btn_copy')}
              </button>
            </div>
            {copied && <p className="badge green">{t('pay_copied')}</p>}
          </div>
          {/* Step 2 — receipt screenshot. */}
          <div className="card" style={{ marginTop: 12 }}>
            <h2>{t('pay_step2_title')}</h2>
            <p className="muted small">{t('pay_step2_text')}</p>
          </div>
          {/* Step 3 — send via Telegram. */}
          <div className="card" style={{ marginTop: 12 }}>
            <h2>{t('pay_step3_title')}</h2>
            <p className="muted small">{t('pay_step3_text')}</p>
            <p className="muted small">
              {t('pay_your_id')} <b style={{ userSelect: 'all' }}>@{admin}</b>
            </p>
            <p className="muted small">
              <BotIcon size={14} className="ico" /> @{str(info.bot_name)}
            </p>
            <a
              className="btn primary"
              href={`https://t.me/${admin}`}
              target="_blank"
              rel="noopener noreferrer"
            >
              {t('pay_send_receipt')}
            </a>
            <p className="muted small" style={{ marginTop: 8 }}>
              {t('pay_admin_review_note')}
            </p>
          </div>
          <p className="muted small" style={{ marginTop: 12 }}>
            {t('pay_terms_note')}
          </p>
        </>
      )}
    </div>
  );
}
