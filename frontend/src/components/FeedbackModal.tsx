import { useState, useEffect } from 'react';
import { useAuth } from '../auth/AuthContext';
import { FeedbackApi, type FeedbackPayload } from '../lib/api';
import { StarIcon, XIcon, CheckCircle2Icon, MessageSquareHeartIcon } from 'lucide-react';

interface FeedbackModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function FeedbackModal({ isOpen, onClose }: FeedbackModalProps) {
  const { user } = useAuth();
  const [rating, setRating] = useState<number>(5);
  const [hoverRating, setHoverRating] = useState<number | null>(null);
  const [category, setCategory] = useState<'feedback' | 'suggestion' | 'bug' | 'praise'>('feedback');
  const [message, setMessage] = useState('');
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  // Close on Escape key
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!message.trim() || message.trim().length < 3) {
      setErr("Iltimos, fikr yoki taklifingizni to'liqroq yozing (kamida 3 ta belgi).");
      return;
    }

    setSubmitting(true);
    setErr(null);

    const payload: FeedbackPayload = {
      rating,
      category,
      message: message.trim(),
      name: name.trim() || undefined,
      phone: phone.trim() || undefined,
    };

    try {
      await FeedbackApi.submit(payload);
      setSubmitted(true);
      setTimeout(() => {
        setSubmitted(false);
        setMessage('');
        onClose();
      }, 2000);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Xatolik yuz berdi. Qayta urinib ko'ring.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="feedback-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-fade-in"
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9999,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '16px',
        backgroundColor: 'rgba(15, 23, 42, 0.65)',
        backdropFilter: 'blur(8px)',
        WebkitBackdropFilter: 'blur(8px)',
      }}
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-md rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-6 sm:p-7 shadow-2xl transition-all"
        style={{
          position: 'relative',
          width: '100%',
          maxWidth: '440px',
          borderRadius: '20px',
          background: 'var(--card, #ffffff)',
          border: '1px solid var(--border, rgba(148, 163, 184, 0.2))',
          padding: '24px 26px',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.35)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Close Button */}
        <button
          type="button"
          onClick={onClose}
          disabled={submitting}
          className="absolute top-4 right-4 p-1.5 rounded-full text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer"
          title="Yopish"
        >
          <XIcon className="h-5 w-5" />
        </button>

        {submitted ? (
          <div className="py-6 text-center space-y-3 animate-scale-up">
            <div className="w-14 h-14 rounded-2xl bg-emerald-500/15 text-emerald-500 flex items-center justify-center mx-auto border border-emerald-500/30 shadow-lg shadow-emerald-500/10">
              <CheckCircle2Icon className="h-8 w-8" />
            </div>
            <h3 className="text-xl font-bold text-slate-900 dark:text-white">
              Katta rahmat!
            </h3>
            <p className="text-xs sm:text-sm text-slate-600 dark:text-slate-300 max-w-xs mx-auto leading-relaxed">
              Sizning fikringiz GRAND EDUCATION platformasini yanada mukammal qilishga yordam beradi.
            </p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Header */}
            <div className="flex items-center gap-3 pr-8">
              <div className="w-10 h-10 rounded-xl bg-amber-500/15 text-amber-500 flex items-center justify-center border border-amber-500/30 shrink-0">
                <MessageSquareHeartIcon className="h-5 w-5" />
              </div>
              <div>
                <h3 id="feedback-modal-title" className="text-base sm:text-lg font-bold text-slate-900 dark:text-white leading-tight">
                  Fikr yoki taklif qoldirish
                </h3>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                  Platformani yaxshilash bo'yicha fikringizni ulashing
                </p>
              </div>
            </div>

            {/* Error banner */}
            {err && (
              <div className="p-2.5 rounded-xl bg-rose-500/10 border border-rose-500/25 text-rose-600 dark:text-rose-400 text-xs font-medium">
                {err}
              </div>
            )}

            {/* 1. Star Rating with Golden Hover */}
            <div className="text-center py-3 px-4 bg-slate-50 dark:bg-slate-800/50 rounded-2xl border border-slate-200/80 dark:border-slate-800 shadow-inner">
              <span className="block text-[11px] font-bold text-slate-500 dark:text-slate-400 mb-2 uppercase tracking-wider">
                Bahongizni belgilang:
              </span>
              <div className="flex items-center justify-center gap-3">
                {[1, 2, 3, 4, 5].map((star) => {
                  const activeStar = (hoverRating !== null ? hoverRating : rating) >= star;
                  return (
                    <button
                      key={star}
                      type="button"
                      onMouseEnter={() => setHoverRating(star)}
                      onMouseLeave={() => setHoverRating(null)}
                      onClick={() => setRating(star)}
                      className="p-1.5 transition-transform hover:scale-130 active:scale-110 focus:outline-none cursor-pointer"
                      title={`${star} ball`}
                    >
                      <StarIcon
                        className={`h-7 w-7 transition-all duration-150 ${
                          activeStar
                            ? 'text-amber-400 fill-amber-400 drop-shadow-[0_2px_10px_rgba(245,158,11,0.7)]'
                            : 'text-slate-300 dark:text-slate-600 hover:text-amber-300'
                        }`}
                        style={{
                          color: activeStar ? '#f59e0b' : '#cbd5e1',
                          fill: activeStar ? '#f59e0b' : 'none',
                        }}
                      />
                    </button>
                  );
                })}
              </div>
              <span className="text-xs font-extrabold text-amber-500 dark:text-amber-400 mt-1.5 inline-block">
                {rating === 5
                  ? 'Ajoyib! (5/5) ⭐'
                  : rating === 4
                  ? 'Yaxshi (4/5) 👍'
                  : rating === 3
                  ? 'O\'rtacha (3/5) 👌'
                  : rating === 2
                  ? 'Kamchiliklar bor (2/5) ⚠️'
                  : 'Qoniqarsiz (1/5) ❌'}
              </span>
            </div>

            {/* 2. Category Selector (Pills) */}
            <div>
              <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1.5">
                Kategoriya:
              </label>
              <div className="flex flex-wrap gap-2">
                {[
                  { id: 'feedback', label: '💬 Fikr' },
                  { id: 'suggestion', label: '💡 Taklif' },
                  { id: 'bug', label: '🚨 Xatolik' },
                  { id: 'praise', label: '❤️ Tashakkur' },
                ].map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => setCategory(item.id as any)}
                    className={`py-2 px-3.5 rounded-xl text-xs font-bold border transition-all cursor-pointer ${
                      category === item.id
                        ? 'bg-amber-500 text-slate-950 border-amber-500 shadow-sm shadow-amber-500/30'
                        : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 border-slate-200 dark:border-slate-700 hover:border-amber-400/50'
                    }`}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </div>

            {/* 3. Message Textarea */}
            <div>
              <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1.5">
                Xabaringiz / Fikringiz:
              </label>
              <textarea
                rows={3}
                required
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                placeholder="Platforma bo'yicha fikr, savol yoki taklifingizni qoldiring..."
                className="w-full rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-950/70 p-3.5 text-xs sm:text-sm text-slate-900 dark:text-slate-100 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-amber-500 leading-relaxed resize-none transition-all shadow-inner"
              />
            </div>

            {/* 4. Guest info if not logged in */}
            {!user && (
              <div className="grid grid-cols-2 gap-2.5">
                <div>
                  <label className="block text-[11px] font-medium text-slate-600 dark:text-slate-400 mb-1">
                    Ismingiz:
                  </label>
                  <input
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="Sardor"
                    className="w-full rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50/50 dark:bg-slate-950/50 px-3 py-1.5 text-xs text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-amber-500/30 focus:border-amber-500"
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-medium text-slate-600 dark:text-slate-400 mb-1">
                    Telefon raqam:
                  </label>
                  <input
                    type="tel"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    placeholder="+998 90..."
                    className="w-full rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50/50 dark:bg-slate-950/50 px-3 py-1.5 text-xs text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-amber-500/30 focus:border-amber-500"
                  />
                </div>
              </div>
            )}

            {/* Actions */}
            <div className="flex items-center gap-2 pt-2">
              <button
                type="button"
                onClick={onClose}
                disabled={submitting}
                className="flex-1 py-2.5 rounded-xl text-xs font-semibold text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors border border-slate-200 dark:border-slate-700 cursor-pointer"
              >
                Bekor qilish
              </button>
              <button
                type="submit"
                disabled={submitting}
                className="flex-2 py-2.5 rounded-xl bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 text-slate-950 font-bold text-xs sm:text-sm shadow-md shadow-amber-500/25 disabled:opacity-50 transition-all cursor-pointer flex items-center justify-center gap-1.5"
              >
                {submitting ? "Yuborilmoqda..." : "Yuborish 🚀"}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
