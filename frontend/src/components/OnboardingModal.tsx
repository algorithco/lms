import { useAuth } from '../context/AuthContext';
import Onboarding from '../pages/Onboarding';

interface OnboardingModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: () => void;
}

export default function OnboardingModal({ isOpen, onClose, onSuccess }: OnboardingModalProps) {
  const { user } = useAuth();

  const role = (user?.role || '').toLowerCase();
  const isStaffOrTeacher =
    role === 'admin' || role === 'teacher' || role === 'superadmin' || role === 'center_admin' || Boolean(user?.is_superuser);
  const isStudent = role === 'student' && !isStaffOrTeacher;

  const isDismissed =
    typeof window !== 'undefined' &&
    (localStorage.getItem('onboarding_dismissed') === 'true' ||
      localStorage.getItem('grandec_onboarding_done') === 'true' ||
      localStorage.getItem('grand_ed_onboarding_done') === 'true');

  if (!isOpen || !isStudent || isDismissed) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Smart Onboarding So'rovnoma"
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9999,
        background: 'var(--bg-page, var(--bg))',
        overflowY: 'auto',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      <Onboarding
        isModal
        onClose={() => {
          try {
            localStorage.setItem('onboarding_dismissed', 'true');
          } catch {
            /* ignore */
          }
          onClose();
        }}
        onSuccess={onSuccess}
      />
    </div>
  );
}
