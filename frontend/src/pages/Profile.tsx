import { Link } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { useLang, type AppLang } from '../i18n/LangContext';
import { useTheme, type Theme } from '../theme/ThemeContext';
import {
  MonitorIcon,
  MoonIcon,
  SunIcon,
  UserIcon,
} from '../components/icons';
import UsageLimits from '../components/UsageLimits';
import ParentMonitoringCard from '../components/ParentMonitoringCard';

function getInitials(name?: string, email?: string): string {
  if (name && name.trim()) {
    const parts = name.trim().split(/\s+/);
    if (parts.length >= 2) {
      return (parts[0][0] + parts[1][0]).toUpperCase();
    }
    return parts[0].slice(0, 2).toUpperCase();
  }
  if (email && email.trim()) {
    return email.slice(0, 2).toUpperCase();
  }
  return 'U';
}

export default function Profile() {
  const { user } = useAuth();
  const { lang, setLang } = useLang();
  const { theme, setTheme, resolvedTheme } = useTheme();

  if (!user) return null;

  const initials = getInitials(user.full_name, user.email);

  return (
    <div style={{ maxWidth: 860, margin: '0 auto', paddingBottom: 60 }}>
      {/* Header Card with User Avatar & Info */}
      <div
        className="card"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 20,
          padding: 24,
          marginBottom: 24,
          background: 'linear-gradient(135deg, var(--card), var(--card-2))',
          flexWrap: 'wrap',
        }}
      >
        {user.avatar ? (
          <img
            src={user.avatar}
            alt={user.full_name || 'Profil'}
            style={{
              width: 72,
              height: 72,
              borderRadius: '50%',
              objectFit: 'cover',
              border: '3px solid var(--accent)',
              boxShadow: '0 4px 20px rgba(245, 158, 11, 0.3)',
            }}
          />
        ) : (
          <span
            style={{
              width: 72,
              height: 72,
              borderRadius: '50%',
              background: 'linear-gradient(135deg, #f59e0b, #d97706)',
              color: '#ffffff',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 26,
              fontWeight: 800,
              boxShadow: '0 4px 20px rgba(245, 158, 11, 0.3)',
              flexShrink: 0,
            }}
          >
            {initials}
          </span>
        )}

        <div style={{ flex: 1, minWidth: 200 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            <h1 style={{ margin: 0, fontSize: 24, fontWeight: 800 }}>
              {user.full_name || 'Foydalanuvchi'}
            </h1>
            <span
              style={{
                fontSize: 11,
                fontWeight: 700,
                textTransform: 'uppercase',
                padding: '3px 10px',
                borderRadius: 20,
                background: 'rgba(245, 158, 11, 0.15)',
                color: 'var(--accent-dark)',
                border: '1px solid rgba(245, 158, 11, 0.3)',
              }}
            >
              {user.role}
            </span>
            <span
              style={{
                fontSize: 11,
                fontWeight: 700,
                padding: '3px 10px',
                borderRadius: 20,
                background: 'rgba(16, 185, 129, 0.15)',
                color: '#10b981',
                border: '1px solid rgba(16, 185, 129, 0.3)',
              }}
            >
              ✓ Faol hisob
            </span>
          </div>
          <p className="muted" style={{ margin: '6px 0 0', fontSize: 14 }}>
            {user.email}
          </p>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 20 }}>
        {/* Personal Details Card */}
        <div className="card" style={{ padding: 24 }}>
          <h2 style={{ fontSize: 18, marginTop: 0, marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
            <UserIcon size={20} style={{ color: 'var(--accent)' }} />
            Shaxsiy ma'lumotlar
          </h2>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div>
              <span className="muted small" style={{ display: 'block', marginBottom: 2 }}>To'liq ism</span>
              <strong style={{ fontSize: 15 }}>{user.full_name || '—'}</strong>
            </div>
            <div>
              <span className="muted small" style={{ display: 'block', marginBottom: 2 }}>Elektron pochta (Email)</span>
              <strong style={{ fontSize: 15 }}>{user.email}</strong>
            </div>
            <div>
              <span className="muted small" style={{ display: 'block', marginBottom: 2 }}>Platformadagi rol</span>
              <strong style={{ fontSize: 15, textTransform: 'capitalize' }}>{user.role}</strong>
            </div>
          </div>
        </div>

        {/* Interface & Theme Settings Card */}
        <div className="card" style={{ padding: 24 }}>
          <h2 style={{ fontSize: 18, marginTop: 0, marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
            <MoonIcon size={20} style={{ color: 'var(--accent)' }} />
            Interfeys va sozlamalar
          </h2>

          {/* Theme Selector */}
          <div style={{ marginBottom: 20 }}>
            <span className="muted small" style={{ display: 'block', marginBottom: 8, fontWeight: 600 }}>
              Mavzu (Theme):
            </span>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
              {[
                { key: 'dark' as Theme, label: "Qorong'i", icon: MoonIcon },
                { key: 'light' as Theme, label: "Yorug'", icon: SunIcon },
                { key: 'system' as Theme, label: 'Tizim', icon: MonitorIcon },
              ].map((item) => {
                const isActive = theme === item.key;
                const Icon = item.icon;
                return (
                  <button
                    key={item.key}
                    type="button"
                    onClick={() => setTheme(item.key)}
                    style={{
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: 6,
                      padding: '12px 8px',
                      borderRadius: 12,
                      cursor: 'pointer',
                      border: isActive ? '2px solid var(--accent)' : '1px solid var(--border)',
                      background: isActive ? 'var(--card-2)' : 'transparent',
                      color: isActive ? 'var(--accent-dark)' : 'var(--ink)',
                      fontWeight: isActive ? 700 : 500,
                      transition: 'all 0.15s ease',
                    }}
                  >
                    <Icon size={18} />
                    <span style={{ fontSize: 12 }}>{item.label}</span>
                  </button>
                );
              })}
            </div>
            <span className="muted small" style={{ display: 'block', marginTop: 6 }}>
              Hozirgi faol holat: <strong>{resolvedTheme === 'dark' ? "Qorong'i (Dark UI)" : "Yorug' (Light UI)"}</strong>
            </span>
          </div>

          {/* Language Selector */}
          <div>
            <span className="muted small" style={{ display: 'block', marginBottom: 8, fontWeight: 600 }}>
              Interfeys tili (Language):
            </span>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
              {[
                { code: 'uz' as AppLang, label: "O'zbekcha" },
                { code: 'ru' as AppLang, label: 'Русский' },
                { code: 'en' as AppLang, label: 'English' },
              ].map((item) => {
                const isActive = lang === item.code;
                return (
                  <button
                    key={item.code}
                    type="button"
                    onClick={() => setLang(item.code)}
                    style={{
                      padding: '10px 8px',
                      borderRadius: 12,
                      cursor: 'pointer',
                      border: isActive ? '2px solid var(--accent)' : '1px solid var(--border)',
                      background: isActive ? 'var(--card-2)' : 'transparent',
                      color: isActive ? 'var(--accent-dark)' : 'var(--ink)',
                      fontWeight: isActive ? 700 : 500,
                      fontSize: 12,
                      transition: 'all 0.15s ease',
                    }}
                  >
                    {item.label}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </div>

      {/* Parent Monitoring Smart Alerts */}
      <div style={{ marginTop: 24 }}>
        <ParentMonitoringCard />
      </div>

      {/* Subscription & Usage Limits */}
      <div style={{ marginTop: 24 }}>
        <UsageLimits />
      </div>

      {/* Quick Nav Card */}
      <div
        className="card"
        style={{
          marginTop: 24,
          padding: 20,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: 12,
        }}
      >
        <div>
          <strong style={{ display: 'block', fontSize: 15 }}>Obunani boshqarish yoki yangilash</strong>
          <span className="muted small">Tariflarni ko'rish va to'lov cheklarini tekshirish</span>
        </div>
        <Link to="/subscribe" className="btn primary sm btn-glow" style={{ textDecoration: 'none' }}>
          Tariflarni ko'rish →
        </Link>
      </div>
    </div>
  );
}
