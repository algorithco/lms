import { useState, useMemo, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  Check,
  Copy,
  ExternalLink,
  HelpCircle,
  Sparkles,
  Trash2,
  Zap,
  ShieldAlert,
  BookOpen,
  Send,
  Edit3,
} from 'lucide-react';
import { api } from '../lib/api';
import { parseSmartTestText, type ParsedQuestion, type SupportedSubject } from '../lib/testParser';

const SAMPLE_15_LITERATURE = `1. Alisher Navoiy qachon va qayerda tavallud topgan?
*A) 1441-yil 9-fevralda Hirotda
B) 1483-yil 14-fevralda Andijonda
C) 1336-yil 9-aprelda Keshda
D) 1530-yil Kobulda

2. Alisher Navoiy yaratgan ilk 'Xamsa' necha dostonni o'z ichiga oladi?
A) 3 ta doston
B) 4 ta doston
*C) 5 ta doston
D) 7 ta doston

3. "Hayrat ul-abror" dostoni qanday janrda yozilgan?
A) Sarguzasht doston
*B) Ta'limiy-falsafiy doston
C) Qahramonlik dostoni
D) Romantik doston

4. Zaxiriddin Muhammad Boburning shoh asari qaysi?
A) Xamsa
*B) Boburnoma
C) Shohnoma
D) Devoni Foniy

5. "Boburnoma" asari qaysi tilda bitilgan?
*A) Sof turkiy (o'zbek) tilida
B) Arab tilida
C) Fors-tojik tilida
D) Urdu tilida

6. Abdulla Qodiriyning ilk o'zbek romani qaysi?
A) Mehrobdan chayon
*B) O'tkan kunlar
C) Jinlar bazmi
D) Obid ketmon

7. "O'tkan kunlar" romanida Otabekning birinchi rafiqasi kim?
*A) Kumushbibi
B) Zaynab
C) Xushro'ybibi
D) Oftoboyim

8. Cho'lponning "Kecha va kunduz" romanidagi bosh qahramon qizning ismi nima?
A) Kumush
*B) Zebi
C) Robiya
D) Anorxon

9. Fitrat qalamiga mansub "Abulfayzxon" asarining janri nima?
*A) Tarixiy tragediya (drama)
B) Komediya
C) Lirik doston
D) Roman

10. Usmon Nosir qaysi yilda tavallud topgan?
A) 1905-yil
B) 1908-yil
*C) 1912-yil
D) 1920-yil

11. O'tkir Hoshimovning "Dunyoning ishlari" asari qanday mavzuda?
A) Urush qahramonlari
*B) Onalarni ardoqlash va xotiralari
C) Yoshlar sevgisi
D) Sayohat xotiralari

12. Erkin Vohidovning mashhur qasidasi qanday nomlanadi?
*A) O'zbegim
B) Ona tilim
C) Do'stlik
D) Bahor

13. Abdulla Oripov O'zbekiston Respublikasining qaysi davlat ramzi muallifi?
A) Davlat bayrog'i
*B) Davlat madhiyasi
C) Davlat gerbi
D) Konstitutsiya muqaddimasi

14. "Ruhlar isyoni" dostoni qaysi shoir qalamiga mansub?
A) Erkin Vohidov
*B) Erkin Samandar
C) Abdulla Oripov
D) Rauf Parfi

15. Shukur Xolmirzayev qaysi janrning yetuk ustasi hisoblanadi?
*A) Psixologik hikoya va qissa
B) Masal
C) Drama
D) Qasida`;

const SAMPLE_10_GRAMMAR = `1. O'zbek tilida nechta unli tovush mavjud?
A) 5 ta
*B) 6 ta
C) 8 ta
D) 9 ta

2. Qaysi qatorda faqat jarangli undoshlar berilgan?
*A) b, d, g, z, v
B) p, t, k, s, f
C) m, n, l, r, q
D) x, h, ch, sh, j

3. Qaysi so'zda tutuq belgisi tovushni ajratish uchun xizmat qilgan?
A) san'at
*B) jur'at
C) a'lo
D) ma'sul

4. Quyidagi so'zlardan qaysi biri sifat so'z turkumiga mansub?
*A) Shirin
B) Tezlik
C) Yugurdi
D) Maktab

5. Qaysi gapda vositasiz to'ldiruvchi qatnashgan?
*A) Kitobni do'stimga berdim.
B) Uyga tezda yetib keldik.
C) Bahorda gullar ochildi.
D) Dars soat to'qqizda boshlanadi.

6. "Yozmoq" fe'lining o'tgan zamon shakli qaysi?
A) Yozmoqda
B) Yozadi
*C) Yozdi
D) Yozmoqchi

7. Qaysi javobda qo'shma ot berilgan?
*A) Toshkent
B) Kitobxon
C) Bog'bon
D) Gullar

8. "Ko'm-ko'k" so'zi sifatning qaysi darajasiga kiradi?
*A) Orttirma daraja
B) Qiyosiy daraja
C) Oddiy daraja
D) Kichraytirish darajasi

9. Bosh va ergash gapdan tashkil topgan gap turi nima deyiladi?
*A) Ergashgan qo'shma gap
B) Bog'langan qo'shma gap
C) Bog'lovchisiz qo'shma gap
D) Sodda gap

10. Qaysi so'z imloviy jihatdan to'g'ri yozilgan?
A) Muxim
*B) Muhim
C) Muhiym
D) Muxym`;

