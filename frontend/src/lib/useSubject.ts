import { useEffect, useState } from 'react';
import { useAuth } from '../auth/AuthContext';

export type Subject = 'uzbek' | 'english';

/**
 * The study subject (what is being prepared for) — NOT the interface language.
 * Follows the profile, then the stored choice, and updates when the switcher fires
 * `subject-changed`.
 */
export function useSubject(): Subject {
  const { user } = useAuth();
  const read = (): Subject => {
    if (user?.active_subject === 'english' || user?.active_subject === 'uzbek') return user.active_subject;
    try {
      return localStorage.getItem('lms_subject') === 'english' ? 'english' : 'uzbek';
    } catch {
      return 'uzbek';
    }
  };
  const [subject, setSubject] = useState<Subject>(read);

  useEffect(() => {
    setSubject(read());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.active_subject]);

  useEffect(() => {
    const onChange = (e: Event) => {
      const next = (e as CustomEvent<Subject>).detail;
      if (next === 'english' || next === 'uzbek') setSubject(next);
    };
    window.addEventListener('subject-changed', onChange);
    return () => window.removeEventListener('subject-changed', onChange);
  }, []);

  return subject;
}
