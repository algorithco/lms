import { useState, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Camera,
  CheckCircle2,
  XCircle,
  Sparkles,
  Zap,
  ArrowRight,
  RefreshCw,
  AlertCircle,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import confetti from 'canvas-confetti';
import { OmrApi, type OmrScanResponse } from '../lib/api';

export default function ScanOMR() {
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [mockCode, setMockCode] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [result, setResult] = useState<OmrScanResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filterMode, setFilterMode] = useState<'all' | 'correct' | 'wrong'>('all');

  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const selected = e.target.files[0];
      setFile(selected);
      setPreviewUrl(URL.createObjectURL(selected));
      setError(null);
      setResult(null);
    }
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const selected = e.dataTransfer.files[0];
      setFile(selected);
      setPreviewUrl(URL.createObjectURL(selected));
      setError(null);
      setResult(null);
    }
  };

  const handleScan = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      setError("Iltimos, avval titul varaqa rasmini yuklang.");
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);

    const fd = new FormData();
    fd.append('image', file);
    if (mockCode.trim()) {
      fd.append('mock_code', mockCode.trim());
    }

    try {
      const res = await OmrApi.scan(fd);
      if (res.ok) {
        setResult(res);
        if (res.is_passed) {
          try {
            confetti({
              particleCount: 80,
              spread: 70,
              origin: { y: 0.6 },
              colors: ['#10B981', '#34D399', '#F59E0B'],
            });
          } catch {
            /* ignore */
          }
        }
      } else {
        setError(res.error || "Titul varaqani tahlil qilishda xatolik yuz berdi.");
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Server bilan bog'lanishda xatolik yuz berdi.");
    } finally {
      setLoading(false);
    }
  };

  const filteredBreakdown = (result?.breakdown || []).filter((item) => {
    if (filterMode === 'correct') return item.is_correct;
    if (filterMode === 'wrong') return !item.is_correct;
    return true;
  });

  return (
    <div style={{ maxWidth: 1000, margin: '0 auto', paddingBottom: 60 }}>
      {/* Top Banner */}
      <div style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
          <span className="badge blue" style={{ fontSize: '0.8rem', padding: '4px 10px' }}>
            <Sparkles size={13} style={{ marginRight: 4 }} /> Vision OMR AI
          </span>
          <span className="badge green" style={{ fontSize: '0.8rem', padding: '4px 10px' }}>
            ⚡ 2-3 soniyada natija
          </span>
        </div>
        <h1 style={{ fontSize: '1.85rem', fontWeight: 900, margin: 0, color: 'var(--ink)' }}>
          📷 Titul varaqa (Answer Sheet) avto-skaneri
        </h1>
        <p className="muted" style={{ fontSize: '0.92rem', marginTop: 4 }}>
          BMB Milliy sertifikat, Attestatsiya va IELTS javoblar varaqasining rasmini yuklang.
          Tizim belgilangan doirachalarni (A, B, C, D) avtomatik aniqlab, to'g'ri kalitlar bilan solishtiradi.
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: result ? '1fr' : 'repeat(auto-fit, minmax(320px, 1fr))', gap: 24 }}>
        {/* Upload Box */}
        <div className="card" style={{ padding: 24, borderRadius: 16 }}>
          <h3 style={{ margin: '0 0 16px 0', fontSize: '1.05rem', fontWeight: 800 }}>
            1. Javoblar varaqasi rasmi
          </h3>

          <div
            onDragOver={(e) => e.preventDefault()}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            style={{
              border: '2px dashed rgba(255, 255, 255, 0.18)',
              borderRadius: 14,
              padding: previewUrl ? 16 : 36,
              textAlign: 'center',
              cursor: 'pointer',
              background: previewUrl ? 'rgba(0,0,0,0.3)' : 'rgba(255, 255, 255, 0.02)',
              transition: 'all 0.2s ease',
              marginBottom: 16,
            }}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              capture="environment"
              style={{ display: 'none' }}
              onChange={handleFileChange}
            />

            {previewUrl ? (
              <div>
                <img
                  src={previewUrl}
                  alt="Titul varaqasi"
                  style={{
                    maxHeight: 260,
                    maxWidth: '100%',
                    objectFit: 'contain',
                    borderRadius: 8,
                    marginBottom: 12,
                    boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
                  }}
                />
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6, fontSize: '0.85rem', color: '#6EE7B7' }}>
                  <CheckCircle2 size={16} /> Rasm tanlandi ({file?.name})
                </div>
                <span className="muted small">O'zgartirish uchun qayta bosing</span>
              </div>
            ) : (
              <div>
                <div
                  style={{
                    width: 54,
                    height: 54,
                    borderRadius: 16,
                    background: 'rgba(59, 130, 246, 0.15)',
                    color: '#60A5FA',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    margin: '0 auto 12px',
                  }}
                >
                  <Camera size={26} />
                </div>
                <div style={{ fontWeight: 700, fontSize: '0.98rem', marginBottom: 4 }}>
                  Suratga oling yoki rasmni bu yerga tashlang
                </div>
                <div className="muted small" style={{ maxWidth: 280, margin: '0 auto' }}>
                  Kamera yoki galereyadan titul varaq fotosini yuklang (JPG, PNG, HEIC)
                </div>
              </div>
            )}
          </div>

          {/* Optional Mock Code */}
          <div style={{ marginBottom: 16 }}>
            <label style={{ display: 'block', fontSize: '0.84rem', fontWeight: 700, marginBottom: 6 }}>
              Test yoki Mock kodi (Ixtiyoriy, tituldan avtomatik ham o'qiladi):
            </label>
            <input
              type="text"
              placeholder="Masalan: MOCK-101 yoki #2026"
              value={mockCode}
              onChange={(e) => setMockCode(e.target.value)}
              style={{
                width: '100%',
                padding: '10px 14px',
                borderRadius: 10,
                border: '1px solid rgba(255, 255, 255, 0.12)',
                background: 'rgba(0,0,0,0.25)',
                color: 'var(--ink)',
                fontSize: '0.9rem',
              }}
            />
          </div>

          {error && (
            <div
              style={{
                padding: '12px 14px',
                borderRadius: 10,
                background: 'rgba(244, 63, 94, 0.15)',
                border: '1px solid #F43F5E',
                color: '#FDA4AF',
                fontSize: '0.85rem',
                marginBottom: 16,
                display: 'flex',
                alignItems: 'center',
                gap: 8,
              }}
            >
              <AlertCircle size={16} />
              <span>{error}</span>
            </div>
          )}

          <button
            type="button"
            disabled={loading || !file}
            onClick={handleScan}
            className="btn primary"
            style={{
              width: '100%',
              padding: '12px',
              fontWeight: 800,
              fontSize: '0.95rem',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 8,
            }}
          >
            {loading ? (
              <>
                <RefreshCw size={18} className="animate-spin" />
                Doirachalar skanerlanmoqda...
              </>
            ) : (
              <>
                <Zap size={18} />
                Titul varaqni tekshirish
              </>
            )}
          </button>
        </div>

        {/* Instructions Card (shown when no result) */}
        {!result && (
          <div className="card" style={{ padding: 24, borderRadius: 16 }}>
            <h3 style={{ margin: '0 0 14px 0', fontSize: '1.05rem', fontWeight: 800 }}>
              💡 Aniq tahlil uchun yo'riqnoma
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div style={{ display: 'flex', gap: 12 }}>
                <div style={{ width: 28, height: 28, borderRadius: 8, background: 'rgba(16, 185, 129, 0.2)', color: '#34D399', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 800, flexShrink: 0 }}>
                  1
                </div>
                <div>
                  <strong style={{ fontSize: '0.9rem', display: 'block' }}>Yorug'lik va burchak</strong>
                  <span className="muted small">Varaq ustiga soya tushmasin. Kamerani qog'ozga to'g'ri (90 gradus) tuting.</span>
                </div>
              </div>

              <div style={{ display: 'flex', gap: 12 }}>
                <div style={{ width: 28, height: 28, borderRadius: 8, background: 'rgba(59, 130, 246, 0.2)', color: '#60A5FA', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 800, flexShrink: 0 }}>
                  2
                </div>
                <div>
                  <strong style={{ fontSize: '0.9rem', display: 'block' }}>Doirachalar to'ldirilishi</strong>
                  <span className="muted small">Katakchalar to'liq ko'k yoki qora ruchka/qalamda bo'yalgan bo'lishi lozim.</span>
                </div>
              </div>

              <div style={{ display: 'flex', gap: 12 }}>
                <div style={{ width: 28, height: 28, borderRadius: 8, background: 'rgba(245, 158, 11, 0.2)', color: '#FBBF24', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 800, flexShrink: 0 }}>
                  3
                </div>
                <div>
                  <strong style={{ fontSize: '0.9rem', display: 'block' }}>Telegram bot orqali tekshirish</strong>
                  <span className="muted small">
                    Botimizga ham fotosuratni to'g'ridan-to'g'ri yuborishingiz mumkin: <b>@uz_essaygrader_bot</b> (📷 Titul varaqni tekshirish).
                  </span>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* RESULT REPORT SECTION */}
      <AnimatePresence>
        {result && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            transition={{ duration: 0.3 }}
            style={{ marginTop: 28 }}
          >
            {/* Scoreboard Cards */}
            <div
              className="card"
              style={{
                background: result.is_passed
                  ? 'linear-gradient(135deg, rgba(16, 185, 129, 0.15) 0%, rgba(5, 150, 105, 0.05) 100%)'
                  : 'linear-gradient(135deg, rgba(244, 63, 94, 0.15) 0%, rgba(225, 29, 72, 0.05) 100%)',
                borderColor: result.is_passed ? 'rgba(16, 185, 129, 0.4)' : 'rgba(244, 63, 94, 0.4)',
                borderRadius: 18,
                padding: 24,
                marginBottom: 24,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap', marginBottom: 20 }}>
                <div>
                  <span className="badge blue" style={{ marginBottom: 6 }}>
                    {result.mock_code} · {result.subject === 'english' ? '🇬🇧 English' : '🇺🇿 Ona tili'}
                  </span>
                  <h2 style={{ margin: 0, fontSize: '1.45rem', fontWeight: 900 }}>
                    {result.test_title}
                  </h2>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <div
                    style={{
                      padding: '10px 18px',
                      borderRadius: 14,
                      background: result.is_passed ? 'rgba(16, 185, 129, 0.25)' : 'rgba(244, 63, 94, 0.25)',
                      border: `2px solid ${result.is_passed ? '#10B981' : '#F43F5E'}`,
                      textAlign: 'center',
                    }}
                  >
                    <div style={{ fontSize: '0.75rem', fontWeight: 800, textTransform: 'uppercase', color: result.is_passed ? '#6EE7B7' : '#FDA4AF' }}>
                      {result.is_passed ? "Muvaffaqiyatli o'tdi" : "Yetarli ball emas"}
                    </div>
                    <div style={{ fontSize: '1.35rem', fontWeight: 900, color: '#fff' }}>
                      {result.grade}
                    </div>
                  </div>
                </div>
              </div>

              {/* 4 Metrics Tiles */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 12 }}>
                <div style={{ padding: 14, borderRadius: 12, background: 'rgba(0,0,0,0.25)' }}>
                  <span className="muted small">To'g'ri javoblar</span>
                  <div style={{ fontSize: '1.4rem', fontWeight: 900, color: '#34D399' }}>
                    {result.correct_count} / {result.total_questions}
                  </div>
                </div>

                <div style={{ padding: 14, borderRadius: 12, background: 'rgba(0,0,0,0.25)' }}>
                  <span className="muted small">To'plangan ball</span>
                  <div style={{ fontSize: '1.4rem', fontWeight: 900, color: '#60A5FA' }}>
                    {result.total_score} / {result.max_score} ({result.percentage}%)
                  </div>
                </div>

                <div style={{ padding: 14, borderRadius: 12, background: 'rgba(0,0,0,0.25)' }}>
                  <span className="muted small">Noto'g'ri / Bo'sh</span>
                  <div style={{ fontSize: '1.4rem', fontWeight: 900, color: '#F87171' }}>
                    {result.incorrect_count} xato · {result.blank_count} bo'sh
                  </div>
                </div>

                <div style={{ padding: 14, borderRadius: 12, background: 'rgba(0,0,0,0.25)' }}>
                  <span className="muted small">Gamification XP</span>
                  <div style={{ fontSize: '1.4rem', fontWeight: 900, color: '#FBBF24' }}>
                    +{result.xp_earned || 25} XP 🔥
                  </div>
                </div>
              </div>
            </div>

            {/* Question Breakdown Filter & Grid */}
            <div className="card" style={{ padding: 24, borderRadius: 18 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16, flexWrap: 'wrap', gap: 10 }}>
                <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 800 }}>
                  Savollar bo'yicha batafsil tahlil
                </h3>
                <div style={{ display: 'flex', gap: 6 }}>
                  <button
                    type="button"
                    onClick={() => setFilterMode('all')}
                    className={`btn sm ${filterMode === 'all' ? 'primary' : 'ghost'}`}
                  >
                    Barchasi ({result.breakdown.length})
                  </button>
                  <button
                    type="button"
                    onClick={() => setFilterMode('correct')}
                    className={`btn sm ${filterMode === 'correct' ? 'primary' : 'ghost'}`}
                    style={{ color: filterMode === 'correct' ? '#fff' : '#34D399' }}
                  >
                    To'g'ri ({result.correct_count})
                  </button>
                  <button
                    type="button"
                    onClick={() => setFilterMode('wrong')}
                    className={`btn sm ${filterMode === 'wrong' ? 'primary' : 'ghost'}`}
                    style={{ color: filterMode === 'wrong' ? '#fff' : '#F87171' }}
                  >
                    Xatolar ({result.incorrect_count + result.blank_count})
                  </button>
                </div>
              </div>

              {/* Pill List */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 10 }}>
                {filteredBreakdown.map((item) => (
                  <div
                    key={item.question_number}
                    style={{
                      padding: '12px 14px',
                      borderRadius: 12,
                      background: item.is_correct
                        ? 'rgba(16, 185, 129, 0.08)'
                        : 'rgba(244, 63, 94, 0.08)',
                      border: `1px solid ${item.is_correct ? 'rgba(16, 185, 129, 0.25)' : 'rgba(244, 63, 94, 0.25)'}`,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      gap: 8,
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <span
                        style={{
                          width: 28,
                          height: 28,
                          borderRadius: 8,
                          background: item.is_correct ? 'rgba(16, 185, 129, 0.25)' : 'rgba(244, 63, 94, 0.25)',
                          color: item.is_correct ? '#34D399' : '#F87171',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          fontWeight: 800,
                          fontSize: '0.85rem',
                        }}
                      >
                        {item.question_number}
                      </span>
                      <div>
                        <div style={{ fontSize: '0.85rem', fontWeight: 700 }}>
                          Siz: <b>{item.selected_answer}</b> · To'g'ri: <b>{item.correct_answer}</b>
                        </div>
                        <span className="muted small" style={{ fontSize: '0.74rem' }}>
                          {item.points}/{item.max_points} ball
                        </span>
                      </div>
                    </div>

                    <div>
                      {item.is_correct ? (
                        <CheckCircle2 size={18} color="#10B981" />
                      ) : (
                        <XCircle size={18} color="#F43F5E" />
                      )}
                    </div>
                  </div>
                ))}
              </div>

              {/* Action Buttons */}
              <div style={{ display: 'flex', gap: 12, marginTop: 24, flexWrap: 'wrap' }}>
                <button
                  type="button"
                  onClick={() => {
                    setResult(null);
                    setFile(null);
                    setPreviewUrl(null);
                  }}
                  className="btn ghost"
                  style={{ display: 'flex', alignItems: 'center', gap: 6 }}
                >
                  <RefreshCw size={15} /> Boshqa varaqni tekshirish
                </button>
                <Link
                  to="/tests"
                  className="btn primary"
                  style={{ display: 'flex', alignItems: 'center', gap: 6, textDecoration: 'none' }}
                >
                  <span>Testlar bazasiga o'tish</span>
                  <ArrowRight size={15} />
                </Link>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
