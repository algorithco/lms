import { useState, useRef, useEffect, useMemo } from 'react';
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
  BookOpen,
  Search,
  Check,
  FileText,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import confetti from 'canvas-confetti';
import { OmrApi, type OmrScanResponse, type OmrAvailableTest } from '../lib/api';

export default function ScanOMR() {
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [selectionMode, setSelectionMode] = useState<'select' | 'auto'>('select');
  const [availableTests, setAvailableTests] = useState<OmrAvailableTest[]>([]);
  const [selectedTestId, setSelectedTestId] = useState<number | null>(null);
  const [searchTestQuery, setSearchTestQuery] = useState<string>('');
  const [mockCode, setMockCode] = useState<string>('');
  const [codeNotFoundAlert, setCodeNotFoundAlert] = useState<{ detected: string } | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [result, setResult] = useState<OmrScanResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filterMode, setFilterMode] = useState<'all' | 'correct' | 'wrong'>('all');

  const fileInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    OmrApi.getAvailableTests()
      .then((data) => {
        if (data.ok && Array.isArray(data.tests)) {
          setAvailableTests(data.tests);
          if (data.tests.length > 0) {
            setSelectedTestId(data.tests[0].id);
            setMockCode(data.tests[0].mock_code || '');
          }
        }
      })
      .catch((err) => {
        console.warn('Available tests fetch failed:', err);
      });
  }, []);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const selected = e.target.files[0];
      setFile(selected);
      setPreviewUrl(URL.createObjectURL(selected));
      setError(null);
      setCodeNotFoundAlert(null);
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
      setCodeNotFoundAlert(null);
      setResult(null);
    }
  };

  const handleSelectTest = (id: number) => {
    setSelectedTestId(id);
    const found = availableTests.find((t) => t.id === id);
    if (found) {
      setMockCode(found.mock_code || '');
    }
    setCodeNotFoundAlert(null);
  };

  const filteredTests = useMemo(() => {
    const q = searchTestQuery.trim().toLowerCase();
    if (!q) return availableTests;
    return availableTests.filter((t) =>
      t.title.toLowerCase().includes(q) ||
      (t.mock_code && t.mock_code.toLowerCase().includes(q)) ||
      (t.access_code && t.access_code.toLowerCase().includes(q)) ||
      (t.subject && t.subject.toLowerCase().includes(q))
    );
  }, [availableTests, searchTestQuery]);

  const handleScan = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      setError("Iltimos, avval titul varaqa rasmini yuklang.");
      return;
    }

    setLoading(true);
    setError(null);
    setCodeNotFoundAlert(null);
    setResult(null);

    const fd = new FormData();
    fd.append('image', file);

    if (selectionMode === 'select' && selectedTestId) {
      fd.append('test_id', String(selectedTestId));
      if (mockCode.trim()) {
        fd.append('mock_code', mockCode.trim());
      }
    } else {
      if (mockCode.trim()) {
        fd.append('mock_code', mockCode.trim());
      }
    }

    try {
      const res = await OmrApi.scan(fd);
      if (res.code_not_found) {
        setCodeNotFoundAlert({ detected: res.detected_code || '' });
        setSelectionMode('select');
      } else if (res.ok) {
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

          {/* Test Selection Switch */}
          <div style={{ marginBottom: 16 }}>
            <label style={{ display: 'block', fontSize: '0.84rem', fontWeight: 700, marginBottom: 8 }}>
              2. Testni aniqlash usuli:
            </label>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 12 }}>
              <button
                type="button"
                onClick={() => setSelectionMode('select')}
                className={`btn sm ${selectionMode === 'select' ? 'primary' : 'ghost'}`}
                style={{
                  fontSize: '0.82rem',
                  padding: '8px 10px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 6,
                  borderRadius: 10,
                }}
              >
                <BookOpen size={14} />
                <span>Bazamizdagi test</span>
              </button>
              <button
                type="button"
                onClick={() => setSelectionMode('auto')}
                className={`btn sm ${selectionMode === 'auto' ? 'primary' : 'ghost'}`}
                style={{
                  fontSize: '0.82rem',
                  padding: '8px 10px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 6,
                  borderRadius: 10,
                }}
              >
                <Zap size={14} />
                <span>Tituldan aniqlash</span>
              </button>
            </div>

            {/* Warning if Vision OCR detected unknown code */}
            {codeNotFoundAlert && (
              <div
                style={{
                  padding: '12px 14px',
                  borderRadius: 10,
                  background: 'rgba(245, 158, 11, 0.15)',
                  border: '1px solid #F59E0B',
                  color: '#FDE68A',
                  fontSize: '0.85rem',
                  marginBottom: 14,
                  lineHeight: 1.45,
                }}
              >
                ⚠️ Tituldan o'qilgan <b>'{codeNotFoundAlert.detected || "Noma'lum"}'</b> kodi bo'yicha test bazada topilmadi.
                Iltimos, pastdagi ro'yxatdan qaysi testga javob berganingizni tanlang.
              </div>
            )}

            {selectionMode === 'select' ? (
              <div>
                {/* Search Box for Tests */}
                {availableTests.length > 5 && (
                  <div style={{ position: 'relative', marginBottom: 8 }}>
                    <Search size={14} style={{ position: 'absolute', left: 12, top: 12, color: 'var(--muted)' }} />
                    <input
                      type="text"
                      placeholder="Test nomi yoki kodini qidirish..."
                      value={searchTestQuery}
                      onChange={(e) => setSearchTestQuery(e.target.value)}
                      style={{
                        width: '100%',
                        padding: '10px 14px 10px 36px',
                        borderRadius: 12,
                        border: '1px solid var(--border)',
                        background: 'var(--card-2)',
                        color: 'var(--ink)',
                        fontSize: '0.86rem',
                        fontWeight: 600,
                        boxShadow: '0 1px 4px rgba(0,0,0,0.02)',
                      }}
                    />
                  </div>
                )}

                {/* Dropdown / Select List */}
                <select
                  value={selectedTestId || ''}
                  onChange={(e) => handleSelectTest(Number(e.target.value))}
                  style={{
                    width: '100%',
                    padding: '12px 14px',
                    borderRadius: 12,
                    border: '1.5px solid rgba(245, 158, 11, 0.4)',
                    background: 'var(--card-2)',
                    color: 'var(--ink)',
                    fontSize: '0.9rem',
                    fontWeight: 700,
                    outline: 'none',
                    cursor: 'pointer',
                    boxShadow: '0 2px 8px rgba(0, 0, 0, 0.04)',
                  }}
                >
                  {filteredTests.map((t) => {
                    const rawCode = String(t.mock_code || t.access_code || '').trim();
                    const cleanCode = rawCode.replace(/^#+/, '').trim();
                    let cleanTitle = String(t.title || '').replace(/#?#?[A-Z0-9_-]*(?:MOCK|CEFR|IELTS|BMB|DIAGNOSTIC)[A-Z0-9_-]*/gi, '').trim();
                    cleanTitle = cleanTitle.replace(/^[-—:() ]+|[-—:() ]+$/g, '').trim() || t.title;
                    return (
                      <option key={t.id} value={t.id} style={{ background: 'var(--card)', color: 'var(--ink)', padding: '8px' }}>
                        {cleanCode ? `[${cleanCode}] ` : ''}{cleanTitle} ({t.total_questions} talik)
                      </option>
                    );
                  })}
                </select>

                {/* Selected Test Badge */}
                {selectedTestId && (
                  <div
                    style={{
                      marginTop: 10,
                      padding: '10px 14px',
                      borderRadius: 10,
                      background: 'rgba(16, 185, 129, 0.08)',
                      border: '1px solid rgba(16, 185, 129, 0.25)',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 8,
                      fontSize: '0.85rem',
                      color: '#065F46',
                      fontWeight: 600,
                    }}
                  >
                    <Check size={16} color="#059669" />
                    <span>
                      Tanlangan: <b style={{ color: '#047857' }}>{mockCode ? `#${mockCode.replace(/^#+/, '')}` : 'Test tanlandi'}</b> · {filteredTests.find((t) => t.id === selectedTestId)?.total_questions || 40} ta savolli kalit bilan tekshiriladi
                    </span>
                  </div>
                )}
              </div>
            ) : (
              <div>
                <input
                  type="text"
                  placeholder="Ixtiyoriy test kodi (masalan: BMB-101 yoki IELTS-201)"
                  value={mockCode}
                  onChange={(e) => setMockCode(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '11px 14px',
                    borderRadius: 12,
                    border: '1px solid #CBD5E1',
                    background: '#FFFFFF',
                    color: '#0F172A',
                    fontSize: '0.88rem',
                    fontWeight: 600,
                    boxShadow: '0 1px 4px rgba(0,0,0,0.02)',
                  }}
                />
                <span className="muted small" style={{ display: 'block', marginTop: 4, fontSize: '0.76rem' }}>
                  Bo'sh qoldirsangiz, sun'iy intellekt titul varaqasining o'zidan kodni o'qiydi.
                </span>
              </div>
            )}
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
                  <strong style={{ fontSize: '0.9rem', display: 'block' }}>BMB va IELTS rasmiy kalitlari</strong>
                  <span className="muted small">
                    Bazadagi rasmiy #BMB-101, #IELTS-201 yoki #CEFR-301 testlarini tanlab, o'z natijangizni 2 soniyada tekshiring.
                  </span>
                </div>
              </div>

              <div style={{ display: 'flex', gap: 12 }}>
                <div style={{ width: 28, height: 28, borderRadius: 8, background: 'rgba(168, 85, 247, 0.2)', color: '#C084FC', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 800, flexShrink: 0 }}>
                  <FileText size={15} />
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
                <div style={{ padding: 14, borderRadius: 12, background: 'var(--card-2)', border: '1px solid var(--border)' }}>
                  <span className="muted small" style={{ color: 'var(--muted)', fontWeight: 600 }}>To'g'ri javoblar</span>
                  <div style={{ fontSize: '1.4rem', fontWeight: 900, color: '#059669' }}>
                    {result.correct_count} / {result.total_questions}
                  </div>
                </div>

                <div style={{ padding: 14, borderRadius: 12, background: 'var(--card-2)', border: '1px solid var(--border)' }}>
                  <span className="muted small" style={{ color: 'var(--muted)', fontWeight: 600 }}>To'plangan ball</span>
                  <div style={{ fontSize: '1.4rem', fontWeight: 900, color: '#2563EB' }}>
                    {result.total_score} / {result.max_score} ({result.percentage}%)
                  </div>
                </div>

                <div style={{ padding: 14, borderRadius: 12, background: 'var(--card-2)', border: '1px solid var(--border)' }}>
                  <span className="muted small" style={{ color: 'var(--muted)', fontWeight: 600 }}>Noto'g'ri / Bo'sh</span>
                  <div style={{ fontSize: '1.4rem', fontWeight: 900, color: '#DC2626' }}>
                    {result.incorrect_count} xato · {result.blank_count} bo'sh
                  </div>
                </div>

                <div style={{ padding: 14, borderRadius: 12, background: 'var(--card-2)', border: '1px solid var(--border)' }}>
                  <span className="muted small" style={{ color: 'var(--muted)', fontWeight: 600 }}>Gamification XP</span>
                  <div style={{ fontSize: '1.4rem', fontWeight: 900, color: '#D97706' }}>
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
                    Barchasi ({(result.breakdown || []).length})
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
                    Xatolar ({((result.incorrect_count || 0) + (result.blank_count || 0))})
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
