import { useState } from 'react';
import { useAuth } from '../auth/AuthContext';
import { ProfileApi } from '../lib/api';

interface SubjectSwitcherProps {
  className?: string;
  size?: 'sm' | 'md' | 'lg';
  onSwitch?: (subject: 'uzbek' | 'english') => void;
}

export default function SubjectSwitcher({
  className = '',
  size = 'md',
  onSwitch,
}: SubjectSwitcherProps) {
  const { user, updateUserLocal } = useAuth();
  const [loading, setLoading] = useState(false);

  // Active subject from user profile or local fallback
  const currentSubject: 'uzbek' | 'english' =
    user?.active_subject === 'english'
      ? 'english'
      : (localStorage.getItem('lms_subject') as 'uzbek' | 'english') || 'uzbek';

  const handleSelect = async (nextSubject: 'uzbek' | 'english') => {
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
          active_subject: (res.active_subject as 'uzbek' | 'english') || nextSubject,
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

  const isSelected = (sub: 'uzbek' | 'english') => currentSubject === sub;
  const sizeClass = size === 'sm' ? 'size-sm' : size === 'lg' ? 'size-lg' : '';

  return (
    <div
      role="group"
      aria-label="Fan tanlash"
      className={`subject-switcher-container bg-slate-900/80 p-1 rounded-xl border border-slate-700/60 inline-flex items-center gap-1 ${className}`}
    >
      {/* Uzbek: Ona tili */}
      <button
        type="button"
        disabled={loading}
        onClick={() => handleSelect('uzbek')}
        aria-pressed={isSelected('uzbek')}
        className={`subject-switcher-btn ${sizeClass} ${
          isSelected('uzbek')
            ? 'active bg-amber-500 text-slate-950 font-semibold shadow-sm rounded-lg py-1.5 px-3.5 transition-all'
            : 'text-slate-400 hover:text-white py-1.5 px-3.5 transition-all'
        }`}
      >
        <span className="subject-switcher-flag" role="img" aria-label="O'zbekiston">
          🇺🇿
        </span>
        <span>Ona tili</span>
      </button>

      {/* English */}
      <button
        type="button"
        disabled={loading}
        onClick={() => handleSelect('english')}
        aria-pressed={isSelected('english')}
        className={`subject-switcher-btn ${sizeClass} ${
          isSelected('english')
            ? 'active bg-amber-500 text-slate-950 font-semibold shadow-sm rounded-lg py-1.5 px-3.5 transition-all'
            : 'text-slate-400 hover:text-white py-1.5 px-3.5 transition-all'
        }`}
      >
        <span className="subject-switcher-flag" role="img" aria-label="English">
          🇬🇧
        </span>
        <span>English</span>
      </button>
    </div>
  );
}
