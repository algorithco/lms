import { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import {
  CheckIcon,
  ClockIcon,
  RefreshIcon,
  ShieldCheckIcon,
  StarIcon,
} from '../components/icons';
import SEO from '../components/SEO';
import StudentAttemptReviewModal from '../components/StudentAttemptReviewModal';
import {
  type GradebookResponse,
  type ItemAnalysisResponse,
  TeacherGradebookApi,
} from '../lib/api';

export default function TeacherGradebook() {
  const { id = '' } = useParams();
  const { user } = useAuth();

  const [activeTab, setActiveTab] = useState<'gradebook' | 'items'>('gradebook');
  const [data, setData] = useState<GradebookResponse | null>(null);
  const [itemData, setItemData] = useState<ItemAnalysisResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedAttemptId, setSelectedAttemptId] = useState<number | null>(null);

  const fetchData = async () => {
    setLoading(true);
    setErr(null);
    try {
      const [gb, items] = await Promise.all([
        TeacherGradebookApi.gradebook(id),
        TeacherGradebookApi.itemAnalysis(id).catch(() => null),
      ]);
      setData(gb);
      if (items) setItemData(items);
    } catch (e) {
      setErr(e instanceof Error ? e.message : 'Natijalar vedomostini yuklab bo‘lmadi.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  // Filter students by search
  const filteredStudents = useMemo(() => {
    if (!data?.students) return [];
    if (!searchQuery.trim()) return data.students;
    const q = searchQuery.toLowerCase().trim();
    return data.students.filter(
      (s) =>
        s.student_name.toLowerCase().includes(q) ||
        s.username.toLowerCase().includes(q) ||
        s.rasch_grade.toLowerCase().includes(q),
    );
  }, [data?.students, searchQuery]);

  // 1-Click Export to Excel (.csv with UTF-8 BOM)
  const handleExportExcel = () => {
    if (!data || !data.students || data.students.length === 0) {
      alert("Eksport qilish uchun o'quvchilar natijalari mavjud emas.");
      return;
    }

    const headers = [
      "O'rin",
      "O'quvchi F.I.Sh",
      "Username",
      "Xom ball",
      "Jami savollar",
      "Foiz (%)",
      "Rasch Dinamik Bali",
      "Daraja",
      "Sarflangan vaqt",
      "Topshirilgan sana",
    ];

    const rows = data.students.map((s) => [
      s.rank,
      `"${s.student_name.replace(/"/g, '""')}"`,
      `"${s.username.replace(/"/g, '""')}"`,
      s.raw_score_num,
      s.total_questions,
      s.percentage,
      s.rasch_score,
      `"${s.rasch_grade}"`,
      `"${s.time_spent_formatted}"`,
      `"${s.completed_at}"`,
    ]);

    const csvContent =
      '\uFEFF' +
      [headers.join(','), ...rows.map((e) => e.join(','))].join('\r\n');

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    const safeTitle = (data.test_title || 'Test')
      .replace(/[^a-zA-Z0-9_\u0400-\u04FF]/g, '_')
      .slice(0, 30);
    link.setAttribute('href', url);
    link.setAttribute(
      'download',
      `Vedomost_${safeTitle}_${new Date().toISOString().slice(0, 10)}.csv`,
    );
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  // 1-Click PDF Export via browser print dialog
  const handlePrintPdf = () => {
    window.print();
  };

  const isTeacherOrAdmin =
    user?.role === 'teacher' ||
    user?.role === 'admin' ||
    user?.role === 'center_admin';

  if (!isTeacherOrAdmin) {
    return (
      <div style={{ maxWidth: 680, margin: '40px auto', textAlign: 'center', padding: 24 }}>
        <h2 style={{ color: '#EF4444' }}>Ruxsat berilmagan</h2>
        <p className="muted">
          Ushbu natijalar vedomosti va psixometrik tahlil faqat o'qituvchilar va ma'murlar uchun ochiq.
        </p>
        <Link to="/tests" className="btn primary" style={{ marginTop: 16 }}>
          ← Testlar ro'yxatiga qaytish
        </Link>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 1140, margin: '0 auto', paddingBottom: 60 }}>
      <SEO
        title={data ? `${data.test_title} — Natijalar Vedomosti | GRANDEC` : `Vedomost #${id} | GRANDEC`}
        description="O'quvchilarning rasmiy test natijalari vedomosti, Rasch ballari va eksport kabineti."
      />

      {/* Screen View Header */}
      <div className="no-print" style={{ marginBottom: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12, marginBottom: 12 }}>
          <Link
            to="/tests"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              color: 'var(--muted)',
              fontSize: 13,
              fontWeight: 700,
              textDecoration: 'none',
            }}
          >
            ← Barcha testlarga qaytish
          </Link>

          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <button
              type="button"
              onClick={fetchData}
              disabled={loading}
              className="btn sm"
              style={{
                background: 'var(--card-2)',
                border: '1px solid var(--border)',
                color: 'var(--ink)',
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                padding: '7px 14px',
                borderRadius: 10,
                cursor: 'pointer',
                fontWeight: 700,
              }}
              title="Yangilash"
            >
              <RefreshIcon size={14} />
              <span>Yangilash</span>
            </button>

            <button
              type="button"
              onClick={handleExportExcel}
              className="btn sm"
              style={{
                background: 'linear-gradient(135deg, #10B981 0%, #059669 100%)',
                color: '#FFFFFF',
                border: 'none',
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                padding: '7px 16px',
                borderRadius: 10,
                cursor: 'pointer',
                fontWeight: 800,
                boxShadow: '0 2px 8px rgba(16, 185, 129, 0.3)',
              }}
            >
              <span>📊</span>
              <span>Excel (.csv) yuklab olish</span>
            </button>

            <button
              type="button"
              onClick={handlePrintPdf}
              className="btn sm primary"
              style={{
                background: 'linear-gradient(135deg, #F59E0B 0%, #D97706 100%)',
                color: '#FFFFFF',
                border: 'none',
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                padding: '7px 16px',
                borderRadius: 10,
                cursor: 'pointer',
                fontWeight: 800,
                boxShadow: '0 2px 8px rgba(245, 158, 11, 0.3)',
              }}
            >
              <span>📄</span>
              <span>PDF Vedomost yuklab olish</span>
            </button>
          </div>
        </div>

        {/* Title & Metadata Badges */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', marginBottom: 6 }}>
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 800,
                  padding: '3px 10px',
                  borderRadius: 999,
                  background: 'rgba(245, 158, 11, 0.15)',
                  color: '#D97706',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 5,
                }}
              >
                <ShieldCheckIcon size={13} />
                <span>Ustoz Kabineti</span>
              </span>

              {data?.mock_code && (
                <span
                  style={{
                    fontSize: 11,
                    fontWeight: 800,
                    padding: '3px 10px',
                    borderRadius: 999,
                    background: 'rgba(16, 185, 129, 0.15)',
                    color: '#059669',
                  }}
                >
                  Kod: {data.mock_code}
                </span>
              )}

              {data?.created_at && (
                <span style={{ fontSize: 12, color: 'var(--muted)', fontWeight: 600 }}>
                  Sana: {data.created_at}
                </span>
              )}
            </div>

            <h1 style={{ margin: 0, fontSize: 'clamp(1.5rem, 3vw, 1.9rem)', fontWeight: 900, color: 'var(--ink)' }}>
              {data?.test_title || `Test #${id} Natijalari`}
            </h1>
            <p className="muted" style={{ margin: '4px 0 0', fontSize: 13.5 }}>
              O&apos;qituvchi: <b>{data?.teacher_name || user?.full_name || "O'qituvchi"}</b> · Savollar: <b>{data?.total_questions || 0} ta</b>
            </p>
          </div>
        </div>
      </div>

      {err && (
        <div className="error" style={{ marginBottom: 20 }}>
          {err}
        </div>
      )}

      {/* 4 SUMMARY STATS CARDS */}
      <div
        className="no-print grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4"
        style={{ marginBottom: 24 }}
      >
        {/* Card 1: Jami topshirganlar */}
        <div
          className="card"
          style={{
            padding: '18px 20px',
            borderRadius: 18,
            background: 'var(--card)',
            border: '1px solid var(--border)',
            boxShadow: 'var(--card-shadow)',
            display: 'flex',
            alignItems: 'center',
            gap: 14,
          }}
        >
          <div
            style={{
              width: 46,
              height: 46,
              borderRadius: 14,
              background: 'rgba(59, 130, 246, 0.12)',
              color: '#3B82F6',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontWeight: 900,
              flexShrink: 0,
            }}
          >
            👥
          </div>
          <div>
            <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              Jami topshirganlar
            </span>
            <div style={{ fontSize: 22, fontWeight: 900, color: 'var(--ink)', lineHeight: 1.2 }}>
              {data?.total_students || 0} nafar
            </div>
            <span style={{ fontSize: 11, color: '#3B82F6', fontWeight: 600 }}>o&apos;quvchi baholandi</span>
          </div>
        </div>

        {/* Card 2: O'rtacha xom ball */}
        <div
          className="card"
          style={{
            padding: '18px 20px',
            borderRadius: 18,
            background: 'var(--card)',
            border: '1px solid var(--border)',
            boxShadow: 'var(--card-shadow)',
            display: 'flex',
            alignItems: 'center',
            gap: 14,
          }}
        >
          <div
            style={{
              width: 46,
              height: 46,
              borderRadius: 14,
              background: 'rgba(16, 185, 129, 0.12)',
              color: '#10B981',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontWeight: 900,
              flexShrink: 0,
            }}
          >
            <CheckIcon size={24} />
          </div>
          <div>
            <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              O&apos;rtacha xom ball
            </span>
            <div style={{ fontSize: 22, fontWeight: 900, color: 'var(--ink)', lineHeight: 1.2 }}>
              {data?.avg_raw_score || 0} / {data?.total_questions || 0}
            </div>
            <span style={{ fontSize: 11, color: '#10B981', fontWeight: 700 }}>
              {data?.avg_percentage || 0}% muvaffaqiyat
            </span>
          </div>
        </div>

        {/* Card 3: O'rtacha Rasch dinamik ball */}
        <div
          className="card"
          style={{
            padding: '18px 20px',
            borderRadius: 18,
            background: 'var(--card)',
            border: '1px solid var(--border)',
            boxShadow: 'var(--card-shadow)',
            display: 'flex',
            alignItems: 'center',
            gap: 14,
          }}
        >
          <div
            style={{
              width: 46,
              height: 46,
              borderRadius: 14,
              background: 'rgba(245, 158, 11, 0.15)',
              color: '#F59E0B',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontWeight: 900,
              flexShrink: 0,
            }}
          >
            <StarIcon size={24} />
          </div>
          <div>
            <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              Rasch dinamik bali
            </span>
            <div style={{ fontSize: 22, fontWeight: 900, color: '#D97706', lineHeight: 1.2 }}>
              ⭐️ {data?.avg_rasch_score || 0}
            </div>
            <span style={{ fontSize: 11, color: 'var(--muted)', fontWeight: 600 }}>1PL IRT o&apos;rtachasi</span>
          </div>
        </div>

        {/* Card 4: Eng qiyin savol */}
        <div
          className="card"
          style={{
            padding: '18px 20px',
            borderRadius: 18,
            background: 'var(--card)',
            border: '1px solid var(--border)',
            boxShadow: 'var(--card-shadow)',
            display: 'flex',
            alignItems: 'center',
            gap: 14,
          }}
        >
          <div
            style={{
              width: 46,
              height: 46,
              borderRadius: 14,
              background: 'rgba(239, 68, 68, 0.12)',
              color: '#EF4444',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontWeight: 900,
              flexShrink: 0,
            }}
          >
            🔥
          </div>
          <div style={{ minWidth: 0, flex: 1 }}>
            <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              Eng qiyin savol
            </span>
            {data?.hardest_question ? (
              <>
                <div style={{ fontSize: 15, fontWeight: 900, color: '#EF4444', lineHeight: 1.2, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  #{data.hardest_question.question_number}-savol ({data.hardest_question.correct_percentage}%)
                </div>
                <span style={{ fontSize: 11, color: 'var(--muted)', fontWeight: 600 }}>
                  Vazni: ⭐️ {data.hardest_question.rasch_weight} ball
                </span>
              </>
            ) : (
              <div style={{ fontSize: 13, color: 'var(--muted)', fontWeight: 600 }}>Yetarli ma&apos;lumot yo&apos;q</div>
            )}
          </div>
        </div>
      </div>

      {/* TABS: Vedomost vs Item Analysis */}
      <div className="no-print" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12, marginBottom: 16 }}>
        <div style={{ display: 'flex', gap: 8, background: 'var(--card-2)', padding: 4, borderRadius: 12, border: '1px solid var(--border)' }}>
          <button
            type="button"
            onClick={() => setActiveTab('gradebook')}
            style={{
              padding: '8px 18px',
              borderRadius: 8,
              border: 'none',
              background: activeTab === 'gradebook' ? 'var(--card)' : 'transparent',
              color: activeTab === 'gradebook' ? 'var(--ink)' : 'var(--muted)',
              fontWeight: 800,
              fontSize: 13.5,
              cursor: 'pointer',
              boxShadow: activeTab === 'gradebook' ? 'var(--card-shadow)' : 'none',
              transition: 'all 0.15s ease',
            }}
          >
            📋 O&apos;quvchilar Vedomosti ({filteredStudents.length})
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('items')}
            style={{
              padding: '8px 18px',
              borderRadius: 8,
              border: 'none',
              background: activeTab === 'items' ? 'var(--card)' : 'transparent',
              color: activeTab === 'items' ? 'var(--ink)' : 'var(--muted)',
              fontWeight: 800,
              fontSize: 13.5,
              cursor: 'pointer',
              boxShadow: activeTab === 'items' ? 'var(--card-shadow)' : 'none',
              transition: 'all 0.15s ease',
            }}
          >
            🔍 Savollar Psixometrik Tahlili ({itemData?.items?.length || 0})
          </button>
        </div>

        {activeTab === 'gradebook' && (
          <div style={{ position: 'relative', width: '100%', maxWidth: 280 }}>
            <input
              type="text"
              placeholder="O'quvchini qidirish…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              style={{
                width: '100%',
                padding: '8px 14px',
                borderRadius: 10,
                fontSize: 13,
                fontWeight: 600,
                background: 'var(--card)',
                border: '1px solid var(--border)',
                color: 'var(--ink)',
              }}
            />
          </div>
        )}
      </div>

      {/* TAB 1: O'QUVCHILAR NATIJALAR VEDOMOSTI (SCREEN TABLE) */}
      {activeTab === 'gradebook' && (
        <div
          className="no-print card"
          style={{
            borderRadius: 20,
            overflow: 'hidden',
            padding: 0,
            background: 'var(--card)',
            border: '1px solid var(--border)',
            boxShadow: 'var(--card-shadow)',
          }}
        >
          {loading ? (
            <div style={{ padding: 40, textAlign: 'center', color: 'var(--muted)' }}>
              Natijalar yuklanmoqda…
            </div>
          ) : filteredStudents.length === 0 ? (
            <div style={{ padding: 48, textAlign: 'center', color: 'var(--muted)' }}>
              <div style={{ fontSize: 32, marginBottom: 8 }}>📝</div>
              <strong>Hozircha hech qanday natija mavjud emas.</strong>
              <p style={{ margin: '4px 0 0', fontSize: 13 }}>
                O&apos;quvchilaringizga ushbu test kodini yoki havolasini yuboring.
              </p>
            </div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: 13.5 }}>
                <thead>
                  <tr style={{ background: 'var(--card-2)', borderBottom: '1px solid var(--border)', color: 'var(--muted)', fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                    <th style={{ padding: '14px 16px', width: 60, textAlign: 'center' }}>№</th>
                    <th style={{ padding: '14px 16px' }}>O&apos;quvchi F.I.Sh</th>
                    <th style={{ padding: '14px 16px', textAlign: 'center' }}>Xom ball</th>
                    <th style={{ padding: '14px 16px', textAlign: 'center' }}>Rasch Dinamik Bali</th>
                    <th style={{ padding: '14px 16px', textAlign: 'center' }}>Daraja</th>
                    <th style={{ padding: '14px 16px', textAlign: 'center' }}>Sarflangan vaqt</th>
                    <th style={{ padding: '14px 16px', textAlign: 'right' }}>Topshirilgan vaqt</th>
                    <th style={{ padding: '14px 16px', textAlign: 'center' }}>Xatolar tahlili</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredStudents.map((st) => (
                    <tr
                      key={st.attempt_id}
                      style={{
                        borderBottom: '1px solid var(--border)',
                        transition: 'background 0.15s ease',
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.background = 'rgba(245, 158, 11, 0.04)';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.background = 'transparent';
                      }}
                    >
                      {/* O'rin */}
                      <td style={{ padding: '14px 16px', textAlign: 'center', fontWeight: 900 }}>
                        {st.rank === 1 ? (
                          <span style={{ fontSize: 18 }} title="1-o'rin (Oltin)">🥇</span>
                        ) : st.rank === 2 ? (
                          <span style={{ fontSize: 18 }} title="2-o'rin (Kumush)">🥈</span>
                        ) : st.rank === 3 ? (
                          <span style={{ fontSize: 18 }} title="3-o'rin (Bronza)">🥉</span>
                        ) : (
                          <span style={{ color: 'var(--muted)', fontSize: 13 }}>{st.rank}</span>
                        )}
                      </td>

                      {/* Student info */}
                      <td style={{ padding: '14px 16px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                          <div
                            style={{
                              width: 32,
                              height: 32,
                              borderRadius: '50%',
                              background: 'linear-gradient(135deg, #F59E0B, #D97706)',
                              color: '#FFFFFF',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              fontSize: 12,
                              fontWeight: 900,
                              flexShrink: 0,
                            }}
                          >
                            {(st.student_name || '?').split(' ').map((p) => p[0]).join('').slice(0, 2).toUpperCase()}
                          </div>
                          <div style={{ minWidth: 0 }}>
                            <div style={{ fontWeight: 800, color: 'var(--ink)' }}>{st.student_name}</div>
                            <small style={{ color: 'var(--muted)', fontSize: 11 }}>@{st.username}</small>
                          </div>
                        </div>
                      </td>

                      {/* Raw Score */}
                      <td style={{ padding: '14px 16px', textAlign: 'center' }}>
                        <strong style={{ color: 'var(--ink)', fontSize: 14 }}>{st.raw_score}</strong>
                        <div style={{ fontSize: 11, color: '#10B981', fontWeight: 700 }}>{st.percentage}%</div>
                      </td>

                      {/* Rasch Score */}
                      <td style={{ padding: '14px 16px', textAlign: 'center' }}>
                        <span
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 4,
                            padding: '4px 10px',
                            borderRadius: 20,
                            background: 'rgba(245, 158, 11, 0.12)',
                            color: '#D97706',
                            fontWeight: 800,
                            fontSize: 13,
                          }}
                        >
                          ⭐️ {st.rasch_score} ball
                        </span>
                      </td>

                      {/* Grade */}
                      <td style={{ padding: '14px 16px', textAlign: 'center' }}>
                        <span
                          style={{
                            padding: '3px 10px',
                            borderRadius: 999,
                            fontWeight: 900,
                            fontSize: 12,
                            background:
                              st.rasch_grade === 'A+' || st.rasch_grade === 'A'
                                ? 'rgba(16, 185, 129, 0.15)'
                                : st.rasch_grade.startsWith('B')
                                ? 'rgba(59, 130, 246, 0.15)'
                                : st.rasch_grade.startsWith('C')
                                ? 'rgba(245, 158, 11, 0.15)'
                                : 'rgba(239, 68, 68, 0.15)',
                            color:
                              st.rasch_grade === 'A+' || st.rasch_grade === 'A'
                                ? '#059669'
                                : st.rasch_grade.startsWith('B')
                                ? '#2563EB'
                                : st.rasch_grade.startsWith('C')
                                ? '#D97706'
                                : '#DC2626',
                          }}
                        >
                          {st.rasch_grade}
                        </span>
                      </td>

                      {/* Time Spent */}
                      <td style={{ padding: '14px 16px', textAlign: 'center', color: 'var(--muted)', fontWeight: 600 }}>
                        <div style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                          <ClockIcon size={12} />
                          <span>{st.time_spent_formatted}</span>
                        </div>
                      </td>

                      {/* Completed At */}
                      <td style={{ padding: '14px 16px', textAlign: 'right', color: 'var(--muted)', fontSize: 12.5 }}>
                        {st.completed_at}
                      </td>

                      {/* Mistake Inspector Action */}
                      <td style={{ padding: '14px 16px', textAlign: 'center' }}>
                        <button
                          type="button"
                          onClick={() => setSelectedAttemptId(st.attempt_id)}
                          className="btn sm"
                          style={{
                            padding: '5px 12px',
                            borderRadius: 8,
                            fontSize: 12,
                            fontWeight: 700,
                            background: 'rgba(245, 158, 11, 0.12)',
                            color: '#D97706',
                            border: '1px solid rgba(245, 158, 11, 0.35)',
                            cursor: 'pointer',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 5,
                            transition: 'all 0.15s ease',
                          }}
                          title="Ushbu o'quvchining savollar bo'yicha xatolarini tahlil qilish"
                        >
                          <span>🔍</span>
                          <span>Xatolar tahlili</span>
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* TAB 2: SAVOLLAR PSIXOMETRIK TAHLILI (ITEM ANALYSIS) */}
      {activeTab === 'items' && (
        <div
          className="no-print card"
          style={{
            borderRadius: 20,
            overflow: 'hidden',
            padding: 0,
            background: 'var(--card)',
            border: '1px solid var(--border)',
            boxShadow: 'var(--card-shadow)',
          }}
        >
          {!itemData || itemData.items.length === 0 ? (
            <div style={{ padding: 48, textAlign: 'center', color: 'var(--muted)' }}>
              Savollar tahlili yuklanmoqda yoki savollar topilmadi…
            </div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: 13.5 }}>
                <thead>
                  <tr style={{ background: 'var(--card-2)', borderBottom: '1px solid var(--border)', color: 'var(--muted)', fontSize: 12, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                    <th style={{ padding: '14px 16px', width: 50, textAlign: 'center' }}>№</th>
                    <th style={{ padding: '14px 16px' }}>Savol matni</th>
                    <th style={{ padding: '14px 16px', textAlign: 'center' }}>To&apos;g&apos;ri topish foizi ($P_i$)</th>
                    <th style={{ padding: '14px 16px', textAlign: 'center' }}>Rasch Vazni</th>
                    <th style={{ padding: '14px 16px' }}>Eng ko&apos;p chalg&apos;itgan noto&apos;g&apos;ri variant</th>
                  </tr>
                </thead>
                <tbody>
                  {itemData.items.map((it) => (
                    <tr
                      key={it.question_id}
                      style={{
                        borderBottom: '1px solid var(--border)',
                        transition: 'background 0.15s ease',
                      }}
                    >
                      {/* Q Number */}
                      <td style={{ padding: '14px 16px', textAlign: 'center', fontWeight: 900, color: 'var(--ink)' }}>
                        #{it.question_number}
                      </td>

                      {/* Question Text */}
                      <td style={{ padding: '14px 16px', maxWidth: 360 }}>
                        <div style={{ fontWeight: 700, color: 'var(--ink)', lineHeight: 1.4 }}>
                          {it.text}
                        </div>
                        <small style={{ color: 'var(--muted)', fontSize: 11 }}>
                          Jami urinishlar: {it.total_attempts} ta · To&apos;g&apos;ri: {it.correct_attempts} ta
                        </small>
                      </td>

                      {/* Accuracy bar */}
                      <td style={{ padding: '14px 16px', textAlign: 'center', width: 180 }}>
                        <div style={{ fontWeight: 800, fontSize: 13.5, color: it.correct_percentage >= 70 ? '#059669' : it.correct_percentage >= 40 ? '#D97706' : '#DC2626', marginBottom: 4 }}>
                          {it.correct_percentage}%
                        </div>
                        <div style={{ width: '100%', height: 6, borderRadius: 999, background: 'var(--card-2)', overflow: 'hidden' }}>
                          <div
                            style={{
                              width: `${it.correct_percentage}%`,
                              height: '100%',
                              borderRadius: 999,
                              background: it.correct_percentage >= 70 ? '#10B981' : it.correct_percentage >= 40 ? '#F59E0B' : '#EF4444',
                            }}
                          />
                        </div>
                      </td>

                      {/* Rasch Weight */}
                      <td style={{ padding: '14px 16px', textAlign: 'center' }}>
                        <span
                          style={{
                            padding: '3px 10px',
                            borderRadius: 14,
                            background: 'rgba(245, 158, 11, 0.12)',
                            color: '#D97706',
                            fontWeight: 800,
                            fontSize: 12.5,
                          }}
                        >
                          ⭐️ {it.rasch_weight} ball
                        </span>
                        <div style={{ fontSize: 10.5, color: 'var(--muted)', marginTop: 2 }}>
                          Logit: {it.difficulty_logit}
                        </div>
                      </td>

                      {/* Most distracting choice */}
                      <td style={{ padding: '14px 16px' }}>
                        {it.most_distracting_choice ? (
                          <div
                            style={{
                              padding: '6px 10px',
                              borderRadius: 8,
                              background: 'rgba(239, 68, 68, 0.08)',
                              border: '1px solid rgba(239, 68, 68, 0.2)',
                              fontSize: 12,
                              color: '#DC2626',
                            }}
                          >
                            <strong>⚠️ &quot;{it.most_distracting_choice.text}&quot;</strong>
                            <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2 }}>
                              {it.most_distracting_choice.pick_count} nafar o&apos;quvchi ({it.most_distracting_choice.pick_percentage}%) adashgan
                            </div>
                          </div>
                        ) : (
                          <span style={{ color: 'var(--muted)', fontSize: 12 }}>Chalg&apos;ituvchi qayd etilmadi</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* =======================================================================
          OFFICIAL PRINTABLE PDF TEMPLATE (FAFAT CHOP ETISHDA / PDFDA CHIQADI)
          ======================================================================= */}
      <div className="printable-gradebook" style={{ display: 'none', padding: '20px 24px' }}>
        {/* Rasmiy Blank Bosh qismi */}
        <div style={{ borderBottom: '2px solid #000000', paddingBottom: 14, marginBottom: 18, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <div style={{ fontSize: 20, fontWeight: 900, letterSpacing: '0.05em', color: '#000000' }}>GRANDEC ACADEMIC EDTECH</div>
            <div style={{ fontSize: 13, fontWeight: 700, color: '#333333' }}>O&apos;QUVCHI NATIJALARI RASMIY VEDOMOSTI</div>
            <div style={{ fontSize: 11, color: '#666666' }}>Milliy ta&apos;lim va baholash standarti (Rasch IRT 1PL)</div>
          </div>
          <div style={{ textAlign: 'right', fontSize: 11, color: '#333333' }}>
            <div><b>Sana:</b> {data?.created_at || new Date().toLocaleDateString('uz-UZ')}</div>
            <div><b>Test kodi:</b> {data?.mock_code || `#TEST-${id}`}</div>
            <div><b>Tizim:</b> grandec.uz</div>
          </div>
        </div>

        {/* Test va Ustoz haqida ma'lumot */}
        <div style={{ background: '#f5f5f5', padding: '12px 16px', borderRadius: 6, marginBottom: 16, fontSize: 12, display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
          <div><b>Test nomi:</b> {data?.test_title}</div>
          <div><b>O&apos;qituvchi:</b> {data?.teacher_name || user?.full_name}</div>
          <div><b>Jami savollar:</b> {data?.total_questions || 0} ta</div>
          <div><b>Qatnashchilar:</b> {data?.total_students || 0} nafar</div>
          <div><b>O&apos;rtacha xom ball:</b> {data?.avg_raw_score || 0} / {data?.total_questions || 0}</div>
          <div><b>O&apos;rtacha foiz:</b> {data?.avg_percentage || 0}%</div>
          <div><b>O&apos;rtacha Rasch:</b> {data?.avg_rasch_score || 0} ball</div>
          <div><b>Holati:</b> Tasdiqlangan</div>
        </div>

        {/* Baholar Jadvali */}
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11, marginBottom: 30 }}>
          <thead>
            <tr style={{ background: '#eeeeee', borderBottom: '1.5px solid #000000', borderTop: '1.5px solid #000000' }}>
              <th style={{ padding: '6px 8px', border: '1px solid #999', textAlign: 'center', width: 35 }}>№</th>
              <th style={{ padding: '6px 8px', border: '1px solid #999' }}>O&apos;quvchi F.I.Sh</th>
              <th style={{ padding: '6px 8px', border: '1px solid #999', textAlign: 'center' }}>Foydalanuvchi</th>
              <th style={{ padding: '6px 8px', border: '1px solid #999', textAlign: 'center' }}>Xom ball</th>
              <th style={{ padding: '6px 8px', border: '1px solid #999', textAlign: 'center' }}>Foiz</th>
              <th style={{ padding: '6px 8px', border: '1px solid #999', textAlign: 'center' }}>Rasch Bali</th>
              <th style={{ padding: '6px 8px', border: '1px solid #999', textAlign: 'center' }}>Daraja</th>
              <th style={{ padding: '6px 8px', border: '1px solid #999', textAlign: 'center' }}>Sarflangan vaqt</th>
            </tr>
          </thead>
          <tbody>
            {(data?.students || []).map((s) => (
              <tr key={s.attempt_id} style={{ borderBottom: '1px solid #ccc' }}>
                <td style={{ padding: '5px 8px', border: '1px solid #999', textAlign: 'center', fontWeight: 'bold' }}>{s.rank}</td>
                <td style={{ padding: '5px 8px', border: '1px solid #999', fontWeight: 'bold' }}>{s.student_name}</td>
                <td style={{ padding: '5px 8px', border: '1px solid #999', textAlign: 'center' }}>@{s.username}</td>
                <td style={{ padding: '5px 8px', border: '1px solid #999', textAlign: 'center' }}>{s.raw_score}</td>
                <td style={{ padding: '5px 8px', border: '1px solid #999', textAlign: 'center' }}>{s.percentage}%</td>
                <td style={{ padding: '5px 8px', border: '1px solid #999', textAlign: 'center', fontWeight: 'bold' }}>{s.rasch_score} ball</td>
                <td style={{ padding: '5px 8px', border: '1px solid #999', textAlign: 'center', fontWeight: 'bold' }}>{s.rasch_grade}</td>
                <td style={{ padding: '5px 8px', border: '1px solid #999', textAlign: 'center' }}>{s.time_spent_formatted}</td>
              </tr>
            ))}
          </tbody>
        </table>

        {/* Imzo va Muhr Joyi */}
        <div style={{ marginTop: 40, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', fontSize: 12 }}>
          <div>
            <div><b>O&apos;qituvchi F.I.Sh:</b> {data?.teacher_name || user?.full_name}</div>
            <div style={{ marginTop: 16 }}><b>Imzo:</b> ___________________________</div>
          </div>
          <div style={{ textAlign: 'center' }}>
            <div style={{ width: 100, height: 100, border: '1px dashed #999999', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto', fontSize: 10, color: '#999999' }}>
              M.O&apos;.
            </div>
            <div style={{ marginTop: 6, fontSize: 10, color: '#666666' }}>Muhr o&apos;rni</div>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div><b>O&apos;quv bo&apos;limi boshlig&apos;i:</b> ____________________</div>
            <div style={{ marginTop: 16 }}><b>Sana:</b> &quot;_____&quot; ________________ 2026 y.</div>
          </div>
        </div>

        <div style={{ marginTop: 40, borderTop: '1px solid #dddddd', paddingTop: 8, fontSize: 9.5, color: '#888888', textAlign: 'center' }}>
          Ushbu rasmiy vedomost GRAND EDUCATION LMS avtomatlashtirilgan baholash dvigateli tomonidan shakllantirilgan. Hujjat kodi: GRN-GB-{id}-{Date.now().toString().slice(-6)}
        </div>
      </div>

      {/* Mistake Inspector Modal */}
      <StudentAttemptReviewModal
        isOpen={Boolean(selectedAttemptId)}
        attemptId={selectedAttemptId}
        onClose={() => setSelectedAttemptId(null)}
      />
    </div>
  );
}
