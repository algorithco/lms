import { useEffect, useState } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import {
  GraduationCap,
  Building2,
  BookOpen,
  Award,
  ArrowRight,
  CheckCircle2,
  Copy,
  Check,
  Phone,
  ArrowLeft,
  Flame,
  AlertCircle,
} from 'lucide-react';
import { StudentGroupDetailApi, type StudentGroupViewData } from '../lib/api';
import { useToast } from '../context/ToastContext';

export default function StudentGroupDetail() {
  const { groupId } = useParams<{ groupId: string }>();
  const navigate = useNavigate();
  const [data, setData] = useState<StudentGroupViewData | null>(null);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const toast = useToast();

  const loadData = async () => {
    if (!groupId) return;
    try {
      setLoading(true);
      setError(null);
      const res = await StudentGroupDetailApi.getStudentView(Number(groupId));
      setData(res);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Guruh ma‘lumotlarini yuklab bo‘lmadi';
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [groupId]);

  const copyCode = () => {
    if (!data?.group.invite_code) return;
    navigator.clipboard.writeText(data.group.invite_code);
    setCopied(true);
    toast.success('Guruh kodi nusxalandi: ' + data.group.invite_code);
    setTimeout(() => setCopied(false), 2000);
  };

  if (loading) {
    return (
      <div style={{ maxWidth: 1000, margin: '0 auto', padding: '60px 16px', textAlign: 'center', color: '#94A3B8' }}>
        <div style={{ fontSize: 18, fontWeight: 600 }}>Guruh muhiti yuklanmoqda...</div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div style={{ maxWidth: 600, margin: '60px auto', padding: 24, textAlign: 'center' }}>
        <AlertCircle size={48} color="#EF4444" style={{ marginBottom: 16 }} />
        <h2 style={{ fontSize: 20, fontWeight: 700, margin: '0 0 8px' }}>Guruh topilmadi yoki ruxsat yo‘q</h2>
        <p style={{ color: '#94A3B8', fontSize: 14, margin: '0 0 20px' }}>
          {error || 'Siz ushbu guruh a‘zosi emassiz.'}
        </p>
        <Link
          to="/dashboard"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 8,
            padding: '10px 20px',
            borderRadius: 10,
            background: '#C8922A',
            color: '#fff',
            textDecoration: 'none',
            fontWeight: 600,
          }}
        >
          <ArrowLeft size={16} /> Bosh sahifaga qaytish
        </Link>
      </div>
    );
  }

  const { group, branch, teacher, assigned_tests, leaderboard, my_rank } = data;

  return (
    <div style={{ maxWidth: 1050, margin: '0 auto', padding: '20px 16px 80px' }}>
      {/* Back button */}
      <div style={{ marginBottom: 16 }}>
        <button
          onClick={() => navigate(-1)}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 6,
            background: 'none',
            border: 'none',
            color: '#94A3B8',
            cursor: 'pointer',
            fontSize: 14,
            fontWeight: 500,
          }}
        >
          <ArrowLeft size={16} /> Orqaga
        </button>
      </div>

      {/* Main Group Header Card */}
      <div
        style={{
          background: 'linear-gradient(135deg, rgba(30, 41, 59, 0.9) 0%, rgba(15, 23, 42, 0.95) 100%)',
          borderRadius: 22,
          padding: '24px 28px',
          border: '1px solid rgba(200, 146, 42, 0.25)',
          boxShadow: '0 10px 30px rgba(0,0,0,0.25)',
          marginBottom: 24,
        }}
      >
        <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'flex-start', gap: 16 }}>
          <div>
            {/* Branch and Code Badges */}
            <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 8, marginBottom: 10 }}>
              {branch && (
                <span
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 6,
                    padding: '4px 10px',
                    borderRadius: 8,
                    background: 'rgba(59, 130, 246, 0.15)',
                    color: '#60A5FA',
                    fontSize: 12,
                    fontWeight: 600,
                    border: '1px solid rgba(59, 130, 246, 0.3)',
                  }}
                >
                  <Building2 size={13} />
                  {branch.name} [{branch.branch_code}]
                </span>
              )}

              <span
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 6,
                  padding: '4px 10px',
                  borderRadius: 8,
                  background: 'rgba(200, 146, 42, 0.15)',
                  color: '#F59E0B',
                  fontSize: 12,
                  fontWeight: 700,
                  border: '1px solid rgba(200, 146, 42, 0.3)',
                }}
              >
                Guruh Kodi: {group.invite_code}
              </span>
            </div>

            <h1 style={{ fontSize: 24, fontWeight: 800, margin: '0 0 6px', color: '#F8FAFC' }}>
              {group.name}
            </h1>

            {group.description && (
              <p style={{ margin: '0 0 12px', color: '#94A3B8', fontSize: 14 }}>
                {group.description}
              </p>
            )}

            {/* Teacher Details */}
            <div
              style={{
                display: 'inline-flex',
                flexWrap: 'wrap',
                alignItems: 'center',
                gap: 12,
                background: 'rgba(255,255,255,0.04)',
                padding: '8px 14px',
                borderRadius: 12,
                marginTop: 6,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span
                  style={{
                    width: 32,
                    height: 32,
                    borderRadius: 8,
                    background: 'rgba(200, 146, 42, 0.2)',
                    color: '#F59E0B',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <GraduationCap size={18} />
                </span>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 700, color: '#F8FAFC' }}>
                    {teacher.name}
                  </div>
                  <div style={{ fontSize: 11, color: '#94A3B8' }}>
                    {teacher.subject_label} • {teacher.qualification}
                  </div>
                </div>
              </div>

              {teacher.phone && (
                <a
                  href={`tel:${teacher.phone}`}
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 4,
                    fontSize: 12,
                    color: '#10B981',
                    textDecoration: 'none',
                    padding: '4px 8px',
                    borderRadius: 6,
                    background: 'rgba(16, 185, 129, 0.1)',
                  }}
                >
                  <Phone size={12} /> {teacher.phone}
                </a>
              )}
            </div>
          </div>

          {/* Quick Code Share Action */}
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 10 }}>
            <button
              onClick={copyCode}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 8,
                padding: '9px 16px',
                borderRadius: 10,
                background: 'rgba(255,255,255,0.08)',
                border: '1px solid rgba(255,255,255,0.15)',
                color: '#fff',
                fontSize: 13,
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              {copied ? <Check size={16} color="#10B981" /> : <Copy size={16} />}
              {copied ? 'Nusxalandi!' : 'Kodni ulashish'}
            </button>

            {my_rank && (
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '6px 14px',
                  borderRadius: 10,
                  background: 'rgba(200,146,42,0.15)',
                  border: '1px solid rgba(200,146,42,0.3)',
                  color: '#F59E0B',
                  fontSize: 13,
                  fontWeight: 700,
                }}
              >
                <Flame size={16} />
                Sizning reytingingiz: {my_rank}-o‘rin
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Main Content: 2-column on desktop */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(330px, 1fr))', gap: 24 }}>
        {/* Left Column: Assigned Homework Tests */}
        <div>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
            <h2 style={{ fontSize: 18, fontWeight: 700, margin: 0, display: 'flex', alignItems: 'center', gap: 8 }}>
              <BookOpen size={20} color="#C8922A" />
              Faol Uy Vazifasi Testlari ({assigned_tests.length})
            </h2>
          </div>

          {assigned_tests.length === 0 ? (
            <div
              style={{
                background: 'var(--card-bg, #1E293B)',
                borderRadius: 16,
                padding: '30px 20px',
                textAlign: 'center',
                color: '#94A3B8',
                border: '1px solid rgba(255,255,255,0.08)',
              }}
            >
              <CheckCircle2 size={36} color="#10B981" style={{ marginBottom: 10 }} />
              <div style={{ fontSize: 15, fontWeight: 600, color: '#F8FAFC' }}>
                Hozircha faol vazifalar yo‘q
              </div>
              <p style={{ fontSize: 13, margin: '6px 0 0' }}>
                Ustoz yangi test biriktirganda shu yerda paydo bo‘ladi.
              </p>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {assigned_tests.map((t) => (
                <div
                  key={t.id}
                  style={{
                    background: 'var(--card-bg, #1E293B)',
                    borderRadius: 16,
                    padding: '18px',
                    border: '1px solid rgba(255,255,255,0.08)',
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'space-between',
                    gap: 12,
                    boxShadow: '0 4px 14px rgba(0,0,0,0.1)',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 10 }}>
                    <div>
                      <h3 style={{ fontSize: 16, fontWeight: 700, margin: '0 0 6px', color: '#F8FAFC' }}>
                        {t.title}
                      </h3>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 12, fontSize: 12, color: '#94A3B8' }}>
                        <span>📝 {t.total_questions} ta savol</span>
                        <span>⏱ {t.duration_minutes} daqiqa</span>
                      </div>
                    </div>

                    {t.status === 'completed' && t.result ? (
                      <span
                        style={{
                          padding: '4px 10px',
                          borderRadius: 8,
                          background: 'rgba(16, 185, 129, 0.15)',
                          color: '#10B981',
                          fontSize: 12,
                          fontWeight: 700,
                          border: '1px solid rgba(16, 185, 129, 0.3)',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        ✅ {t.result.percentage}% ({t.result.grade})
                      </span>
                    ) : (
                      <span
                        style={{
                          padding: '4px 10px',
                          borderRadius: 8,
                          background: 'rgba(200, 146, 42, 0.15)',
                          color: '#F59E0B',
                          fontSize: 12,
                          fontWeight: 700,
                          border: '1px solid rgba(200, 146, 42, 0.3)',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        ⚡️ Kutilmoqda
                      </span>
                    )}
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingTop: 6 }}>
                    {t.status === 'completed' && t.result ? (
                      <div style={{ fontSize: 12, color: '#94A3B8' }}>
                        Sana: {t.result.date} • Ball: {t.result.score}/{t.result.max_score}
                      </div>
                    ) : (
                      <div style={{ fontSize: 12, color: '#F59E0B' }}>
                        Muddati: Joriy darsgacha topshiring
                      </div>
                    )}

                    <Link
                      to={t.status === 'completed' ? `/results/${t.id}` : `/tests/${t.id}`}
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 6,
                        padding: '8px 16px',
                        borderRadius: 10,
                        background: t.status === 'completed' ? 'rgba(255,255,255,0.08)' : '#C8922A',
                        color: '#fff',
                        fontWeight: 600,
                        fontSize: 13,
                        textDecoration: 'none',
                      }}
                    >
                      {t.status === 'completed' ? 'Natijani ko‘rish' : 'Testni boshlash'}
                      <ArrowRight size={14} />
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Right Column: Live Group Leaderboard */}
        <div>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
            <h2 style={{ fontSize: 18, fontWeight: 700, margin: 0, display: 'flex', alignItems: 'center', gap: 8 }}>
              <Award size={20} color="#F59E0B" />
              Jonli Guruh Reytingi (Leaderboard)
            </h2>
            <span style={{ fontSize: 12, color: '#94A3B8' }}>
              Jami: {leaderboard.length} o‘quvchi
            </span>
          </div>

          <div
            style={{
              background: 'var(--card-bg, #1E293B)',
              borderRadius: 18,
              border: '1px solid rgba(255,255,255,0.08)',
              overflow: 'hidden',
              boxShadow: '0 4px 14px rgba(0,0,0,0.1)',
            }}
          >
            {leaderboard.length === 0 ? (
              <div style={{ padding: '30px 20px', textAlign: 'center', color: '#94A3B8', fontSize: 14 }}>
                Hozircha hech kim test topshirmagan.
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column' }}>
                {leaderboard.map((item) => (
                  <div
                    key={item.student_id}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '14px 18px',
                      borderBottom: '1px solid rgba(255,255,255,0.05)',
                      background: item.is_me
                        ? 'linear-gradient(90deg, rgba(200,146,42,0.18) 0%, rgba(200,146,42,0.05) 100%)'
                        : undefined,
                      borderLeft: item.is_me ? '3px solid #C8922A' : undefined,
                    }}
                  >
                    {/* Rank & Name */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                      <span
                        style={{
                          width: 28,
                          height: 28,
                          borderRadius: 8,
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          fontWeight: 800,
                          fontSize: 14,
                          background:
                            item.rank === 1
                              ? 'linear-gradient(135deg, #F59E0B, #D97706)'
                              : item.rank === 2
                              ? 'linear-gradient(135deg, #94A3B8, #64748B)'
                              : item.rank === 3
                              ? 'linear-gradient(135deg, #B45309, #78350F)'
                              : 'rgba(255,255,255,0.06)',
                          color: item.rank <= 3 ? '#fff' : '#94A3B8',
                        }}
                      >
                        {item.medal || item.rank}
                      </span>

                      <div>
                        <div style={{ fontSize: 14, fontWeight: 700, color: item.is_me ? '#F59E0B' : '#F8FAFC' }}>
                          {item.student_name} {item.is_me && '(Siz)'}
                        </div>
                        <div style={{ fontSize: 11, color: '#94A3B8' }}>
                          {item.tests_taken} ta test • BMB: <b>{item.bmb_grade}</b>
                        </div>
                      </div>
                    </div>

                    {/* Percentage & Grade */}
                    <div style={{ textAlign: 'right' }}>
                      <div style={{ fontSize: 15, fontWeight: 800, color: '#10B981' }}>
                        {item.avg_test_pct > 0 ? `${item.avg_test_pct}%` : '0%'}
                      </div>
                      <div style={{ fontSize: 11, color: '#94A3B8' }}>
                        {item.last_active}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
