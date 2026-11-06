import React, { useEffect, useState } from 'react';
import {
  GraduationCap,
  Building2,
  Plus,
  Search,
  Filter,
  CheckCircle2,
  X,
  Phone,
  Mail,
  Settings,
} from 'lucide-react';
import { TeacherManagementApi, type TeacherManagementItem } from '../lib/api';
import { useToast } from '../context/ToastContext';

const SUBJECT_LABELS: Record<string, string> = {
  biology: '🧬 Biologiya',
  chemistry: '🧪 Kimyo',
  law: '⚖️ Huquqshunoslik',
  uzbek: '🇺🇿 Ona tili va Adabiyot',
  english: '🇬🇧 Ingliz tili',
};

export default function PanelTeachers() {
  const [teachers, setTeachers] = useState<TeacherManagementItem[]>([]);
  const [branches, setBranches] = useState<{ id: number; name: string; branch_code: string; region: string }[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [selectedBranch, setSelectedBranch] = useState<string>('all');
  const [selectedSubject, setSelectedSubject] = useState<string>('all');

  const [modalOpen, setModalOpen] = useState(false);
  const [editingTeacher, setEditingTeacher] = useState<TeacherManagementItem | null>(null);

  // Form
  const [email, setEmail] = useState('');
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [password, setPassword] = useState('');
  const [branchId, setBranchId] = useState<number | ''>('');
  const [subject, setSubject] = useState('biology');
  const [canCreateTest, setCanCreateTest] = useState(true);
  const [canCreateEssay, setCanCreateEssay] = useState(true);
  const [isActive, setIsActive] = useState(true);
  const [saving, setSaving] = useState(false);

  const toast = useToast();

  const loadTeachers = async () => {
    try {
      setLoading(true);
      const res = await TeacherManagementApi.list();
      setTeachers(res.results || []);
      setBranches(res.branches || []);
    } catch (err) {
      toast.error('Ustozlar ro‘yxatini yuklashda xatolik');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTeachers();
  }, []);

  const openCreateModal = () => {
    setEditingTeacher(null);
    setEmail('');
    setName('');
    setPhone('');
    setPassword('GrandTeacher2026!');
    setBranchId(branches.length > 0 ? branches[0].id : '');
    setSubject('biology');
    setCanCreateTest(true);
    setCanCreateEssay(true);
    setIsActive(true);
    setModalOpen(true);
  };

  const openEditModal = (t: TeacherManagementItem) => {
    setEditingTeacher(t);
    setEmail(t.email);
    setName(t.name);
    setPhone(t.phone || '');
    setPassword('');
    setBranchId(t.branch ? t.branch.id : '');
    setSubject(t.subject || 'biology');
    setCanCreateTest(t.can_create_test);
    setCanCreateEssay(t.can_create_essay_topic);
    setIsActive(t.is_active);
    setModalOpen(true);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    try {
      await TeacherManagementApi.assign({
        teacher_id: editingTeacher ? editingTeacher.id : undefined,
        email: email.trim(),
        name: name.trim(),
        password: password.trim() || undefined,
        branch_id: branchId === '' ? null : Number(branchId),
        subject,
        phone: phone.trim(),
        can_create_test: canCreateTest,
        can_create_essay_topic: canCreateEssay,
        is_active: isActive,
      });
      toast.success(editingTeacher ? 'Ustoz sozlamalari yangilandi' : 'Yangi ustoz muvaffaqiyatli qo‘shildi');
      setModalOpen(false);
      loadTeachers();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Saqlashda xatolik yuz berdi';
      toast.error(msg);
    } finally {
      setSaving(false);
    }
  };

  const filtered = teachers.filter((t) => {
    const q = search.toLowerCase();
    const matchSearch =
      t.name.toLowerCase().includes(q) ||
      t.email.toLowerCase().includes(q) ||
      (t.branch && t.branch.name.toLowerCase().includes(q));

    const matchBranch = selectedBranch === 'all' || (t.branch && String(t.branch.id) === selectedBranch);
    const matchSubject = selectedSubject === 'all' || t.subject === selectedSubject;

    return matchSearch && matchBranch && matchSubject;
  });

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto', padding: '24px 16px 80px' }}>
      {/* Header */}
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 16,
          marginBottom: 24,
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: 42,
                height: 42,
                borderRadius: 12,
                background: 'linear-gradient(135deg, rgba(16,185,129,0.2) 0%, rgba(16,185,129,0.05) 100%)',
                color: '#10B981',
                border: '1px solid rgba(16,185,129,0.3)',
              }}
            >
              <GraduationCap size={24} />
            </span>
            <h1 style={{ fontSize: 24, fontWeight: 700, margin: 0 }}>
              Ustozlar va Kursxona Boshqaruvi
            </h1>
          </div>
          <p style={{ margin: '6px 0 0', color: 'var(--text-secondary, #64748B)', fontSize: 14 }}>
            O‘qituvchilarni filiallar va fanlarga (Biologiya, Kimyo, Huquq, Ona tili, Ingliz tili) biriktiring va ruxsatlarini boshqaring.
          </p>
        </div>

        <button
          onClick={openCreateModal}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 8,
            padding: '12px 22px',
            borderRadius: 12,
            background: 'linear-gradient(135deg, #C8922A 0%, #D97706 100%)',
            color: '#fff',
            fontWeight: 600,
            fontSize: 14,
            border: 'none',
            cursor: 'pointer',
            boxShadow: '0 4px 14px rgba(200,146,42,0.3)',
          }}
        >
          <Plus size={18} />
          Yangi Ustoz Biriktirish
        </button>
      </div>

      {/* Filter and Search Bar */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: 12,
          marginBottom: 24,
        }}
      >
        {/* Search */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            background: 'var(--card-bg, #1E293B)',
            borderRadius: 12,
            padding: '10px 14px',
            border: '1px solid var(--border-color, rgba(255,255,255,0.08))',
          }}
        >
          <Search size={16} color="#94A3B8" />
          <input
            type="text"
            placeholder="Ustoz ismi, emaili bo‘yicha qidirish..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{
              flex: 1,
              background: 'transparent',
              border: 'none',
              outline: 'none',
              color: 'var(--text-primary, #F8FAFC)',
              fontSize: 13,
            }}
          />
        </div>

        {/* Branch filter */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            background: 'var(--card-bg, #1E293B)',
            borderRadius: 12,
            padding: '10px 14px',
            border: '1px solid var(--border-color, rgba(255,255,255,0.08))',
          }}
        >
          <Building2 size={16} color="#94A3B8" />
          <select
            value={selectedBranch}
            onChange={(e) => setSelectedBranch(e.target.value)}
            style={{
              flex: 1,
              background: 'transparent',
              border: 'none',
              outline: 'none',
              color: 'var(--text-primary, #F8FAFC)',
              fontSize: 13,
              cursor: 'pointer',
            }}
          >
            <option value="all">Barcha Filiallar ({branches.length})</option>
            {branches.map((b) => (
              <option key={b.id} value={String(b.id)}>
                {b.name} [{b.branch_code}]
              </option>
            ))}
          </select>
        </div>

        {/* Subject filter */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            background: 'var(--card-bg, #1E293B)',
            borderRadius: 12,
            padding: '10px 14px',
            border: '1px solid var(--border-color, rgba(255,255,255,0.08))',
          }}
        >
          <Filter size={16} color="#94A3B8" />
          <select
            value={selectedSubject}
            onChange={(e) => setSelectedSubject(e.target.value)}
            style={{
              flex: 1,
              background: 'transparent',
              border: 'none',
              outline: 'none',
              color: 'var(--text-primary, #F8FAFC)',
              fontSize: 13,
              cursor: 'pointer',
            }}
          >
            <option value="all">Barcha Fanlar</option>
            <option value="biology">🧬 Biologiya</option>
            <option value="chemistry">🧪 Kimyo</option>
            <option value="law">⚖️ Huquqshunoslik</option>
            <option value="uzbek">🇺🇿 Ona tili</option>
            <option value="english">🇬🇧 Ingliz tili</option>
          </select>
        </div>
      </div>

      {/* Teachers List */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: '60px 0', color: '#94A3B8' }}>
          Ustozlar ro‘yxati yuklanmoqda...
        </div>
      ) : filtered.length === 0 ? (
        <div
          style={{
            textAlign: 'center',
            padding: '60px 20px',
            background: 'var(--card-bg, #1E293B)',
            borderRadius: 18,
            border: '1px dashed var(--border-color, rgba(255,255,255,0.15))',
          }}
        >
          <GraduationCap size={48} color="#64748B" style={{ marginBottom: 12 }} />
          <h3 style={{ fontSize: 18, fontWeight: 600, margin: '0 0 8px' }}>Ustoz topilmadi</h3>
          <p style={{ color: '#94A3B8', fontSize: 14, margin: '0 0 16px' }}>
            Tanlangan mezonlar bo‘yicha ustoz topilmadi.
          </p>
          <button
            onClick={openCreateModal}
            style={{
              padding: '10px 20px',
              borderRadius: 10,
              background: '#C8922A',
              color: '#fff',
              border: 'none',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            + Ustoz biriktirish
          </button>
        </div>
      ) : (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))',
            gap: 18,
          }}
        >
          {filtered.map((t) => (
            <div
              key={t.id}
              style={{
                background: 'var(--card-bg, #1E293B)',
                borderRadius: 18,
                padding: '20px',
                border: '1px solid var(--border-color, rgba(255,255,255,0.08))',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                gap: 14,
              }}
            >
              <div>
                {/* Header */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 10 }}>
                  <div>
                    <h3 style={{ fontSize: 16, fontWeight: 700, margin: '0 0 4px', color: '#F8FAFC' }}>
                      {t.name}
                    </h3>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: '#94A3B8' }}>
                      <Mail size={13} />
                      <span>{t.email}</span>
                    </div>
                    {t.phone && (
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: '#94A3B8', marginTop: 2 }}>
                        <Phone size={13} />
                        <span>{t.phone}</span>
                      </div>
                    )}
                  </div>

                  <button
                    onClick={() => openEditModal(t)}
                    style={{
                      padding: '6px 12px',
                      borderRadius: 8,
                      background: 'rgba(255,255,255,0.06)',
                      border: '1px solid rgba(255,255,255,0.1)',
                      color: '#F8FAFC',
                      fontSize: 12,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: 4,
                    }}
                  >
                    <Settings size={14} />
                    Sozlash
                  </button>
                </div>

                {/* Badges */}
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 12 }}>
                  {/* Subject */}
                  <span
                    style={{
                      padding: '4px 10px',
                      borderRadius: 8,
                      background: 'rgba(200,146,42,0.15)',
                      color: '#F59E0B',
                      fontSize: 12,
                      fontWeight: 600,
                      border: '1px solid rgba(200,146,42,0.3)',
                    }}
                  >
                    {SUBJECT_LABELS[t.subject] || t.subject}
                  </span>

                  {/* Branch */}
                  {t.branch ? (
                    <span
                      style={{
                        padding: '4px 10px',
                        borderRadius: 8,
                        background: 'rgba(59,130,246,0.15)',
                        color: '#60A5FA',
                        fontSize: 12,
                        fontWeight: 600,
                        border: '1px solid rgba(59,130,246,0.3)',
                      }}
                    >
                      🏛 {t.branch.branch_code}: {t.branch.name}
                    </span>
                  ) : (
                    <span
                      style={{
                        padding: '4px 10px',
                        borderRadius: 8,
                        background: 'rgba(239,68,68,0.15)',
                        color: '#F87171',
                        fontSize: 12,
                        fontWeight: 600,
                      }}
                    >
                      Filialsiz
                    </span>
                  )}
                </div>

                {/* Groups list */}
                {t.groups && t.groups.length > 0 && (
                  <div style={{ marginTop: 12, padding: '8px 12px', background: 'rgba(255,255,255,0.03)', borderRadius: 10 }}>
                    <div style={{ fontSize: 11, color: '#94A3B8', marginBottom: 4 }}>Boshqaradigan guruhlari:</div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                      {t.groups.map((g) => (
                        <span
                          key={g.id}
                          style={{
                            fontSize: 11,
                            padding: '2px 8px',
                            background: 'rgba(255,255,255,0.06)',
                            borderRadius: 6,
                            color: '#CBD5E1',
                          }}
                        >
                          <b>{g.invite_code}</b>: {g.name} ({g.student_count})
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Bottom Info */}
              <div
                style={{
                  paddingTop: 12,
                  borderTop: '1px solid rgba(255,255,255,0.08)',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  fontSize: 12,
                  color: '#94A3B8',
                }}
              >
                <div style={{ display: 'flex', gap: 14 }}>
                  <span>
                    👥 <b>{t.groups_count}</b> guruh
                  </span>
                  <span>
                    🎓 <b>{t.students_count}</b> o‘quvchi
                  </span>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  {t.can_create_test ? (
                    <span style={{ color: '#10B981', display: 'flex', alignItems: 'center', gap: 4 }}>
                      <CheckCircle2 size={14} /> Test
                    </span>
                  ) : null}
                  {t.is_active ? (
                    <span style={{ color: '#10B981' }}>• Faol</span>
                  ) : (
                    <span style={{ color: '#EF4444' }}>• Nofaol</span>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Modal: Assign / Edit Teacher */}
      {modalOpen && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.7)',
            backdropFilter: 'blur(5px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 9999,
            padding: 16,
          }}
        >
          <div
            style={{
              background: 'var(--card-bg, #1E293B)',
              width: '100%',
              maxWidth: 520,
              borderRadius: 20,
              padding: '24px 28px',
              border: '1px solid rgba(255,255,255,0.1)',
              maxHeight: '90vh',
              overflowY: 'auto',
              boxShadow: '0 20px 50px rgba(0,0,0,0.5)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
              <h2 style={{ fontSize: 19, fontWeight: 700, margin: 0 }}>
                {editingTeacher ? 'Ustoz Sozlamalari' : 'Yangi Ustoz Biriktirish'}
              </h2>
              <button
                onClick={() => setModalOpen(false)}
                style={{ background: 'none', border: 'none', color: '#94A3B8', cursor: 'pointer' }}
              >
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              <div>
                <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 6 }}>
                  Ustoz Emaili *
                </label>
                <input
                  type="email"
                  required
                  disabled={Boolean(editingTeacher)}
                  placeholder="ustoz@grandec.uz"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '11px 14px',
                    borderRadius: 10,
                    background: 'rgba(255,255,255,0.05)',
                    border: '1px solid rgba(255,255,255,0.15)',
                    color: '#fff',
                    fontSize: 14,
                    boxSizing: 'border-box',
                  }}
                />
              </div>

              {!editingTeacher && (
                <div>
                  <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 6 }}>
                    Ustoz F.I.Sh *
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="Masalan: Zafar Qodirov"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    style={{
                      width: '100%',
                      padding: '11px 14px',
                      borderRadius: 10,
                      background: 'rgba(255,255,255,0.05)',
                      border: '1px solid rgba(255,255,255,0.15)',
                      color: '#fff',
                      fontSize: 14,
                      boxSizing: 'border-box',
                    }}
                  />
                </div>
              )}

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div>
                  <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 6 }}>
                    Filial (Kursxona)
                  </label>
                  <select
                    value={branchId}
                    onChange={(e) => setBranchId(e.target.value ? Number(e.target.value) : '')}
                    style={{
                      width: '100%',
                      padding: '11px 14px',
                      borderRadius: 10,
                      background: 'rgba(255,255,255,0.05)',
                      border: '1px solid rgba(255,255,255,0.15)',
                      color: '#fff',
                      fontSize: 14,
                      boxSizing: 'border-box',
                    }}
                  >
                    <option value="">Filialsiz (Mustaqil)</option>
                    {branches.map((b) => (
                      <option key={b.id} value={b.id}>
                        {b.name} [{b.branch_code}]
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 6 }}>
                    O‘qitadigan Fani
                  </label>
                  <select
                    value={subject}
                    onChange={(e) => setSubject(e.target.value)}
                    style={{
                      width: '100%',
                      padding: '11px 14px',
                      borderRadius: 10,
                      background: 'rgba(255,255,255,0.05)',
                      border: '1px solid rgba(255,255,255,0.15)',
                      color: '#fff',
                      fontSize: 14,
                      boxSizing: 'border-box',
                    }}
                  >
                    <option value="biology">🧬 Biologiya</option>
                    <option value="chemistry">🧪 Kimyo</option>
                    <option value="law">⚖️ Huquqshunoslik</option>
                    <option value="uzbek">🇺🇿 Ona tili</option>
                    <option value="english">🇬🇧 Ingliz tili</option>
                  </select>
                </div>
              </div>

              <div>
                <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 6 }}>
                  Telefon Raqami
                </label>
                <input
                  type="text"
                  placeholder="+998 90 123 45 67"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '11px 14px',
                    borderRadius: 10,
                    background: 'rgba(255,255,255,0.05)',
                    border: '1px solid rgba(255,255,255,0.15)',
                    color: '#fff',
                    fontSize: 14,
                    boxSizing: 'border-box',
                  }}
                />
              </div>

              {/* Permissions */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 4 }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={canCreateTest}
                    onChange={(e) => setCanCreateTest(e.target.checked)}
                  />
                  <span>Test va Mock yaratishga ruxsat berish</span>
                </label>
                <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={canCreateEssay}
                    onChange={(e) => setCanCreateEssay(e.target.checked)}
                  />
                  <span>Esse mavzusi qo‘shishga ruxsat berish</span>
                </label>
                <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={isActive}
                    onChange={(e) => setIsActive(e.target.checked)}
                  />
                  <span>Hisob faol (Active)</span>
                </label>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12, marginTop: 14 }}>
                <button
                  type="button"
                  onClick={() => setModalOpen(false)}
                  style={{
                    padding: '10px 18px',
                    borderRadius: 10,
                    background: 'transparent',
                    border: '1px solid rgba(255,255,255,0.15)',
                    color: '#94A3B8',
                    cursor: 'pointer',
                    fontSize: 14,
                  }}
                >
                  Bekor qilish
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  style={{
                    padding: '10px 24px',
                    borderRadius: 10,
                    background: '#C8922A',
                    border: 'none',
                    color: '#fff',
                    fontWeight: 600,
                    cursor: 'pointer',
                    fontSize: 14,
                    opacity: saving ? 0.7 : 1,
                  }}
                >
                  {saving ? 'Saqlanmoqda...' : 'Saqlash'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
