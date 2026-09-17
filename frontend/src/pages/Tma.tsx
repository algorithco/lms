import { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { useLang } from '../i18n/LangContext';
import { TmaApi } from './tma/api';
import type { TmaProfile } from './tma/api';
import { loadTelegramScript, tg } from './tma/telegram';
import Home from './tma/Home';
import TestFlow from './tma/TestFlow';
import Essays from './tma/Essays';
import './tma/Tma.css';

/** Bot username fallback for the "open in Telegram" link (mirrors settings.TELEGRAM_BOT_NAME default). */
const BOT_USERNAME = 'uz_essaygrader_bot';

type Boot = 'boot' | 'outside' | 'authing' | 'ready' | 'error';
type Tab = 'home' | 'essays';
type TmaAuthResponse = {
  success: boolean;
  user?: Record<string, unknown>;
  tokens?: { access: string; refresh: string };
  error?: string;
};

/**
 * Dedicated Telegram Mini App (routes /tma + /tma/, public).
 * Old tma/index.html parity: dark mini-app shell, bottom tabs, test player,
 * essay writer — all over /tma/api/* JSON. NOT the full website.
 */
export default function Tma() {
  const { user, loginWithTelegram } = useAuth();
  const { t } = useLang();
  const [boot, setBoot] = useState<Boot>('boot');
  const [error, setError] = useState<string | null>(null);
  const [profile, setProfile] = useState<TmaProfile | null>(null);
  const [tab, setTab] = useState<Tab>('home');
  const [activeTestId, setActiveTestId] = useState<number | null>(null);
  const backHandlerRef = useRef<(() => void) | null>(null);
  // React StrictMode intentionally re-runs effects in development. Share the
  // in-flight request so the same Telegram initData is never submitted twice
  // (the backend correctly rejects replayed initData).
  const authRequestRef = useRef<Promise<TmaAuthResponse> | null>(null);

  const setBackHandler = useCallback((fn: (() => void) | null) => {
    backHandlerRef.current = fn;
  }, []);

  // Sync Telegram BackButton with the registered handler (every render).
  useEffect(() => {
    const bb = tg()?.BackButton;
    if (!bb) return;
    const h = backHandlerRef.current;
    if (!h) {
      bb.hide();
      return;
    }
    bb.show();
    bb.onClick(h);
    return () => {
      bb.offClick(h);
      bb.hide();
    };
  });

  useEffect(() => {
    let cancelled = false;
    (async () => {
      await loadTelegramScript();
      if (cancelled) return;
      const wa = tg();
      const initData = wa?.initData ?? '';
      if (!wa || !initData) {
        setBoot(user ? 'ready' : 'outside');
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
      setBoot('authing');
      try {
        if (!authRequestRef.current) {
          authRequestRef.current = fetch('/tma/api/auth/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ init_data: initData }),
          }).then(async (res) => {
            const data = (await res.json()) as TmaAuthResponse;
            if (!res.ok || !data.success || !data.tokens || !data.user) {
              throw new Error(data.error || 'Telegram auth failed');
            }
            return data;
          });
        }
        const data = await authRequestRef.current;
        if (cancelled) return;
        // Keep the validated values local so TypeScript can preserve the
        // narrowing across the shared promise boundary.
        if (!data.tokens || !data.user) throw new Error('Telegram auth failed');
        loginWithTelegram(data.tokens, data.user);
        const prof = await TmaApi.profile();
        if (cancelled) return;
        setProfile(prof);
        setBoot('ready');
      } catch (e) {
        if (cancelled) return;
        setError(e instanceof Error ? e.message : 'Telegram auth failed');
        setBoot('error');
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Refresh header stats when returning to tabs.
  const refreshProfile = useCallback(() => {
    TmaApi.profile().then(setProfile).catch(() => undefined);
  }, []);

  const openTest = (id: number) => {
    backHandlerRef.current = null;
    setActiveTestId(id);
  };

  const exitFlow = () => {
    backHandlerRef.current = null;
    setActiveTestId(null);
    refreshProfile();
  };

  const switchTab = (next: Tab) => {
    backHandlerRef.current = null;
    setActiveTestId(null);
    setTab(next);
    refreshProfile();
  };

  if (boot === 'boot' || boot === 'authing') {
    return (
      <div className="tma-root">
        <div className="tma-auth">
          <div>
            <div className="tma-spin" />
            <p className="tma-muted tma-center">{t('tma_checking')}</p>
          </div>
        </div>
      </div>
    );
  }

  if (boot === 'outside') {
    return (
      <div className="tma-root">
        <div className="tma-auth">
          <div className="tma-auth-card">
            <div className="tma-auth-logo">📚</div>
            <h1 style={{ fontSize: 22, fontWeight: 800, margin: '0 0 8px' }}>Ona Tili &amp; Adabiyot</h1>
            <p className="tma-muted" style={{ marginBottom: 24 }}>{t('tma_open_in_telegram')}</p>
            <a
              className="tma-btn tma-btn-hl"
              href={`https://t.me/${BOT_USERNAME}`}
              target="_blank"
              rel="noreferrer"
              style={{ display: 'block', textDecoration: 'none' }}
            >
              Telegram bot
            </a>
            <p className="tma-muted" style={{ marginTop: 16 }}>
              <Link to="/login" style={{ color: 'var(--tma-hl)' }}>{t('login_with_telegram')}</Link>
            </p>
          </div>
        </div>
      </div>
    );
  }

  if (boot === 'error') {
    return (
      <div className="tma-root">
        <div className="tma-auth">
          <div className="tma-auth-card">
            <h1 style={{ fontSize: 20, fontWeight: 800 }}>{t('login')}</h1>
            <p style={{ color: '#f87171' }}>{error}</p>
            <button className="tma-btn tma-btn-card" onClick={() => window.location.reload()}>
              {t('tma_submit')}
            </button>
          </div>
        </div>
      </div>
    );
  }

  const firstName = user?.first_name || (user?.full_name ?? '').split(' ')[0] || '';
  const inFlow = activeTestId !== null;

  return (
    <div className="tma-root">
      <div className="tma-wrap">
        <header className="tma-header">
          <h1>{firstName ? `Salom, ${firstName}!` : t('dashboard')}</h1>
          <span className="tma-xp">⚡ {profile?.stats.total_xp ?? 0} XP</span>
        </header>

        <main className="tma-main">
          {inFlow ? (
            <TestFlow testId={activeTestId} onExit={exitFlow} setBackHandler={setBackHandler} />
          ) : tab === 'home' ? (
            <Home profile={profile} onProfileLoaded={setProfile} onOpenTest={openTest} />
          ) : (
            <Essays setBackHandler={setBackHandler} />
          )}
        </main>

        {!inFlow && (
          <nav className="tma-nav">
            <div className="tma-nav-inner">
              <button className={tab === 'home' ? 'on' : ''} onClick={() => switchTab('home')}>
                <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" /></svg>
                <span>{t('tma_home')}</span>
              </button>
              <button
                className={tab === 'home' ? 'on' : ''}
                onClick={() => {
                  switchTab('home');
                  window.scrollTo({ top: 0 });
                }}
              >
                <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
                <span>{t('tma_tests')}</span>
              </button>
              <button className={tab === 'essays' ? 'on' : ''} onClick={() => switchTab('essays')}>
                <svg fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2"><path strokeLinecap="round" strokeLinejoin="round" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" /></svg>
                <span>{t('tma_essays_tab')}</span>
              </button>
            </div>
          </nav>
        )}
      </div>
    </div>
  );
}
