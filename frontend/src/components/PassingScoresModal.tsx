import { XIcon } from './icons';

interface PassingScoresModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function PassingScoresModal({ isOpen, onClose }: PassingScoresModalProps) {
  if (!isOpen) return null;

  return (
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
      onClick={onClose}
    >
      <div
        style={{
          background: '#FFFFFF',
          color: '#0F172A',
          maxWidth: 580,
          width: '100%',
          borderRadius: 24,
          padding: '28px 24px',
          boxShadow: '0 24px 60px rgba(0, 0, 0, 0.3)',
          position: 'relative',
          maxHeight: '90vh',
          overflowY: 'auto',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ fontSize: 26 }}>📊</span>
            <div>
              <h2 style={{ margin: 0, fontSize: 18, fontWeight: 900, color: '#0F172A' }}>
                Rasmiy O&apos;tish Ballari 2026
              </h2>
              <p style={{ margin: '2px 0 0', fontSize: 12, color: '#64748B', fontWeight: 600 }}>
                BMB Davlat standarti va Pedagoglar attestatsiyasi talablari
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            style={{
              width: 34,
              height: 34,
              borderRadius: 10,
              background: '#F1F5F9',
              border: 'none',
              color: '#64748B',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
            }}
          >
            <XIcon size={18} />
          </button>
        </div>

        {/* 1. BMB Milliy Sertifikat Table */}
        <div style={{ marginBottom: 20 }}>
          <h3 style={{ fontSize: 14, fontWeight: 800, color: '#D97706', marginBottom: 10, display: 'flex', alignItems: 'center', gap: 6 }}>
            <span>🇺🇿</span> Milliy Sertifikat (Ona tili va adabiyot)
          </h3>
          <div style={{ borderRadius: 14, border: '1px solid #E2E8F0', overflow: 'hidden' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, textAlign: 'left' }}>
              <thead>
                <tr style={{ background: '#F8FAFC', borderBottom: '1px solid #E2E8F0' }}>
                  <th style={{ padding: '8px 12px', fontWeight: 800 }}>Daraja</th>
                  <th style={{ padding: '8px 12px', fontWeight: 800 }}>Foiz</th>
                  <th style={{ padding: '8px 12px', fontWeight: 800 }}>Imtiyoz</th>
                </tr>
              </thead>
              <tbody>
                <tr style={{ borderBottom: '1px solid #F1F5F9' }}>
                  <td style={{ padding: '8px 12px', fontWeight: 900, color: '#10B981' }}>A+</td>
                  <td style={{ padding: '8px 12px', fontWeight: 700 }}>86% – 100%</td>
                  <td style={{ padding: '8px 12px', color: '#059669', fontWeight: 700 }}>Maksimal 100% ball OTMga</td>
                </tr>
                <tr style={{ borderBottom: '1px solid #F1F5F9' }}>
                  <td style={{ padding: '8px 12px', fontWeight: 900, color: '#059669' }}>A</td>
                  <td style={{ padding: '8px 12px', fontWeight: 700 }}>75% – 85%</td>
                  <td style={{ padding: '8px 12px', color: '#059669', fontWeight: 700 }}>Maksimal ball OTMga</td>
                </tr>
                <tr style={{ borderBottom: '1px solid #F1F5F9' }}>
                  <td style={{ padding: '8px 12px', fontWeight: 800, color: '#0284C7' }}>B+</td>
                  <td style={{ padding: '8px 12px', fontWeight: 700 }}>68% – 74%</td>
                  <td style={{ padding: '8px 12px', color: '#0284C7' }}>Tabaqalashtirilgan ball</td>
                </tr>
                <tr style={{ borderBottom: '1px solid #F1F5F9' }}>
                  <td style={{ padding: '8px 12px', fontWeight: 800, color: '#3B82F6' }}>B</td>
                  <td style={{ padding: '8px 12px', fontWeight: 700 }}>60% – 67%</td>
                  <td style={{ padding: '8px 12px', color: '#3B82F6' }}>Tabaqalashtirilgan ball</td>
                </tr>
                <tr>
                  <td style={{ padding: '8px 12px', fontWeight: 700, color: '#F59E0B' }}>C+ / C</td>
                  <td style={{ padding: '8px 12px', fontWeight: 700 }}>46% – 59%</td>
                  <td style={{ padding: '8px 12px', color: '#64748B' }}>Cheklangan imtiyoz</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        {/* 2. Pedagoglar Attestatsiyasi 2026 */}
        <div style={{ marginBottom: 20 }}>
          <h3 style={{ fontSize: 14, fontWeight: 800, color: '#8B5CF6', marginBottom: 10, display: 'flex', alignItems: 'center', gap: 6 }}>
            <span>🎓</span> Pedagoglar Attestatsiyasi 2026 (70% Ustama)
          </h3>
          <div style={{ borderRadius: 14, border: '1px solid #E2E8F0', overflow: 'hidden' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, textAlign: 'left' }}>
              <thead>
                <tr style={{ background: '#F8FAFC', borderBottom: '1px solid #E2E8F0' }}>
                  <th style={{ padding: '8px 12px', fontWeight: 800 }}>Toifa</th>
                  <th style={{ padding: '8px 12px', fontWeight: 800 }}>Minimal Ball</th>
                  <th style={{ padding: '8px 12px', fontWeight: 800 }}>Ustama</th>
                </tr>
              </thead>
              <tbody>
                <tr style={{ borderBottom: '1px solid #F1F5F9' }}>
                  <td style={{ padding: '8px 12px', fontWeight: 800, color: '#7C3AED' }}>Oliy Toifa</td>
                  <td style={{ padding: '8px 12px', fontWeight: 700 }}>80+ ball (50 tadan)</td>
                  <td style={{ padding: '8px 12px', color: '#059669', fontWeight: 800 }}>+70% oylik maosh</td>
                </tr>
                <tr style={{ borderBottom: '1px solid #F1F5F9' }}>
                  <td style={{ padding: '8px 12px', fontWeight: 800, color: '#7C3AED' }}>Birinchi Toifa</td>
                  <td style={{ padding: '8px 12px', fontWeight: 700 }}>70+ ball</td>
                  <td style={{ padding: '8px 12px', color: '#059669', fontWeight: 700 }}>+50% ustama</td>
                </tr>
                <tr>
                  <td style={{ padding: '8px 12px', fontWeight: 800, color: '#7C3AED' }}>Ikkinchi Toifa</td>
                  <td style={{ padding: '8px 12px', fontWeight: 700 }}>60+ ball</td>
                  <td style={{ padding: '8px 12px', color: '#64748B' }}>Toifa tasdiqlanadi</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <button
          type="button"
          onClick={onClose}
          style={{
            width: '100%',
            padding: '11px 16px',
            borderRadius: 14,
            background: 'linear-gradient(135deg, #F59E0B, #D97706)',
            color: '#FFFFFF',
            fontWeight: 800,
            fontSize: 14,
            border: 'none',
            cursor: 'pointer',
          }}
        >
          Yopish
        </button>
      </div>
    </div>
  );
}
