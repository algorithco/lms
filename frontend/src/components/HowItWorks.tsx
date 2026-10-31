import { useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { useLang } from '../i18n/LangContext';
import { useTheme } from '../theme/ThemeContext';
import { landingFor } from '../lib/api';

export default function HowItWorks() {
  const { t } = useLang();
  const { user, openAuthModal } = useAuth();
  const { resolvedTheme } = useTheme();
  const navigate = useNavigate();
  const isDark = resolvedTheme !== 'light';

  const startTo = user ? landingFor(user) : '/register';

  const steps = [
    { num: '1', title: t('step1_title'), desc: t('step1_desc') },
    { num: '2', title: t('step2_title'), desc: t('step2_desc') },
    { num: '3', title: t('step3_title'), desc: t('step3_desc') },
  ];

  return (
    <section
      id="how"
      className="bg-slate-50 dark:bg-slate-900/60 border-t border-b border-slate-200 dark:border-slate-800 transition-colors duration-200"
      style={{
        padding: '70px 20px',
        background: isDark ? 'rgba(15, 23, 42, 0.7)' : '#f8fafc',
        borderTop: isDark ? '1px solid rgba(255, 255, 255, 0.08)' : '1px solid var(--border)',
        borderBottom: isDark ? '1px solid rgba(255, 255, 255, 0.08)' : '1px solid var(--border)',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      <div style={{ margin: '0 auto', maxWidth: 1000, position: 'relative', zIndex: 1 }}>
        <div style={{ textAlign: 'center', maxWidth: 600, margin: '0 auto 48px' }}>
          <span
            className="text-amber-500 font-extrabold uppercase tracking-widest text-xs inline-block mb-2"
            style={{
              fontSize: 11,
              fontWeight: 900,
              letterSpacing: '0.22em',
              color: '#F59E0B',
              textTransform: 'uppercase',
              display: 'inline-block',
              marginBottom: 8,
            }}
          >
            {t('how_eyebrow')}
          </span>
          <h2
            className="text-slate-900 dark:text-white font-black"
            style={{
              fontSize: 'clamp(1.8rem, 3.5vw, 2.5rem)',
              fontWeight: 900,
              color: isDark ? '#FFFFFF' : '#0F172A',
              margin: '4px 0',
            }}
          >
            {t('how_title_1')} <span className="hero-title-gradient">{t('how_title_2')}</span>
          </h2>
        </div>

        <div
          className="grid grid-cols-1 md:grid-cols-3 gap-6"
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
            gap: 24,
          }}
        >
          {steps.map((st, i) => (
            <div
              key={i}
              className="step-card bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-3xl p-8 sm:p-9 text-center transition-all duration-300 flex flex-col items-center"
              style={{
                background: isDark ? '#0F172A' : '#FFFFFF',
                border: isDark ? '1px solid rgba(255, 255, 255, 0.08)' : '1px solid #E2E8F0',
                borderRadius: 20,
                padding: '36px 28px',
                textAlign: 'center',
                backdropFilter: 'blur(16px)',
                transition: 'all 0.25s cubic-bezier(0.16, 1, 0.3, 1)',
                position: 'relative',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                boxShadow: isDark
                  ? '0 10px 30px rgba(0, 0, 0, 0.45)'
                  : '0 4px 20px rgba(0, 0, 0, 0.05)',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = 'rgba(245, 158, 11, 0.6)';
                e.currentTarget.style.transform = 'translateY(-4px)';
                e.currentTarget.style.boxShadow = isDark
                  ? '0 16px 36px -8px rgba(245, 158, 11, 0.25)'
                  : '0 12px 28px -6px rgba(245, 158, 11, 0.25)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = isDark ? 'rgba(255, 255, 255, 0.08)' : '#E2E8F0';
                e.currentTarget.style.transform = 'translateY(0)';
                e.currentTarget.style.boxShadow = isDark
                  ? '0 10px 30px rgba(0, 0, 0, 0.45)'
                  : '0 4px 20px rgba(0, 0, 0, 0.05)';
              }}
            >
              {/* Badge 1, 2, 3: Uniform Modern Amber Gradient */}
              <div
                style={{
                  width: 54,
                  height: 54,
                  borderRadius: 16,
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#ffffff',
                  fontSize: 20,
                  fontWeight: 900,
                  marginBottom: 20,
                  background: 'linear-gradient(135deg, #f59e0b, #d97706)',
                  border: '1px solid rgba(251, 191, 36, 0.4)',
                  boxShadow: '0 8px 24px rgba(245, 158, 11, 0.3)',
                  letterSpacing: '-0.5px',
                }}
              >
                {st.num}
              </div>
              <h3
                className="text-slate-900 dark:text-white font-extrabold tracking-tight"
                style={{
                  fontSize: 19,
                  fontWeight: 800,
                  color: isDark ? '#FFFFFF' : '#0F172A',
                  margin: '0 0 12px',
                  letterSpacing: '-0.3px',
                }}
              >
                {st.title}
              </h3>
              <p
                className="text-slate-600 dark:text-slate-300 leading-relaxed"
                style={{
                  fontSize: 14,
                  color: isDark ? '#CBD5E1' : '#475569',
                  lineHeight: 1.65,
                  margin: 0,
                }}
              >
                {st.desc}
              </p>
            </div>
          ))}
        </div>

        <div style={{ marginTop: 44, textAlign: 'center' }}>
          <button
            type="button"
            onClick={() => (user ? navigate(startTo) : openAuthModal('register'))}
            className="btn-glow"
            style={{
              padding: '14px 36px',
              fontSize: 15,
              fontWeight: 800,
              borderRadius: 14,
              background: 'linear-gradient(135deg, #F59E0B, #FBBF24)',
              color: '#090d16',
              border: 'none',
              cursor: 'pointer',
              boxShadow: '0 4px 20px rgba(245, 158, 11, 0.4)',
            }}
          >
            {t('cta_free_account')} →
          </button>
        </div>
      </div>
    </section>
  );
}
