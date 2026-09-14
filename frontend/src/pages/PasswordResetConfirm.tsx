import { useState } from 'react';
import type { FormEvent } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useLang } from '../i18n/LangContext';
import { Auth } from '../lib/api';

/** Sets a new password from an emailed reset link (/password-reset/confirm/:uid/:token). */
export default function PasswordResetConfirm() {
  const { t } = useLang();
  const { uid = '', token = '' } = useParams();
  const [p1, setP1] = useState('');
  const [p2, setP2] = useState('');
  const [done, setDone] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      await Auth.confirmPasswordReset({
        uid,
        token,
        new_password1: p1,
        new_password2: p2,
      });
      setDone(true);
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : 'Failed.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth-wrap">
      <div className="auth-card">
        <img src="/grandec.png" alt="GRANDEC" className="auth-logo" />
        <h1>{t('pr_title')}</h1>
        {done ? (
          <>
            <p className="muted">{t('reset_complete_body')}</p>
            <p>
              <Link to="/login">{t('reset_back_login')}</Link>
            </p>
          </>
        ) : (
          <>
            <p className="muted">{t('pr_subtitle')}</p>
            <form onSubmit={onSubmit} className="form">
              <div className="floating">
                <input
                  id="pr-new"
                  type="password"
                  required
                  placeholder={t('pr_new_label')}
                  value={p1}
                  onChange={(e) => setP1(e.target.value)}
                />
                <label htmlFor="pr-new">{t('pr_new_label')}</label>
              </div>
              <div className="floating">
                <input
                  id="pr-confirm"
                  type="password"
                  required
                  placeholder={t('pr_confirm_label')}
                  value={p2}
                  onChange={(e) => setP2(e.target.value)}
                />
                <label htmlFor="pr-confirm">{t('pr_confirm_label')}</label>
              </div>
              {err && <p className="error">{err}</p>}
              <button className="btn primary btn-glow" disabled={busy}>
                {busy ? '…' : t('pr_submit')}
              </button>
            </form>
            <p className="muted" style={{ marginTop: 16 }}>
              <Link to="/password-reset">{t('pr_resend')}</Link>
            </p>
          </>
        )}
      </div>
    </div>
  );
}
