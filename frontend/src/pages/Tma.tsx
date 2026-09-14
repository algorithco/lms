import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { useLang } from '../i18n/LangContext';

/** Bot username fallback for the "open in Telegram" link (mirrors settings.TELEGRAM_BOT_NAME default). */
const BOT_USERNAME = 'uz_essaygrader_bot';

interface TelegramThemeParams {
  bg_color?: string;
  text_color?: string;
  button_color?: string;
  button_text_color?: string;
}

interface TelegramWebApp {
  initData: string;
  colorScheme: 'light' | 'dark';
  themeParams: TelegramThemeParams;
  ready: () => void;
  expand: () => void;
  setHeaderColor: (color: string) => void;
  setBackgroundColor: (color: string) => void;
}

declare global {
  interface Window {
    Telegram?: { WebApp?: TelegramWebApp };
  }
}

type TmaPhase = 'boot' | 'outside' | 'authing' | 'hub' | 'error';

interface TmaAuthResponse {
  success: boolean;
  user?: Record<string, unknown>;
  tokens?: { access: string; refresh: string };
  error?: string;
}

function loadTelegramScript(): Promise<void> {
  if (window.Telegram?.WebApp) return Promise.resolve();
  return new Promise((resolve) => {
    const s = document.createElement('script');
    s.src = 'https://telegram.org/js/telegram-web-app.js';
    s.async = true;
    s.onload = () => resolve();
    s.onerror = () => resolve();
    document.head.appendChild(s);
  });
}

/**
 * Telegram Mini App shell (route /tma, public).
 * Replaces the old server-rendered tma/index.html: Telegram initData is
 * exchanged at POST /tma/api/auth/ for a JWT pair (auto-register on first
 * open), then the hub links into the regular SPA pages.
 */
export default function Tma() {
  const { user, loginWithTelegram } = useAuth();
  const { t } = useLang();
  const [phase, setPhase] = useState<TmaPhase>('boot');
  const [error, setError] = useState<string | null>(null);
  const [displayName, setDisplayName] = useState('');

  useEffect(() => {
    let cancelled = false;
    (async () => {
      await loadTelegramScript();
      if (cancelled) return;
      const wa = window.Telegram?.WebApp;
      const initData = wa?.initData ?? '';
      if (!wa || !initData) {
        // Opened in a normal browser: reuse an existing SPA session if any,
        // otherwise point at the bot / email login.
        setPhase(user ? 'hub' : 'outside');
        if (user) setDisplayName(user.full_name);
        return;
      }
      try {
        wa.ready();
        wa.expand();
        try {
          wa.setHeaderColor('#1a1a2e');
          wa.setBackgroundColor('#1a1a2e');
        } catch {
          /* older clients — ignore */
        }
      } catch {
        /* non-critical */
      }
      setPhase('authing');
      try {
        const res = await fetch('/tma/api/auth/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ init_data: initData }),
        });
        const data = (await res.json()) as TmaAuthResponse;
        if (!res.ok || !data.success || !data.tokens || !data.user) {
          throw new Error(data.error || 'Telegram auth failed');
        }
        if (cancelled) return;
        loginWithTelegram(data.tokens, data.user);
        const rawName = data.user.full_name;
        setDisplayName(typeof rawName === 'string' ? rawName : '');
        setPhase('hub');
      } catch (e) {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : 'Telegram auth failed');
        setPhase('error');
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const name = displayName || user?.full_name || '';

  return (
    <div className="auth-wrap">
      <div className="auth-card">
        <img src="/grandec.png" alt="GRANDEC" className="auth-logo" />
        {phase === 'boot' || phase === 'authing' ? (
          <p className="muted">…</p>
        ) : phase === 'outside' ? (
          <div>
            <h1>{t('login')}</h1>
            <p className="muted">{t('telegram_login_step1')}</p>
            <a
              className="btn primary"
              href={`https://t.me/${BOT_USERNAME}`}
              target="_blank"
              rel="noreferrer"
              style={{ display: 'block', textAlign: 'center', textDecoration: 'none' }}
            >
              Telegram bot
            </a>
            <p className="muted" style={{ marginTop: 12 }}>
              <Link to="/login">{t('login_with_telegram')}</Link>
            </p>
          </div>
        ) : phase === 'error' ? (
          <div>
            <h1>{t('login')}</h1>
            <p className="error">{error}</p>
            <button className="btn" onClick={() => window.location.reload()}>
              {t('submit')}
            </button>
          </div>
        ) : (
          <div>
            <h1>{name ? `${name}` : t('dashboard')}</h1>
            <div style={{ display: 'grid', gap: 10, marginTop: 16 }}>
              <Link className="btn primary" to="/tests" style={{ textAlign: 'center', textDecoration: 'none' }}>
                {t('tests')}
              </Link>
              <Link className="btn" to="/arena" style={{ textAlign: 'center', textDecoration: 'none' }}>
                {t('arena')}
              </Link>
              <Link className="btn" to="/essays" style={{ textAlign: 'center', textDecoration: 'none' }}>
                {t('essays')}
              </Link>
              <Link className="btn" to="/results" style={{ textAlign: 'center', textDecoration: 'none' }}>
                {t('my_results')}
              </Link>
              <Link className="btn" to="/dashboard" style={{ textAlign: 'center', textDecoration: 'none' }}>
                {t('dashboard')}
              </Link>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
