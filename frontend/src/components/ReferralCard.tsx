import { useEffect, useState } from 'react';
import { useTranslation } from '../i18n/useTranslation';
import { ReferralApi, type ReferralStats } from '../lib/api';
import { useToast } from '../context/ToastContext';

export default function ReferralCard() {
  const { t } = useTranslation();
  const [stats, setStats] = useState<ReferralStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);
  const toast = useToast();

  useEffect(() => {
    ReferralApi.getMyCode()
      .then((data) => setStats(data))
      .catch((err) => console.warn('Could not load referral stats:', err))
      .finally(() => setLoading(false));
  }, []);

  if (loading || !stats) {
    return null;
  }

  const shareUrl = stats.referral_link || `https://grandec.uz/r/${stats.referral_code}`;
  const shareText = t(
    'referral_share_text',
    `🎁 Do'stim, sizga rasmiy Mock Test va AI Esse tekshiruvi sovg'a qilaman! grandec.uz da o'z bilimingizni sinab ko'ring: ${shareUrl}`
  );

  const copyToClipboard = () => {
    navigator.clipboard.writeText(shareUrl);
    setCopied(true);
    toast.success(t('referral_copied', 'Havola nusxalandi!'));
    setTimeout(() => setCopied(false), 2000);
  };

  const shareViaTelegram = () => {
    const tgUrl = `https://t.me/share/url?url=${encodeURIComponent(shareUrl)}&text=${encodeURIComponent(shareText)}`;
    window.open(tgUrl, '_blank');
  };

  return (
    <div
      className="card w-full my-6 overflow-hidden"
      style={{
        borderRadius: 20,
        background: 'linear-gradient(135deg, rgba(245, 158, 11, 0.08) 0%, rgba(217, 119, 6, 0.03) 100%)',
        border: '1.5px solid rgba(245, 158, 11, 0.25)',
        boxShadow: '0 8px 32px rgba(245, 158, 11, 0.06)',
        padding: '24px',
      }}
    >
      <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-6">
        {/* Left: Icon & Description */}
        <div className="flex items-start gap-4">
          <div
            style={{
              width: 52,
              height: 52,
              borderRadius: 16,
              background: 'linear-gradient(135deg, #F59E0B, #D97706)',
              color: '#FFFFFF',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 26,
              flexShrink: 0,
              boxShadow: '0 6px 20px rgba(245, 158, 11, 0.35)',
            }}
          >
            🎁
          </div>
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 900,
                  letterSpacing: '0.08em',
                  textTransform: 'uppercase',
                  padding: '3px 8px',
                  borderRadius: 6,
                  background: 'rgba(245, 158, 11, 0.2)',
                  color: '#D97706',
                }}
              >
                {t('referral_badge', 'Viral Bonus')}
              </span>
              <h3 className="font-extrabold text-slate-900 dark:text-white text-base sm:text-lg m-0">
                {t('referral_title', 'Referal dasturi')}
              </h3>
            </div>
            <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-300 m-0 max-w-xl leading-relaxed">
              {t(
                'referral_desc',
                "Do'stlaringizni taklif qiling va har bir do'stingiz ro'yxatdan o'tganda +5 ta bepul test va +2 ta esse tekshiruviga ega bo'ling!"
              )}
            </p>

            {/* Quick Stats Pills */}
            <div className="flex flex-wrap items-center gap-3 mt-3">
              <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg bg-white/70 dark:bg-slate-800/70 border border-slate-200 dark:border-slate-700 text-xs font-semibold text-slate-700 dark:text-slate-200">
                <span>👥 {t('referral_invited_count', 'Taklif qilingan do\'stlar')}:</span>
                <span className="font-bold text-amber-600 dark:text-amber-400">{stats.total_invited}</span>
              </div>
              <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg bg-white/70 dark:bg-slate-800/70 border border-slate-200 dark:border-slate-700 text-xs font-semibold text-slate-700 dark:text-slate-200">
                <span>⚡ {t('referral_earned_bonus', 'Olingan bonuslar')}:</span>
                <span className="font-bold text-emerald-600 dark:text-emerald-400">
                  +{stats.bonus_tests} test / +{stats.bonus_essays} esse
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Right: Copy & Share Controls */}
        <div className="w-full lg:w-auto flex flex-col sm:flex-row items-stretch sm:items-center gap-2.5 shrink-0">
          <div className="relative flex-1 sm:w-80">
            <input
              type="text"
              readOnly
              value={shareUrl}
              className="w-full bg-white dark:bg-slate-900/90 border border-amber-500/40 text-xs sm:text-sm text-slate-800 dark:text-slate-200 rounded-xl py-3 px-3.5 pr-24 focus:outline-none focus:ring-2 focus:ring-amber-500/40 font-mono shadow-sm"
            />
            <button
              type="button"
              onClick={copyToClipboard}
              className="absolute right-1.5 top-1/2 -translate-y-1/2 bg-amber-500 hover:bg-amber-600 text-white text-xs font-bold px-3 py-1.5 rounded-lg transition-all flex items-center gap-1 cursor-pointer shadow-sm"
            >
              <span>{copied ? '✓' : '📋'}</span>
              <span>{copied ? t('referral_copied', 'Nusxalandi!') : t('referral_copy_btn', 'Nusxalash')}</span>
            </button>
          </div>

          <button
            type="button"
            onClick={shareViaTelegram}
            className="bg-[#24A1DE] hover:bg-[#208bbf] text-white text-xs sm:text-sm font-bold px-5 py-3 rounded-xl flex items-center justify-center gap-2 transition-all shrink-0 shadow-md hover:shadow-lg cursor-pointer"
          >
            <span className="text-base">✈️</span>
            <span>{t('referral_share_btn', "Do'stlarga ulashish")}</span>
          </button>
        </div>
      </div>
    </div>
  );
}
