import { useState } from 'react';
import { useAuth } from '../auth/AuthContext';
import { useLang } from '../i18n/LangContext';
import { ProfileApi } from '../lib/api';

type Subject = 'uzbek' | 'english';

interface SubjectSwitcherProps {
  className?: string;
  size?: 'sm' | 'md' | 'lg';
  onSwitch?: (subject: Subject) => void;
}

/**
 * Subject (what you study) — NOT the interface language. The interface
 * language has its own switcher; the two states are stored separately.
 */
export default function SubjectSwitcher({ className = '', size = 'md', onSwitch }: SubjectSwitcherProps) {
  const { user, updateUserLocal } = useAuth();
  const { t } = useLang();
  const [loading, setLoading] = useState(false);

  // Active subject from user profile or local fallback
  const currentSubject: Subject =
    user?.active_subject === 'english'
      ? 'english'
      : (localStorage.getItem('lms_subject') as Subject) || 'uzbek';

  const handleSelect = async (nextSubject: Subject) => {
    if (nextSubject === currentSubject || loading) return;

    setLoading(true);
    localStorage.setItem('lms_subject', nextSubject);

    // Strictly align the default exam target with the chosen subject
    const nextTarget = nextSubject === 'english' ? 'ielts' : 'national_certificate';
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
  const option = (subject: Subject, label: string) => (
    <button
      type="button"
      disabled={loading}
      onClick={() => handleSelect(subject)}
      aria-pressed={currentSubject === subject}
      className={`subject-switcher-btn ${sizeClass}${currentSubject === subject ? ' active' : ''}`}
    >
      {label}
    </button>
  );

  return (
    <div role="group" aria-label={t('subject_label')} className={`subject-switcher-container ${className}`}>
      {option('uzbek', t('subject_uzbek'))}
      {option('english', t('subject_english'))}
    </div>
  );
}
