import { useState } from 'react';
import { LockIcon, XIcon, ZapIcon } from './icons';
import CardPaymentModal from './CardPaymentModal';
import { useAuth } from '../auth/AuthContext';
import { isPlatformAdmin } from '../lib/api';

interface LimitExceededModalProps {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  message?: string;
  feature?: 'test' | 'essay' | 'arena' | 'general';
}

export default function LimitExceededModal({
  isOpen,
  onClose,
  title = "Bepul Sinov Limiti Tugadi",
  message = "Siz bepul sinov limitingizdan to'liq foydalandingiz. Davom ettirish uchun STARTER (7 000 so'm) yoki PRO (15 000 so'm) tarifiga o'ting!",
}: LimitExceededModalProps) {
  const { user } = useAuth();
  const [showPaymentModal, setShowPaymentModal] = useState(false);

  // Root Admin Immunity: Admins never encounter paywalls or limit exceeded modals
  if (isPlatformAdmin(user) || user?.is_staff || user?.role === 'admin' || user?.role === 'center_admin') {
    return null;
  }

  if (!isOpen) return null;

  if (showPaymentModal) {
    return (
      <CardPaymentModal
        isOpen={true}
        initialTariff="PRO"
        onClose={() => {
          setShowPaymentModal(false);
          onClose();
        }}
        onSuccess={() => {
          setShowPaymentModal(false);
          onClose();
        }}
      />
    );
  }

  const handleUpgrade = () => {
    setShowPaymentModal(true);
  };

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9999,
        background: 'rgba(15, 23, 42, 0.75)',
        backdropFilter: 'blur(8px)',
        WebkitBackdropFilter: 'blur(8px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '16px',
      }}
      role="dialog"
      aria-modal="true"
    >
      <div
        style={{
          width: '100%',
          maxWidth: 480,
          background: 'var(--card, #FFFFFF)',
          color: 'var(--ink, #0F172A)',
          borderRadius: 24,
          padding: '28px 24px',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.35)',
          border: '1.5px solid rgba(245, 158, 11, 0.4)',
          position: 'relative',
          animation: 'fadeInScale 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
        }}
      >
        {/* Close Button */}
        <button
          type="button"
          onClick={onClose}
          style={{
            position: 'absolute',
            top: 16,
            right: 16,
            background: 'transparent',
            border: 'none',
            color: 'var(--muted, #64748B)',
            cursor: 'pointer',
            padding: 6,
            borderRadius: 8,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
          aria-label="Yopish"
        >
          <XIcon size={20} />
        </button>

        {/* Lock Icon Header */}
        <div style={{ textAlign: 'center', marginBottom: 16 }}>
          <div
            style={{
              width: 64,
              height: 64,
              borderRadius: '50%',
              background: 'linear-gradient(135deg, #FEF3C7 0%, #FDE68A 100%)',
              border: '2px solid #F59E0B',
              color: '#D97706',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              boxShadow: '0 8px 20px -4px rgba(245, 158, 11, 0.35)',
              marginBottom: 12,
            }}
          >
            <LockIcon size={30} />
          </div>
          <h3
            style={{
              margin: '0 0 8px',
              fontSize: 20,
              fontWeight: 900,
              color: 'var(--ink, #0F172A)',
            }}
          >
            {title}
          </h3>
          <p
            style={{
              margin: 0,
              fontSize: 14,
              color: 'var(--muted, #64748B)',
              lineHeight: 1.5,
            }}
          >
            {message}
          </p>
        </div>

        {/* Perks Box */}
        <div
          style={{
            background: 'linear-gradient(135deg, rgba(245, 158, 11, 0.08) 0%, rgba(217, 119, 6, 0.04) 100%)',
            border: '1px solid rgba(245, 158, 11, 0.25)',
            borderRadius: 16,
            padding: '14px 16px',
            marginBottom: 20,
            display: 'flex',
            flexDirection: 'column',
            gap: 10,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 13, fontWeight: 700 }}>
            <span>🎯</span>
            <span>BMB va Attestatsiya 2026 to&apos;liq Mock testlari</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 13, fontWeight: 700 }}>
            <span>✍️</span>
            <span>12 mezonli AI Esse va qo&apos;lyozma skaner tahlili</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 13, fontWeight: 700 }}>
            <span>⚔️</span>
            <span>1v1 Jonli Arenada cheksiz bellashuvlar</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 13, fontWeight: 700 }}>
            <span>⚡️</span>
            <span>Rasch 1PL dinamik baholash va rasmiy sertifikat</span>
          </div>
        </div>

        {/* Action Buttons */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <button
            type="button"
            onClick={handleUpgrade}
            style={{
              width: '100%',
              padding: '13px 20px',
              borderRadius: 14,
              background: 'linear-gradient(135deg, #F59E0B 0%, #D97706 100%)',
              color: '#FFFFFF',
              fontWeight: 800,
              fontSize: 15,
              border: 'none',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 8,
              boxShadow: '0 8px 24px -4px rgba(217, 119, 6, 0.4)',
              transition: 'all 0.15s ease',
            }}
          >
            <ZapIcon size={18} />
            <span>Tariflarni ko&apos;rish va obuna bo&apos;lish →</span>
          </button>

          <button
            type="button"
            onClick={onClose}
            style={{
              width: '100%',
              padding: '10px 16px',
              borderRadius: 12,
              background: 'transparent',
              border: '1px solid var(--border, rgba(226, 232, 240, 0.8))',
              color: 'var(--muted, #64748B)',
              fontWeight: 700,
              fontSize: 13.5,
              cursor: 'pointer',
            }}
          >
            Hozircha bekor qilish
          </button>
        </div>
      </div>
    </div>
  );
}
