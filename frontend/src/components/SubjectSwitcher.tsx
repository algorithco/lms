import { useState } from 'react';
import { useAuth } from '../auth/AuthContext';
import { useLang } from '../i18n/LangContext';
import { ProfileApi } from '../lib/api';
import { isValidSubject, type Subject } from '../lib/useSubject';

interface SubjectSwitcherProps {
  className?: string;
  size?: 'sm' | 'md' | 'lg';
  /** seg = full-width segmented control (phones, under the top bar). */
  variant?: 'pill' | 'seg';
  onSwitch?: (subject: Subject) => void;
}

const SUBJECT_LIST: { id: Subject; icon: string; labelKey: string; fallbackLabel: string }[] = [
  { id: 'uzbek', icon: '🇺🇿', labelKey: 'subject_uzbek', fallbackLabel: 'Ona tili' },
  { id: 'english', icon: '🇬🇧', labelKey: 'subject_english', fallbackLabel: 'Ingliz tili' },
  { id: 'biology', icon: '🧬', labelKey: 'subject_biology', fallbackLabel: 'Biologiya' },
  { id: 'chemistry', icon: '🧪', labelKey: 'subject_chemistry', fallbackLabel: 'Kimyo' },
  { id: 'law', icon: '⚖️', labelKey: 'subject_law', fallbackLabel: 'Huquq' },
];

/**
 * Subject (what you study) — NOT the interface language. The interface
 * language has its own switcher; the two states are stored separately.
 */
export default function SubjectSwitcher({
  className = '',
  size = 'md',
  variant = 'pill',
  onSwitch,
}: SubjectSwitcherProps) {
  const { user, updateUserLocal } = useAuth();
  const { t } = useLang();
  const [loading, setLoading] = useState(false);

  // Active subject from user profile or local fallback
  const currentSubject: Subject = isValidSubject(user?.active_subject)
    ? user.active_subject
    : (() => {
        try {
          const stored = localStorage.getItem('lms_subject');
          if (isValidSubject(stored)) return stored;
        } catch {
          /* ignore */
        }
        return 'uzbek';
      })();

  const handleSelect = async (nextSubject: Subject) => {
    if (nextSubject === currentSubject || loading) return;

    setLoading(true);
    try {
      localStorage.setItem('lms_subject', nextSubject);
    } catch {
      /* ignore */
    }

    // Strictly align the default exam target with the chosen subject
    const nextTarget =
      nextSubject === 'english' ? 'ielts' : 'national_certificate';
    const nextGrade = nextSubject === 'english' ? 'Band 7.5' : 'A+';

    if (user) {
      try {
        const res = await ProfileApi.switchSubject(nextSubject, nextTarget);
        updateUserLocal({
          active_subject: (res.active_subject as Subject) || nextSubject,
          exam_target: res.exam_target || nextTarget,
          target_grade: res.target_grade || nextGrade,
          daily_plan_summary: res.daily_plan_summary || undefined,
        });
      } catch (err) {
        console.error('Failed to switch subject on server:', err);
        // Still update locally for smooth UI experience
        updateUserLocal({
          active_subject: nextSubject,
          exam_target: nextTarget,
          target_grade: nextGrade,
        });
      }
    }

    window.dispatchEvent(new CustomEvent('subject-changed', { detail: nextSubject }));
    onSwitch?.(nextSubject);
    setLoading(false);
  };

  const sizeClass = size === 'sm' ? 'size-sm' : size === 'lg' ? 'size-lg' : '';

  if (variant === 'seg') {
    return (
      <div
        role="group"
        aria-label={t('subject_label')}
        className={`ui-seg ${className}`}
        style={{
          display: 'flex',
          alignItems: 'center',
          overflowX: 'auto',
          maxWidth: '100%',
          scrollbarWidth: 'none',
          WebkitOverflowScrolling: 'touch',
          gap: 4,
          padding: 3,
        }}
      >
        {SUBJECT_LIST.map((s) => {
          const isActive = currentSubject === s.id;
          return (
            <button
              key={s.id}
              type="button"
              disabled={loading}
              aria-pressed={isActive}
              onClick={() => handleSelect(s.id)}
              style={{
                whiteSpace: 'nowrap',
                flexShrink: 0,
                display: 'inline-flex',
                alignItems: 'center',
                gap: 5,
                padding: '6px 12px',
                borderRadius: 8,
                fontSize: 13,
                fontWeight: isActive ? 700 : 500,
                border: isActive ? '1px solid #c8922a' : '1px solid transparent',
                background: isActive ? 'rgba(200, 146, 42, 0.18)' : 'transparent',
                color: isActive ? '#f59e0b' : 'inherit',
                cursor: 'pointer',
                transition: 'all 0.18s ease',
              }}
            >
              <span>{s.icon}</span>
              <span>{t(s.labelKey) || s.fallbackLabel}</span>
            </button>
          );
        })}
      </div>
    );
  }

  return (
    <div
      role="group"
      aria-label={t('subject_label')}
      className={`subject-switcher-container ${className}`}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        overflowX: 'auto',
        maxWidth: '100%',
        scrollbarWidth: 'none',
        WebkitOverflowScrolling: 'touch',
        gap: 4,
        padding: '3px 4px',
        borderRadius: 12,
      }}
    >
      {SUBJECT_LIST.map((s) => {
        const isActive = currentSubject === s.id;
        return (
          <button
            key={s.id}
            type="button"
            disabled={loading}
            onClick={() => handleSelect(s.id)}
            aria-pressed={isActive}
            className={`subject-switcher-btn ${sizeClass}${isActive ? ' active' : ''}`}
            style={{
              whiteSpace: 'nowrap',
              flexShrink: 0,
              display: 'inline-flex',
              alignItems: 'center',
              gap: 5,
              padding: size === 'sm' ? '4px 10px' : '6px 13px',
              borderRadius: 8,
              fontSize: size === 'sm' ? 12 : 13,
              fontWeight: isActive ? 700 : 500,
              cursor: 'pointer',
              border: isActive ? '1.5px solid #c8922a' : '1px solid transparent',
              boxShadow: isActive ? '0 1px 6px rgba(200, 146, 42, 0.35)' : 'none',
              transition: 'all 0.18s ease',
            }}
          >
            <span style={{ fontSize: 14 }}>{s.icon}</span>
            <span>{t(s.labelKey) || s.fallbackLabel}</span>
          </button>
        );
      })}
    </div>
  );
}
