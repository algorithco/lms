import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { useLang } from '../i18n/LangContext';
import { GoogleAuth, TelegramAuth, landingFor } from '../lib/api';
import { ArrowLeftIcon } from '../components/icons';
import Particles from '../components/Particles';
import SEO from '../components/SEO';

type TgPhase = 'idle' | 'waiting' | 'code' | 'done';

export default function Login() {
  const { login, loginWithTelegram, error } = useAuth();
  const { t } = useLang();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);

  // -- Telegram bot login (mirrors old login.html flow) --------------------
  const [tgPhase, setTgPhase] = useState<TgPhase>('idle');
  const [tgToken, setTgToken] = useState<string | null>(null);
  const [tgDeepLink, setTgDeepLink] = useState<string | null>(null);
  const [tgCode, setTgCode] = useState('');
  const [tgError, setTgError] = useState<string | null>(null);
  const [tgBusy, setTgBusy] = useState(false);
  const pollRef = useRef<number | null>(null);

  const stopPolling = () => {
    if (pollRef.current !== null) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  useEffect(() => stopPolling, []);

  const adoptTelegramLogin = (tokens: { access: string; refresh: string }, user: Record<string, unknown>) => {
    stopPolling();
    setTgPhase('done');
    const adopted = loginWithTelegram(tokens, user);
    navigate(landingFor(adopted));
  };

  const pollStatus = async (token: string) => {
    try {
      const st = await TelegramAuth.status(token);
      if (st.status === 'verified') {
        stopPolling();
        setTgPhase('code');
        setTgError(null);
      } else if (st.status !== 'pending') {
        stopPolling();
        setTgPhase('idle');
        setTgToken(null);
        setTgError(st.error || t('code_invalid_js'));
      }
    } catch {
      /* transient network error — keep polling */
    }
  };

  const startTelegramAuth = async () => {
    stopPolling();
    setTgError(null);
    setTgBusy(true);
    // Reserve the popup synchronously in the click handler. Opening it after
    // awaiting the API call is blocked by many browsers as an unsolicited
    // popup, which made the Telegram button appear to do nothing.
    const telegramWindow = window.open('', '_blank');
    try {
      const data = await TelegramAuth.start();
      if (!data.deep_link || !data.deep_link.startsWith('https://t.me/')) {
        throw new Error('Bad deep link');
      }
      setTgToken(data.token);
      setTgDeepLink(data.deep_link);
      setTgPhase('waiting');
      if (telegramWindow && !telegramWindow.closed) {
        telegramWindow.opener = null;
        telegramWindow.location.href = data.deep_link;
        telegramWindow.focus();
      }
      pollRef.current = window.setInterval(() => void pollStatus(data.token), 2000);
    } catch {
      // Close only the blank popup we created for this attempt.
      if (telegramWindow && !telegramWindow.closed) telegramWindow.close();
      setTgPhase('idle');
      setTgToken(null);
      setTgDeepLink(null);
      setTgError(t('code_invalid_js'));
    } finally {
      setTgBusy(false);
    }
  };

  const submitTelegramCode = async (e: FormEvent) => {
    e.preventDefault();
    if (!/^\d{6}$/.test(tgCode.trim())) {
      setTgError(t('code_invalid_js'));
      return;
    }
    setTgBusy(true);
    setTgError(null);
    try {
      const data = await TelegramAuth.loginWithCode(tgCode.trim());
      adoptTelegramLogin(data.tokens, data.user);
    } catch (err) {
      setTgError(err instanceof Error ? err.message : t('code_invalid_js'));
    } finally {
      setTgBusy(false);
    }
  };

  const confirmTelegramDone = async () => {
    if (!tgToken) return;
    setTgBusy(true);
    setTgError(null);
    try {
      const data = await TelegramAuth.loginWithToken(tgToken);
      adoptTelegramLogin(data.tokens, data.user);
    } catch {
      // Token not consumable yet (user still in bot conversation) — resume
      // polling and let them finish, or enter the 6-digit code instead.
      if (pollRef.current === null && tgToken) {
        const token = tgToken;
        pollRef.current = window.setInterval(() => void pollStatus(token), 2000);
      }
      setTgError(t('code_hint'));
    } finally {
      setTgBusy(false);
    }
  };

  const cancelTelegramAuth = () => {
    stopPolling();
    setTgPhase('idle');
    setTgToken(null);
    setTgDeepLink(null);
    setTgCode('');
    setTgError(null);
  };

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      const user = await login(email, password);
      navigate(landingFor(user));
    } catch {
      /* error shown from context */
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth-wrap" style={{ position: 'relative', overflow: 'hidden' }}>
      <SEO
        title={t('login_title')}
        description={t('login_subtitle')}
        canonical="/login"
      />
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

        {/* -- 1-Click Fast Auth (Google & Telegram) -------------------- */}
        <div style={{ marginTop: 20, display: 'flex', flexDirection: 'column', gap: 10 }}>
          <a
            href={GoogleAuth.startUrl}
            className="btn"
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 10,
              background: 'rgba(255, 255, 255, 0.05)',
              border: '1px solid rgba(255, 255, 255, 0.15)',
              textDecoration: 'none',
              fontWeight: 700,
            }}
          >
            <svg width="18" height="18" viewBox="0 0 24 24">
              <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
              <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
              <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z" />
              <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z" />
            </svg>
            {t('login_with_google')}
          </a>

          {tgPhase === 'idle' && (
            <button
              type="button"
              className="btn"
              disabled={tgBusy}
              onClick={() => void startTelegramAuth()}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 10,
                background: 'rgba(42, 171, 238, 0.12)',
                border: '1px solid rgba(42, 171, 238, 0.35)',
                color: '#38bdf8',
                fontWeight: 700,
              }}
            >
              {tgBusy ? '…' : t('login_with_telegram')}
            </button>
          )}
        </div>
        <div>
          {tgPhase === 'waiting' && (
            <div>
              <p className="muted small">{t('telegram_login_step1')}</p>
              <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                {tgDeepLink && (
                  <a
                    className="btn"
                    href={tgDeepLink}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{ textDecoration: 'none' }}
                  >
                    Open Telegram
                  </a>
                )}
                <button className="btn" disabled={tgBusy} onClick={() => void confirmTelegramDone()}>
                  {tgBusy ? '…' : t('submit')}
                </button>
                <button className="btn" onClick={cancelTelegramAuth}>
                  ✕
                </button>
              </div>
            </div>
          )}
          {tgPhase === 'code' && (
            <form onSubmit={(e) => void submitTelegramCode(e)} className="form" style={{ marginTop: 12 }}>
              <p className="muted small">✅ {t('telegram_login_step2')}</p>
              <p className="muted small">{t('code_hint')}</p>
              <div className="floating">
                <input
                  id="tg-code"
                  type="text"
                  inputMode="numeric"
                  maxLength={6}
                  pattern="[0-9]{6}"
                  placeholder="123456"
                  value={tgCode}
                  onChange={(e) => setTgCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                  autoComplete="one-time-code"
                />
                <label htmlFor="tg-code">123456</label>
              </div>
              <button className="btn primary" disabled={tgBusy || tgCode.length !== 6}>
                {tgBusy ? '…' : t('submit')}
              </button>
              <p className="muted small" style={{ marginTop: 8 }}>{t('code_expires')}</p>
              <button type="button" className="btn" onClick={cancelTelegramAuth}>
                ✕
              </button>
            </form>
          )}
          {tgError && <p className="error">{tgError}</p>}
        </div>

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
