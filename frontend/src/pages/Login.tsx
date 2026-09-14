import { useState } from 'react';
import type { FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { useLang } from '../i18n/LangContext';
import { ensureSession } from '../lib/api';
import { ArrowLeftIcon } from '../components/icons';
import Particles from '../components/Particles';

export default function Login() {
  const { login, error } = useAuth();
  const { t } = useLang();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      await login(email, password);
      // Best-effort Django session for arena WS + session endpoints.
      ensureSession(email, password).catch(() => false);
      navigate('/dashboard');
    } catch {
      /* error shown from context */
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth-wrap" style={{ position: 'relative', overflow: 'hidden' }}>
      <div
        aria-hidden="true"
        style={{
          position: 'absolute',
          inset: 0,
          pointerEvents: 'none',
          opacity: 0.55,
        }}
      >
        <Particles
          particleCount={260}
          particleSpread={10}
          speed={0.1}
          particleColors={['#FACC15', '#EAB308', '#FEF08A']}
          alphaParticles
          particleBaseSize={100}
          sizeRandomness={1}
          cameraDistance={20}
        />
      </div>
      <div className="auth-card" style={{ position: 'relative', zIndex: 1 }}>
        <Link to="/" className="muted small" style={{ display: 'inline-flex', alignItems: 'center', gap: 6, textDecoration: 'none', marginBottom: 12 }}>
          <ArrowLeftIcon size={14} className="ico" /> {t('back_home')}
        </Link>
        <img src="/grandec.png" alt="GRANDEC" className="auth-logo" />
        <h1>{t('login')}</h1>
        <p className="muted">{t('login_subtitle')}</p>
        <form onSubmit={onSubmit} className="form">
          <div className="floating">
            <input
              id="email"
              type="email"
              required
              placeholder={t('email')}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
            />
            <label htmlFor="email">{t('email')}</label>
          </div>
          <div className="floating">
            <input
              id="password"
              type="password"
              required
              placeholder={t('password')}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
            />
            <label htmlFor="password">{t('password')}</label>
          </div>
          {error && <p className="error">{error}</p>}
          <button className="btn primary btn-glow" disabled={busy}>
            {busy ? '…' : t('login')}
          </button>
        </form>
        <p className="muted" style={{ marginTop: 16 }}>
          <Link to="/password-reset">{t('forgot_password')}</Link>
        </p>
        <p className="muted">
          <Link to="/register">{t('register')}</Link>
        </p>
      </div>
    </div>
  );
}
