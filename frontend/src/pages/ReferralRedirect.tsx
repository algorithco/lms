import { useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { useToast } from '../context/ToastContext';
import { ReferralApi } from '../lib/api';

export default function ReferralRedirect() {
  const { code } = useParams<{ code: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();
  const toast = useToast();

  useEffect(() => {
    if (!code) {
      navigate('/dashboard');
      return;
    }

    // Save for register flow
    localStorage.setItem('pending_referral_code', code);

    if (user) {
      // If user is already logged in, apply the referral code right away
      ReferralApi.apply(code)
        .then((res) => {
          toast.success(res.message || 'Do\'stingizning taklif bonusi hisobingizga qo\'shildi!');
        })
        .catch((err) => {
          if (err.message) toast.info(err.message);
        })
        .finally(() => {
          navigate('/dashboard');
        });
    } else {
      // If guest, send to registration with referral query param
      navigate(`/register?ref=${encodeURIComponent(code)}`);
    }
  }, [code, user, navigate, toast]);

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center text-slate-100 p-4">
      <div className="w-10 h-10 border-4 border-amber-500/30 border-t-amber-400 rounded-full animate-spin mb-4" />
      <p className="text-slate-400 text-sm font-medium">Taklif havolasi tekshirilmoqda...</p>
    </div>
  );
}
