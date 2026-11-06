import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Shield, Check, X, Award, ChevronRight } from 'lucide-react';
import type { StreakInfoResponse } from '../lib/api';


interface StreakBadgeProps {
  streakData: StreakInfoResponse | null;
  compact?: boolean;
  className?: string;
}

export function StreakBadge({ streakData, compact = false, className = '' }: StreakBadgeProps) {
  const [modalOpen, setModalOpen] = useState(false);

  if (!streakData) return null;

  const isActive = streakData.is_active_today;
  const days = streakData.current_streak;

  const defaultWeekDays = [
    { day: 'Du', date: '', is_today: false, is_past: true, is_active: days > 0 },
    { day: 'Se', date: '', is_today: false, is_past: true, is_active: days > 1 },
    { day: 'Chor', date: '', is_today: false, is_past: true, is_active: days > 2 },
    { day: 'Pay', date: '', is_today: false, is_past: true, is_active: days > 3 },
    { day: 'Jum', date: '', is_today: true, is_past: false, is_active: isActive },
    { day: 'Shan', date: '', is_today: false, is_past: false, is_active: false },
    { day: 'Yak', date: '', is_today: false, is_past: false, is_active: false },
  ];

  const weekDays = streakData.week_days?.length ? streakData.week_days : defaultWeekDays;
  const milestones = streakData.milestones?.length
    ? streakData.milestones
    : [
        {
          target: 7,
          title: '7 kunlik Olov',
          reward: 'PRO bonus & BMB Mock kuponi',
          reached: days >= 7,
          progress_percent: Math.min(100, Math.round((days / 7) * 100)),
        },
        {
          target: 30,
          title: '30 kunlik Afsona',
          reward: 'VIP Attestatsiya va Sertifikat toʻplami',
          reached: days >= 30,
          progress_percent: Math.min(100, Math.round((days / 30) * 100)),
        },
      ];

  return (
    <>
      <button
        type="button"
        onClick={() => setModalOpen(true)}
        className={`streak-badge-btn ${className}`}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '6px',
          padding: compact ? '4px 10px' : '6px 14px',
          borderRadius: '20px',
          cursor: 'pointer',
          fontWeight: 700,
          fontSize: compact ? '12px' : '13px',
          transition: 'all 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
          outline: 'none',
          ...(isActive
            ? {
                background: 'linear-gradient(135deg, rgba(249, 115, 22, 0.15), rgba(239, 68, 68, 0.15))',
                border: '1px solid rgba(249, 115, 22, 0.45)',
                color: '#EA580C',
                boxShadow: '0 0 12px rgba(249, 115, 22, 0.25)',
              }
            : {
                background: 'linear-gradient(135deg, rgba(148, 163, 184, 0.12), rgba(203, 213, 225, 0.08))',
                border: '1px solid rgba(148, 163, 184, 0.3)',
                color: '#64748B',
              }),
        }}
        title={isActive ? `🔥 Olov yonmoqda: ${days} kun!` : `❄️ ${days} kun - bugun test yechib olovni saqlang!`}
      >
        <span style={{ fontSize: '15px' }}>{isActive ? '🔥' : '❄️'}</span>
        <span>{days} kun</span>
        {!compact && !isActive && (
          <span style={{ fontSize: '11px', opacity: 0.85, fontWeight: 500 }} className="hidden sm:inline">
            — bugun test yeching!
          </span>
        )}
      </button>

      {/* Interactive Streak Details Modal */}
      {modalOpen && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 9999,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: 'rgba(0, 0, 0, 0.65)',
            backdropFilter: 'blur(6px)',
            padding: '16px',
          }}
          onClick={() => setModalOpen(false)}
        >
          <div
            style={{
              width: '100%',
              maxWidth: '440px',
              borderRadius: '20px',
              background: 'var(--card-bg, #1E293B)',
              border: '1px solid rgba(200, 146, 42, 0.3)',
              boxShadow: '0 20px 40px -10px rgba(0, 0, 0, 0.5), 0 0 30px rgba(249, 115, 22, 0.15)',
              color: 'var(--text-main, #F8FAFC)',
              padding: '24px',
              position: 'relative',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Close icon */}
            <button
              type="button"
              onClick={() => setModalOpen(false)}
              style={{
                position: 'absolute',
                top: '16px',
                right: '16px',
                background: 'transparent',
                border: 'none',
                color: '#94A3B8',
                cursor: 'pointer',
              }}
            >
              <X size={20} />
            </button>

            {/* Header */}
            <div style={{ textAlign: 'center', marginBottom: '20px' }}>
              <div
                style={{
                  width: '64px',
                  height: '64px',
                  borderRadius: '50%',
                  margin: '0 auto 12px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '32px',
                  background: isActive
                    ? 'radial-gradient(circle, rgba(249, 115, 22, 0.3), rgba(239, 68, 68, 0.1))'
                    : 'radial-gradient(circle, rgba(148, 163, 184, 0.2), rgba(203, 213, 225, 0.05))',
                  border: isActive ? '2px solid #F97316' : '2px solid #94A3B8',
                  boxShadow: isActive ? '0 0 24px rgba(249, 115, 22, 0.4)' : 'none',
                }}
              >
                {isActive ? '🔥' : '❄️'}
              </div>
              <h3 style={{ fontSize: '20px', fontWeight: 800, margin: '0 0 4px', color: '#F8FAFC' }}>
                {days} Kunlik Olov
              </h3>
              <p style={{ margin: 0, fontSize: '13px', color: isActive ? '#10B981' : '#F59E0B', fontWeight: 600 }}>
                {isActive
                  ? '✅ Bugungi olov saqlab qolindi!'
                  : '⚠️ Olovni oʻchirmaslik uchun bugun kamida 1 ta test topshiring!'}
              </p>
            </div>

            {/* 7-Day Weekly Grid */}
            <div
              style={{
                background: 'rgba(15, 23, 42, 0.45)',
                border: '1px solid rgba(255, 255, 255, 0.08)',
                borderRadius: '14px',
                padding: '14px 10px',
                marginBottom: '20px',
              }}
            >
              <div style={{ fontSize: '12px', fontWeight: 600, color: '#94A3B8', marginBottom: '10px', textAlign: 'center' }}>
                BU HAFTALIK DAVOMATLIK
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: '6px' }}>
                {weekDays.map((item, idx) => (
                  <div key={idx} style={{ textAlign: 'center' }}>
                    <div style={{ fontSize: '11px', color: item.is_today ? '#F97316' : '#94A3B8', fontWeight: item.is_today ? 700 : 500, marginBottom: '6px' }}>
                      {item.day}
                    </div>
                    <div
                      style={{
                        width: '32px',
                        height: '32px',
                        margin: '0 auto',
                        borderRadius: '50%',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: '13px',
                        fontWeight: 700,
                        transition: 'all 0.2s',
                        ...(item.is_active
                          ? {
                              background: '#10B981',
                              color: '#FFFFFF',
                              boxShadow: '0 0 10px rgba(16, 185, 129, 0.4)',
                            }
                          : item.is_today
                            ? {
                                border: '2px dashed #F97316',
                                color: '#F97316',
                                background: 'rgba(249, 115, 22, 0.1)',
                              }
                            : {
                                background: 'rgba(255, 255, 255, 0.05)',
                                color: '#64748B',
                              }),
                      }}
                    >
                      {item.is_active ? <Check size={16} strokeWidth={3} /> : item.is_today ? '🔥' : '·'}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Milestones */}
            <div style={{ display: 'grid', gap: '10px', marginBottom: '20px' }}>
              <div style={{ fontSize: '12px', fontWeight: 600, color: '#94A3B8' }}>YUTUQ MARRALARI (MILESTONES)</div>
              {milestones.map((m, idx) => (
                <div
                  key={idx}
                  style={{
                    background: 'rgba(255, 255, 255, 0.04)',
                    border: '1px solid rgba(255, 255, 255, 0.06)',
                    borderRadius: '12px',
                    padding: '12px 14px',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <Award size={16} color={m.reached ? '#F59E0B' : '#94A3B8'} />
                      <span style={{ fontWeight: 700, fontSize: '13px' }}>{m.title}</span>
                    </div>
                    <span style={{ fontSize: '12px', fontWeight: 700, color: m.reached ? '#10B981' : '#F59E0B' }}>
                      {days} / {m.target} kun
                    </span>
                  </div>
                  <div style={{ fontSize: '11px', color: '#94A3B8', marginBottom: '8px' }}>
                    🎁 Sovgʻa: <strong style={{ color: '#E2E8F0' }}>{m.reward}</strong>
                  </div>
                  <div style={{ width: '100%', height: '6px', background: 'rgba(255, 255, 255, 0.1)', borderRadius: '3px', overflow: 'hidden' }}>
                    <div
                      style={{
                        width: `${m.progress_percent}%`,
                        height: '100%',
                        background: m.reached ? 'linear-gradient(90deg, #10B981, #34D399)' : 'linear-gradient(90deg, #F59E0B, #F97316)',
                        borderRadius: '3px',
                      }}
                    />
                  </div>
                </div>
              ))}
            </div>

            {/* Freeze Shield & Action */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px', marginTop: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: '#94A3B8' }}>
                <Shield size={16} color="#38BDF8" />
                <span>Muzlatish himoyasi: <strong style={{ color: '#F8FAFC' }}>{streakData.streak_freeze_count} ta</strong></span>
              </div>
              <Link
                to="/tests"
                onClick={() => setModalOpen(false)}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '10px 18px',
                  borderRadius: '12px',
                  background: 'linear-gradient(135deg, #C8922A, #F59E0B)',
                  color: '#000000',
                  fontWeight: 700,
                  fontSize: '13px',
                  textDecoration: 'none',
                  boxShadow: '0 4px 14px rgba(200, 146, 42, 0.35)',
                }}
              >
                <span>🚀 Test Yechish</span>
                <ChevronRight size={14} />
              </Link>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

/** Celebration modal shown when student completes test and extends their streak! */
export function StreakCelebrationModal({
  streakCount,
  onClose,
}: {
  streakCount: number;
  onClose: () => void;
}) {
  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 10000,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'rgba(0, 0, 0, 0.75)',
        backdropFilter: 'blur(8px)',
        padding: '16px',
      }}
      onClick={onClose}
    >
      <div
        style={{
          width: '100%',
          maxWidth: '400px',
          borderRadius: '24px',
          background: 'var(--card-bg, #1E293B)',
          border: '2px solid #F97316',
          boxShadow: '0 0 50px rgba(249, 115, 22, 0.4)',
          textAlign: 'center',
          padding: '32px 24px',
          color: '#F8FAFC',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ fontSize: '56px', marginBottom: '12px' }}>🔥</div>
        <h2 style={{ fontSize: '22px', fontWeight: 800, margin: '0 0 8px', color: '#F8FAFC' }}>
          Olov uzaytirildi: {streakCount} kunga yetdi!
        </h2>
        <p style={{ margin: '0 0 24px', fontSize: '14px', color: '#94A3B8', lineHeight: 1.5 }}>
          Ajoyib intizom! Siz bugungi maqsadni bajardingiz va kundalik bilim olovingizni saqlab qoldingiz.
        </p>
        <button
          type="button"
          onClick={onClose}
          style={{
            padding: '12px 32px',
            borderRadius: '14px',
            background: 'linear-gradient(135deg, #F97316, #EA580C)',
            border: 'none',
            color: '#FFFFFF',
            fontWeight: 800,
            fontSize: '15px',
            cursor: 'pointer',
            boxShadow: '0 4px 20px rgba(249, 115, 22, 0.45)',
          }}
        >
          Ajoyib, davom etamiz! 🚀
        </button>
      </div>
    </div>
  );
}
export default StreakBadge;
