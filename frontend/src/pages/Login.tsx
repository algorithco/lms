import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { useLang } from '../i18n/LangContext';
import { TelegramAuth, ensureSession, landingFor } from '../lib/api';
import { ArrowLeftIcon } from '../components/icons';
import Particles from '../components/Particles';

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
    try {
      const data = await TelegramAuth.start();
      if (!data.deep_link || !data.deep_link.startsWith('https://t.me/')) {
        throw new Error('Bad deep link');
      }
      setTgToken(data.token);
      setTgPhase('waiting');
      window.open(data.deep_link, '_blank', 'noopener,noreferrer');
      pollRef.current = window.setInterval(() => void pollStatus(data.token), 2000);
    } catch {
      setTgPhase('idle');
      setTgToken(null);
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
    setTgCode('');
    setTgError(null);
  };

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      const user = await login(email, password);
      // Best-effort Django session for arena WS + session endpoints.
      ensureSession(email, password).catch(() => false);
      navigate(landingFor(user));
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

        {/* -- Telegram bot login ------------------------------------------- */}
        <div style={{ marginTop: 20 }}>
          {tgPhase === 'idle' && (
            <button className="btn" disabled={tgBusy} onClick={() => void startTelegramAuth()}>
              {tgBusy ? '…' : t('login_with_telegram')}
            </button>
          )}
          {tgPhase === 'waiting' && (
            <div>
              <p className="muted small">{t('telegram_login_step1')}</p>
              <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
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
