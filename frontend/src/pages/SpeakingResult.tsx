import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  Sparkles,
  ArrowLeft,
  RefreshCw,
} from 'lucide-react';
import confetti from 'canvas-confetti';
import { SpeakingApi, type SpeakingSubmissionDetail } from '../lib/api';

export default function SpeakingResult() {
  const { id } = useParams<{ id: string }>();
  const [sub, setSub] = useState<SpeakingSubmissionDetail | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    SpeakingApi.submission(id)
      .then((res) => {
        setSub(res);
        try {
          confetti({
            particleCount: 80,
            spread: 70,
            origin: { y: 0.6 },
            colors: ['#6366F1', '#818CF8', '#10B981', '#F59E0B'],
          });
        } catch {
          /* ignore */
        }
      })
      .catch((e: unknown) => {
        setError(e instanceof Error ? e.message : "Natijani yuklashda xatolik.");
      })
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: '80px 20px', color: 'var(--ink-muted)' }}>
        <RefreshCw size={32} className="animate-spin" style={{ margin: '0 auto 12px' }} />
        <div>Speaking natijalari yuklanmoqda...</div>
      </div>
    );
  }

  if (error || !sub) {
    return (
      <div className="card error" style={{ maxWidth: 600, margin: '40px auto' }}>
        <h3>Xatolik yuz berdi</h3>
        <p>{error || "Natija topilmadi."}</p>
        <Link to="/speaking" className="btn ghost sm">
          ← Speaking ro'yxatiga qaytish
        </Link>
      </div>
    );
  }

  const criteria = [
    {
      key: 'fc',
      title: 'Fluency & Coherence',
      score: sub.fluency_score,
      desc: "Nutq ravonligi, fikrlar izchilligi va pauzalar darajasi.",
      color: '#60A5FA',
      bg: 'rgba(59, 130, 246, 0.15)',
    },
    {
      key: 'lr',
      title: 'Lexical Resource',
      score: sub.lexical_score,
      desc: "So'z boyligi, mavzuga xos terminlar va idiomalar qo'llanilishi.",
      color: '#34D399',
      bg: 'rgba(16, 185, 129, 0.15)',
    },
    {
      key: 'gra',
      title: 'Grammar Range & Accuracy',
      score: sub.grammar_score,
      desc: "Murakkab gap qurilmalari va grammatik xatolarning yo'qligi.",
      color: '#FBBF24',
      bg: 'rgba(245, 158, 11, 0.15)',
    },
    {
      key: 'pr',
      title: 'Pronunciation',
      score: sub.pronunciation_score,
      desc: "Talaffuz ravshanligi, urg'u va so'zlashuv ohangdorligi.",
      color: '#C084FC',
      bg: 'rgba(168, 85, 247, 0.15)',
    },
  ];

  return (
    <div style={{ maxWidth: 900, margin: '0 auto', paddingBottom: 60 }}>
      {/* Top breadcrumb */}
      <div style={{ marginBottom: 16 }}>
        <Link to="/speaking" className="btn ghost sm" style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          <ArrowLeft size={14} /> Barcha speaking mavzulari
        </Link>
      </div>

      {/* Main Band Score Header Card */}
      <motion.div
        initial={{ opacity: 0, y: 15 }}
        animate={{ opacity: 1, y: 0 }}
        className="card"
        style={{
          background: 'linear-gradient(135deg, rgba(99, 102, 241, 0.2) 0%, rgba(79, 70, 229, 0.08) 100%)',
          borderColor: 'rgba(99, 102, 241, 0.4)',
          borderRadius: 20,
          padding: 28,
          marginBottom: 24,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: 20,
        }}
      >
        <div>
          <span className="badge blue" style={{ marginBottom: 8 }}>
            🎙️ {sub.part_label || "IELTS Speaking"} · Rasmiy baholash
          </span>
          <h1 style={{ fontSize: '1.65rem', fontWeight: 900, margin: '0 0 6px 0', color: 'var(--ink)' }}>
            {sub.topic_title}
          </h1>
          <span className="muted small">
            Davomiyligi: {sub.duration_seconds} soniya · Sana: {new Date(sub.created_at).toLocaleDateString()}
          </span>
        </div>

        {/* Big Overall Band Score Pill */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 14,
            padding: '16px 24px',
            borderRadius: 18,
            background: 'rgba(0,0,0,0.3)',
            border: '2px solid rgba(99, 102, 241, 0.5)',
          }}
        >
          <div
            style={{
              width: 54,
              height: 54,
              borderRadius: '50%',
              background: 'linear-gradient(135deg, #6366F1 0%, #4F46E5 100%)',
              color: '#fff',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontWeight: 900,
              fontSize: '1.35rem',
              boxShadow: '0 6px 20px rgba(99, 102, 241, 0.4)',
            }}
          >
            {sub.overall_band.toFixed(1)}
          </div>
          <div>
            <div style={{ fontSize: '0.8rem', fontWeight: 800, color: '#A5B4FC', textTransform: 'uppercase' }}>
              Overall Band
            </div>
            <div style={{ fontSize: '1.15rem', fontWeight: 900, color: '#fff' }}>
              {sub.overall_band >= 7.5
                ? "Yuqori daraja (C1)"
                : sub.overall_band >= 6.5
                ? "Yaxshi daraja (B2+)"
                : "O'rtacha daraja (B2)"}
            </div>
          </div>
        </div>
      </motion.div>

      {/* 4 Official IELTS Criteria Grid */}
      <h3 style={{ fontSize: '1.1rem', fontWeight: 800, marginBottom: 14 }}>
        📊 4 Ta Rasmiy IELTS Mezonlari Bo'yicha Ballar
      </h3>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 14, marginBottom: 24 }}>
        {criteria.map((c) => (
          <div
            key={c.key}
            className="card"
            style={{
              padding: 18,
              borderRadius: 16,
              background: c.bg,
              border: `1px solid ${c.color}40`,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
              <span style={{ fontSize: '0.82rem', fontWeight: 800, color: 'var(--ink)' }}>{c.title}</span>
              <span
                style={{
                  padding: '3px 8px',
                  borderRadius: 8,
                  background: 'rgba(0,0,0,0.3)',
                  color: c.color,
                  fontWeight: 900,
                  fontSize: '0.95rem',
                }}
              >
                {c.score.toFixed(1)}
              </span>
            </div>
            <p className="muted small" style={{ margin: 0, fontSize: '0.76rem', lineHeight: 1.4 }}>
              {c.desc}
            </p>
          </div>
        ))}
      </div>

      {/* Audio Playback & Transcript */}
      <div className="card" style={{ padding: 24, borderRadius: 18, marginBottom: 24 }}>
        <h3 style={{ margin: '0 0 12px 0', fontSize: '1.05rem', fontWeight: 800 }}>
          🎧 Sizning yozib olingan nutqingiz
        </h3>

        {sub.audio_url && (
          <div style={{ marginBottom: 16 }}>
            <audio src={sub.audio_url} controls style={{ width: '100%', borderRadius: 10 }} />
          </div>
        )}

        <div style={{ padding: '14px 16px', borderRadius: 12, background: 'rgba(0,0,0,0.25)', border: '1px solid rgba(255, 255, 255, 0.08)' }}>
          <span style={{ fontSize: '0.76rem', fontWeight: 800, color: '#A5B4FC', textTransform: 'uppercase', display: 'block', marginBottom: 6 }}>
            Ovoz matni (Verbatim Transcript):
          </span>
          <p style={{ margin: 0, fontSize: '0.92rem', lineHeight: 1.6, fontStyle: 'italic', color: 'var(--ink)' }}>
            "{sub.transcript || "Ovoz matni tahlili saqlanmagan."}"
          </p>
        </div>
      </div>

      {/* AI Examiner Detailed Feedback */}
      {sub.feedback && (
        <div className="card" style={{ padding: 24, borderRadius: 18, marginBottom: 24 }}>
          <h3 style={{ margin: '0 0 16px 0', fontSize: '1.1rem', fontWeight: 800, display: 'flex', alignItems: 'center', gap: 8 }}>
            <Sparkles size={18} color="#FBBF24" /> AI Examiner Tahlili va Tavsiyalari
          </h3>

          {sub.feedback.summary && (
            <div style={{ marginBottom: 18, padding: 14, borderRadius: 12, background: 'rgba(16, 185, 129, 0.1)', border: '1px solid rgba(16, 185, 129, 0.25)', color: '#D1FAE5', fontSize: '0.9rem', lineHeight: 1.5 }}>
              <b>Xulosa:</b> {sub.feedback.summary}
            </div>
          )}

          {/* Vocabulary Suggestions (Band 8+ upgrades) */}
          {sub.feedback.vocabulary_suggestions && sub.feedback.vocabulary_suggestions.length > 0 && (
            <div style={{ marginBottom: 20 }}>
              <h4 style={{ margin: '0 0 10px 0', fontSize: '0.95rem', fontWeight: 800, color: '#6EE7B7' }}>
                💎 Band 8+ Leksik tavsiyalar (So'zlarni boyitish):
              </h4>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 10 }}>
                {sub.feedback.vocabulary_suggestions.map((v, idx) => (
                  <div key={idx} style={{ padding: '10px 14px', borderRadius: 10, background: 'rgba(0,0,0,0.2)', border: '1px solid rgba(255, 255, 255, 0.08)' }}>
                    <div style={{ fontSize: '0.84rem' }}>
                      <span style={{ color: '#F87171' }}>"{v.original}"</span> → <strong style={{ color: '#34D399' }}>"{v.improved}"</strong>
                    </div>
                    {v.explanation && <span className="muted small" style={{ fontSize: '0.74rem' }}>{v.explanation}</span>}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Grammar corrections */}
          {sub.feedback.grammar_corrections && sub.feedback.grammar_corrections.length > 0 && (
            <div>
              <h4 style={{ margin: '0 0 10px 0', fontSize: '0.95rem', fontWeight: 800, color: '#F87171' }}>
                ✏️ Grammatik tuzatishlar:
              </h4>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {sub.feedback.grammar_corrections.map((g, idx) => (
                  <div key={idx} style={{ padding: '10px 14px', borderRadius: 10, background: 'rgba(244, 63, 94, 0.08)', border: '1px solid rgba(244, 63, 94, 0.2)' }}>
                    <div style={{ fontSize: '0.86rem' }}>
                      <span style={{ textDecoration: 'line-through', color: '#FDA4AF' }}>{g.incorrect}</span> → <strong style={{ color: '#34D399' }}>{g.corrected}</strong>
                    </div>
                    {g.rule && <span className="muted small" style={{ fontSize: '0.74rem' }}>Qoida: {g.rule}</span>}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Action footer */}
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        <Link to={`/speaking/practice/${sub.topic_id}`} className="btn primary" style={{ textDecoration: 'none' }}>
          🔄 Ushbu mavzuni qayta mashq qilish
        </Link>
        <Link to="/speaking" className="btn ghost" style={{ textDecoration: 'none' }}>
          Yangi speaking mavzulariga o'tish →
        </Link>
      </div>
    </div>
  );
}
