import { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { useToast } from '../context/ToastContext';
import { GroupInviteApi, type GroupJoinPreview } from '../lib/api';
import { Sparkles, Users, BookOpen, UserCheck, ShieldCheck, ArrowRight, LogIn } from 'lucide-react';

export default function JoinGroup() {
  const { token } = useParams<{ token: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();
  const toast = useToast();

  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [group, setGroup] = useState<GroupJoinPreview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [joined, setJoined] = useState(false);

  useEffect(() => {
    if (!token) return;
    setLoading(true);
    GroupInviteApi.preview(token)
      .then((data) => {
        setGroup(data);
        if (data.is_member) {
          setJoined(true);
        }
      })
      .catch((err) => {
        setError(err.message || 'Guruh taklif havolasi topilmadi yoki muddati o\'tgan.');
      })
      .finally(() => {
        setLoading(false);
      });
  }, [token]);

  const handleJoin = async () => {
    if (!token) return;
    if (!user) {
      navigate(`/login?next=${encodeURIComponent(`/join/${token}`)}`);
      return;
    }

    setSubmitting(true);
    try {
      const res = await GroupInviteApi.join(token);
      toast.success(res.message || 'Guruhga muvaffaqiyatli qo\'shildingiz!');
      setJoined(true);
      setTimeout(() => {
        navigate('/dashboard');
      }, 1500);
    } catch (err: any) {
      toast.error(err.message || 'Guruhga qo\'shilishda xatolik yuz berdi.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 flex flex-col justify-center items-center p-4 selection:bg-amber-500 selection:text-slate-950">
      <div className="w-full max-w-lg">
        {/* Brand Header */}
        <div className="text-center mb-8">
          <Link to="/" className="inline-flex items-center gap-3 group">
            <div className="w-12 h-12 rounded-2xl bg-gradient-to-tr from-amber-500 to-amber-300 p-0.5 shadow-lg shadow-amber-500/20 group-hover:scale-105 transition-transform">
              <div className="w-full h-full bg-slate-950 rounded-[14px] flex items-center justify-center">
                <Sparkles className="w-6 h-6 text-amber-400" />
              </div>
            </div>
            <div className="text-left">
              <span className="block text-xl font-black tracking-tight text-white">GRAND EDUCATION</span>
              <span className="block text-xs font-semibold tracking-widest text-amber-400 uppercase">Academic EdTech</span>
            </div>
          </Link>
        </div>

        {/* Main Card */}
        <div className="bg-slate-950/80 backdrop-blur-xl border border-slate-800 rounded-3xl p-6 sm:p-8 shadow-2xl relative overflow-hidden">
          <div className="absolute top-0 right-0 w-64 h-64 bg-amber-500/5 rounded-full blur-3xl pointer-events-none" />
          <div className="absolute bottom-0 left-0 w-64 h-64 bg-emerald-500/5 rounded-full blur-3xl pointer-events-none" />

          {loading ? (
            <div className="py-16 text-center">
              <div className="w-10 h-10 border-4 border-amber-500/30 border-t-amber-400 rounded-full animate-spin mx-auto mb-4" />
              <p className="text-slate-400 text-sm font-medium">Guruh ma'lumotlari yuklanmoqda...</p>
            </div>
          ) : error ? (
            <div className="py-12 text-center">
              <div className="w-16 h-16 rounded-2xl bg-rose-500/10 border border-rose-500/20 text-rose-400 flex items-center justify-center mx-auto mb-4">
                ✕
              </div>
              <h2 className="text-xl font-bold text-white mb-2">Guruh topilmadi</h2>
              <p className="text-slate-400 text-sm mb-6 max-w-sm mx-auto">{error}</p>
              <Link
                to="/"
                className="inline-flex items-center gap-2 px-6 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-white font-medium text-sm transition-colors"
              >
                Bosh sahifaga qaytish
              </Link>
            </div>
          ) : group ? (
            <div>
              <div className="flex items-center justify-between gap-4 mb-6 pb-6 border-b border-slate-800/80">
                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20">
                  <BookOpen className="w-3.5 h-3.5" />
                  {group.subject_display || group.subject}
                </span>
                <span className="inline-flex items-center gap-1.5 text-xs text-slate-400 font-medium">
                  <Users className="w-3.5 h-3.5 text-slate-500" />
                  {group.student_count} ta o'quvchi
                </span>
              </div>

              <div className="text-center mb-6">
                <h1 className="text-2xl sm:text-3xl font-black text-white mb-2 tracking-tight">
                  {group.name}
                </h1>
                <p className="text-slate-400 text-sm flex items-center justify-center gap-2">
                  <UserCheck className="w-4 h-4 text-emerald-400" />
                  Ustoz: <strong className="text-slate-200">{group.teacher_name}</strong>
                </p>
                {group.description && (
                  <p className="mt-3 text-slate-400 text-xs italic bg-slate-900/60 p-3 rounded-xl border border-slate-800">
                    "{group.description}"
                  </p>
                )}
              </div>

              {/* Automatic PRO Privilege Banner */}
              <div className="bg-gradient-to-r from-amber-500/10 via-amber-400/5 to-transparent border border-amber-500/20 rounded-2xl p-4 mb-6 flex items-start gap-3">
                <div className="p-2 rounded-xl bg-amber-500/20 text-amber-400 shrink-0">
                  <ShieldCheck className="w-5 h-5" />
                </div>
                <div>
                  <h4 className="text-amber-300 font-bold text-sm">Avtomatik PRO Imtiyozi</h4>
                  <p className="text-slate-300 text-xs mt-0.5 leading-relaxed">
                    Ushbu guruhga qo'shilsangiz, profilingizga 365 kunlik <strong>PRO tarifi</strong> (barcha rasmiy BMB testlari va kunlik 50 ta AI repetitor) avtomatik yoqiladi.
                  </p>
                </div>
              </div>

              {/* Action Buttons */}
              {joined ? (
                <div className="space-y-3">
                  <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 rounded-xl text-center text-sm font-semibold flex items-center justify-center gap-2">
                    <UserCheck className="w-4 h-4" />
                    Siz allaqachon ushbu guruh a'zosisiz!
                  </div>
                  <button
                    type="button"
                    onClick={() => navigate('/dashboard')}
                    className="w-full py-3.5 px-6 rounded-2xl bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-400 hover:to-teal-400 text-slate-950 font-black text-sm shadow-lg shadow-emerald-500/20 flex items-center justify-center gap-2 transition-all"
                  >
                    Kabinetga o'tish <ArrowRight className="w-4 h-4" />
                  </button>
                </div>
              ) : user ? (
                <button
                  type="button"
                  onClick={handleJoin}
                  disabled={submitting}
                  className="w-full py-4 px-6 rounded-2xl bg-gradient-to-r from-amber-500 via-amber-400 to-amber-500 hover:from-amber-400 hover:to-amber-300 text-slate-950 font-black text-base shadow-lg shadow-amber-500/25 flex items-center justify-center gap-2 transition-all hover:scale-[1.01] active:scale-[0.99] disabled:opacity-50"
                >
                  {submitting ? (
                    <div className="w-5 h-5 border-2 border-slate-950 border-t-transparent rounded-full animate-spin" />
                  ) : (
                    <>
                      <span>✅ Guruhga qo'shilish</span>
                      <ArrowRight className="w-4 h-4" />
                    </>
                  )}
                </button>
              ) : (
                <div className="space-y-3">
                  <Link
                    to={`/login?next=${encodeURIComponent(`/join/${token}`)}`}
                    className="w-full py-4 px-6 rounded-2xl bg-gradient-to-r from-amber-500 via-amber-400 to-amber-500 hover:from-amber-400 hover:to-amber-300 text-slate-950 font-black text-base shadow-lg shadow-amber-500/25 flex items-center justify-center gap-2 transition-all hover:scale-[1.01] active:scale-[0.99]"
                  >
                    <LogIn className="w-5 h-5" />
                    <span>Kirish va Guruhga qo'shilish</span>
                  </Link>

                  <div className="flex items-center gap-2 text-center text-xs text-slate-400">
                    <span className="w-full border-t border-slate-800" />
                    <span className="px-2 shrink-0">yoki</span>
                    <span className="w-full border-t border-slate-800" />
                  </div>

                  <Link
                    to={`/register?next=${encodeURIComponent(`/join/${token}`)}`}
                    className="w-full py-3 px-6 rounded-2xl bg-slate-900 hover:bg-slate-800 text-slate-300 hover:text-white font-semibold text-sm border border-slate-800 text-center block transition-colors"
                  >
                    Yangi hisob yaratish (Ro'yxatdan o'tish)
                  </Link>
                </div>
              )}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
