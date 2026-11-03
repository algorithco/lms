import { useEffect, useState } from 'react';
import { useTranslation } from '../i18n/useTranslation';
import { ReferralApi, type ReferralStats } from '../lib/api';
import { useToast } from '../context/ToastContext';

interface Props {
  /** compact = one row for the dashboard; the full card lives on the profile page. */
  variant?: 'full' | 'compact';
}

async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    try {
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.setAttribute('readonly', '');
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.select();
      const ok = document.execCommand('copy');
      document.body.removeChild(ta);
      return ok;
    } catch {
      return false;
    }
  }
}

export default function ReferralCard({ variant = 'full' }: Props) {
  const { t } = useTranslation();
  const [stats, setStats] = useState<ReferralStats | null>(null);
  const [copied, setCopied] = useState(false);
  const toast = useToast();

  useEffect(() => {
    ReferralApi.getMyCode()
      .then((data) => setStats(data))
      .catch((err) => console.warn('Could not load referral stats:', err));
  }, []);

  if (!stats) return null;

  const shareUrl = stats.referral_link || `https://grandec.uz/r/${stats.referral_code}`;
  const shareText = t('referral_share_text');

  const onCopy = async () => {
    const ok = await copyText(shareUrl);
    if (!ok) {
      toast.error(t('referral_copy_failed'));
      return;
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const onShare = () => {
    if (typeof navigator.share === 'function') {
      navigator.share({ title: t('referral_title'), text: shareText, url: shareUrl }).catch(() => undefined);
      return;
    }
    const tgUrl = `https://t.me/share/url?url=${encodeURIComponent(shareUrl)}&text=${encodeURIComponent(shareText)}`;
    window.open(tgUrl, '_blank', 'noopener');
  };

  const group = (
    <div className="ref-group">
      <div className="ref-group__field">
        <input
          type="text"
          readOnly
          value={shareUrl}
          className="ui-input ui-input--mono"
          aria-label={t('referral_link_label')}
          onFocus={(e) => e.currentTarget.select()}
        />
        <button type="button" className="ui-btn ui-btn--primary" onClick={onCopy} aria-live="polite">
          {copied ? t('referral_copied_short') : t('referral_copy_btn')}
        </button>
      </div>
      <button type="button" className="ui-btn" onClick={onShare}>
        {t('referral_share_native')}
      </button>
    </div>
  );

  if (variant === 'compact') {
    return (
      <section className="ref-card ref-card--compact" aria-label={t('referral_title')}>
        <h3 className="ref-card__title">{t('referral_title')}</h3>
        {group}
      </section>
    );
  }

  return (
    <section className="ref-card" aria-label={t('referral_title')}>
      <div className="ref-card__head">
        <div className="ref-card__icon" aria-hidden="true">🎁</div>
        <div>
          <h3 className="ref-card__title">{t('referral_title')}</h3>
          <p className="ref-card__desc">{t('referral_desc')}</p>
        </div>
      </div>
      {group}
      <div className="ref-stats">
        <span>
          {t('referral_invited_count')}: <b>{stats.total_invited}</b>
        </span>
        <span className="ref-stats__sep" aria-hidden="true">·</span>
        <span>
          {t('referral_earned_bonus')}: <b>+{stats.bonus_tests} {t('referral_unit_test')} / +{stats.bonus_essays} {t('referral_unit_essay')}</b>
        </span>
      </div>
    </section>
  );
}