const SAMPLE_5_ENGLISH = `1. Which of the following is a synonym for 'meticulous'?
A) Careless
*B) Thorough and careful
C) Rapid
D) Hasty

2. Identify the correct sentence in passive voice:
A) The chef prepares the dinner.
*B) The dinner was prepared by the chef.
C) The chef was preparing dinner.
D) The dinner prepares the chef.

3. Choose the appropriate preposition: 'She has been living in London ___ 2018.'
A) for
*B) since
C) during
D) in

4. What is the main theme of IELTS Academic Writing Task 1?
*A) Describing factual data from charts or graphs
B) Writing a personal opinion letter
C) Telling an imaginative story
D) Composing a poem

5. Which word has a negative connotation?
A) Ambitious
B) Determined
*C) Ruthless
D) Confident`;

export default function SmartTestCreate() {
  const navigate = useNavigate();

  // Test Settings
  const [subject, setSubject] = useState<SupportedSubject>('uzbek');
  const [title, setTitle] = useState('');
  const [timeLimit, setTimeLimit] = useState<number>(20);
  const [isStrictMode, setIsStrictMode] = useState(false);
  const [customCode, setCustomCode] = useState('');

  // Raw text input & questions
  const [rawText, setRawText] = useState(SAMPLE_15_LITERATURE);
  const [readingPassage, setReadingPassage] = useState('');
  const [questions, setQuestions] = useState<ParsedQuestion[]>([]);
  const [editingQIdx, setEditingQIdx] = useState<number | null>(null);

  // UI state
  const [busy, setBusy] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [createdResult, setCreatedResult] = useState<{
    test_id: number;
    mock_code: string;
    share_url: string;
    title: string;
    questions_count: number;
  } | null>(null);
  const [copiedLink, setCopiedLink] = useState(false);
  const [copiedCode, setCopiedCode] = useState(false);

  // Parse text on change
  useEffect(() => {
    const res = parseSmartTestText(rawText, subject);
    setQuestions(res.questions);
    if (res.readingPassage) {
      setReadingPassage(res.readingPassage);
    }
    if (!title && res.questions.length > 0) {
      if (subject === 'adabiyot') {
        setTitle(`8-sinf Adabiyot — ${res.questions.length} talik oraliq nazorat`);
      } else if (subject === 'milliy') {
        setTitle(`Milliy Sertifikat — ${res.questions.length} talik BMB Diagnostika`);
      } else if (subject === 'english') {
        setTitle(`English CBT Mock — ${res.questions.length} Questions`);
      } else {
        setTitle(`Ona tili — ${res.questions.length} talik mavzulashtirilgan test`);
      }
    }
  }, [rawText, subject, title]);

  const unansweredCount = useMemo(() => {
    return questions.filter((q) => !q.correctAnswer).length;
  }, [questions]);

  // Click choice to toggle correct answer
  const handleSelectChoice = (questionIndex: number, choiceCode: string) => {
    setQuestions((prev) => {
      const copy = [...prev];
      const q = { ...copy[questionIndex] };
      q.correctAnswer = choiceCode;
      q.hasExplicitAnswer = true;
      copy[questionIndex] = q;
      return copy;
    });
  };

  // Inline edit question text
  const handleUpdateQuestionText = (questionIndex: number, newText: string) => {
    setQuestions((prev) => {
      const copy = [...prev];
      copy[questionIndex] = { ...copy[questionIndex], text: newText };
      return copy;
    });
  };

  // Delete question
  const handleDeleteQuestion = (questionIndex: number) => {
    setQuestions((prev) => {
      const filtered = prev.filter((_, idx) => idx !== questionIndex);
      return filtered.map((q, idx) => ({ ...q, order: idx + 1 }));
    });
    if (editingQIdx === questionIndex) {
      setEditingQIdx(null);
    }
  };

  // Submit test
  const handlePublish = async () => {
    if (questions.length === 0) {
      setErrorMsg('Saqlash uchun kamida 1 ta savol bo‘lishi lozim.');
      return;
    }
    if (unansweredCount > 0) {
      setErrorMsg(
        `Diqqat! ${unansweredCount} ta savolda to‘g‘ri javob belgilanmagan. Iltimos, o‘ng tomondagi kartochkalarda to‘g‘ri variant ustiga bosing.`
      );
      return;
    }

    setBusy(true);
    setErrorMsg(null);

    const payload = {
      test_title: title.trim() || `${questions.length} talik test`,
      subject,
      time_limit_minutes: Number(timeLimit) || 0,
      is_strict_mode: isStrictMode,
      custom_code: customCode.trim() || undefined,
      reading_passage: readingPassage.trim(),
      questions: questions.map((q, idx) => ({
        order: idx + 1,
        text: q.text,
        choices: q.choices,
        correct_answer: q.correctAnswer || 'A',
        explanation: q.explanation,
      })),
    };

    try {
      const res = await api.post<{
        success: boolean;
        test_id: number;
        mock_code: string;
        share_url?: string;
        title: string;
        questions_count: number;
      }>('/api/tests/smart-create/', payload);

      setCreatedResult({
        test_id: res.test_id,
        mock_code: res.mock_code,
        share_url: `${window.location.origin}/tests/${res.test_id}`,
        title: res.title,
        questions_count: res.questions_count,
      });
    } catch (err2: unknown) {
      const msg = err2 instanceof Error ? err2.message : 'Testni saqlashda xatolik yuz berdi.';
      setErrorMsg(msg);
    } finally {
      setBusy(false);
    }
  };

  const copyToClipboard = (text: string, type: 'link' | 'code') => {
    navigator.clipboard.writeText(text);
    if (type === 'link') {
      setCopiedLink(true);
      setTimeout(() => setCopiedLink(false), 2500);
    } else {
      setCopiedCode(true);
      setTimeout(() => setCopiedCode(false), 2500);
    }
  };

  return (
    <div style={{ minHeight: '100%', background: '#F8FAFC', padding: '24px 20px 80px' }}>
      <div style={{ maxWidth: 1400, margin: '0 auto' }}>
      {/* Breadcrumb & Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 24,
          flexWrap: 'wrap',
          gap: 12,
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: '#64748B', marginBottom: 6 }}>
            <Link to="/tests" style={{ color: '#64748B', textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: 4 }}>
              <ArrowLeft size={14} /> Testlar
            </Link>
            <span>/</span>
            <span style={{ color: '#0F172A', fontWeight: 600 }}>Yangi test yaratish</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div
              style={{
                width: 44,
                height: 44,
                borderRadius: 12,
                background: 'linear-gradient(135deg, rgba(245, 158, 11, 0.15), rgba(217, 119, 6, 0.15))',
                border: '1px solid rgba(245, 158, 11, 0.3)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Zap size={22} color="#D97706" />
            </div>
            <div>
              <h1 style={{ fontSize: 24, fontWeight: 900, color: '#0F172A', margin: 0, letterSpacing: '-0.02em' }}>
                Smart Paste — 1 soniyada test qo‘shish
              </h1>
              <p style={{ fontSize: 13.5, color: '#64748B', margin: '4px 0 0' }}>
                Word yoki Telegram'dan tayyor test matnini nusxalab tashlang. Tizim avtomatik savol va javoblarga ajratadi.
              </p>
            </div>
          </div>
        </div>

        {/* Back Link */}
        <Link
          to="/tests"
          className="btn"
          style={{
            background: '#FFFFFF',
            border: '1px solid #E2E8F0',
            color: '#475569',
            fontWeight: 700,
            borderRadius: 12,
            padding: '10px 18px',
            textDecoration: 'none',
            fontSize: 13,
            boxShadow: '0 2px 8px rgba(0,0,0,0.03)',
          }}
        >
          Testlar ro‘yxatiga qaytish
        </Link>
      </div>

      {/* Success Modal / Banner */}
      {createdResult && (
        <div
          style={{
            background: '#FFFFFF',
            borderRadius: 24,
            border: '2px solid #10B981',
            boxShadow: '0 20px 40px -15px rgba(16, 185, 129, 0.2)',
            padding: 32,
            marginBottom: 32,
            textAlign: 'center',
          }}
        >
          <div
            style={{
              width: 64,
              height: 64,
              borderRadius: '50%',
              background: 'rgba(16, 185, 129, 0.12)',
              border: '2px solid #10B981',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto 16px',
            }}
          >
            <Check size={32} color="#10B981" />
          </div>
          <h2 style={{ fontSize: 22, fontWeight: 900, color: '#0F172A', margin: '0 0 6px' }}>
            🎉 Test muvaffaqiyatli saqlandi va e’lon qilindi!
          </h2>
          <p style={{ fontSize: 14, color: '#64748B', margin: '0 0 24px' }}>
            «{createdResult.title}» testi bazaga yozildi ({createdResult.questions_count} ta savol). O‘quvchilarga havola yoki maxsus kod orqali ulashing:
          </p>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
              gap: 16,
              maxWidth: 760,
              margin: '0 auto 28px',
            }}
          >
            {/* Mock Code Card */}
            <div
              style={{
                background: '#F8FAFC',
                border: '1px solid #E2E8F0',
                borderRadius: 16,
                padding: 18,
                textAlign: 'center',
              }}
            >
              <div style={{ fontSize: 11, fontWeight: 800, color: '#64748B', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 6 }}>
                Tezkor Ulanish Kodi (PIN)
              </div>
              <div style={{ fontSize: 26, fontWeight: 900, color: '#D97706', letterSpacing: '1px', marginBottom: 12 }}>
                {createdResult.mock_code}
              </div>
              <button
                type="button"
                onClick={() => copyToClipboard(createdResult.mock_code, 'code')}
                className="btn sm"
                style={{
                  background: copiedCode ? '#10B981' : '#FFFFFF',
                  color: copiedCode ? '#FFFFFF' : '#0F172A',
                  border: '1px solid #CBD5E1',
                  borderRadius: 10,
                  fontWeight: 700,
                  fontSize: 12.5,
                  padding: '7px 16px',
                  cursor: 'pointer',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 6,
                }}
              >
                {copiedCode ? <Check size={14} /> : <Copy size={14} />}
                {copiedCode ? 'Nusxalandi!' : 'Kodni nusxalash'}
              </button>
            </div>

            {/* Direct Link Card */}
            <div
              style={{
                background: '#F8FAFC',
                border: '1px solid #E2E8F0',
                borderRadius: 16,
                padding: 18,
                textAlign: 'center',
              }}
            >
              <div style={{ fontSize: 11, fontWeight: 800, color: '#64748B', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 6 }}>
                To‘g‘ridan-to‘g‘ri Havola
              </div>
              <div
                style={{
                  fontSize: 13,
                  fontWeight: 700,
                  color: '#0F172A',
                  marginBottom: 12,
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                  padding: '4px 8px',
                  background: '#FFFFFF',
                  borderRadius: 8,
                  border: '1px solid #E2E8F0',
                }}
              >
                {createdResult.share_url}
              </div>
              <button
                type="button"
                onClick={() => copyToClipboard(createdResult.share_url, 'link')}
                className="btn sm"
                style={{
                  background: copiedLink ? '#10B981' : '#FFFFFF',
                  color: copiedLink ? '#FFFFFF' : '#0F172A',
                  border: '1px solid #CBD5E1',
                  borderRadius: 10,
                  fontWeight: 700,
                  fontSize: 12.5,
                  padding: '7px 16px',
                  cursor: 'pointer',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 6,
                }}
              >
                {copiedLink ? <Check size={14} /> : <Copy size={14} />}
                {copiedLink ? 'Nusxalandi!' : 'Havolani nusxalash'}
              </button>
            </div>
          </div>

          {/* Action Buttons: Telegram Share & Open Test */}
          <div style={{ display: 'flex', justifyContent: 'center', gap: 14, flexWrap: 'wrap' }}>
            {/* Telegram Share Button */}
            <a
              href={`https://t.me/share/url?url=${encodeURIComponent(createdResult.share_url)}&text=${encodeURIComponent(
                `🏆 GRAND EDUCATION — Yangi test e'lon qilindi!\n\n📖 Test: ${createdResult.title}\n🔢 Savollar soni: ${createdResult.questions_count} ta\n🔑 Ulanish kodi: ${createdResult.mock_code}\n\n👇 Testni yechish uchun quyidagi havola ustiga bosing:`
              )}`}
              target="_blank"
              rel="noopener noreferrer"
              className="btn"
              style={{
                background: '#0088cc',
                color: '#FFFFFF',
                fontWeight: 800,
                fontSize: 14,
                padding: '12px 24px',
                borderRadius: 12,
                border: 'none',
                cursor: 'pointer',
                display: 'inline-flex',
                alignItems: 'center',
                gap: 8,
                textDecoration: 'none',
                boxShadow: '0 4px 14px rgba(0, 136, 204, 0.3)',
              }}
            >
              <Send size={16} />
              <span>Telegram guruhga ulashish</span>
            </a>

            <button
              type="button"
              onClick={() => navigate(`/tests/${createdResult.test_id}`)}
              style={{
                background: 'linear-gradient(135deg, #F59E0B 0%, #D97706 100%)',
                color: '#FFFFFF',
                fontWeight: 800,
                fontSize: 14,
                padding: '12px 26px',
                borderRadius: 12,
                border: 'none',
                cursor: 'pointer',
                display: 'inline-flex',
                alignItems: 'center',
                gap: 8,
                boxShadow: '0 4px 16px rgba(217, 119, 6, 0.35)',
              }}
            >
              <span>Testni ko‘rish</span>
              <ExternalLink size={16} />
            </button>

            <button
              type="button"
              onClick={() => navigate(`/tests/${createdResult.test_id}/gradebook`)}
              style={{
                background: 'linear-gradient(135deg, #10B981 0%, #059669 100%)',
                color: '#FFFFFF',
                fontWeight: 800,
                fontSize: 14,
                padding: '12px 24px',
                borderRadius: 12,
                border: 'none',
                cursor: 'pointer',
                display: 'inline-flex',
                alignItems: 'center',
                gap: 8,
                boxShadow: '0 4px 16px rgba(16, 185, 129, 0.35)',
              }}
            >
              <span>📊</span>
              <span>Vedomostni ko‘rish</span>
            </button>

            <button
              type="button"
              onClick={() => {
                setCreatedResult(null);
                setRawText('');
                setTitle('');
              }}
              style={{
                background: '#FFFFFF',
                color: '#475569',
                fontWeight: 700,
                fontSize: 14,
                padding: '12px 20px',
                borderRadius: 12,
                border: '1px solid #CBD5E1',
                cursor: 'pointer',
              }}
            >
              + Yana yangi test yaratish
            </button>
          </div>
        </div>
      )}

      {/* Settings Form Card */}
      <div
        style={{
          background: '#FFFFFF',
          borderRadius: 24,
          border: '1px solid #E2E8F0',
          boxShadow: '0 4px 20px rgba(0, 0, 0, 0.03)',
          padding: 26,
          marginBottom: 24,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16, fontSize: 14, fontWeight: 800, color: '#0F172A' }}>
          <Sparkles size={16} color="#D97706" />
          <span>Moslashuvchan Test Sozlamalari</span>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 18 }}>
          {/* Test Nomi */}
          <div>
            <label style={{ display: 'block', fontSize: 12.5, fontWeight: 700, color: '#475569', marginBottom: 6 }}>
              Test Nomi <span style={{ color: '#EF4444' }}>*</span>
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Masalan: 8-sinf Adabiyot — 15 talik oraliq nazorat"
              required
              style={{
                width: '100%',
                padding: '10px 14px',
                borderRadius: 10,
                border: '1px solid #CBD5E1',
                fontSize: 13.5,
                fontWeight: 600,
                color: '#0F172A',
                background: '#F8FAFC',
              }}
            />
          </div>

          {/* Fani va Yo‘nalishi */}
          <div>
            <label style={{ display: 'block', fontSize: 12.5, fontWeight: 700, color: '#475569', marginBottom: 6 }}>
              Fani va Yo‘nalishi
            </label>
            <select
              value={subject}
              onChange={(e) => setSubject(e.target.value as SupportedSubject)}
              style={{
                width: '100%',
                padding: '10px 14px',
                borderRadius: 10,
                border: '1px solid #CBD5E1',
                fontSize: 13.5,
                fontWeight: 600,
                color: '#0F172A',
                background: '#F8FAFC',
              }}
            >
              <option value="uzbek">🇺🇿 Ona tili (Grammatika va amaliyot)</option>
              <option value="adabiyot">📚 Adabiyot (Tarixiy va badiiy asarlar)</option>
              <option value="milliy">🏛️ Milliy sertifikat (BMB Davlat standarti)</option>
              <option value="english">🇬🇧 Ingliz tili (IELTS / CEFR Multi-level)</option>
            </select>
          </div>

          {/* Vaqt Limiti */}
          <div>
            <label style={{ display: 'block', fontSize: 12.5, fontWeight: 700, color: '#475569', marginBottom: 6 }}>
              Vaqt Limiti: <span style={{ color: '#D97706' }}>{timeLimit === 0 ? 'Cheksiz' : `${timeLimit} daqiqa`}</span>
            </label>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {[15, 20, 30, 45, 60, 180, 0].map((mins) => (
                <button
                  key={mins}
                  type="button"
                  onClick={() => setTimeLimit(mins)}
                  style={{
                    padding: '6px 10px',
                    borderRadius: 8,
                    fontSize: 11.5,
                    fontWeight: 700,
                    cursor: 'pointer',
                    background: timeLimit === mins ? '#D97706' : '#F1F5F9',
                    color: timeLimit === mins ? '#FFFFFF' : '#475569',
                    border: 'none',
                    transition: 'all 0.15s ease',
                  }}
                >
                  {mins === 0 ? 'Cheksiz' : `${mins}m`}
                </button>
              ))}
            </div>
          </div>

          {/* Anti-cheat Strict Mode */}
          <div>
            <label style={{ display: 'block', fontSize: 12.5, fontWeight: 700, color: '#475569', marginBottom: 6 }}>
              Xavfsizlik & Anti-Cheat
            </label>
            <label
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 8,
                fontSize: 13,
                fontWeight: 600,
                color: '#0F172A',
                cursor: 'pointer',
                padding: '8px 12px',
                borderRadius: 10,
                background: isStrictMode ? 'rgba(239, 68, 68, 0.08)' : '#F8FAFC',
                border: isStrictMode ? '1px solid rgba(239, 68, 68, 0.3)' : '1px solid #E2E8F0',
              }}
            >
              <input
                type="checkbox"
                checked={isStrictMode}
                onChange={(e) => setIsStrictMode(e.target.checked)}
                style={{ accentColor: '#EF4444' }}
              />
              <ShieldAlert size={16} color={isStrictMode ? '#EF4444' : '#64748B'} />
              <span>Strict Exam Mode</span>
            </label>
          </div>

          {/* Maxsus Kod */}
          <div>
            <label style={{ display: 'block', fontSize: 12.5, fontWeight: 700, color: '#475569', marginBottom: 6 }}>
              Maxsus Ulanish Kodi (Ixtiyoriy)
            </label>
            <input
              type="text"
              value={customCode}
              onChange={(e) => setCustomCode(e.target.value.toUpperCase())}
              placeholder="#MOCK-15 (bo'sh qolsa avtomatik)"
              style={{
                width: '100%',
                padding: '10px 14px',
                borderRadius: 10,
                border: '1px solid #CBD5E1',
                fontSize: 13.5,
                fontWeight: 700,
                color: '#D97706',
                background: '#F8FAFC',
                letterSpacing: '1px',
              }}
            />
          </div>
        </div>
      </div>

      {/* Main 2-Column Split: Paste Input (Left) vs Live Preview (Right) */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))', gap: 24, alignItems: 'start' }}>
        {/* LEFT COLUMN: SMART PASTE INPUT */}
        <div
          style={{
            background: '#FFFFFF',
            borderRadius: 24,
            border: '1px solid #E2E8F0',
            boxShadow: '0 4px 20px rgba(0, 0, 0, 0.03)',
            padding: 26,
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14, flexWrap: 'wrap', gap: 8 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <BookOpen size={18} color="#D97706" />
              <strong style={{ fontSize: 15, color: '#0F172A' }}>Xom Test Matnini Tashlash</strong>
            </div>

            {/* Quick Demo Fill Buttons */}
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              <button
                type="button"
                onClick={() => {
                  setSubject('adabiyot');
                  setTitle('8-sinf Adabiyot — 15 talik oraliq nazorat');
                  setRawText(SAMPLE_15_LITERATURE);
                }}
                title="15 talik Adabiyot testini namuna sifatida yuklash"
                style={{
                  background: '#F8FAFC',
                  border: '1px solid #CBD5E1',
                  color: '#475569',
                  borderRadius: 8,
                  fontSize: 11,
                  fontWeight: 700,
                  padding: '4px 8px',
                  cursor: 'pointer',
                }}
              >
                📋 15 talik Adabiyot
              </button>
              <button
                type="button"
                onClick={() => {
                  setSubject('uzbek');
                  setTitle('Ona tili — 10 talik grammatika testi');
                  setRawText(SAMPLE_10_GRAMMAR);
                }}
                title="10 talik Grammatika testini namuna sifatida yuklash"
                style={{
                  background: '#F8FAFC',
                  border: '1px solid #CBD5E1',
                  color: '#475569',
                  borderRadius: 8,
                  fontSize: 11,
                  fontWeight: 700,
                  padding: '4px 8px',
                  cursor: 'pointer',
                }}
              >
                📋 10 talik Grammatika
              </button>
              <button
                type="button"
                onClick={() => {
                  setSubject('english');
                  setTitle('English CBT Mock — 5 Questions');
                  setRawText(SAMPLE_5_ENGLISH);
                }}
                title="5 talik Ingliz tili testini namuna sifatida yuklash"
                style={{
                  background: '#F8FAFC',
                  border: '1px solid #CBD5E1',
                  color: '#475569',
                  borderRadius: 8,
                  fontSize: 11,
                  fontWeight: 700,
                  padding: '4px 8px',
                  cursor: 'pointer',
                }}
              >
                📋 5 talik English
              </button>
              <button
                type="button"
                onClick={() => setRawText('')}
                title="Tozalash"
                style={{
                  background: '#FEE2E2',
                  border: '1px solid #FCA5A5',
                  color: '#B91C1C',
                  borderRadius: 8,
                  fontSize: 11,
                  fontWeight: 700,
                  padding: '4px 8px',
                  cursor: 'pointer',
                }}
              >
                <Trash2 size={12} />
              </button>
            </div>
          </div>

          <div
            style={{
              background: '#FFFBEB',
              border: '1px solid #FDE68A',
              borderRadius: 12,
              padding: '10px 14px',
              fontSize: 12,
              color: '#92400E',
              lineHeight: 1.5,
              marginBottom: 14,
            }}
          >
            <strong>💡 Format yo‘riqnomasi:</strong> Savol raqami (<code>1.</code>, <code>1)</code>), variantlar (<code>A)</code>, <code>B)</code> yoki <code>(A)</code>, <code>A.</code>). To‘g‘ri javobni variant oldiga <code>*</code> yoki <code>+</code> qo‘yib (masalan: <code>*A)</code>), yoki savol tagiga <code>Javob: B</code>, <code>Ans: C</code> deb yozing.
          </div>

          <textarea
            value={rawText}
            onChange={(e) => setRawText(e.target.value)}
            placeholder="Test matnini bu yerga tashlang (Ctrl+V)..."
            rows={22}
            style={{
              width: '100%',
              padding: 18,
              borderRadius: 16,
              border: '1.5px solid #CBD5E1',
              fontSize: 13.5,
              fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
              color: '#0F172A',
              background: '#F8FAFC',
              lineHeight: 1.65,
              resize: 'vertical',
              outline: 'none',
              boxShadow: 'inset 0 1px 3px rgba(0, 0, 0, 0.02)',
              transition: 'border-color 0.2s ease, box-shadow 0.2s ease',
            }}
            onFocus={(e) => {
              e.currentTarget.style.borderColor = '#D97706';
              e.currentTarget.style.boxShadow = '0 0 0 3px rgba(217, 119, 6, 0.15)';
            }}
            onBlur={(e) => {
              e.currentTarget.style.borderColor = '#CBD5E1';
              e.currentTarget.style.boxShadow = 'inset 0 1px 3px rgba(0, 0, 0, 0.02)';
            }}
          />
        </div>

        {/* RIGHT COLUMN: INTERACTIVE LIVE PREVIEW */}
        <div
          style={{
            background: '#FFFFFF',
            borderRadius: 24,
            border: '1px solid #E2E8F0',
            boxShadow: '0 4px 20px rgba(0, 0, 0, 0.03)',
            padding: 26,
          }}
        >
          {/* Header Stats & Publish Button */}
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              flexWrap: 'wrap',
              gap: 12,
              paddingBottom: 18,
              borderBottom: '1px solid #E2E8F0',
              marginBottom: 20,
            }}
          >
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 6,
                    padding: '4px 10px',
                    borderRadius: 20,
                    background: questions.length > 0 ? 'rgba(16, 185, 129, 0.12)' : 'rgba(239, 68, 68, 0.1)',
                    color: questions.length > 0 ? '#059669' : '#DC2626',
                    fontSize: 12.5,
                    fontWeight: 800,
                  }}
                >
                  {questions.length > 0 ? `✅ ${questions.length} ta savol aniqlandi` : '❌ Savollar topilmadi'}
                </span>
                {unansweredCount > 0 && (
                  <span
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: 4,
                      padding: '4px 10px',
                      borderRadius: 20,
                      background: 'rgba(245, 158, 11, 0.12)',
                      color: '#D97706',
                      fontSize: 11.5,
                      fontWeight: 800,
                    }}
                  >
                    ⚠️ {unansweredCount} ta javobsiz
                  </span>
                )}
              </div>
            </div>

            {/* Save & Publish Action */}
            <button
              type="button"
              onClick={handlePublish}
              disabled={busy || questions.length === 0}
              style={{
                background: questions.length === 0 ? '#CBD5E1' : 'linear-gradient(135deg, #F59E0B 0%, #D97706 100%)',
                color: '#FFFFFF',
                fontWeight: 900,
                fontSize: 14,
                padding: '10px 22px',
                borderRadius: 12,
                border: 'none',
                cursor: questions.length === 0 || busy ? 'not-allowed' : 'pointer',
                display: 'inline-flex',
                alignItems: 'center',
                gap: 8,
                boxShadow: questions.length > 0 ? '0 4px 14px rgba(217, 119, 6, 0.35)' : 'none',
                transition: 'all 0.15s ease',
              }}
            >
              {busy ? (
                'Saqlanmoqda…'
              ) : (
                <>
                  <Zap size={16} />
                  <span>Testni saqlash va kod yaratish</span>
                </>
              )}
            </button>
          </div>

          {/* Error Message */}
          {errorMsg && (
            <div
              style={{
                padding: '12px 16px',
                borderRadius: 12,
                background: 'rgba(239, 68, 68, 0.1)',
                border: '1px solid rgba(239, 68, 68, 0.3)',
                color: '#B91C1C',
                fontSize: 13,
                fontWeight: 600,
                marginBottom: 16,
              }}
            >
              {errorMsg}
            </div>
          )}

          {/* Questions Scrollable List */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16, maxHeight: '650px', overflowY: 'auto', paddingRight: 6 }}>
            {questions.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '60px 20px', color: '#94A3B8' }}>
                <HelpCircle size={40} style={{ margin: '0 auto 12px', opacity: 0.5 }} />
                <p style={{ margin: 0, fontWeight: 600, fontSize: 14 }}>
                  Chap tomonga test matnini tashlang yoki namunalardan birini tanlang.
                </p>
              </div>
            ) : (
              questions.map((q, qIdx) => {
                const hasCorrect = Boolean(q.correctAnswer);
                const isEditingThis = editingQIdx === qIdx;
                return (
                  <div
                    key={q.order}
                    style={{
                      background: hasCorrect ? 'rgba(240, 253, 244, 0.55)' : '#FFFFFF',
                      borderRadius: 18,
                      border: hasCorrect ? '1.5px solid #86EFAC' : '1.5px solid #FCD34D',
                      boxShadow: '0 2px 8px rgba(0, 0, 0, 0.02)',
                      padding: '18px 20px',
                      position: 'relative',
                      transition: 'all 0.2s ease',
                    }}
                  >
                    {/* Header */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span
                          style={{
                            width: 26,
                            height: 26,
                            borderRadius: '50%',
                            background: '#0F172A',
                            color: '#FFFFFF',
                            fontSize: 12,
                            fontWeight: 800,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                          }}
                        >
                          {q.order}
                        </span>
                        <span style={{ fontSize: 13, fontWeight: 800, color: '#0F172A' }}>
                          Savol #{q.order}
                        </span>
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        {!hasCorrect && (
                          <span style={{ fontSize: 11, fontWeight: 700, color: '#D97706', background: 'rgba(245, 158, 11, 0.1)', padding: '2px 8px', borderRadius: 6 }}>
                            Javob tanlanmagan
                          </span>
                        )}

                        {/* Inline Edit Button */}
                        <button
                          type="button"
                          onClick={() => setEditingQIdx(isEditingThis ? null : qIdx)}
                          title="Savol matnini tahrirlash"
                          style={{
                            background: isEditingThis ? '#E2E8F0' : 'transparent',
                            border: 'none',
                            color: isEditingThis ? '#0F172A' : '#64748B',
                            borderRadius: 6,
                            cursor: 'pointer',
                            padding: '4px 6px',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 4,
                            fontSize: 11.5,
                            fontWeight: 600,
                          }}
                        >
                          <Edit3 size={14} />
                          <span>{isEditingThis ? 'Tayyor' : 'Tahrirlash'}</span>
                        </button>

                        {/* Delete Question Button */}
                        <button
                          type="button"
                          onClick={() => handleDeleteQuestion(qIdx)}
                          title="Savolni o‘chirish"
                          style={{
                            background: 'transparent',
                            border: 'none',
                            color: '#94A3B8',
                            cursor: 'pointer',
                            padding: 4,
                          }}
                        >
                          <Trash2 size={16} />
                        </button>
                      </div>
                    </div>

                    {/* Question Text (or inline edit textarea) */}
                    {isEditingThis ? (
                      <div style={{ marginBottom: 14 }}>
                        <textarea
                          value={q.text}
                          onChange={(e) => handleUpdateQuestionText(qIdx, e.target.value)}
                          rows={3}
                          style={{
                            width: '100%',
                            padding: '8px 12px',
                            borderRadius: 10,
                            border: '1.5px solid #D97706',
                            background: '#FFFFFF',
                            color: '#0F172A',
                            fontSize: 13,
                            fontWeight: 600,
                            lineHeight: 1.5,
                            fontFamily: 'inherit',
                          }}
                        />
                      </div>
                    ) : (
                      <p
                        onClick={() => setEditingQIdx(qIdx)}
                        title="Matnni tahrirlash uchun bosing"
                        style={{
                          fontSize: 13.5,
                          fontWeight: 600,
                          color: '#0F172A',
                          margin: '0 0 14px',
                          lineHeight: 1.5,
                          cursor: 'pointer',
                        }}
                      >
                        {q.text}
                      </p>
                    )}

                    {/* Options (Clickable to select correct answer) */}
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 8 }}>
                      {q.choices.map((c) => {
                        const isCorrect = q.correctAnswer === c.code;
                        return (
                          <button
                            key={c.code}
                            type="button"
                            onClick={() => handleSelectChoice(qIdx, c.code)}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: 10,
                              padding: '10px 12px',
                              borderRadius: 10,
                              border: isCorrect ? '1.5px solid #10B981' : '1px solid #CBD5E1',
                              background: isCorrect ? 'rgba(16, 185, 129, 0.08)' : '#FFFFFF',
                              color: isCorrect ? '#065F46' : '#334155',
                              cursor: 'pointer',
                              textAlign: 'left',
                              fontSize: 12.5,
                              fontWeight: isCorrect ? 700 : 500,
                              transition: 'all 0.12s ease',
                            }}
                          >
                            <span
                              style={{
                                width: 22,
                                height: 22,
                                borderRadius: '50%',
                                background: isCorrect ? '#10B981' : '#F1F5F9',
                                color: isCorrect ? '#FFFFFF' : '#475569',
                                fontSize: 11,
                                fontWeight: 800,
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                flexShrink: 0,
                              }}
                            >
                              {isCorrect ? '✓' : c.code}
                            </span>
                            <span style={{ flex: 1, wordBreak: 'break-word' }}>{c.text}</span>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>
      </div>
    </div>
  );
}
