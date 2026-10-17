import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../lib/api';
import { AwardIcon, ClockIcon, TrophyIcon, UserIcon } from '../components/icons';
import { useTranslation } from '../i18n/useTranslation';

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
  const { t } = useTranslation();
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
            <TrophyIcon size={16} /> {t('tournaments_live_sunday')}
          </div>
          <h1 style={{ fontSize: 28, margin: '0 0 10px', fontWeight: 900 }}>
            {t('tournaments_hero_title')}
          </h1>
          <p className="muted" style={{ margin: 0, fontSize: 15, lineHeight: 1.6 }}>
            {t('tournaments_hero_desc')}
          </p>
        </div>

        <div style={{ textAlign: 'center', background: 'var(--card)', padding: '18px 24px', borderRadius: 16, border: '1px solid var(--border)' }}>
          <span className="muted small" style={{ display: 'block', marginBottom: 4 }}>{t('tournaments_next_label')}</span>
          <strong style={{ fontSize: 20, color: 'var(--accent)', display: 'block' }}>{t('tournaments_next_schedule')}</strong>
          <span style={{ fontSize: 12, color: '#10b981', fontWeight: 700 }}>{t('tournaments_live_stream')}</span>
        </div>
      </div>

      {/* Prize Fund Highlights */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 16, marginBottom: 30 }}>
        <div className="card" style={{ padding: 20, textAlign: 'center', border: '1px solid rgba(245, 158, 11, 0.3)' }}>
          <div style={{ fontSize: 32, marginBottom: 8 }}>🥇</div>
          <strong style={{ fontSize: 16, display: 'block', color: 'var(--accent)' }}>{t('tournaments_prize_1_title')}</strong>
          <span className="muted small" style={{ marginTop: 4, display: 'block' }}>
            {t('tournaments_prize_1_desc')}
          </span>
        </div>

        <div className="card" style={{ padding: 20, textAlign: 'center', border: '1px solid var(--border)' }}>
          <div style={{ fontSize: 32, marginBottom: 8 }}>🥈</div>
          <strong style={{ fontSize: 16, display: 'block' }}>{t('tournaments_prize_2_title')}</strong>
          <span className="muted small" style={{ marginTop: 4, display: 'block' }}>
            {t('tournaments_prize_2_desc')}
          </span>
        </div>

        <div className="card" style={{ padding: 20, textAlign: 'center', border: '1px solid var(--border)' }}>
          <div style={{ fontSize: 32, marginBottom: 8 }}>🥉</div>
          <strong style={{ fontSize: 16, display: 'block' }}>{t('tournaments_prize_3_title')}</strong>
          <span className="muted small" style={{ marginTop: 4, display: 'block' }}>
            {t('tournaments_prize_3_desc')}
          </span>
        </div>
      </div>

      {/* Tournaments List */}
      <h2 style={{ fontSize: 20, marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
        <AwardIcon size={20} style={{ color: 'var(--accent)' }} /> {t('tournaments_table_title')}
      </h2>

      {loading ? (
        <div className="card" style={{ padding: 30, textAlign: 'center' }}>...</div>
      ) : tournaments.length === 0 ? (
        <div className="card" style={{ padding: 40, textAlign: 'center' }}>
          <p className="muted" style={{ margin: 0 }}>{t('tournaments_empty')}</p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {tournaments.map((tItem) => {
            const isLive = tItem.status === 'live';
            const isFinished = tItem.status === 'finished';

            return (
              <div
                key={tItem.id}
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
                        {t('tournaments_status_live')}
                      </span>
                    ) : isFinished ? (
                      <span style={{ background: 'var(--muted)', color: '#fff', fontSize: 11, fontWeight: 700, padding: '3px 8px', borderRadius: 6 }}>
                        {t('tournaments_status_finished')}
                      </span>
                    ) : (
                      <span style={{ background: 'rgba(245, 158, 11, 0.2)', color: 'var(--accent-dark)', fontSize: 11, fontWeight: 800, padding: '3px 8px', borderRadius: 6 }}>
                        {t('tournaments_status_upcoming')}
                      </span>
                    )}
                    <h3 style={{ margin: 0, fontSize: 18, fontWeight: 800 }}>{tItem.title}</h3>
                  </div>

                  <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', fontSize: 13, color: 'var(--muted)', marginTop: 8 }}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                      <ClockIcon size={14} /> {new Date(tItem.scheduled_at).toLocaleString('uz-UZ', { dateStyle: 'medium', timeStyle: 'short' })}
                    </span>
                    <span>⏱ {tItem.duration_minutes} {t('tournaments_minutes')}</span>
                    <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                      <UserIcon size={14} /> {tItem.participants_count} {t('tournaments_participants')}
                    </span>
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  {tItem.user_joined && (
                    <span style={{ fontSize: 12, fontWeight: 700, color: '#10b981' }}>
                      {t('tournaments_you_registered')} {tItem.user_rank ? `(${tItem.user_rank}-o'rin, ${tItem.user_score} ball)` : ''}
                    </span>
                  )}

                  <Link
                    to={`/tournaments/${tItem.id}/live`}
                    className={`btn ${isLive ? 'primary btn-glow' : 'secondary'}`}
                    style={{ textDecoration: 'none', padding: '10px 20px', fontWeight: 800 }}
                  >
                    {isLive ? t('tournaments_btn_enter_live') : t('tournaments_btn_open')}
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
