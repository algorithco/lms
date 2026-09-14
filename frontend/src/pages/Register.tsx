import { useState } from 'react';
import type { FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { useLang } from '../i18n/LangContext';
import { ensureSession } from '../lib/api';

export default function Register() {
  const { register, error } = useAuth();
  const { t } = useLang();
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState({
    email: '',
    password: '',
    password_confirm: '',
    first_name: '',
    last_name: '',
  });

  const set =
    (k: keyof typeof form) =>
    (e: { target: { value: string } }) =>
      setForm((f) => ({ ...f, [k]: e.target.value }));

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      await register(form);
      ensureSession(form.email, form.password).catch(() => false);
      navigate('/dashboard');
    } catch {
      /* error shown from context */
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth-wrap">
      <div className="auth-card">
        <img src="/grandec.png" alt="GRANDEC" className="auth-logo" />
        <h1>{t('register')}</h1>
        <p className="muted">{t('register_subtitle')}</p>
        <form onSubmit={onSubmit} className="form">
          <div className="floating">
            <input id="reg-email" type="email" required placeholder={t('email')} value={form.email} onChange={set('email')} />
            <label htmlFor="reg-email">{t('email')}</label>
          </div>
          <div className="row">
            <div className="floating">
              <input id="reg-fn" required placeholder={t('first_name')} value={form.first_name} onChange={set('first_name')} />
              <label htmlFor="reg-fn">{t('first_name')}</label>
            </div>
            <div className="floating">
              <input id="reg-ln" required placeholder={t('last_name')} value={form.last_name} onChange={set('last_name')} />
              <label htmlFor="reg-ln">{t('last_name')}</label>
            </div>
          </div>
          <div className="floating">
            <input
              id="reg-pw"
              type="password"
              required
              placeholder={t('password')}
              value={form.password}
              onChange={set('password')}
              autoComplete="new-password"
            />
            <label htmlFor="reg-pw">{t('password')}</label>
          </div>
          <div className="floating">
            <input
              id="reg-pw2"
              type="password"
              required
              placeholder={t('password_confirm')}
              value={form.password_confirm}
              onChange={set('password_confirm')}
              autoComplete="new-password"
            />
            <label htmlFor="reg-pw2">{t('password_confirm')}</label>
          </div>
          {error && <p className="error">{error}</p>}
          <button className="btn primary btn-glow" disabled={busy}>
            {busy ? '…' : t('register')}
          </button>
        </form>
        <p className="muted" style={{ marginTop: 16 }}>
          <Link to="/login">{t('login')}</Link>
        </p>
      </div>
    </div>
  );
}
