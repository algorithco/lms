import { useState } from 'react';
import type { FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { useLang } from '../i18n/LangContext';
import { GoogleAuth, landingFor } from '../lib/api';
import SEO from '../components/SEO';

export default function Register() {
  const { register, loginWithGoogle, error } = useAuth();
  const { t } = useLang();
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [googleBusy, setGoogleBusy] = useState(false);
  const [googleError, setGoogleError] = useState<string | null>(null);
  const hasGoogle = Boolean(import.meta.env.VITE_GOOGLE_CLIENT_ID && import.meta.env.VITE_GOOGLE_CLIENT_ID.trim() !== "");
  const [form, setForm] = useState({
    email: '',
    password: '',
    password_confirm: '',
    first_name: '',
    last_name: '',
    role: 'student' as 'student' | 'teacher',
  });

  const set =
    (k: keyof typeof form) =>
    (e: { target: { value: string } }) =>
      setForm((f) => ({ ...f, [k]: e.target.value }));

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
                setGoogleError(err instanceof Error ? err.message : 'Google orqali ro‘yxatdan o‘tishda xatolik yuz berdi.');
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

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      const user = await register(form);
      navigate(landingFor(user));
    } catch {
      /* error shown from context */
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth-wrap">
      <SEO
        title={t('register_title')}
        description={t('register_subtitle')}
        canonical="/register"
      />
      <div className="auth-card">
        <img src="/grandec.png" alt="GRANDEC" className="auth-logo" />
        <h1>{t('register')}</h1>
        <p className="muted">{t('register_subtitle')}</p>

        <div style={{ margin: '16px 0 20px', display: 'flex', flexDirection: 'column', gap: 10 }}>
          <Link
            to="/login"
            className="btn"
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 10,
              width: '100%',
              background: 'linear-gradient(135deg, #229ED9 0%, #0284c7 100%)',
              border: 'none',
              color: '#ffffff',
              fontWeight: 800,
              fontSize: 14,
              padding: '13px 18px',
              borderRadius: 12,
              textDecoration: 'none',
              boxShadow: '0 4px 16px rgba(34, 158, 217, 0.35)',
            }}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
              <path
                d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm4.64 6.8c-.15 1.58-.8 5.42-1.13 7.19-.14.75-.42 1-.68 1.03-.58.05-1.02-.38-1.58-.75-.88-.58-1.38-.94-2.23-1.5-.99-.65-.35-1.01.22-1.59.15-.15 2.71-2.48 2.76-2.69.01-.03.01-.14-.07-.19-.08-.05-.19-.02-.27 0-.12.03-1.99 1.27-5.61 3.72-.53.36-1.01.54-1.44.53-.47-.01-1.38-.27-2.06-.49-.83-.27-1.49-.42-1.43-.88.03-.24.38-.49 1.03-.75 4.04-1.76 6.74-2.92 8.09-3.51 3.85-1.65 4.65-1.94 5.17-1.95.12 0 .37.03.54.17.14.12.18.28.2.45-.02.07-.02.19-.04.28z"
                fill="#ffffff"
              />
            </svg>
            📱 Telegram orqali 1-klikda kirish / ro‘yxatdan o‘tish
          </Link>

          {hasGoogle && (
            <button
              type="button"
              onClick={handleGoogleClick}
              disabled={googleBusy}
              className="btn"
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 10,
                width: '100%',
                background: 'rgba(255, 255, 255, 0.05)',
                border: '1px solid rgba(255, 255, 255, 0.15)',
                color: '#f8fafc',
                fontWeight: 700,
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
              {googleBusy ? 'Google hisobiga ulanmoqda...' : 'Google orqali 1-klikda ro‘yxatdan o‘tish'}
            </button>
          )}
          {hasGoogle && googleError && <p className="error" style={{ marginTop: 8 }}>{googleError}</p>}
        </div>

        <div style={{ position: 'relative', textAlign: 'center', margin: '14px 0' }}>
          <div style={{ position: 'absolute', top: '50%', left: 0, right: 0, height: 1, background: 'rgba(148, 163, 184, 0.12)' }} />
          <span style={{ position: 'relative', background: 'var(--card)', padding: '0 10px', fontSize: 12, color: 'var(--muted)' }}>
            yoki email orqali
          </span>
        </div>

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
