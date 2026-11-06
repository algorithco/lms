import { useEffect, useState } from 'react';
import { useAuth } from '../auth/AuthContext';

export type Subject = 'uzbek' | 'english' | 'biology' | 'chemistry' | 'law';

export const VALID_SUBJECTS: Subject[] = ['uzbek', 'english', 'biology', 'chemistry', 'law'];

export function isValidSubject(s: unknown): s is Subject {
  return typeof s === 'string' && VALID_SUBJECTS.includes(s as Subject);
}

/**
 * The study subject (what is being prepared for) — NOT the interface language.
 * Follows the profile, then the stored choice, and updates when the switcher fires
 * `subject-changed`.
 */
export function useSubject(): Subject {
  const { user } = useAuth();
  const read = (): Subject => {
    if (isValidSubject(user?.active_subject)) return user.active_subject;
    try {
      const stored = localStorage.getItem('lms_subject');
      if (isValidSubject(stored)) return stored;
    } catch {
      /* ignore storage access error */
    }
    return 'uzbek';
  };
  const [subject, setSubject] = useState<Subject>(read);

  useEffect(() => {
    setSubject(read());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user?.active_subject]);

  useEffect(() => {
    const onChange = (e: Event) => {
      const next = (e as CustomEvent<Subject>).detail;
      if (isValidSubject(next)) setSubject(next);
    };
    window.addEventListener('subject-changed', onChange);
    return () => window.removeEventListener('subject-changed', onChange);
  }, []);

  return subject;
}
