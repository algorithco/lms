import { useEffect, useState } from 'react';
import { useTranslation } from '../i18n/useTranslation';
import { ReferralApi, type ReferralStats } from '../lib/api';
import { useToast } from '../context/ToastContext';

export default function ReferralCard() {
  const { t } = useTranslation();
  const [stats, setStats] = useState<ReferralStats | null>(null);
  const [loading, setLoading] = useState(true);
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
  const shareText = `🎁 Do'stim, sizga 1 ta bepul rasmiy Mock Test va AI Esse tekshiruvi sovg'a qilaman! grandec.uz da o'z bilimingizni sinab ko'ring: ${shareUrl}`;

  const copyToClipboard = () => {
    navigator.clipboard.writeText(shareUrl);
    toast.success('Taklif havolasi nusxalandi!');
  };

  const shareViaTelegram = () => {
    const tgUrl = `https://t.me/share/url?url=${encodeURIComponent(shareUrl)}&text=${encodeURIComponent(shareText)}`;
    window.open(tgUrl, '_blank');
  };

  return (
    <div className="w-full my-6 bg-gradient-to-r from-amber-500/10 via-amber-500/5 to-transparent border border-amber-500/20 rounded-2xl p-4 sm:p-5 flex flex-col md:flex-row items-center justify-between gap-4 shadow-sm">
      <div className="flex items-center gap-3.5">
        <div className="w-11 h-11 rounded-xl bg-amber-500/20 text-amber-600 dark:text-amber-400 flex items-center justify-center text-xl shrink-0 shadow-sm">
          🎁
        </div>
        <div>
          <h3 className="font-bold text-slate-900 dark:text-white text-sm sm:text-base">
            {t('dashboard.referral_title', "Do'stingizga 1 ta bepul test sovg'a qiling va bonus oling!")}
          </h3>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
            {t('dashboard.referral_desc', "Do'stingiz ro'yxatdan o'tsa unga +1 ta test/esse, sizga ham +1 ta rasmiy Mock Test beriladi.")}
          </p>
        </div>
      </div>

      <div className="flex items-center gap-2 w-full md:w-auto shrink-0">
        <div className="relative flex-1 md:w-72">
          <input
            type="text"
            readOnly
            value={shareUrl}
            className="w-full bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 text-xs text-slate-700 dark:text-slate-300 rounded-xl py-2.5 px-3.5 pr-9 focus:outline-none focus:ring-1 focus:ring-amber-500 font-mono shadow-inner"
          />
          <button
            type="button"
            onClick={copyToClipboard}
            title={t('dashboard.referral_copy', 'Nusxalash')}
            className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-amber-500 text-sm transition-colors cursor-pointer"
          >
            📋
          </button>
        </div>
        <button
          type="button"
          onClick={shareViaTelegram}
          className="bg-[#24A1DE] hover:bg-[#208bbf] text-white text-xs font-semibold px-4 py-2.5 rounded-xl flex items-center gap-2 transition-all shrink-0 shadow-sm hover:shadow cursor-pointer"
        >
          <span>✈️</span>
          <span>{t('dashboard.referral_share', 'Ulashish')}</span>
        </button>
      </div>
    </div>
  );
}
