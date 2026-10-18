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

    if (user) {
      try {
        const res = await ProfileApi.switchSubject(nextSubject);
        updateUserLocal({ active_subject: res.active_subject });
      } catch (err) {
        console.error('Failed to switch subject on server:', err);
        // Still update locally for smooth UI experience
        updateUserLocal({ active_subject: nextSubject });
      }
    }

    window.dispatchEvent(new CustomEvent('subject-changed', { detail: nextSubject }));
    onSwitch?.(nextSubject);
    setLoading(false);
  };

  const isLg = size === 'lg';
  const isSm = size === 'sm';

  return (
    <div
      role="group"
      aria-label="Fan tanlash"
      className={`inline-flex items-center p-1 rounded-full border shadow-sm transition-all duration-200 ${
        isLg ? 'p-1.5' : isSm ? 'p-0.5' : 'p-1'
      } bg-slate-100 dark:bg-slate-800/90 border-slate-200 dark:border-slate-700/80 ${className}`}
      style={{ minHeight: isSm ? '36px' : '44px' }}
    >
      {/* Uzbek Subject Pill */}
      <button
        type="button"
        disabled={loading}
        onClick={() => handleSelect('uzbek')}
        aria-pressed={currentSubject === 'uzbek'}
        className={`flex items-center justify-center gap-1.5 rounded-full font-medium transition-all duration-200 touch-manipulation select-none ${
          isLg
            ? 'px-4 py-2 text-sm min-h-[44px]'
            : isSm
            ? 'px-2.5 py-1 text-xs min-h-[34px]'
            : 'px-3.5 py-1.5 text-xs sm:text-sm min-h-[40px] sm:min-h-[44px]'
        } ${
          currentSubject === 'uzbek'
            ? 'bg-white dark:bg-slate-900 text-emerald-700 dark:text-emerald-400 shadow-sm ring-1 ring-emerald-500/20 font-semibold'
            : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100'
        }`}
      >
        <span className="text-base leading-none" role="img" aria-label="O'zbekiston">
          🇺🇿
        </span>
        <span className="truncate">Ona tili</span>
        {currentSubject === 'uzbek' && (
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse hidden sm:inline-block" />
        )}
      </button>

      {/* English (IELTS & Multi-level) Subject Pill */}
      <button
        type="button"
        disabled={loading}
        onClick={() => handleSelect('english')}
        aria-pressed={currentSubject === 'english'}
        className={`flex items-center justify-center gap-1.5 rounded-full font-medium transition-all duration-200 touch-manipulation select-none ${
          isLg
            ? 'px-4 py-2 text-sm min-h-[44px]'
            : isSm
            ? 'px-2.5 py-1 text-xs min-h-[34px]'
            : 'px-3.5 py-1.5 text-xs sm:text-sm min-h-[40px] sm:min-h-[44px]'
        } ${
          currentSubject === 'english'
            ? 'bg-white dark:bg-slate-900 text-indigo-700 dark:text-indigo-400 shadow-sm ring-1 ring-indigo-500/20 font-semibold'
            : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100'
        }`}
      >
        <span className="text-base leading-none" role="img" aria-label="English">
          🇬🇧
        </span>
        <span className="truncate">English (IELTS)</span>
        {currentSubject === 'english' && (
          <span className="w-1.5 h-1.5 rounded-full bg-indigo-500 animate-pulse hidden sm:inline-block" />
        )}
      </button>
    </div>
  );
}
