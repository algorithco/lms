import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { useLang } from '../i18n/LangContext';
import { GoogleAuth, TelegramAuth, landingFor } from '../lib/api';
import { ArrowLeftIcon } from '../components/icons';
import Particles from '../components/Particles';
import SEO from '../components/SEO';

type TgPhase = 'idle' | 'waiting' | 'code' | 'done';

export default function Login() {
  const { login, loginWithTelegram, loginWithGoogle, error } = useAuth();
  const { t, setLang } = useLang();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const urlError = searchParams.get('error');

  const [authTab, setAuthTab] = useState<'student' | 'staff'>('student');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [googleBusy, setGoogleBusy] = useState(false);
  const [googleError, setGoogleError] = useState<string | null>(null);
  const hasGoogle = Boolean(import.meta.env.VITE_GOOGLE_CLIENT_ID && import.meta.env.VITE_GOOGLE_CLIENT_ID.trim() !== "");

  // Friendly error message for URL error code
    // Silently clean up ?error=google_not_configured from address bar
  useEffect(() => {
    if (urlError === 'google_not_configured' || (typeof window !== 'undefined' && window.location.search.includes('google_not_configured'))) {
      window.history.replaceState({}, document.title, window.location.pathname);
    }
  }, [urlError]);

  const getUrlErrorMessage = (code: string | null): string | null => {
    if (!code) return null;
    switch (code) {
      case 'google_not_configured':
        return null;
      case 'google_cancelled':
        return 'Google orqali kirish bekor qilindi.';
      case 'google_invalid_state':
        return 'Xavfsizlik tekshiruvidan o‘tmadi. Iltimos, qaytadan urinib ko‘ring.';
      case 'email_exists':
        return 'Bu email allaqachon ro‘yxatdan o‘tgan. Iltimos, parol bilan kiring.';
      case 'account_inactive':
        return 'Ushbu hisob faol emas. Qo‘llab-quvvatlash xizmatiga murojaat qiling.';
      default:
        return 'Avtorizatsiyada xatolik yuz berdi.';
    }
  };

  const isGoogleUnconfigured =
    urlError === 'google_not_configured' ||
    (typeof error === 'string' &&
      (error.includes('google_not_configured') ||
        error.includes('Google orqali kirish hali sozlanmagan') ||
        error.includes('Google kirish hali sozlanmagan')));
  const activeError = isGoogleUnconfigured
    ? null
    : (getUrlErrorMessage(urlError) || googleError || error);

  const handleGoogleClick = async () => {
    setGoogleBusy(true);
    setGoogleError(null);
    try {
      const cfg = await GoogleAuth.getConfig();
      const google = (window as unknown as {
        google?: {
          accounts?: {
            id?: {
              initialize: (options: Record<string, unknown>) => void;
              prompt: (notification?: (event: unknown) => void) => void;
            };
          };
        };
      }).google;

      if (cfg.enabled && cfg.client_id && google?.accounts?.id) {
        google.accounts.id.initialize({
          client_id: cfg.client_id,
          callback: async (resp: { credential?: string }) => {
            if (resp.credential) {
              try {
                const user = await loginWithGoogle(resp.credential);
                navigate(landingFor(user));
              } catch (err) {
                setGoogleError(err instanceof Error ? err.message : 'Google orqali kirishda xatolik yuz berdi.');
                setGoogleBusy(false);
              }
            }
          },
          auto_select: false,
          cancel_on_tap_outside: true,
        });

        google.accounts.id.prompt((notification: unknown) => {
          const notif = notification as { isNotDisplayed?: () => boolean; isSkippedMoment?: () => boolean };
          if (notif?.isNotDisplayed?.() || notif?.isSkippedMoment?.()) {
            window.location.href = GoogleAuth.startUrl;
          }
        });
        return;
      }
    } catch {
      /* fallback to standard redirect */
    }
    window.location.href = GoogleAuth.startUrl;
  };

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

  const adoptTelegramLogin = (tokens: { access: string; refresh: string }, user: Record<string, unknown>) => {
    stopPolling();
    setTgPhase('done');
    const adopted = loginWithTelegram(tokens, user);
    navigate(landingFor(adopted));
  };

  useEffect(() => {
    // 1-Click Auto-login if inside Telegram Mini App (TMA)
    const tg = (window as unknown as { Telegram?: { WebApp?: { initData?: string; initDataUnsafe?: { user?: { language_code?: string } }; ready?: () => void; expand?: () => void } } })?.Telegram;
    const tgWebApp = tg?.WebApp;
    if (tgWebApp) {
      const tgLang = tgWebApp.initDataUnsafe?.user?.language_code?.toLowerCase();
      if (tgLang) {
        const detected = tgLang.startsWith('ru') ? 'ru' : tgLang.startsWith('en') ? 'en' : 'uz';
        setLang(detected);
      }
      if (tgWebApp.initData) {
      try {
        tgWebApp.ready?.();
        tgWebApp.expand?.();
      } catch {
        /* ignore */
      }
      setTgBusy(true);
      TelegramAuth.loginWithInitData(tgWebApp.initData)
        .then((res) => {
          adoptTelegramLogin(res.tokens, res.user);
        })
        .catch(() => {
          setTgBusy(false);
        });
      }
    }

    return stopPolling;
  }, []);



  const pollStatus = async (token: string) => {
    try {
      const st = await TelegramAuth.status(token);
      if (st.status === 'verified') {
        stopPolling();
        setTgBusy(true);
        try {
          const res = await TelegramAuth.loginWithToken(token);
          adoptTelegramLogin(res.tokens, res.user);
          return;
        } catch {
          // If automatic token login fails, fallback to code input
          setTgPhase('code');
          setTgError(null);
        } finally {
          setTgBusy(false);
        }
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
        <img src="/logo-mark.png" alt="GRANDEC" className="auth-logo" />
        <h1>{t('login')}</h1>
        <p className="muted">{t('login_subtitle')}</p>

        {/* Auth Role Tabs: Student (1-Click Passwordless) vs Staff/Admin (Email & Password) */}
        <div
          role="tablist"
          style={{
            display: 'flex',
            background: 'rgba(255, 255, 255, 0.05)',
            borderRadius: 12,
            padding: 4,
            marginTop: 16,
            marginBottom: 20,
            border: '1px solid rgba(255, 255, 255, 0.1)',
            gap: 4,
          }}
        >
          <button
            type="button"
            role="tab"
            aria-selected={authTab === 'student'}
            onClick={() => setAuthTab('student')}
            style={{
              flex: 1,
              padding: '10px 12px',
              borderRadius: 8,
              border: 'none',
              background: authTab === 'student' ? '#0284c7' : 'transparent',
              color: authTab === 'student' ? '#ffffff' : 'var(--muted)',
              fontWeight: 700,
              fontSize: 13,
              cursor: 'pointer',
              transition: 'all 0.2s ease',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 6,
            }}
          >
            ⚡ O‘quvchilar (Telegram 1-klik)
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={authTab === 'staff'}
            onClick={() => setAuthTab('staff')}
            style={{
              flex: 1,
              padding: '10px 12px',
              borderRadius: 8,
              border: 'none',
              background: authTab === 'staff' ? 'rgba(255, 255, 255, 0.15)' : 'transparent',
              color: authTab === 'staff' ? '#ffffff' : 'var(--muted)',
              fontWeight: 700,
              fontSize: 13,
              cursor: 'pointer',
              transition: 'all 0.2s ease',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 6,
            }}
          >
            🔑 O‘qituvchilar va Admin
          </button>
        </div>

        {authTab === 'student' ? (
          <div>
            <div
              style={{
                background: 'rgba(34, 158, 217, 0.08)',
                border: '1px solid rgba(34, 158, 217, 0.25)',
                borderRadius: 12,
                padding: '12px 14px',
                marginBottom: 18,
                textAlign: 'center',
              }}
            >
              <div style={{ fontSize: 13, fontWeight: 600, color: '#38bdf8', marginBottom: 4 }}>
                ⚡ Parol eslab qolish shart emas!
              </div>
              <div style={{ fontSize: 12, color: 'var(--muted)', lineHeight: 1.4 }}>
                Telegram hisobingiz orqali bir marta bosishda xavfsiz kiring.
              </div>
            </div>

            {/* Hero CTA: Telegram 1-click */}
            {tgPhase === 'idle' && (
              <button
                type="button"
                className="btn"
                disabled={tgBusy}
                onClick={() => void startTelegramAuth()}
                style={{
                  width: '100%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 10,
                  background: 'linear-gradient(135deg, #229ED9 0%, #0284c7 100%)',
                  border: 'none',
                  color: '#ffffff',
                  fontWeight: 800,
                  fontSize: 15,
                  padding: '14px 18px',
                  borderRadius: 12,
                  boxShadow: '0 4px 16px rgba(34, 158, 217, 0.35)',
                  cursor: tgBusy ? 'wait' : 'pointer',
                  transition: 'transform 0.15s, box-shadow 0.15s',
                  marginBottom: 12,
                }}
              >
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
                  <path
                    d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69.01-.03.01-.14-.07-.19-.08-.05-.19-.02-.27 0-.12.03-1.99 1.27-5.61 3.72-.53.36-1.01.54-1.44.53-.47-.01-1.38-.27-2.06-.49-.83-.27-1.49-.42-1.43-.88.03-.24.38-.49 1.03-.75 4.04-1.76 6.74-2.92 8.09-3.51 3.85-1.65 4.65-1.94 5.17-1.95.12 0 .37.03.54.17.14.12.18.28.2.45-.02.07-.02.19-.04.28z"
                    fill="#ffffff"
                  />
                </svg>
                {tgBusy ? 'Telegram ochilmoqda...' : '📱 Telegram orqali 1-klikda kirish'}
              </button>
            )}

            {/* Telegram Interactive Verification State */}
            {tgPhase === 'waiting' && (
              <div
                style={{
                  marginBottom: 14,
                  padding: 16,
                  borderRadius: 14,
                  background: 'rgba(56, 189, 248, 0.08)',
                  border: '1px solid rgba(56, 189, 248, 0.25)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
                  <span style={{ fontSize: 20 }}>⚡️</span>
                  <strong style={{ fontSize: 14, color: '#38bdf8' }}>
                    {t('telegram_1click_authenticating')}
                  </strong>
                </div>
                <p className="muted small" style={{ margin: '0 0 12px', lineHeight: 1.5 }}>
                  {t('telegram_1click_hint')}
                </p>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  {tgDeepLink && (
                    <a
                      className="btn"
                      href={tgDeepLink}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{
                        textDecoration: 'none',
                        background: 'rgba(56, 189, 248, 0.15)',
                        color: '#38bdf8',
                        border: '1px solid rgba(56, 189, 248, 0.3)',
                        fontWeight: 700,
                        padding: '8px 14px',
                      }}
                    >
                      {t('telegram_open_btn')}
                    </a>
                  )}
                  <button
                    type="button"
                    className="btn primary sm"
                    disabled={tgBusy}
                    onClick={() => void confirmTelegramDone()}
                  >
                    {tgBusy ? '…' : t('submit')}
                  </button>
                  <button type="button" className="btn sm" onClick={cancelTelegramAuth}>
                    ✕
                  </button>
                </div>
                <div style={{ marginTop: 12, paddingTop: 10, borderTop: '1px dashed rgba(255, 255, 255, 0.1)' }}>
                  <button
                    type="button"
                    onClick={() => setTgPhase('code')}
                    style={{
                      background: 'none',
                      border: 'none',
                      color: 'var(--muted)',
                      fontSize: 12,
                      cursor: 'pointer',
                      textDecoration: 'underline',
                      padding: 0,
                    }}
                  >
                    {t('telegram_manual_code_fallback')}
                  </button>
                </div>
              </div>
            )}

            {/* Telegram 6-digit Code State */}
            {tgPhase === 'code' && (
              <form onSubmit={(e) => void submitTelegramCode(e)} className="form" style={{ marginBottom: 14 }}>
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

            {/* Secondary CTA: Google Auth (Only shown if VITE_GOOGLE_CLIENT_ID is configured) */}
            {hasGoogle && (
              <button
                type="button"
                onClick={handleGoogleClick}
                disabled={googleBusy}
                className="btn"
                style={{
                  width: '100%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 10,
                  background: 'rgba(255, 255, 255, 0.05)',
                  border: '1px solid rgba(255, 255, 255, 0.15)',
                  color: '#f8fafc',
                  fontWeight: 700,
                  padding: '12px 16px',
                  borderRadius: 12,
                  cursor: googleBusy ? 'wait' : 'pointer',
                  opacity: googleBusy ? 0.7 : 1,
                }}
              >
                <svg width="18" height="18" viewBox="0 0 24 24">
                  <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                  <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                  <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z" />
                  <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z" />
                </svg>
                {googleBusy ? 'Google hisobiga ulanmoqda...' : '🌐 Google orqali kirish'}
              </button>
            )}

            {tgError && <p className="error" style={{ marginTop: 12 }}>{tgError}</p>}
            {activeError && activeError !== 'google_not_configured' && !activeError.includes('google_not_configured') && (
              <p className="error" style={{ marginTop: 12 }}>{activeError}</p>
            )}
          </div>
        ) : (
          <div>
            <p className="muted small" style={{ marginBottom: 16 }}>
              Ustozlar va adminlar uchun xizmat pochtasi hamda maxfiy parol orqali kirish.
            </p>
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
              {activeError && <p className="error">{activeError}</p>}
              <button className="btn primary btn-glow" disabled={busy} style={{ width: '100%', marginTop: 8 }}>
                {busy ? '…' : t('login')}
              </button>
            </form>
            <p className="muted" style={{ marginTop: 16, textAlign: 'center' }}>
              <Link to="/password-reset">{t('forgot_password')}</Link>
            </p>
          </div>
        )}

        <p className="muted" style={{ marginTop: 24, textAlign: 'center' }}>
          <Link to="/register">{t('register')}</Link>
        </p>

      </div>
    </div>
  );
}
