import { useEffect, useState } from 'react';
import { Gift, Copy, Check, Share2, Users, Sparkles } from 'lucide-react';
import { ReferralApi, type ReferralStats } from '../lib/api';
import { useToast } from '../context/ToastContext';

export default function ReferralCard() {
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
  const shareText = `🎁 Do'stim, sizga 1 ta bepul rasmiy Mock Test va AI Esse tekshiruvi sovg'a qilaman! grandec.uz da o'z bilimingizni sinab ko'ring: ${shareUrl}`;

  const copyToClipboard = () => {
    navigator.clipboard.writeText(shareUrl);
    setCopied(true);
    toast.success('Taklif havolasi nusxalandi!');
    setTimeout(() => setCopied(false), 2000);
  };

  const shareViaTelegram = () => {
    const tgUrl = `https://t.me/share/url?url=${encodeURIComponent(shareUrl)}&text=${encodeURIComponent(shareText)}`;
    window.open(tgUrl, '_blank');
  };

  return (
    <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-amber-500/15 via-slate-900 to-slate-950 border border-amber-500/30 p-6 sm:p-7 shadow-xl shadow-amber-500/5">
      {/* Glow ornaments */}
      <div className="absolute -top-12 -right-12 w-48 h-48 bg-amber-500/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute -bottom-12 -left-12 w-48 h-48 bg-amber-400/5 rounded-full blur-3xl pointer-events-none" />

      <div className="relative z-10 flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
        {/* Left Side: Pitch */}
        <div className="max-w-xl">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-amber-500/20 text-amber-300 text-xs font-bold border border-amber-500/30 mb-3">
            <Gift className="w-3.5 h-3.5" />
            <span>MUKOFOT VA DO'STLAR DASTURI</span>
          </div>
          <h3 className="text-xl sm:text-2xl font-black text-white tracking-tight">
            🎁 Do'stingizga 1 ta bepul test sovg'a qiling va bonusga ega bo'ling!
          </h3>
          <p className="mt-2 text-slate-300 text-sm leading-relaxed">
            Taklif havolangiz orqali do'stingiz ro'yxatdan o'tsa, unga <strong>+1 ta bepul test</strong> va <strong>+1 ta esse</strong> sovg'a qilinadi. Sizga ham har bir do'stingiz uchun <strong>+1 ta to'liq rasmiy Mock Test</strong> beriladi!
          </p>

          {/* Stat counters */}
          <div className="mt-4 flex items-center gap-6 text-xs text-slate-300">
            <div className="flex items-center gap-2">
              <Users className="w-4 h-4 text-amber-400" />
              <span>Taklif qilingan: <strong className="text-white font-bold">{stats.total_invited} ta</strong></span>
            </div>
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-emerald-400" />
              <span>Bonus testlaringiz: <strong className="text-emerald-300 font-bold">+{stats.bonus_tests} ta</strong></span>
            </div>
          </div>
        </div>

        {/* Right Side: Copy & Share box */}
        <div className="w-full md:w-auto shrink-0 flex flex-col sm:flex-row md:flex-col gap-2.5">
          <div className="flex items-center gap-2 bg-slate-950/80 border border-slate-800 rounded-2xl p-1.5 pl-3">
            <span className="text-xs font-mono text-amber-400 font-bold select-all truncate max-w-[200px]">
              grandec.uz/r/{stats.referral_code}
            </span>
            <button
              type="button"
              onClick={copyToClipboard}
              className="p-2 rounded-xl bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 transition-colors shrink-0"
              title="Havolani nusxalash"
            >
              {copied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
            </button>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={copyToClipboard}
              className="flex-1 sm:flex-none px-4 py-2.5 rounded-xl bg-gradient-to-r from-amber-500 to-amber-400 hover:from-amber-400 hover:to-amber-300 text-slate-950 font-black text-xs shadow-md shadow-amber-500/20 flex items-center justify-center gap-1.5 transition-all"
            >
              {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
              <span>{copied ? 'Nusxalandi!' : 'Nusxa olish'}</span>
            </button>

            <button
              type="button"
              onClick={shareViaTelegram}
              className="flex-1 sm:flex-none px-4 py-2.5 rounded-xl bg-[#229ED9]/20 hover:bg-[#229ED9]/30 text-[#229ED9] border border-[#229ED9]/40 font-bold text-xs flex items-center justify-center gap-1.5 transition-colors"
            >
              <Share2 className="w-3.5 h-3.5" />
              <span>Telegramda ulashish</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
