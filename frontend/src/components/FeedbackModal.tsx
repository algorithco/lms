import { useState } from 'react';
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
      }, 2200);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Xatolik yuz berdi. Qayta urinib ko'ring.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-fade-in">
      <div className="relative w-full max-w-lg rounded-3xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 p-6 sm:p-8 shadow-2xl transition-all">
        {/* Close Button */}
        <button
          type="button"
          onClick={onClose}
          disabled={submitting}
          className="absolute top-5 right-5 p-2 rounded-full text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
          title="Yopish"
        >
          <XIcon className="h-5 w-5" />
        </button>

        {submitted ? (
          <div className="py-8 text-center space-y-4 animate-scale-up">
            <div className="w-16 h-16 rounded-3xl bg-emerald-500/15 text-emerald-500 flex items-center justify-center mx-auto border border-emerald-500/30">
              <CheckCircle2Icon className="h-9 w-9" />
            </div>
            <h3 className="text-xl sm:text-2xl font-bold text-slate-900 dark:text-white">
              Katta rahmat!
            </h3>
            <p className="text-sm text-slate-600 dark:text-slate-300 max-w-sm mx-auto">
              Sizning fikringiz va taklifingiz GRAND EDUCATION platformasini yanada mukammal qilishga yordam beradi.
            </p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-5">
            {/* Header */}
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-2xl bg-amber-500/15 text-amber-500 flex items-center justify-center border border-amber-500/30 shrink-0">
                <MessageSquareHeartIcon className="h-5 w-5" />
              </div>
              <div>
                <h3 className="text-lg sm:text-xl font-bold text-slate-900 dark:text-white">
                  Fikr yoki taklif qoldirish
                </h3>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Platformamizni yaxshilash bo'yicha fikr va bahoingizni ulashing
                </p>
              </div>
            </div>

            {/* Error banner */}
            {err && (
              <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-600 dark:text-rose-400 text-xs font-medium">
                {err}
              </div>
            )}

            {/* 1. Star Rating */}
            <div className="text-center py-2 bg-slate-50 dark:bg-slate-800/50 rounded-2xl border border-slate-100 dark:border-slate-800">
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 mb-1.5">
                Platforma bahosi:
              </label>
              <div className="flex items-center justify-center gap-1.5">
                {[1, 2, 3, 4, 5].map((star) => {
                  const activeStar = (hoverRating !== null ? hoverRating : rating) >= star;
                  return (
                    <button
                      key={star}
                      type="button"
                      onMouseEnter={() => setHoverRating(star)}
                      onMouseLeave={() => setHoverRating(null)}
                      onClick={() => setRating(star)}
                      className="p-1 text-2xl transition-transform hover:scale-125 focus:outline-none"
                    >
                      <StarIcon
                        className={`h-7 w-7 transition-colors ${
                          activeStar
                            ? 'text-amber-400 fill-amber-400 drop-shadow-[0_2px_8px_rgba(251,191,36,0.5)]'
                            : 'text-slate-300 dark:text-slate-600'
                        }`}
                      />
                    </button>
                  );
                })}
              </div>
              <span className="text-xs font-semibold text-amber-500 dark:text-amber-400 mt-1 inline-block">
                {rating === 5
                  ? 'Ajoyib! (5/5)'
                  : rating === 4
                  ? 'Yaxshi (4/5)'
                  : rating === 3
                  ? 'O\'rtacha (3/5)'
                  : rating === 2
                  ? 'Kamchiliklar bor (2/5)'
                  : 'Qoniqarsiz (1/5)'}
              </span>
            </div>

            {/* 2. Category Selector */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
                Xabar turi:
              </label>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                {[
                  { id: 'feedback', label: '💬 Fikr' },
                  { id: 'suggestion', label: '💡 Taklif' },
                  { id: 'bug', label: '🐛 Xatolik' },
                  { id: 'praise', label: '❤️ Tashakkur' },
                ].map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => setCategory(item.id as any)}
                    className={`py-2 px-2.5 rounded-xl text-xs font-bold border transition-all text-center ${
                      category === item.id
                        ? 'bg-blue-600 text-white border-blue-500 shadow-md shadow-blue-500/20'
                        : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 border-slate-200 dark:border-slate-700 hover:border-slate-300'
                    }`}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </div>

            {/* 3. Message Textarea */}
            <div>
              <label className="block text-xs font-semibold text-slate-700 dark:text-slate-300 mb-1.5">
                Xabaringiz / Fikringiz:
              </label>
              <textarea
                rows={4}
                required
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                placeholder="Platforma bo'yicha qanday taklifingiz yoki savolingiz bor? Batafsil yozing..."
                className="w-full rounded-2xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 px-4 py-3 text-sm text-slate-900 dark:text-slate-100 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 leading-relaxed resize-none"
              />
            </div>

            {/* 4. Optional Guest Name / Phone if not logged in */}
            {!user && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                    Ismingiz (ixtiyoriy):
                  </label>
                  <input
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="Masalan: Sardor"
                    className="w-full rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 px-3.5 py-2 text-xs text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">
                    Telefon raqam (ixtiyoriy):
                  </label>
                  <input
                    type="tel"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    placeholder="+998 90 123 45 67"
                    className="w-full rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-950 px-3.5 py-2 text-xs text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>
            )}

            {/* Submit & Cancel */}
            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={onClose}
                disabled={submitting}
                className="px-4 py-2.5 rounded-xl text-xs font-semibold text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
              >
                Bekor qilish
              </button>
              <button
                type="submit"
                disabled={submitting}
                className="px-6 py-2.5 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white font-bold text-xs shadow-lg shadow-blue-600/30 disabled:opacity-50 transition-all cursor-pointer"
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
