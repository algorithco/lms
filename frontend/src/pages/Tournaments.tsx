import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../lib/api';
import { AwardIcon, ClockIcon, TrophyIcon, UserIcon } from '../components/icons';

interface TournamentItem {
  id: number;
  title: string;
  description: string;
  scheduled_at: string;
  duration_minutes: number;
  status: 'upcoming' | 'live' | 'finished';
  prize_fund_description: string;
  participants_count: number;
  user_joined: boolean;
  user_score: number | null;
  user_rank: number | null;
}

export default function Tournaments() {
  const [tournaments, setTournaments] = useState<TournamentItem[]>([]);
  const [loading, setLoading] = useState(true);

  const loadTournaments = async () => {
    try {
      const res = await api.get<{ tournaments: TournamentItem[] }>('/tournaments/');
      setTournaments(res.tournaments || []);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadTournaments();
  }, []);

  return (
    <div style={{ maxWidth: 1040, margin: '0 auto', paddingBottom: 60 }}>
      {/* Banner */}
      <div
        className="card"
        style={{
          padding: '32px 28px',
          borderRadius: 20,
          background: 'linear-gradient(135deg, rgba(245, 158, 11, 0.15), rgba(16, 185, 129, 0.1))',
          border: '1px solid rgba(245, 158, 11, 0.3)',
          marginBottom: 30,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: 20,
        }}
      >
        <div style={{ maxWidth: 640 }}>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '4px 12px', borderRadius: 20, background: 'rgba(245, 158, 11, 0.2)', color: 'var(--accent-dark)', fontWeight: 800, fontSize: 12, marginBottom: 12 }}>
            <TrophyIcon size={16} /> JONLI YAKSHANBA TURNIRLARI
          </div>
          <h1 style={{ fontSize: 28, margin: '0 0 10px', fontWeight: 900 }}>
            Ona tili va Adabiyotidan Katta E-Sport Ligasi
          </h1>
          <p className="muted" style={{ margin: 0, fontSize: 15, lineHeight: 1.6 }}>
            Har yakshanba soat 20:00 da butun O'zbekiston bo'ylab o'quvchilar bir vaqtda bellashadilar.
            Real-vaqt reytingi, live animatsiya va qimmatbaho Premium obunalar!
          </p>
        </div>

        <div style={{ textAlign: 'center', background: 'var(--card)', padding: '18px 24px', borderRadius: 16, border: '1px solid var(--border)' }}>
          <span className="muted small" style={{ display: 'block', marginBottom: 4 }}>Keyingi Katta Turnir:</span>
          <strong style={{ fontSize: 20, color: 'var(--accent)', display: 'block' }}>Har Yakshanba 20:00</strong>
          <span style={{ fontSize: 12, color: '#10b981', fontWeight: 700 }}>🟢 Jonli translyatsiya</span>
        </div>
      </div>

      {/* Prize Fund Highlights */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 16, marginBottom: 30 }}>
        <div className="card" style={{ padding: 20, textAlign: 'center', border: '1px solid rgba(245, 158, 11, 0.3)' }}>
          <div style={{ fontSize: 32, marginBottom: 8 }}>🥇</div>
          <strong style={{ fontSize: 16, display: 'block', color: 'var(--accent)' }}>1-O'RIN: Oltin Kubok</strong>
          <span className="muted small" style={{ marginTop: 4, display: 'block' }}>
            1 oylik bepul Premium obuna + Profilga Oltin Kubok nishoni + Sertifikat
          </span>
        </div>

        <div className="card" style={{ padding: 20, textAlign: 'center', border: '1px solid var(--border)' }}>
          <div style={{ fontSize: 32, marginBottom: 8 }}>🥈</div>
          <strong style={{ fontSize: 16, display: 'block' }}>2-O'RIN: Kumush Medal</strong>
          <span className="muted small" style={{ marginTop: 4, display: 'block' }}>
            1 oylik bepul Starter obuna + Kumush medal nishoni
          </span>
        </div>

        <div className="card" style={{ padding: 20, textAlign: 'center', border: '1px solid var(--border)' }}>
          <div style={{ fontSize: 32, marginBottom: 8 }}>🥉</div>
          <strong style={{ fontSize: 16, display: 'block' }}>3-O'RIN: Bronza Medal</strong>
          <span className="muted small" style={{ marginTop: 4, display: 'block' }}>
            1 oylik bepul Starter obuna + Bronza medal nishoni
          </span>
        </div>
      </div>

      {/* Tournaments List */}
      <h2 style={{ fontSize: 20, marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
        <AwardIcon size={20} style={{ color: 'var(--accent)' }} /> Turnirlar jadvali
      </h2>

      {loading ? (
        <div className="card" style={{ padding: 30, textAlign: 'center' }}>Yuklanmoqda...</div>
      ) : tournaments.length === 0 ? (
        <div className="card" style={{ padding: 40, textAlign: 'center' }}>
          <p className="muted" style={{ margin: 0 }}>Hozircha rejalashtirilgan turnirlar mavjud emas. Tez kunda yangi turnir e'lon qilinadi!</p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {tournaments.map((t) => {
            const isLive = t.status === 'live';
            const isFinished = t.status === 'finished';

            return (
              <div
                key={t.id}
                className="card"
                style={{
                  padding: 24,
                  borderRadius: 16,
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  flexWrap: 'wrap',
                  gap: 16,
                  border: isLive ? '2px solid #ef4444' : '1px solid var(--border)',
                }}
              >
                <div style={{ minWidth: 260, flex: 1 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                    {isLive ? (
                      <span style={{ background: '#ef4444', color: '#fff', fontSize: 11, fontWeight: 800, padding: '3px 8px', borderRadius: 6 }}>
                        🔴 JONLI (LIVE)
                      </span>
                    ) : isFinished ? (
                      <span style={{ background: 'var(--muted)', color: '#fff', fontSize: 11, fontWeight: 700, padding: '3px 8px', borderRadius: 6 }}>
                        YAKUNLANGAN
                      </span>
                    ) : (
                      <span style={{ background: 'rgba(245, 158, 11, 0.2)', color: 'var(--accent-dark)', fontSize: 11, fontWeight: 800, padding: '3px 8px', borderRadius: 6 }}>
                        ⏳ KUTILMOQDA
                      </span>
                    )}
                    <h3 style={{ margin: 0, fontSize: 18, fontWeight: 800 }}>{t.title}</h3>
                  </div>

                  <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', fontSize: 13, color: 'var(--muted)', marginTop: 8 }}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                      <ClockIcon size={14} /> {new Date(t.scheduled_at).toLocaleString('uz-UZ', { dateStyle: 'medium', timeStyle: 'short' })}
                    </span>
                    <span>⏱ {t.duration_minutes} daqiqa</span>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                      <UserIcon size={14} /> {t.participants_count} nafar qatnashuvchi
                    </span>
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  {t.user_joined && (
                    <span style={{ fontSize: 12, fontWeight: 700, color: '#10b981' }}>
                      ✓ Siz ro'yxatdansiz {t.user_rank ? `(${t.user_rank}-o'rin, ${t.user_score} ball)` : ''}
                    </span>
                  )}

                  <Link
                    to={`/tournaments/${t.id}/live`}
                    className={`btn ${isLive ? 'primary btn-glow' : 'secondary'}`}
                    style={{ textDecoration: 'none', padding: '10px 20px', fontWeight: 800 }}
                  >
                    {isLive ? "🚀 Turnir xonasiga kirish (Live)" : "Turnir xonasini ochish →"}
                  </Link>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
