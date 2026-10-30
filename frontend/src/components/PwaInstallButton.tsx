import { useEffect, useState } from 'react';
import { DownloadIcon } from './icons';

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed'; platform: string }>;
}

export default function PwaInstallButton({ className }: { className?: string }) {
  const [deferredPrompt, setDeferredPrompt] = useState<BeforeInstallPromptEvent | null>(null);
  const [isInstalled, setIsInstalled] = useState(() => {
    if (typeof window === 'undefined') return false;
    return Boolean(
      window.matchMedia('(display-mode: standalone)').matches ||
      (window.navigator as unknown as { standalone?: boolean }).standalone
    );
  });
  const [infoModal, setInfoModal] = useState(false);

  useEffect(() => {
    const handler = (e: Event) => {
      e.preventDefault();
      setDeferredPrompt(e as BeforeInstallPromptEvent);
    };

    window.addEventListener('beforeinstallprompt', handler);
    window.addEventListener('appinstalled', () => {
      setIsInstalled(true);
      setDeferredPrompt(null);
    });

    return () => {
      window.removeEventListener('beforeinstallprompt', handler);
    };
  }, []);

  const handleInstallClick = async () => {
    if (deferredPrompt) {
      await deferredPrompt.prompt();
      const choice = await deferredPrompt.userChoice;
      if (choice.outcome === 'accepted') {
        setIsInstalled(true);
      }
      setDeferredPrompt(null);
    } else {
      // Show instructional modal if prompt is not natively available (e.g. iOS or manual)
      setInfoModal(true);
    }
  };

  if (isInstalled) return null;

  return (
    <>
      <button
        type="button"
        onClick={handleInstallClick}
        className={className}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 6,
          padding: '6px 12px',
          borderRadius: 10,
          background: 'rgba(16, 185, 129, 0.1)',
          border: '1px solid rgba(16, 185, 129, 0.35)',
          color: '#059669',
          fontWeight: 800,
          fontSize: 12.5,
          cursor: 'pointer',
          transition: 'all 0.2s ease',
        }}
        title="Ilovani o'rnatish (PWA)"
      >
        <DownloadIcon size={14} />
        <span>+ O&apos;rnatish</span>
      </button>

      {/* Manual Install Instructions Modal */}
      {infoModal && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 9999,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: 'rgba(0, 0, 0, 0.65)',
            backdropFilter: 'blur(8px)',
            padding: 16,
          }}
          onClick={() => setInfoModal(false)}
        >
          <div
            style={{
              background: '#FFFFFF',
              color: '#0F172A',
              maxWidth: 400,
              width: '100%',
              borderRadius: 20,
              padding: '24px 20px',
              boxShadow: '0 20px 40px rgba(0, 0, 0, 0.25)',
              textAlign: 'center',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ fontSize: 40, marginBottom: 12 }}>📲</div>
            <h3 style={{ margin: '0 0 8px', fontSize: 18, fontWeight: 900 }}>
              Ilovani o&apos;rnatish
            </h3>
            <p style={{ margin: '0 0 20px', fontSize: 13, color: '#64748B', lineHeight: 1.5 }}>
              Saytdan ilova sifatida foydalanish uchun brauzeringiz menyusidan (yoki ulashish tugmasidan){' '}
              <strong style={{ color: '#0F172A' }}>&ldquo;Bosh ekranga qo&apos;shish&rdquo; (Add to Home Screen)</strong> yoki{' '}
              <strong style={{ color: '#0F172A' }}>&ldquo;Ilovani o&apos;rnatish&rdquo;</strong> ni tanlang.
            </p>
            <button
              type="button"
              onClick={() => setInfoModal(false)}
              style={{
                width: '100%',
                padding: '10px 16px',
                borderRadius: 12,
                background: 'linear-gradient(135deg, #F59E0B, #D97706)',
                color: '#FFFFFF',
                fontWeight: 800,
                fontSize: 14,
                border: 'none',
                cursor: 'pointer',
              }}
            >
              Tushundim
            </button>
          </div>
        </div>
      )}
    </>
  );
}
