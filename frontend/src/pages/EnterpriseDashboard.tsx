import React, { useEffect, useState } from 'react';
import { api } from '../lib/api';
import {
  AwardIcon,
  BarChartIcon,
  DownloadIcon,
  ShieldCheckIcon,
  TrendingUpIcon,
  UploadIcon,
  UsersIcon,
  XIcon,
} from '../components/icons';

interface CenterStats {
  total_students: number;
  seat_limit: number;
  active_today: number;
  avg_score: number;
  bmb_grade: string;
}

interface CenterDetails {
  id: number;
  name: string;
  slug: string;
  student_seat_limit: number;
  remaining_seats: number;
  subscription_expires_at: string | null;
  is_active: boolean;
}

interface BranchItem {
  id: number;
  name: string;
  students_count: number;
  avg_score: number;
  phone: string;
}

interface TeacherItem {
  id: number;
  name: string;
  email: string;
  students_count: number;
  avg_score: number;
  branch_name: string;
}

interface RecentResult {
  id: number;
  student_name: string;
  test_title: string;
  percentage: number;
  is_passed: boolean;
  created_at: string;
}

export default function EnterpriseDashboard() {
  const [center, setCenter] = useState<CenterDetails | null>(null);
  const [stats, setStats] = useState<CenterStats | null>(null);
  const [branches, setBranches] = useState<BranchItem[]>([]);
  const [teachers, setTeachers] = useState<TeacherItem[]>([]);
  const [recentResults, setRecentResults] = useState<RecentResult[]>([]);
  const [loading, setLoading] = useState(true);

  // Bulk import modal state
  const [importModalOpen, setImportModalOpen] = useState(false);
  const [csvText, setCsvText] = useState('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<{ success: boolean; message: string } | null>(null);

  const loadData = async () => {
    try {
      const res = await api.get<{
        center: CenterDetails;
        stats: CenterStats;
        branches: BranchItem[];
        teachers: TeacherItem[];
        recent_results: RecentResult[];
      }>('/enterprise/dashboard/');

      setCenter(res.center);
      setStats(res.stats);
      setBranches(res.branches || []);
      setTeachers(res.teachers || []);
      setRecentResults(res.recent_results || []);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadData();
  }, []);

  const handleBulkImport = async (e: React.FormEvent) => {
    e.preventDefault();
    setImporting(true);
    setImportResult(null);

    try {
      let res: any;
      if (selectedFile) {
        const formData = new FormData();
        formData.append('file', selectedFile);
        res = await api.post('/enterprise/students/bulk-import/', formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
        });
      } else if (csvText.trim()) {
        const lines = csvText.trim().split('\n');
        const students = lines.map((line) => {
          const parts = line.split(/[,;\t]/).map((p) => p.trim());
          return {
            first_name: parts[0] || "O'quvchi",
            last_name: parts[1] || '',
            phone: parts[2] || '',
            email: parts[3] || '',
            branch_name: parts[4] || '',
          };
        });
        res = await api.post('/enterprise/students/bulk-import/', { students });
      } else {
        alert("Iltimos, CSV faylni tanlang yoki matn maydoniga o'quvchilar ma'lumotlarini kiriting.");
        setImporting(false);
        return;
      }

      setImportResult({ success: true, message: res.message });
      setSelectedFile(null);
      setCsvText('');
      await loadData();
    } catch (err: any) {
      setImportResult({
        success: false,
        message: err?.response?.data?.error || "Yuklashda xatolik yuz berdi.",
      });
    } finally {
      setImporting(false);
    }
  };

  const handleDownloadReport = () => {
    window.open('/api/v1/enterprise/report/download/', '_blank');
  };

  if (loading || !center || !stats) {
    return <div className="card" style={{ padding: 40, textAlign: 'center' }}>Enterprise portali yuklanmoqda...</div>;
  }

  const seatUsagePercent = Math.min(100, Math.round((stats.total_students / stats.seat_limit) * 100));

  return (
    <div style={{ maxWidth: 1140, margin: '0 auto', paddingBottom: 60 }}>
      {/* Top Header Card */}
      <div
        className="card"
        style={{
          padding: '28px 24px',
          borderRadius: 20,
          background: 'linear-gradient(135deg, rgba(245, 158, 11, 0.12), rgba(30, 41, 59, 0.6))',
          border: '1px solid rgba(245, 158, 11, 0.3)',
          marginBottom: 24,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: 16,
        }}
      >
        <div>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '3px 10px', borderRadius: 16, background: 'rgba(245, 158, 11, 0.2)', color: 'var(--accent-dark)', fontWeight: 800, fontSize: 11, marginBottom: 8 }}>
            <ShieldCheckIcon size={14} /> B2B SAAS / ENTERPRISE ORGANIZATION HUB
          </div>
          <h1 style={{ fontSize: 26, margin: 0, fontWeight: 900 }}>{center.name}</h1>
          <span className="muted small">O'quv markaz direktori va filiallarni boshqarish kabineti</span>
        </div>

        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          <button
            type="button"
            onClick={handleDownloadReport}
            className="btn secondary"
            style={{ display: 'flex', alignItems: 'center', gap: 6, fontWeight: 700 }}
          >
            <DownloadIcon size={16} /> Oylik tahliliy hisobot (CSV)
          </button>

          <button
            type="button"
            onClick={() => setImportModalOpen(true)}
            className="btn primary btn-glow"
            style={{ display: 'flex', alignItems: 'center', gap: 6, fontWeight: 800 }}
          >
            <UploadIcon size={16} /> O'quvchilarni ommaviy yuklash
          </button>
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 16, marginBottom: 28 }}>
        <div className="card" style={{ padding: 20, borderRadius: 16 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--muted)', marginBottom: 8 }}>
            <span style={{ fontSize: 13, fontWeight: 600 }}>Jami o'quvchilar</span>
            <UsersIcon size={18} style={{ color: 'var(--accent)' }} />
          </div>
          <strong style={{ fontSize: 26, fontWeight: 900 }}>{stats.total_students}</strong>
          <span className="muted small" style={{ display: 'block', marginTop: 4 }}>
            Barcha filiallar bo'yicha
          </span>
        </div>

        <div className="card" style={{ padding: 20, borderRadius: 16 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--muted)', marginBottom: 8 }}>
            <span style={{ fontSize: 13, fontWeight: 600 }}>O'rinlar limiti</span>
            <ShieldCheckIcon size={18} style={{ color: '#10b981' }} />
          </div>
          <strong style={{ fontSize: 26, fontWeight: 900 }}>
            {stats.total_students} / {stats.seat_limit}
          </strong>
          {/* Progress bar */}
          <div style={{ width: '100%', height: 6, borderRadius: 3, background: 'var(--border)', marginTop: 8, overflow: 'hidden' }}>
            <div style={{ width: `${seatUsagePercent}%`, height: '100%', background: seatUsagePercent > 90 ? '#ef4444' : 'var(--accent)' }} />
          </div>
          <span className="muted small" style={{ display: 'block', marginTop: 4 }}>
            {center.remaining_seats} ta bo'sh o'rin mavjud
          </span>
        </div>

        <div className="card" style={{ padding: 20, borderRadius: 16 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--muted)', marginBottom: 8 }}>
            <span style={{ fontSize: 13, fontWeight: 600 }}>Bugun test ishlaganlar</span>
            <TrendingUpIcon size={18} style={{ color: '#3b82f6' }} />
          </div>
          <strong style={{ fontSize: 26, fontWeight: 900 }}>{stats.active_today}</strong>
          <span className="muted small" style={{ display: 'block', marginTop: 4 }}>
            Bugungi faol o'quvchilar
          </span>
        </div>

        <div className="card" style={{ padding: 20, borderRadius: 16 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--muted)', marginBottom: 8 }}>
            <span style={{ fontSize: 13, fontWeight: 600 }}>O'rtacha BMB darajasi</span>
            <AwardIcon size={18} style={{ color: 'var(--accent)' }} />
          </div>
          <strong style={{ fontSize: 26, fontWeight: 900, color: 'var(--accent)' }}>{stats.bmb_grade}</strong>
          <span className="muted small" style={{ display: 'block', marginTop: 4 }}>
            O'rtacha natija: {stats.avg_score}%
          </span>
        </div>
      </div>

      {/* Grid: Filiallararo raqobat & Ustozlar reytingi */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: 20, marginBottom: 28 }}>
        {/* Filiallararo raqobat */}
        <div className="card" style={{ padding: 24, borderRadius: 16 }}>
          <h2 style={{ fontSize: 18, marginTop: 0, marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
            <BarChartIcon size={20} style={{ color: 'var(--accent)' }} /> Filiallararo Raqobat
          </h2>

          {branches.length === 0 ? (
            <div className="muted small">Hozircha filiallar kiritilmagan.</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {branches.map((b, idx) => (
                <div
                  key={b.id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '12px 14px',
                    borderRadius: 12,
                    background: 'var(--card-2)',
                    border: '1px solid var(--border)',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <span style={{ width: 24, fontWeight: 800, fontSize: 14, color: idx === 0 ? 'var(--accent)' : 'var(--muted)' }}>
                      #{idx + 1}
                    </span>
                    <div>
                      <strong style={{ display: 'block', fontSize: 14 }}>{b.name}</strong>
                      <span className="muted small">{b.students_count} nafar o'quvchi</span>
                    </div>
                  </div>

                  <div style={{ textAlign: 'right' }}>
                    <strong style={{ fontSize: 16, color: 'var(--accent)' }}>{b.avg_score}%</strong>
                    <span className="muted small" style={{ display: 'block', fontSize: 11 }}>o'rtacha ball</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Ustozlar reytingi */}
        <div className="card" style={{ padding: 24, borderRadius: 16 }}>
          <h2 style={{ fontSize: 18, marginTop: 0, marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
            <AwardIcon size={20} style={{ color: 'var(--accent)' }} /> Ustozlar Reytingi
          </h2>

          {teachers.length === 0 ? (
            <div className="muted small">O'qituvchilar hisoblari mavjud emas.</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {teachers.map((t, idx) => (
                <div
                  key={t.id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '12px 14px',
                    borderRadius: 12,
                    background: 'var(--card-2)',
                    border: '1px solid var(--border)',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <span style={{ width: 24, fontWeight: 800, fontSize: 14, color: idx === 0 ? 'var(--accent)' : 'var(--muted)' }}>
                      #{idx + 1}
                    </span>
                    <div>
                      <strong style={{ display: 'block', fontSize: 14 }}>{t.name}</strong>
                      <span className="muted small">{t.branch_name} • {t.students_count} o'quvchi</span>
                    </div>
                  </div>

                  <div style={{ textAlign: 'right' }}>
                    <strong style={{ fontSize: 16, color: '#10b981' }}>{t.avg_score}%</strong>
                    <span className="muted small" style={{ display: 'block', fontSize: 11 }}>guruhi o'rtachasi</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Recent Test Submissions */}
      <div className="card" style={{ padding: 24, borderRadius: 16 }}>
        <h2 style={{ fontSize: 18, marginTop: 0, marginBottom: 16 }}>So'nggi topshirilgan testlar</h2>
        {recentResults.length === 0 ? (
          <div className="muted small">Hozircha natijalar mavjud emas.</div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, textAlign: 'left' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border)', color: 'var(--muted)' }}>
                  <th style={{ padding: '8px 10px' }}>O'quvchi</th>
                  <th style={{ padding: '8px 10px' }}>Test nomi</th>
                  <th style={{ padding: '8px 10px' }}>Natija</th>
                  <th style={{ padding: '8px 10px' }}>Holat</th>
                  <th style={{ padding: '8px 10px' }}>Vaqti</th>
                </tr>
              </thead>
              <tbody>
                {recentResults.map((r) => (
                  <tr key={r.id} style={{ borderBottom: '1px solid var(--border)' }}>
                    <td style={{ padding: '10px 10px', fontWeight: 600 }}>{r.student_name}</td>
                    <td style={{ padding: '10px 10px' }}>{r.test_title}</td>
                    <td style={{ padding: '10px 10px', fontWeight: 700, color: 'var(--accent)' }}>{r.percentage}%</td>
                    <td style={{ padding: '10px 10px' }}>
                      <span style={{ color: r.is_passed ? '#10b981' : '#ef4444', fontWeight: 600 }}>
                        {r.is_passed ? "✓ O'tdi" : "✗ O'tmadi"}
                      </span>
                    </td>
                    <td style={{ padding: '10px 10px', color: 'var(--muted)' }}>
                      {new Date(r.created_at).toLocaleString('uz-UZ', { dateStyle: 'short', timeStyle: 'short' })}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Bulk Import Modal */}
      {importModalOpen && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0, 0, 0, 0.7)',
            backdropFilter: 'blur(8px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: 20,
          }}
        >
          <div
            className="card"
            style={{
              maxWidth: 620,
              width: '100%',
              padding: 28,
              borderRadius: 20,
              background: 'var(--card)',
              border: '1px solid var(--border)',
              position: 'relative',
              maxHeight: '90vh',
              overflowY: 'auto',
            }}
          >
            <button
              type="button"
              onClick={() => setImportModalOpen(false)}
              style={{
                position: 'absolute',
                top: 18,
                right: 18,
                background: 'transparent',
                border: 'none',
                color: 'var(--muted)',
                cursor: 'pointer',
              }}
            >
              <XIcon size={20} />
            </button>

            <h2 style={{ fontSize: 20, margin: '0 0 6px', fontWeight: 800 }}>
              📤 O'quvchilarni ommaviy yuklash (Bulk Import)
            </h2>
            <p className="muted small" style={{ margin: '0 0 18px', lineHeight: 1.5 }}>
              Bir vaqtning o'zida 500 tagacha o'quvchini CSV fayl yoki matn orqali markaz bazasiga kiritish.
              Barcha yangi o'quvchilar uchun standart parol: <code>Grand2026!</code>
            </p>

            {importResult && (
              <div
                style={{
                  padding: '12px 16px',
                  borderRadius: 10,
                  marginBottom: 16,
                  background: importResult.success ? 'rgba(16, 185, 129, 0.12)' : 'rgba(239, 68, 68, 0.12)',
                  border: importResult.success ? '1px solid rgba(16, 185, 129, 0.3)' : '1px solid rgba(239, 68, 68, 0.3)',
                  color: importResult.success ? '#10b981' : '#ef4444',
                  fontSize: 13,
                }}
              >
                {importResult.message}
              </div>
            )}

            <form onSubmit={handleBulkImport}>
              {/* Option 1: File Upload */}
              <div style={{ marginBottom: 16 }}>
                <label style={{ display: 'block', fontSize: 13, fontWeight: 700, marginBottom: 6 }}>
                  1. CSV / Excel faylni tanlang:
                </label>
                <input
                  type="file"
                  accept=".csv,.txt"
                  onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    borderRadius: 10,
                    border: '1px solid var(--border)',
                    background: 'var(--card-2)',
                    fontSize: 13,
                  }}
                />
              </div>

              <div style={{ textAlign: 'center', margin: '10px 0', color: 'var(--muted)', fontSize: 12 }}>— YOKI —</div>

              {/* Option 2: Text paste */}
              <div style={{ marginBottom: 20 }}>
                <label style={{ display: 'block', fontSize: 13, fontWeight: 700, marginBottom: 6 }}>
                  2. Ma'lumotlarni matn sifatida kiriting (har bir qator 1 ta o'quvchi):
                </label>
                <span className="muted small" style={{ display: 'block', marginBottom: 6 }}>
                  Format: <code>Ism, Familiya, Telefon, Email, Filial</code>
                </span>
                <textarea
                  rows={6}
                  placeholder="Ali, Valiyev, +998901234567, ali@gmail.com, Chilonzor filiali&#10;Malika, Karimova, +998912345678, malika@gmail.com, Yunusobod filiali"
                  value={csvText}
                  onChange={(e) => setCsvText(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '10px 12px',
                    borderRadius: 10,
                    border: '1px solid var(--border)',
                    background: 'var(--card-2)',
                    color: 'var(--ink)',
                    fontSize: 13,
                    fontFamily: 'monospace',
                  }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
                <button
                  type="button"
                  onClick={() => setImportModalOpen(false)}
                  className="btn secondary"
                >
                  Bekor qilish
                </button>
                <button
                  type="submit"
                  disabled={importing}
                  className="btn primary btn-glow"
                  style={{ fontWeight: 800 }}
                >
                  {importing ? "Yuklanmoqda..." : "Bazaga yuklash ✓"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
