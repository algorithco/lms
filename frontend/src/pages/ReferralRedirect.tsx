import { useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { useToast } from '../context/ToastContext';
import { ReferralApi } from '../lib/api';
import { useLang } from '../i18n/LangContext';

export default function ReferralRedirect() {
  const { code } = useParams<{ code: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();
  const toast = useToast();
  const { t } = useLang();

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
          toast.success(res.message || t('rr_applied'));
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
  }, [code, user, navigate, toast, t]);

  return (
    <div className="exam-state" role="status">
      <div className="exam-state__spinner" aria-hidden="true" />
      <p>{t('rr_checking')}</p>
    </div>
  );
}
