import React, { useEffect, useState } from 'react';
import {
  Building2,
  Plus,
  Users,
  GraduationCap,
  BookOpen,
  MapPin,
  Phone,
  Send,
  CheckCircle2,
  X,
  Search,
} from 'lucide-react';
import { BranchApi, type BranchItem } from '../lib/api';
import { useToast } from '../context/ToastContext';

const SUBJECT_OPTIONS = [
  { value: 'biology', label: '🧬 Biologiya' },
  { value: 'chemistry', label: '🧪 Kimyo' },
  { value: 'law', label: '⚖️ Huquqshunoslik' },
  { value: 'uzbek', label: '🇺🇿 Ona tili va Adabiyot' },
  { value: 'english', label: '🇬🇧 Ingliz tili' },
];

export default function PanelBranches() {
  const [branches, setBranches] = useState<BranchItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [editingBranch, setEditingBranch] = useState<BranchItem | null>(null);

  // Form states
  const [name, setName] = useState('');
  const [branchCode, setBranchCode] = useState('');
  const [region, setRegion] = useState('');
  const [address, setAddress] = useState('');
  const [phone, setPhone] = useState('');
  const [telegramChannel, setTelegramChannel] = useState('');
  const [selectedSubjects, setSelectedSubjects] = useState<string[]>([
    'biology',
    'chemistry',
    'law',
    'uzbek',
    'english',
  ]);
  const [maxTeachers, setMaxTeachers] = useState(20);
  const [maxStudents, setMaxStudents] = useState(500);
  const [saving, setSaving] = useState(false);

  const toast = useToast();

  const loadBranches = async () => {
    try {
      setLoading(true);
      const data = await BranchApi.list();
      setBranches(Array.isArray(data) ? data : []);
    } catch (err) {
      toast.error('Filiallar ro‘yxatini yuklashda xatolik yuz berdi');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadBranches();
  }, []);

  const openCreateModal = () => {
    setEditingBranch(null);
    setName('');
    setBranchCode('');
    setRegion('');
    setAddress('');
    setPhone('');
    setTelegramChannel('');
    setSelectedSubjects(['biology', 'chemistry', 'law', 'uzbek', 'english']);
    setMaxTeachers(20);
    setMaxStudents(500);
    setModalOpen(true);
  };

  const openEditModal = (b: BranchItem) => {
    setEditingBranch(b);
    setName(b.name);
    setBranchCode(b.branch_code);
    setRegion(b.region || '');
    setAddress(b.address || '');
    setPhone(b.phone || '');
    setTelegramChannel(b.telegram_channel || '');
    setSelectedSubjects(b.subjects_offered || ['biology', 'chemistry', 'law', 'uzbek', 'english']);
    setMaxTeachers(b.max_teachers_limit || 20);
    setMaxStudents(b.max_students_limit || 500);
    setModalOpen(true);
  };

  const toggleSubject = (sub: string) => {
    if (selectedSubjects.includes(sub)) {
      if (selectedSubjects.length === 1) return; // at least one
      setSelectedSubjects(selectedSubjects.filter((s) => s !== sub));
    } else {
      setSelectedSubjects([...selectedSubjects, sub]);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      toast.error('Filial nomini kiriting');
      return;
    }
    setSaving(true);
    try {
      if (editingBranch) {
        await BranchApi.update(editingBranch.id, {
          name: name.trim(),
          branch_code: branchCode.trim().toUpperCase(),
          region: region.trim(),
          address: address.trim(),
          phone: phone.trim(),
          telegram_channel: telegramChannel.trim(),
          subjects_offered: selectedSubjects,
          max_teachers_limit: maxTeachers,
          max_students_limit: maxStudents,
        });
        toast.success('Filial ma‘lumotlari muvaffaqiyatli yangilandi');
      } else {
        await BranchApi.create({
          name: name.trim(),
          branch_code: branchCode.trim().toUpperCase(),
          region: region.trim(),
          address: address.trim(),
          phone: phone.trim(),
          telegram_channel: telegramChannel.trim(),
          subjects_offered: selectedSubjects,
          max_teachers_limit: maxTeachers,
          max_students_limit: maxStudents,
        });
        toast.success('Yangi filial muvaffaqiyatli yaratildi');
      }
      setModalOpen(false);
      loadBranches();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Saqlashda xatolik yuz berdi';
      toast.error(msg);
    } finally {
      setSaving(false);
    }
  };

  const filteredBranches = branches.filter((b) => {
    const q = search.toLowerCase();
    return (
      b.name.toLowerCase().includes(q) ||
      b.branch_code.toLowerCase().includes(q) ||
      (b.region && b.region.toLowerCase().includes(q))
    );
  });

  const totalTeachers = branches.reduce((acc, b) => acc + (b.teachers_count || 0), 0);
  const totalGroups = branches.reduce((acc, b) => acc + (b.groups_count || 0), 0);
  const totalStudents = branches.reduce((acc, b) => acc + (b.students_count || 0), 0);

  return (
    <div style={{ maxWidth: 1200, margin: '0 auto', padding: '24px 16px 80px' }}>
      {/* Top Header */}
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
                background: 'linear-gradient(135deg, rgba(200,146,42,0.2) 0%, rgba(200,146,42,0.05) 100%)',
                color: '#C8922A',
                border: '1px solid rgba(200,146,42,0.3)',
              }}
            >
              <Building2 size={24} />
            </span>
            <h1 style={{ fontSize: 24, fontWeight: 700, margin: 0 }}>
              O‘quv Markazlari va Filiallar (Kursxonalar)
            </h1>
          </div>
          <p style={{ margin: '6px 0 0', color: 'var(--text-secondary, #64748B)', fontSize: 14 }}>
            Viloyat va tuman filiallarini, ustozlar kvotasini hamda guruhlar tarmog‘ini markazlashgan holda boshqaring.
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
          Yangi Filial Qo‘shish
        </button>
      </div>

      {/* Metrics Row */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: 16,
          marginBottom: 28,
        }}
      >
        <div
          style={{
            background: 'var(--card-bg, #1E293B)',
            borderRadius: 16,
            padding: '18px 20px',
            border: '1px solid var(--border-color, rgba(255,255,255,0.08))',
            display: 'flex',
            alignItems: 'center',
            gap: 14,
          }}
        >
          <div
            style={{
              width: 44,
              height: 44,
              borderRadius: 12,
              background: 'rgba(59, 130, 246, 0.15)',
              color: '#3B82F6',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <Building2 size={22} />
          </div>
          <div>
            <div style={{ fontSize: 13, color: 'var(--text-secondary, #94A3B8)' }}>Faol Filiallar</div>
            <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--text-primary, #F8FAFC)' }}>
              {branches.length} ta
            </div>
          </div>
        </div>

        <div
          style={{
            background: 'var(--card-bg, #1E293B)',
            borderRadius: 16,
            padding: '18px 20px',
            border: '1px solid var(--border-color, rgba(255,255,255,0.08))',
            display: 'flex',
            alignItems: 'center',
            gap: 14,
          }}
        >
          <div
            style={{
              width: 44,
              height: 44,
              borderRadius: 12,
              background: 'rgba(16, 185, 129, 0.15)',
              color: '#10B981',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <GraduationCap size={22} />
          </div>
          <div>
            <div style={{ fontSize: 13, color: 'var(--text-secondary, #94A3B8)' }}>Biriktirilgan Ustozlar</div>
            <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--text-primary, #F8FAFC)' }}>
              {totalTeachers} nafar
            </div>
          </div>
        </div>

        <div
          style={{
            background: 'var(--card-bg, #1E293B)',
            borderRadius: 16,
            padding: '18px 20px',
            border: '1px solid var(--border-color, rgba(255,255,255,0.08))',
            display: 'flex',
            alignItems: 'center',
            gap: 14,
          }}
        >
          <div
            style={{
              width: 44,
              height: 44,
              borderRadius: 12,
              background: 'rgba(245, 158, 11, 0.15)',
              color: '#F59E0B',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <BookOpen size={22} />
          </div>
          <div>
            <div style={{ fontSize: 13, color: 'var(--text-secondary, #94A3B8)' }}>Ochilgan Guruhlar</div>
            <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--text-primary, #F8FAFC)' }}>
              {totalGroups} ta
            </div>
          </div>
        </div>

        <div
          style={{
            background: 'var(--card-bg, #1E293B)',
            borderRadius: 16,
            padding: '18px 20px',
            border: '1px solid var(--border-color, rgba(255,255,255,0.08))',
            display: 'flex',
            alignItems: 'center',
            gap: 14,
          }}
        >
          <div
            style={{
              width: 44,
              height: 44,
              borderRadius: 12,
              background: 'rgba(139, 92, 246, 0.15)',
              color: '#8B5CF6',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <Users size={22} />
          </div>
          <div>
            <div style={{ fontSize: 13, color: 'var(--text-secondary, #94A3B8)' }}>Jami O‘quvchilar</div>
            <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--text-primary, #F8FAFC)' }}>
              {totalStudents} nafar
            </div>
          </div>
        </div>
      </div>

      {/* Search Bar */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          background: 'var(--card-bg, #1E293B)',
          borderRadius: 14,
          padding: '10px 16px',
          border: '1px solid var(--border-color, rgba(255,255,255,0.08))',
          marginBottom: 20,
        }}
      >
        <Search size={18} color="var(--text-secondary, #94A3B8)" />
        <input
          type="text"
          placeholder="Filial nomi, kodi (masalan SAM-01) yoki viloyat bo‘yicha qidirish..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{
            flex: 1,
            background: 'transparent',
            border: 'none',
            outline: 'none',
            color: 'var(--text-primary, #F8FAFC)',
            fontSize: 14,
          }}
        />
        {search && (
          <button
            onClick={() => setSearch('')}
            style={{ background: 'none', border: 'none', color: '#94A3B8', cursor: 'pointer' }}
          >
            <X size={16} />
          </button>
        )}
      </div>

      {/* Branch Cards Grid */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: '60px 0', color: '#94A3B8' }}>
          Filiallar yuklanmoqda...
        </div>
      ) : filteredBranches.length === 0 ? (
        <div
          style={{
            textAlign: 'center',
            padding: '60px 20px',
            background: 'var(--card-bg, #1E293B)',
            borderRadius: 18,
            border: '1px dashed var(--border-color, rgba(255,255,255,0.15))',
          }}
        >
          <Building2 size={48} color="#64748B" style={{ marginBottom: 12 }} />
          <h3 style={{ fontSize: 18, fontWeight: 600, margin: '0 0 8px' }}>Filial topilmadi</h3>
          <p style={{ color: '#94A3B8', fontSize: 14, margin: '0 0 16px' }}>
            Hozircha hech qanday filial kiritilmagan yoki qidiruvga mos kelmadi.
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
            + Birinchi filialni qo‘shish
          </button>
        </div>
      ) : (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))',
            gap: 20,
          }}
        >
          {filteredBranches.map((b) => (
            <div
              key={b.id}
              style={{
                background: 'var(--card-bg, #1E293B)',
                borderRadius: 18,
                padding: '22px',
                border: '1px solid var(--border-color, rgba(255,255,255,0.08))',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                gap: 16,
                boxShadow: '0 4px 20px rgba(0,0,0,0.15)',
              }}
            >
              <div>
                {/* Card Top */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
                  <div>
                    <span
                      style={{
                        display: 'inline-block',
                        padding: '4px 10px',
                        borderRadius: 8,
                        background: 'rgba(200,146,42,0.15)',
                        color: '#F59E0B',
                        fontSize: 12,
                        fontWeight: 700,
                        border: '1px solid rgba(200,146,42,0.3)',
                        marginBottom: 8,
                      }}
                    >
                      {b.branch_code}
                    </span>
                    <h3 style={{ fontSize: 17, fontWeight: 700, margin: 0, color: 'var(--text-primary, #F8FAFC)' }}>
                      {b.name}
                    </h3>
                  </div>

                  <button
                    onClick={() => openEditModal(b)}
                    style={{
                      padding: '6px 12px',
                      borderRadius: 8,
                      background: 'rgba(255,255,255,0.06)',
                      border: '1px solid rgba(255,255,255,0.1)',
                      color: 'var(--text-primary, #F8FAFC)',
                      fontSize: 12,
                      cursor: 'pointer',
                    }}
                  >
                    Tahrirlash
                  </button>
                </div>

                {/* Details */}
                <div style={{ marginTop: 14, display: 'flex', flexDirection: 'column', gap: 6, fontSize: 13, color: '#94A3B8' }}>
                  {b.region && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <MapPin size={15} color="#C8922A" />
                      <span>{b.region} {b.address ? `• ${b.address}` : ''}</span>
                    </div>
                  )}
                  {b.phone && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <Phone size={15} color="#10B981" />
                      <span>{b.phone}</span>
                    </div>
                  )}
                  {b.telegram_channel && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <Send size={15} color="#3B82F6" />
                      <span>{b.telegram_channel}</span>
                    </div>
                  )}
                </div>

                {/* Subject Tags */}
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 14 }}>
                  {(b.subjects_offered || []).map((sub) => {
                    const match = SUBJECT_OPTIONS.find((s) => s.value === sub);
                    return (
                      <span
                        key={sub}
                        style={{
                          padding: '3px 8px',
                          borderRadius: 6,
                          background: 'rgba(255,255,255,0.05)',
                          fontSize: 11,
                          fontWeight: 500,
                          color: '#CBD5E1',
                        }}
                      >
                        {match ? match.label : sub}
                      </span>
                    );
                  })}
                </div>
              </div>

              {/* Bottom Metrics */}
              <div
                style={{
                  paddingTop: 14,
                  borderTop: '1px solid rgba(255,255,255,0.08)',
                  display: 'grid',
                  gridTemplateColumns: 'repeat(4, 1fr)',
                  gap: 8,
                  textAlign: 'center',
                }}
              >
                <div>
                  <div style={{ fontSize: 11, color: '#94A3B8' }}>Ustozlar</div>
                  <div style={{ fontSize: 14, fontWeight: 700, color: '#F8FAFC' }}>
                    {b.teachers_count} / {b.max_teachers_limit}
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: 11, color: '#94A3B8' }}>Guruhlar</div>
                  <div style={{ fontSize: 14, fontWeight: 700, color: '#F8FAFC' }}>
                    {b.groups_count} ta
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: 11, color: '#94A3B8' }}>O‘quvchilar</div>
                  <div style={{ fontSize: 14, fontWeight: 700, color: '#F8FAFC' }}>
                    {b.students_count} / {b.max_students_limit}
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: 11, color: '#94A3B8' }}>O‘rtacha %</div>
                  <div style={{ fontSize: 14, fontWeight: 700, color: '#10B981' }}>
                    {b.avg_performance > 0 ? `${b.avg_performance}%` : '—'}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Modal: Create / Edit Branch */}
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
              maxWidth: 580,
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
                {editingBranch ? 'Filialni Tahrirlash' : 'Yangi Filial (Kursxona) Qo‘shish'}
              </h2>
              <button
                onClick={() => setModalOpen(false)}
                style={{ background: 'none', border: 'none', color: '#94A3B8', cursor: 'pointer' }}
              >
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              <div>
                <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 6 }}>
                  Filial Nomi *
                </label>
                <input
                  type="text"
                  required
                  placeholder="Masalan: Grand Education — Samarqand Markaziy Filiali"
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

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div>
                  <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 6 }}>
                    Filial Kodi (Unikal)
                  </label>
                  <input
                    type="text"
                    placeholder="Masalan: SAM-01"
                    value={branchCode}
                    onChange={(e) => setBranchCode(e.target.value)}
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

                <div>
                  <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 6 }}>
                    Viloyat / Hudud
                  </label>
                  <input
                    type="text"
                    placeholder="Masalan: Samarqand viloyati"
                    value={region}
                    onChange={(e) => setRegion(e.target.value)}
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
              </div>

              <div>
                <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 6 }}>
                  To‘liq Manzil
                </label>
                <input
                  type="text"
                  placeholder="Masalan: Registon ko‘chasi, 14-uy"
                  value={address}
                  onChange={(e) => setAddress(e.target.value)}
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

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div>
                  <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 6 }}>
                    Aloqa Telefoni
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

                <div>
                  <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 6 }}>
                    Telegram Kanal / Guruh
                  </label>
                  <input
                    type="text"
                    placeholder="@grandec_samarkand"
                    value={telegramChannel}
                    onChange={(e) => setTelegramChannel(e.target.value)}
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
              </div>

              {/* Subjects selection */}
              <div>
                <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 8 }}>
                  Filialda O‘qitiladigan Fanlar
                </label>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                  {SUBJECT_OPTIONS.map((sub) => {
                    const active = selectedSubjects.includes(sub.value);
                    return (
                      <button
                        key={sub.value}
                        type="button"
                        onClick={() => toggleSubject(sub.value)}
                        style={{
                          padding: '7px 14px',
                          borderRadius: 10,
                          fontSize: 13,
                          fontWeight: 500,
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: 6,
                          background: active ? 'rgba(200,146,42,0.2)' : 'rgba(255,255,255,0.05)',
                          border: active ? '1px solid #C8922A' : '1px solid rgba(255,255,255,0.1)',
                          color: active ? '#F59E0B' : '#94A3B8',
                        }}
                      >
                        {active && <CheckCircle2 size={14} />}
                        {sub.label}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Limits */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div>
                  <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 6 }}>
                    Maksimal Ustozlar Limiti
                  </label>
                  <input
                    type="number"
                    min="1"
                    max="100"
                    value={maxTeachers}
                    onChange={(e) => setMaxTeachers(Number(e.target.value))}
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

                <div>
                  <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 6 }}>
                    Maksimal O‘quvchilar Limiti
                  </label>
                  <input
                    type="number"
                    min="10"
                    max="5000"
                    value={maxStudents}
                    onChange={(e) => setMaxStudents(Number(e.target.value))}
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
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12, marginTop: 12 }}>
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
                  {saving ? 'Saqlanmoqda...' : editingBranch ? 'O‘zgarishlarni saqlash' : 'Filialni yaratish'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
