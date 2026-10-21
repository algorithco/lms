import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  AlertCircle,
  ArrowLeft,
  CheckCircle2,
  Copy,
  FileText,
  Plus,
  Sparkles,
  Trash2,
  Upload,
} from 'lucide-react';
import { type ConvertedQuestion, TestsApi } from '../lib/testing';

export default function TeacherAiConverter() {
  // Step 1: Upload state
  const [file, setFile] = useState<File | null>(null);
  const [subject, setSubject] = useState<'uzbek' | 'english'>('uzbek');
  const [converting, setConverting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Step 2: Editor state
  const [isConverted, setIsConverted] = useState(false);
  const [testTitle, setTestTitle] = useState('');
  const [timeLimit, setTimeLimit] = useState(60);
  const [readingPassage, setReadingPassage] = useState('');
  const [questions, setQuestions] = useState<ConvertedQuestion[]>([]);

  // Step 3: Saved state
  const [saving, setSaving] = useState(false);
  const [savedResult, setSavedResult] = useState<{
    test_id: number;
    mock_code: string;
    title: string;
  } | null>(null);
  const [copied, setCopied] = useState(false);

  // Handle file select
  const onFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setError(null);
    }
  };

  // Convert document with Vision AI
  const handleConvert = async () => {
    if (!file) {
      setError('Iltimos, test rasmi yoki PDF faylini tanlang.');
      return;
    }

    setConverting(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('subject', subject);

      const res = await TestsApi.aiConvertDocument(formData);
      if (res.success && res.data) {
        setTestTitle(res.data.test_title || 'AI Test');
        setReadingPassage(res.data.reading_passage || '');
        setQuestions(res.data.questions || []);
        setIsConverted(true);
      } else {
        throw new Error('Test ma\'lumotlarini ajratib olish imkoni bo\'lmadi.');
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Konvertatsiya jarayonida xatolik yuz berdi.';
      setError(msg);
    } finally {
      setConverting(false);
    }
  };

  // Question editing helpers
  const updateQuestionText = (index: number, text: string) => {
    setQuestions((prev) =>
      prev.map((q, i) => (i === index ? { ...q, text } : q))
    );
  };

  const updateChoiceText = (qIndex: number, code: string, text: string) => {
    setQuestions((prev) =>
      prev.map((q, i) => {
        if (i !== qIndex) return q;
        return {
          ...q,
          choices: q.choices.map((c) => (c.code === code ? { ...c, text } : c)),
        };
      })
    );
  };

  const setCorrectAnswer = (qIndex: number, code: string) => {
    setQuestions((prev) =>
      prev.map((q, i) => (i === qIndex ? { ...q, correct_answer: code } : q))
    );
  };

  const updateExplanation = (index: number, explanation: string) => {
    setQuestions((prev) =>
      prev.map((q, i) => (i === index ? { ...q, explanation } : q))
    );
  };

  const removeQuestion = (index: number) => {
    setQuestions((prev) =>
      prev.filter((_, i) => i !== index).map((q, idx) => ({ ...q, order: idx + 1 }))
    );
  };

  const addQuestion = () => {
    setQuestions((prev) => [
      ...prev,
      {
        order: prev.length + 1,
        text: 'Yangi savol matni',
        choices: [
          { code: 'A', text: 'Variant A' },
          { code: 'B', text: 'Variant B' },
          { code: 'C', text: 'Variant C' },
          { code: 'D', text: 'Variant D' },
        ],
        correct_answer: 'A',
        explanation: 'To\'g\'ri javob qoidasi.',
        question_type: 'single_choice',
      },
    ]);
  };

  // Save converted test to database
  const handleSave = async () => {
    if (!testTitle.trim()) {
      setError('Iltimos, test nomini kiriting.');
      return;
    }
    if (questions.length === 0) {
      setError('Kamida 1 ta savol bo\'lishi shart.');
      return;
    }

    setSaving(true);
    setError(null);

    try {
      const res = await TestsApi.aiSaveConverted({
        test_title: testTitle,
        subject,
        time_limit_minutes: timeLimit,
        reading_passage: readingPassage.trim() || undefined,
        questions,
      });

      if (res.success) {
        setSavedResult({
          test_id: res.test_id,
          mock_code: res.mock_code,
          title: res.title,
        });
      } else {
        throw new Error(res.message || 'Saqlashda xatolik yuz berdi.');
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Saqlashda xatolik yuz berdi.';
      setError(msg);
    } finally {
      setSaving(false);
    }
  };

  const copyCode = () => {
    if (!savedResult) return;
    navigator.clipboard.writeText(savedResult.mock_code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div style={{ maxWidth: 1000, margin: '0 auto', padding: '1.5rem 1rem 4rem' }}>
      {/* Top back navigation */}
      <div style={{ marginBottom: '1.5rem' }}>
        <Link
          to="/panel"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
            fontSize: '0.88rem',
            color: 'var(--muted)',
            textDecoration: 'none',
            fontWeight: 600,
          }}
        >
          <ArrowLeft size={16} /> Boshqaruv paneliga qaytish
        </Link>
      </div>

      {/* Header */}
      <div style={{ marginBottom: '2rem' }}>
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '4px 12px', borderRadius: 999, background: 'rgba(99, 102, 241, 0.1)', color: 'var(--accent, #6366f1)', fontSize: '0.8rem', fontWeight: 700, marginBottom: 8 }}>
          <Sparkles size={14} /> AI Vision Test Konvertor
        </div>
        <h1 style={{ margin: '0 0 6px 0', fontSize: '1.8rem', fontWeight: 900 }}>
          Qog'oz va PDF testdan 1 soniyada test yasash
        </h1>
        <p className="muted" style={{ margin: 0, fontSize: '0.95rem' }}>
          Kitob sahifasini rasmga oling yoki PDF faylni yuklang. Gemini Vision AI savollar va variantlarni avtomatik ajratib oladi.
        </p>
      </div>

      {error && (
        <div
          style={{
            padding: '12px 16px',
            borderRadius: 12,
            background: 'rgba(239, 68, 68, 0.12)',
            border: '1px solid rgba(239, 68, 68, 0.3)',
            color: '#ef4444',
            fontSize: '0.9rem',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            marginBottom: '1.5rem',
          }}
        >
          <AlertCircle size={18} />
          <span>{error}</span>
        </div>
      )}

      {/* STEP 1: UPLOAD SCREEN */}
      {!isConverted && (
        <div className="card" style={{ padding: '2rem', borderRadius: 16 }}>
          {/* Subject Switcher */}
          <div style={{ marginBottom: '1.5rem' }}>
            <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 700, marginBottom: 8 }}>
              1. Fan yo'nalishini tanlang:
            </label>
            <div style={{ display: 'inline-flex', gap: 8, padding: 4, background: 'var(--bg)', borderRadius: 12, border: '1px solid var(--border)' }}>
              <button
                type="button"
                className={`btn sm ${subject === 'uzbek' ? 'primary' : 'ghost'}`}
                onClick={() => setSubject('uzbek')}
                style={{ borderRadius: 8 }}
              >
                🇺🇿 Ona tili va Adabiyot (Milliy sertifikat)
              </button>
              <button
                type="button"
                className={`btn sm ${subject === 'english' ? 'primary' : 'ghost'}`}
                onClick={() => setSubject('english')}
                style={{ borderRadius: 8 }}
              >
                🇬🇧 English (IELTS & CEFR)
              </button>
            </div>
          </div>

          {/* File Dropzone */}
          <div style={{ marginBottom: '1.5rem' }}>
            <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 700, marginBottom: 8 }}>
              2. Test faylini yuklang (PDF yoki Rasm):
            </label>
            <label
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                padding: '3rem 1.5rem',
                border: '2px dashed var(--border)',
                borderRadius: 16,
                background: file ? 'rgba(99, 102, 241, 0.04)' : 'var(--bg)',
                cursor: 'pointer',
                transition: 'all 0.2s ease',
              }}
            >
              <input
                type="file"
                accept=".pdf,image/png,image/jpeg,image/jpg,image/webp"
                onChange={onFileChange}
                style={{ display: 'none' }}
              />
              <div
                style={{
                  width: 56,
                  height: 56,
                  borderRadius: 16,
                  background: 'rgba(99, 102, 241, 0.12)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'var(--accent, #6366f1)',
                  marginBottom: 12,
                }}
              >
                {file ? <FileText size={28} /> : <Upload size={28} />}
              </div>
              {file ? (
                <div style={{ textAlign: 'center' }}>
                  <span style={{ fontWeight: 800, fontSize: '1rem', display: 'block', color: 'var(--ink)' }}>
                    {file.name}
                  </span>
                  <span className="muted small">
                    {(file.size / 1024 / 1024).toFixed(2)} MB • O'zgartirish uchun yana bosing
                  </span>
                </div>
              ) : (
                <div style={{ textAlign: 'center' }}>
                  <span style={{ fontWeight: 800, fontSize: '1rem', display: 'block', color: 'var(--ink)', marginBottom: 4 }}>
                    Faylni bu yerga tashlang yoki tanlang
                  </span>
                  <span className="muted small">
                    Qo'llab-quvvatlanadi: PDF, PNG, JPG, JPEG, WEBP (15 MB gacha)
                  </span>
                </div>
              )}
            </label>
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <button
              type="button"
              className="btn primary"
              disabled={!file || converting}
              onClick={handleConvert}
              style={{ minHeight: 46, padding: '0 24px', fontWeight: 800 }}
            >
              {converting ? (
                <>
                  <Sparkles size={16} className="spin" /> AI hujjatni tahlil qilmoqda...
                </>
              ) : (
                <>
                  <Sparkles size={16} /> AI bilan testga aylantirish
                </>
              )}
            </button>
          </div>
        </div>
      )}

      {/* STEP 2: INTERACTIVE TEST EDITOR */}
      {isConverted && !savedResult && (
        <div>
          {/* Top Test Settings Card */}
          <div className="card" style={{ padding: '1.5rem', borderRadius: 16, marginBottom: '1.5rem' }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 16, marginBottom: 16 }}>
              <div>
                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 700, marginBottom: 4 }}>
                  Test nomi:
                </label>
                <input
                  type="text"
                  value={testTitle}
                  onChange={(e) => setTestTitle(e.target.value)}
                  placeholder="Masalan: Ona tili 10-sinf diagnostika testi"
                  style={{ width: '100%', fontWeight: 700 }}
                />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 700, marginBottom: 4 }}>
                  Vaqt me'yori (daqiqa):
                </label>
                <input
                  type="number"
                  min="5"
                  max="180"
                  value={timeLimit}
                  onChange={(e) => setTimeLimit(Number(e.target.value) || 60)}
                  style={{ width: '100%' }}
                />
              </div>
            </div>

            {/* Reading Passage Accordion */}
            <div>
              <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 700, marginBottom: 4 }}>
                Umumiy o'qish matni (Reading Passage) — ixtiyoriy:
              </label>
              <textarea
                rows={4}
                value={readingPassage}
                onChange={(e) => setReadingPassage(e.target.value)}
                placeholder="Agar testda bir nechta savolga daxldor umumiy matn bo'lsa, shu yerga kiriting..."
                style={{ width: '100%', fontSize: '0.9rem', lineHeight: 1.5 }}
              />
            </div>
          </div>

          {/* Questions Header */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
            <h2 style={{ margin: 0, fontSize: '1.3rem', fontWeight: 800 }}>
              Ajratib olingan savollar ({questions.length} ta)
            </h2>
            <button
              type="button"
              className="btn sm ghost"
              onClick={addQuestion}
              style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
            >
              <Plus size={16} /> Savol qo'shish
            </button>
          </div>

          {/* Questions List */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {questions.map((q, qIndex) => (
              <div
                key={qIndex}
                className="card"
                style={{
                  padding: '1.25rem',
                  borderRadius: 14,
                  border: '1px solid var(--border)',
                  background: 'var(--card)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
                  <span
                    className="badge"
                    style={{
                      background: 'rgba(99, 102, 241, 0.15)',
                      color: 'var(--accent, #6366f1)',
                      fontWeight: 800,
                      borderRadius: 8,
                      padding: '4px 10px',
                    }}
                  >
                    #{q.order}-savol
                  </span>
                  <button
                    type="button"
                    className="btn ghost sm"
                    onClick={() => removeQuestion(qIndex)}
                    title="Savolni o'chirish"
                    style={{ color: '#ef4444' }}
                  >
                    <Trash2 size={16} />
                  </button>
                </div>

                {/* Question Text */}
                <div style={{ marginBottom: 12 }}>
                  <textarea
                    rows={2}
                    value={q.text}
                    onChange={(e) => updateQuestionText(qIndex, e.target.value)}
                    placeholder="Savol matnini kiriting..."
                    style={{ width: '100%', fontWeight: 600, fontSize: '0.95rem' }}
                  />
                </div>

                {/* Choices Grid */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 10, marginBottom: 12 }}>
                  {q.choices.map((c) => {
                    const isSelected = q.correct_answer === c.code;
                    return (
                      <div
                        key={c.code}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: 8,
                          padding: '6px 10px',
                          borderRadius: 10,
                          border: isSelected ? '2px solid #10b981' : '1px solid var(--border)',
                          background: isSelected ? 'rgba(16, 185, 129, 0.08)' : 'var(--bg)',
                        }}
                      >
                        <button
                          type="button"
                          onClick={() => setCorrectAnswer(qIndex, c.code)}
                          style={{
                            width: 28,
                            height: 28,
                            borderRadius: '50%',
                            border: 'none',
                            background: isSelected ? '#10b981' : 'var(--border)',
                            color: isSelected ? '#ffffff' : 'var(--muted)',
                            fontWeight: 800,
                            fontSize: '0.8rem',
                            cursor: 'pointer',
                            flexShrink: 0,
                          }}
                          title="To'g'ri javob sifatida belgilash"
                        >
                          {c.code}
                        </button>
                        <input
                          type="text"
                          value={c.text}
                          onChange={(e) => updateChoiceText(qIndex, c.code, e.target.value)}
                          placeholder={`${c.code} varianti`}
                          style={{
                            border: 'none',
                            background: 'transparent',
                            padding: 0,
                            fontSize: '0.88rem',
                            width: '100%',
                            outline: 'none',
                          }}
                        />
                      </div>
                    );
                  })}
                </div>

                {/* Explanation */}
                <div>
                  <input
                    type="text"
                    value={q.explanation || ''}
                    onChange={(e) => updateExplanation(qIndex, e.target.value)}
                    placeholder="💡 Izoh: to'g'ri javobning grammatik yoki ilmiy asosi (ixtiyoriy)..."
                    style={{ width: '100%', fontSize: '0.82rem', color: 'var(--muted)' }}
                  />
                </div>
              </div>
            ))}
          </div>

          {/* Sticky Bottom Actions Bar */}
          <div
            style={{
              position: 'sticky',
              bottom: '1rem',
              marginTop: '2rem',
              padding: '1rem 1.5rem',
              borderRadius: 16,
              background: 'var(--card)',
              border: '1px solid var(--border)',
              boxShadow: '0 20px 40px rgba(0, 0, 0, 0.25)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              zIndex: 30,
              flexWrap: 'wrap',
              gap: 12,
            }}
          >
            <div>
              <strong style={{ fontSize: '1rem', display: 'block' }}>
                Jami: {questions.length} ta savol
              </strong>
              <span className="muted small">
                Har bir savol to'g'ri javobi belgilanganini tekshiring
              </span>
            </div>

            <div style={{ display: 'flex', gap: 10 }}>
              <button
                type="button"
                className="btn ghost"
                onClick={() => setIsConverted(false)}
                disabled={saving}
              >
                Orqaga
              </button>
              <button
                type="button"
                className="btn primary"
                onClick={handleSave}
                disabled={saving}
                style={{ minHeight: 46, padding: '0 24px', fontWeight: 800 }}
              >
                {saving ? 'Saqlanmoqda...' : '💾 Testni tasdiqlash va saqlash'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* STEP 3: SUCCESS MODAL / SCREEN */}
      {savedResult && (
        <div className="card" style={{ padding: '2.5rem', borderRadius: 20, textAlign: 'center' }}>
          <div
            style={{
              width: 64,
              height: 64,
              borderRadius: '50%',
              background: 'rgba(16, 185, 129, 0.15)',
              color: '#10b981',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              marginBottom: 16,
            }}
          >
            <CheckCircle2 size={36} />
          </div>
          <h2 style={{ fontSize: '1.6rem', fontWeight: 900, margin: '0 0 8px 0' }}>
            Test muvaffaqiyatli saqlandi!
          </h2>
          <p className="muted" style={{ maxWidth: 500, margin: '0 auto 20px auto', fontSize: '0.95rem' }}>
            Test platformada nashr etildi. O'quvchilaringiz quyidagi unikal kod orqali testga tezkor ulanishlari mumkin:
          </p>

          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 12,
              padding: '12px 24px',
              borderRadius: 14,
              background: 'rgba(99, 102, 241, 0.1)',
              border: '1px solid rgba(99, 102, 241, 0.3)',
              marginBottom: '2rem',
            }}
          >
            <span style={{ fontSize: '1.5rem', fontWeight: 900, letterSpacing: '0.05em', color: 'var(--accent, #6366f1)' }}>
              {savedResult.mock_code}
            </span>
            <button
              type="button"
              className="btn sm ghost"
              onClick={copyCode}
              title="Kodni nusxalash"
            >
              <Copy size={16} /> {copied ? 'Nusxalandi!' : 'Nusxalash'}
            </button>
          </div>

          <div style={{ display: 'flex', justifyContent: 'center', gap: 12, flexWrap: 'wrap' }}>
            <Link to={`/tests/${savedResult.test_id}`} className="btn primary" style={{ minHeight: 44, padding: '0 20px' }}>
              Testni ko'rish (Preview)
            </Link>
            <button
              type="button"
              className="btn ghost"
              onClick={() => {
                setSavedResult(null);
                setIsConverted(false);
                setFile(null);
              }}
            >
              Yana yangi test yuklash
            </button>
            <Link to="/panel" className="btn ghost">
              Ustoz kabineti
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
