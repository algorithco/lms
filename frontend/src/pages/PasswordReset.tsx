import { useState } from 'react';
import type { FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { useLang } from '../i18n/LangContext';
import { Auth } from '../lib/api';

/** Requests a reset link via the JSON API (POST /api/auth/password-reset/). */
export default function PasswordReset() {
  const { t } = useLang();
  const [email, setEmail] = useState('');
  const [done, setDone] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      await Auth.requestPasswordReset(email);
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
        <h1>{t('forgot_password_title')}</h1>
        {done ? (
          <>
            <p className="muted">{t('reset_done_body')}</p>
            <p>
              <Link to="/login">{t('reset_back_login')}</Link>
            </p>
          </>
        ) : (
          <>
            <p className="muted">{t('reset_request_help')}</p>
            <form onSubmit={onSubmit} className="form">
              <div className="floating">
                <input
                  id="reset-email"
                  type="email"
                  required
                  placeholder={t('email')}
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
                <label htmlFor="reset-email">{t('email')}</label>
              </div>
              {err && <p className="error">{err}</p>}
              <button className="btn primary btn-glow" disabled={busy}>
                {busy ? '…' : t('reset_send')}
              </button>
            </form>
            <p className="muted" style={{ marginTop: 16 }}>
              <Link to="/login">{t('reset_back_login')}</Link>
            </p>
          </>
        )}
      </div>
    </div>
  );
}
