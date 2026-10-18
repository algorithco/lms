import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Mic,
  Clock,
  Sparkles,
  ArrowRight,
  RefreshCw,
} from 'lucide-react';
import { SpeakingApi, type SpeakingTopicItem } from '../lib/api';
import TiltCard from '../components/TiltCard';
import SubjectSwitcher from '../components/SubjectSwitcher';

export default function SpeakingTopics() {
  const [topics, setTopics] = useState<SpeakingTopicItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedPart, setSelectedPart] = useState<'all' | 'part1' | 'part2' | 'part3' | 'multilevel'>('all');

  const fetchTopics = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await SpeakingApi.topics(selectedPart !== 'all' ? { part: selectedPart } : undefined);
      setTopics(res.results || []);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Speaking mavzularini yuklashda xatolik.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTopics();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedPart]);

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto', paddingBottom: 60 }}>
      {/* Top Banner */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 16, marginBottom: 24 }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
            <span className="badge blue" style={{ fontSize: '0.8rem', padding: '4px 10px' }}>
              <Sparkles size={13} style={{ marginRight: 4 }} /> Gemini Multimodal Speech AI
            </span>
            <span className="badge green" style={{ fontSize: '0.8rem', padding: '4px 10px' }}>
              🎯 4 Mezonli IELTS Scoring (FC, LR, GRA, PR)
            </span>
          </div>
          <h1 style={{ fontSize: '1.85rem', fontWeight: 900, margin: 0, color: 'var(--ink)' }}>
            🎙️ IELTS & Multi-level AI Speaking Simulyatori
          </h1>
          <p className="muted" style={{ fontSize: '0.92rem', marginTop: 4 }}>
            Rasmiy Part 1, Part 2 (Cue Card 1 daqiqa tayyorgarlik) va Part 3 savollariga ovozli javob bering.
            Sun'iy intellekt nutqingizni eshitib, Band 1.0–9.0 baho va batafsil tahlil chiqaradi.
          </p>
        </div>

        <div>
          <SubjectSwitcher size="sm" />
        </div>
      </div>

      {/* Part Filter Tabs */}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 20 }}>
        {[
          { id: 'all', label: 'Barcha bo\'limlar' },
          { id: 'part1', label: 'Part 1: Introduction' },
          { id: 'part2', label: 'Part 2: Cue Card (2 min speech)' },
          { id: 'part3', label: 'Part 3: Discussion' },
          { id: 'multilevel', label: 'Multi-level CEFR' },
        ].map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setSelectedPart(tab.id as typeof selectedPart)}
            className={`btn sm ${selectedPart === tab.id ? 'primary' : 'ghost'}`}
            style={{ fontWeight: 700 }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Error / Loading */}
      {error && (
        <div className="card error" style={{ marginBottom: 20 }}>
          {error} <button className="btn sm ghost" onClick={fetchTopics}>Qayta urinish</button>
        </div>
      )}

      {loading ? (
        <div style={{ textAlign: 'center', padding: '60px 20px', color: 'var(--ink-muted)' }}>
          <RefreshCw size={28} className="animate-spin" style={{ margin: '0 auto 12px' }} />
          <div>Speaking savollari yuklanmoqda...</div>
        </div>
      ) : topics.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: '40px 20px' }}>
          <h3>Ushbu bo'limda hozircha mavzu yo'q</h3>
          <p className="muted">Boshqa bo'limni tanlang yoki keyinroq qaytib keling.</p>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(330px, 1fr))', gap: 18 }}>
          {topics.map((t) => (
            <TiltCard key={t.id} glare maxTilt={6} scale={1.02} style={{ borderRadius: 16, height: '100%' }}>
              <div
                className="card link-card"
                style={{
                  height: '100%',
                  margin: 0,
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'space-between',
                  padding: 20,
                  borderRadius: 16,
                  border: '1px solid rgba(255, 255, 255, 0.1)',
                  background: 'linear-gradient(180deg, rgba(30, 41, 59, 0.4) 0%, rgba(15, 23, 42, 0.6) 100%)',
                }}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, marginBottom: 12 }}>
                    <span
                      className="badge"
                      style={{
                        background:
                          t.part === 'part2'
                            ? 'rgba(99, 102, 241, 0.2)'
                            : t.part === 'part1'
                            ? 'rgba(59, 130, 246, 0.2)'
                            : 'rgba(245, 158, 11, 0.2)',
                        color:
                          t.part === 'part2'
                            ? '#A5B4FC'
                            : t.part === 'part1'
                            ? '#93C5FD'
                            : '#FDE047',
                        fontWeight: 700,
                        fontSize: '0.75rem',
                      }}
                    >
                      {t.part_label}
                    </span>

                    <span className="muted small" style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                      <Clock size={12} /> {t.speak_time_seconds}s
                    </span>
                  </div>

                  <h3 style={{ fontSize: '1.08rem', fontWeight: 800, margin: '0 0 10px 0', color: 'var(--ink)' }}>
                    {t.title}
                  </h3>

                  <p
                    className="muted"
                    style={{
                      fontSize: '0.86rem',
                      lineHeight: 1.5,
                      margin: '0 0 14px 0',
                      display: '-webkit-box',
                      WebkitLineClamp: 3,
                      WebkitBoxOrient: 'vertical',
                      overflow: 'hidden',
                    }}
                  >
                    {t.prompt}
                  </p>

                  {/* Bullet points for Part 2 */}
                  {t.bullet_points && t.bullet_points.length > 0 && (
                    <div style={{ marginBottom: 14, padding: '8px 12px', borderRadius: 8, background: 'rgba(0,0,0,0.2)' }}>
                      <span style={{ fontSize: '0.74rem', fontWeight: 800, color: 'var(--ink-muted)', textTransform: 'uppercase' }}>
                        You should say:
                      </span>
                      <ul style={{ margin: '4px 0 0 0', paddingLeft: 16, fontSize: '0.78rem', color: 'var(--ink)' }}>
                        {t.bullet_points.slice(0, 3).map((bp, i) => (
                          <li key={i}>{bp}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>

                <Link
                  to={`/speaking/practice/${t.id}`}
                  className="btn primary sm"
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: 6,
                    fontWeight: 800,
                    textDecoration: 'none',
                    marginTop: 8,
                  }}
                >
                  <Mic size={15} />
                  <span>Mashqni boshlash</span>
                  <ArrowRight size={14} />
                </Link>
              </div>
            </TiltCard>
          ))}
        </div>
      )}
    </div>
  );
}
