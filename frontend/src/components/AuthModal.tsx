import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { GoogleAuth, TelegramAuth, landingFor } from '../lib/api';
import confetti from 'canvas-confetti';
import {
  LockIcon,
  MailIcon,
  SendIcon,
  UserIcon,
  XIcon,
} from './icons';

type TgPhase = 'idle' | 'waiting' | 'code' | 'done';

export default function AuthModal() {
  const {
    isAuthModalOpen,
    authModalMode,
    closeAuthModal,
    login,
    register,
    loginWithTelegram,
    loginWithGoogle,
  } = useAuth();
  const navigate = useNavigate();

  // Mode: 'login' | 'register'
  const [mode, setMode] = useState<'login' | 'register'>(authModalMode);
  const [showEmailForm, setShowEmailForm] = useState(false);

  // Email form state
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [passwordConfirm, setPasswordConfirm] = useState('');
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const role = 'student';
  const [busy, setBusy] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Google 1-click state
  const [googleBusy, setGoogleBusy] = useState(false);
  const hasGoogle = Boolean(import.meta.env.VITE_GOOGLE_CLIENT_ID && import.meta.env.VITE_GOOGLE_CLIENT_ID.trim() !== "");

  // Telegram auth state
  const [tgPhase, setTgPhase] = useState<TgPhase>('idle');
  const [, setTgToken] = useState<string | null>(null);
  const [tgCode, setTgCode] = useState('');
  const [tgBusy, setTgBusy] = useState(false);
  const [tgError, setTgError] = useState<string | null>(null);
  const pollRef = useRef<number | null>(null);

  const [prevModeProp, setPrevModeProp] = useState(authModalMode);
  if (prevModeProp !== authModalMode) {
    setPrevModeProp(authModalMode);
    setMode(authModalMode);
    setErrorMsg(null);
  }

  const stopPolling = () => {
    if (pollRef.current !== null) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
  };

  useEffect(() => {
    return () => stopPolling();
  }, []);

  // Keyboard Escape listener
  useEffect(() => {
    if (!isAuthModalOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        stopPolling();
        closeAuthModal();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isAuthModalOpen, closeAuthModal]);

  if (!isAuthModalOpen) return null;

  const triggerSuccessCelebration = () => {
    try {
      confetti({
        particleCount: 50,
        spread: 60,
        origin: { y: 0.7 },
        colors: ['#F59E0B', '#10B981', '#38BDF8'],
      });
    } catch {
      /* ignore */
    }
  };

  // Google 1-Click OAuth Trigger
  const handleGoogleClick = async () => {
    setGoogleBusy(true);
    setErrorMsg(null);
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
                triggerSuccessCelebration();
                closeAuthModal();
                navigate(landingFor(user));
              } catch (err) {
                setErrorMsg(err instanceof Error ? err.message : 'Google orqali kirishda xatolik yuz berdi.');
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
      /* fallback to standard OAuth redirect */
    }
    window.location.href = GoogleAuth.startUrl;
  };

  // Telegram 1-Click Auth Trigger
  const startTelegramAuth = async () => {
    stopPolling();
    setTgError(null);
    setTgBusy(true);

    const telegramWindow = window.open('', '_blank');
    try {
      const data = await TelegramAuth.start();
      if (!data.deep_link || !data.deep_link.startsWith('https://t.me/')) {
        throw new Error('Noto‘g‘ri havola qaytdi');
      }
      setTgToken(data.token);
      setTgPhase('waiting');

      if (telegramWindow && !telegramWindow.closed) {
        telegramWindow.opener = null;
        telegramWindow.location.href = data.deep_link;
        telegramWindow.focus();
      }

      pollRef.current = window.setInterval(async () => {
        try {
          const st = await TelegramAuth.status(data.token);
          if (st.status === 'verified') {
            stopPolling();
            // Automatically finalize login
            const loginData = await TelegramAuth.loginWithToken(data.token);
            triggerSuccessCelebration();
            const adopted = loginWithTelegram(loginData.tokens, loginData.user);
            closeAuthModal();
            navigate(landingFor(adopted));
          } else if (st.status !== 'pending') {
            stopPolling();
            setTgPhase('idle');
            setTgToken(null);
            setTgError(st.error || 'Telegram orqali tasdiqlash bekor qilindi.');
          }
        } catch {
          /* keep polling on transient errors */
        }
      }, 1500);
    } catch (err) {
      if (telegramWindow && !telegramWindow.closed) telegramWindow.close();
      setTgPhase('idle');
      setTgToken(null);
      setTgError(err instanceof Error ? err.message : 'Telegram orqali ulanishda xatolik yuz berdi.');
    } finally {
      setTgBusy(false);
    }
  };

  // Submit 6-digit Telegram Code
  const submitTelegramCode = async (e: FormEvent) => {
    e.preventDefault();
    if (!/^\d{6}$/.test(tgCode.trim())) {
      setTgError('Iltimos, 6 xonali raqamli kodni kiriting.');
      return;
    }
    setTgBusy(true);
    setTgError(null);
    try {
      const data = await TelegramAuth.loginWithCode(tgCode.trim());
      triggerSuccessCelebration();
      const adopted = loginWithTelegram(data.tokens, data.user);
      closeAuthModal();
      navigate(landingFor(adopted));
    } catch (err) {
      setTgError(err instanceof Error ? err.message : 'Kiritilgan kod xato yoki muddati tugagan.');
    } finally {
      setTgBusy(false);
    }
  };

  // Submit Traditional Email & Password
  const handleEmailSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);
    setBusy(true);

    try {
      if (mode === 'login') {
        const u = await login(email, password);
        triggerSuccessCelebration();
        closeAuthModal();
        navigate(landingFor(u));
      } else {
        if (password !== passwordConfirm) {
          setErrorMsg('Kiritilgan parollar bir-biriga mos kelmadi.');
          setBusy(false);
          return;
        }
        const u = await register({
          email,
          password,
          password_confirm: passwordConfirm,
          first_name: firstName,
          last_name: lastName,
          role,
        });
        triggerSuccessCelebration();
        closeAuthModal();
        navigate(landingFor(u));
      }
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Xatolik yuz berdi. Qayta urinib ko‘ring.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Tezkor autentifikatsiya"
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 100,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '16px',
        background: 'rgba(3, 7, 18, 0.75)',
        backdropFilter: 'blur(16px)',
        WebkitBackdropFilter: 'blur(16px)',
        animation: 'authFadeIn 0.2s ease-out',
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) {
          stopPolling();
          closeAuthModal();
        }
      }}
    >
      <style>{`
        @keyframes authFadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }
        @keyframes authSlideUp {
          from { opacity: 0; transform: scale(0.96) translateY(12px); }
          to { opacity: 1; transform: scale(1) translateY(0); }
        }
        @keyframes pulseGlow {
          0%, 100% { opacity: 0.8; transform: scale(1); }
          50% { opacity: 1; transform: scale(1.02); }
        }
        .auth-1click-btn {
          position: relative;
          display: flex;
          align-items: center;
          justify-content: space-between;
          width: 100%;
          padding: 14px 18px;
          border-radius: 14px;
          font-size: 14px;
          font-weight: 700;
          cursor: pointer;
          transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
          text-decoration: none;
          box-sizing: border-box;
        }
        .auth-1click-btn:hover:not(:disabled) {
          transform: translateY(-2px);
          box-shadow: 0 10px 24px -6px rgba(0, 0, 0, 0.5);
        }
        .auth-input-group {
          position: relative;
          display: flex;
          align-items: center;
        }
        .auth-input-group input {
          width: 100%;
          background: var(--card-2);
          border: 1px solid var(--border);
          border-radius: 12px;
          padding: 12px 14px 12px 40px;
          color: var(--ink);
          font-size: 14px;
          transition: all 0.2s ease;
        }
        .auth-input-group input:focus {
          border-color: #F59E0B;
          box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.15);
          outline: none;
        }
        .auth-input-icon {
          position: absolute;
          left: 14px;
          color: var(--muted);
          pointer-events: none;
        }
      `}</style>

      <div
        style={{
          position: 'relative',
          width: '100%',
          maxWidth: 440,
          background: 'var(--card)',
          border: '1px solid var(--border)',
          boxShadow: '0 25px 60px -15px rgba(0, 0, 0, 0.5)',
          borderRadius: 24,
          padding: '28px 24px',
          overflow: 'hidden',
          animation: 'authSlideUp 0.25s cubic-bezier(0.16, 1, 0.3, 1)',
        }}
      >
        {/* Ambient Top Glow */}
        <div
          style={{
            position: 'absolute',
            top: -60,
            left: '50%',
            transform: 'translateX(-50%)',
            width: 240,
            height: 120,
            background: 'radial-gradient(circle, rgba(245, 158, 11, 0.18) 0%, rgba(16, 185, 129, 0.12) 50%, transparent 80%)',
            filter: 'blur(35px)',
            pointerEvents: 'none',
          }}
        />

        {/* Close Button */}
        <button
          type="button"
          aria-label="Yopish"
          onClick={() => {
            stopPolling();
            closeAuthModal();
          }}
          style={{
            position: 'absolute',
            top: 18,
            right: 18,
            width: 32,
            height: 32,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            borderRadius: 10,
            border: '1px solid var(--border)',
            background: 'var(--card-2)',
            color: 'var(--muted)',
            cursor: 'pointer',
            transition: 'all 0.2s ease',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.color = 'var(--ink)';
            e.currentTarget.style.background = 'var(--dropdown-hover)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.color = 'var(--muted)';
            e.currentTarget.style.background = 'var(--card-2)';
          }}
        >
          <XIcon size={18} />
        </button>

        {/* Header & Logo */}
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: 52,
              height: 52,
              borderRadius: 16,
              background: 'rgba(245, 158, 11, 0.12)',
              border: '1px solid rgba(245, 158, 11, 0.25)',
              boxShadow: '0 0 20px rgba(245, 158, 11, 0.15)',
              marginBottom: 12,
            }}
          >
            <img
              src="/logo-mark.png"
              alt="GRANDEC"
              style={{ width: 40, height: 40, objectFit: 'contain' }}
            />
          </div>

          <h2 style={{ fontSize: 20, fontWeight: 900, color: 'var(--ink)', margin: '0 0 6px' }}>
            {mode === 'login' ? 'Tizimga 1-klikda kiring' : '1-klikda hisob yarating'}
          </h2>
          <p style={{ fontSize: 13, color: 'var(--muted)', margin: 0, lineHeight: 1.5 }}>
            Ona tili va adabiyotidan Milliy sertifikatga tayyorlovchi LMS platformasi
          </p>
        </div>

        {/* Error Alert Box */}
        {((errorMsg && !errorMsg.includes('Google') && !errorMsg.includes('google_not_configured') && errorMsg !== 'google_not_configured') || tgError) && (
          <div
            style={{
              padding: '10px 14px',
              borderRadius: 12,
              fontSize: 12,
              fontWeight: 600,
              color: '#f87171',
              background: 'rgba(239, 68, 68, 0.1)',
              border: '1px solid rgba(239, 68, 68, 0.25)',
              marginBottom: 16,
            }}
          >
            {tgError || errorMsg}
          </div>
        )}

        {/* 1-CLICK AUTH PROVIDERS SECTION */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginBottom: 20 }}>
          {/* PRIMARY: TELEGRAM 1-CLICK BUTTON */}
          {tgPhase === 'idle' && (
            <button
              type="button"
              className="auth-1click-btn"
              onClick={startTelegramAuth}
              disabled={tgBusy}
              style={{
                background: 'linear-gradient(135deg, #229ED9 0%, #0284c7 100%)',
                border: 'none',
                color: '#ffffff',
                boxShadow: '0 4px 16px rgba(34, 158, 217, 0.35)',
                cursor: tgBusy ? 'wait' : 'pointer',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <div
                  style={{
                    width: 34,
                    height: 34,
                    borderRadius: 10,
                    background: 'rgba(255, 255, 255, 0.2)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: '#ffffff',
                    flexShrink: 0,
                  }}
                >
                  <SendIcon size={18} />
                </div>
                <div style={{ textAlign: 'left' }}>
                  <span style={{ display: 'block', fontSize: 15, fontWeight: 800, color: '#ffffff' }}>
                    {tgBusy ? 'Telegram ochilmoqda...' : '📱 Telegram orqali 1-klikda kirish'}
                  </span>
                  <span style={{ display: 'block', fontSize: 11, fontWeight: 500, color: 'rgba(255, 255, 255, 0.85)' }}>
                    Parolsiz 1 soniyada xavfsiz tasdiqlash
                  </span>
                </div>
              </div>
              <span
                style={{
                  fontSize: 10,
                  fontWeight: 800,
                  padding: '3px 8px',
                  borderRadius: 999,
                  background: 'rgba(255, 255, 255, 0.25)',
                  color: '#ffffff',
                }}
              >
                1-klik
              </span>
            </button>
          )}

          {/* SECONDARY: GOOGLE BUTTON (Only shown if VITE_GOOGLE_CLIENT_ID is configured) */}
          {hasGoogle && (
            <button
              type="button"
              className="auth-1click-btn"
              onClick={handleGoogleClick}
              disabled={googleBusy}
              style={{
                background: 'var(--card-2)',
                border: '1px solid var(--border)',
                color: 'var(--ink)',
                opacity: googleBusy ? 0.7 : 1,
                cursor: googleBusy ? 'wait' : 'pointer',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                {/* Google Official 4-Color SVG Icon */}
                <svg width="22" height="22" viewBox="0 0 24 24">
                  <path
                    fill="#4285F4"
                    d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                  />
                  <path
                    fill="#34A853"
                    d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                  />
                  <path
                    fill="#FBBC05"
                    d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
                  />
                  <path
                    fill="#EA4335"
                    d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
                  />
                </svg>
                <div style={{ textAlign: 'left' }}>
                  <span style={{ display: 'block', fontSize: 14, fontWeight: 700 }}>
                    {googleBusy ? 'Google hisobiga ulanmoqda...' : 'Google orqali davom etish'}
                  </span>
                  <span style={{ display: 'block', fontSize: 11, fontWeight: 500, color: 'var(--muted)' }}>
                    {googleBusy ? 'Iltimos, kuting...' : '1 soniyada xavfsiz kirish'}
                  </span>
                </div>
              </div>
              <span
                style={{
                  fontSize: 10,
                  fontWeight: 800,
                  padding: '3px 8px',
                  borderRadius: 999,
                  background: 'rgba(66, 133, 244, 0.15)',
                  color: '#60a5fa',
                  border: '1px solid rgba(66, 133, 244, 0.3)',
                }}
              >
                1-klik
              </span>
            </button>
          )}

          {/* Telegram Waiting Status */}
          {tgPhase === 'waiting' && (
            <div
              style={{
                padding: '16px',
                borderRadius: 14,
                background: 'rgba(42, 171, 238, 0.08)',
                border: '1px solid rgba(42, 171, 238, 0.3)',
                textAlign: 'center',
              }}
            >
              <div
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 8,
                  fontSize: 13,
                  fontWeight: 700,
                  color: '#38bdf8',
                  marginBottom: 8,
                }}
              >
                <span
                  style={{
                    width: 8,
                    height: 8,
                    borderRadius: 999,
                    background: '#38bdf8',
                    boxShadow: '0 0 10px #38bdf8',
                    animation: 'pulseGlow 1.5s infinite',
                  }}
                />
                Telegram boti ochildi...
              </div>
              <p style={{ fontSize: 12, color: '#94a3b8', margin: '0 0 12px', lineHeight: 1.5 }}>
                Telegram botda <b>&quot;Boshlash / Start&quot;</b> tugmasini bosing. Tizim avtomatik kiritadi.
              </p>
              <div style={{ display: 'flex', justifyContent: 'center', gap: 10 }}>
                <button
                  type="button"
                  onClick={() => setTgPhase('code')}
                  style={{
                    fontSize: 12,
                    fontWeight: 600,
                    color: '#F59E0B',
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    textDecoration: 'underline',
                  }}
                >
                  Kodni qo‘lda kiritish
                </button>
                <span style={{ color: '#475569' }}>·</span>
                <button
                  type="button"
                  onClick={() => {
                    stopPolling();
                    setTgPhase('idle');
                  }}
                  style={{
                    fontSize: 12,
                    color: '#94a3b8',
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                  }}
                >
                  Bekor qilish
                </button>
              </div>
            </div>
          )}

          {/* Telegram Code Input Mode */}
          {tgPhase === 'code' && (
            <form
              onSubmit={submitTelegramCode}
              style={{
                padding: '16px',
                borderRadius: 14,
                background: 'rgba(42, 171, 238, 0.08)',
                border: '1px solid rgba(42, 171, 238, 0.3)',
              }}
            >
              <p style={{ fontSize: 12, fontWeight: 600, color: 'var(--ink)', margin: '0 0 10px' }}>
                Telegram bot bergan 6 xonali tasdiqlash kodini kiriting:
              </p>
              <div style={{ display: 'flex', gap: 8 }}>
                <input
                  type="text"
                  maxLength={6}
                  placeholder="123456"
                  value={tgCode}
                  onChange={(e) => setTgCode(e.target.value)}
                  style={{
                    flex: 1,
                    background: 'var(--card-2)',
                    border: '1px solid var(--border)',
                    borderRadius: 10,
                    padding: '10px 14px',
                    fontSize: 16,
                    fontWeight: 800,
                    letterSpacing: '0.2em',
                    textAlign: 'center',
                    color: 'var(--ink)',
                  }}
                />
                <button
                  type="submit"
                  disabled={tgBusy || tgCode.trim().length !== 6}
                  style={{
                    padding: '10px 18px',
                    borderRadius: 10,
                    background: 'linear-gradient(135deg, #F59E0B, #FBBF24)',
                    color: '#090d16',
                    fontWeight: 800,
                    fontSize: 13,
                    border: 'none',
                    cursor: 'pointer',
                  }}
                >
                  {tgBusy ? '...' : 'Tasdiqlash'}
                </button>
              </div>
              <button
                type="button"
                onClick={() => setTgPhase('idle')}
                style={{
                  marginTop: 10,
                  fontSize: 11,
                  color: '#94a3b8',
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                }}
              >
                ← Orqaga
              </button>
            </form>
          )}
        </div>

        {/* OR DIVIDER */}
        <div
          style={{
            position: 'relative',
            textAlign: 'center',
            margin: '18px 0',
          }}
        >
          <div
            style={{
              position: 'absolute',
              top: '50%',
              left: 0,
              right: 0,
              height: 1,
              background: 'rgba(148, 163, 184, 0.12)',
            }}
          />
          <button
            type="button"
            onClick={() => setShowEmailForm((v) => !v)}
            style={{
              position: 'relative',
              background: 'var(--card)',
              border: '1px solid var(--border)',
              borderRadius: 999,
              padding: '4px 14px',
              fontSize: 11,
              fontWeight: 600,
              color: '#94a3b8',
              cursor: 'pointer',
              transition: 'all 0.2s ease',
            }}
          >
            {showEmailForm ? '▲ Email shaklini yashirish' : '▼ yoki email bilan kirish'}
          </button>
        </div>

        {/* COLLAPSIBLE EMAIL FORM */}
        {showEmailForm && (
          <form onSubmit={handleEmailSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {mode === 'register' && (
              <>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                  <div className="auth-input-group">
                    <UserIcon size={16} className="auth-input-icon" />
                    <input
                      type="text"
                      required
                      placeholder="Ism"
                      value={firstName}
                      onChange={(e) => setFirstName(e.target.value)}
                    />
                  </div>
                  <div className="auth-input-group">
                    <UserIcon size={16} className="auth-input-icon" />
                    <input
                      type="text"
                      required
                      placeholder="Familiya"
                      value={lastName}
                      onChange={(e) => setLastName(e.target.value)}
                    />
                  </div>
                </div>
              </>
            )}

            <div className="auth-input-group">
              <MailIcon size={16} className="auth-input-icon" />
              <input
                type="email"
                required
                placeholder="Email manzilingiz"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </div>

            <div className="auth-input-group">
              <LockIcon size={16} className="auth-input-icon" />
              <input
                type="password"
                required
                placeholder="Parol"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>

            {mode === 'register' && (
              <div className="auth-input-group">
                <LockIcon size={16} className="auth-input-icon" />
                <input
                  type="password"
                  required
                  placeholder="Parolni tasdiqlang"
                  value={passwordConfirm}
                  onChange={(e) => setPasswordConfirm(e.target.value)}
                />
              </div>
            )}

            <button
              type="submit"
              disabled={busy}
              style={{
                width: '100%',
                padding: '12px 18px',
                borderRadius: 12,
                background: 'linear-gradient(135deg, #F59E0B, #FBBF24)',
                border: 'none',
                color: '#090d16',
                fontSize: 14,
                fontWeight: 800,
                cursor: 'pointer',
                boxShadow: '0 4px 18px rgba(245, 158, 11, 0.35)',
                marginTop: 4,
              }}
            >
              {busy ? 'Tekshirilmoqda...' : mode === 'login' ? 'Tizimga kirish' : 'Ro‘yxatdan o‘tish'}
            </button>
          </form>
        )}

        {/* Footer Switcher */}
        <div
          style={{
            marginTop: 20,
            paddingTop: 16,
            borderTop: '1px solid rgba(148, 163, 184, 0.1)',
            textAlign: 'center',
            fontSize: 12,
            color: '#94a3b8',
          }}
        >
          {mode === 'login' ? (
            <>
              Yangi o‘quvchimisiz?{' '}
              <button
                type="button"
                onClick={() => {
                  setMode('register');
                  setErrorMsg(null);
                }}
                style={{
                  background: 'none',
                  border: 'none',
                  color: '#F59E0B',
                  fontWeight: 700,
                  cursor: 'pointer',
                }}
              >
                Ro‘yxatdan o‘ting
              </button>
            </>
          ) : (
            <>
              Hisobingiz bormi?{' '}
              <button
                type="button"
                onClick={() => {
                  setMode('login');
                  setErrorMsg(null);
                }}
                style={{
                  background: 'none',
                  border: 'none',
                  color: '#F59E0B',
                  fontWeight: 700,
                  cursor: 'pointer',
                }}
              >
                Tizimga kiring
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
