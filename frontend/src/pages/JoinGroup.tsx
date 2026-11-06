import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import {
  ArrowRight,
  BookOpen,
  LogIn,
  Users,
  X,
  Building2,
  Search,
  KeyRound,
  GraduationCap,
  Sparkles,
  Phone,
  CheckCircle2,
} from 'lucide-react';
import { useAuth } from '../auth/AuthContext';
import { useToast } from '../context/ToastContext';
import { useLang } from '../i18n/LangContext';
import {
  GroupInviteApi,
  SchoolBranchesCatalogApi,
  StudentGroupDetailApi,
  type GroupJoinPreview,
  type CatalogBranchItem,
} from '../lib/api';

export default function JoinGroup() {
  const { token } = useParams<{ token?: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();
  const toast = useToast();
  const { t } = useLang();

  // Tab: 'code' | 'catalog'
  const [activeTab, setActiveTab] = useState<'code' | 'catalog'>(token ? 'code' : 'code');

  // Direct Code / Token Flow
  const [codeInput, setCodeInput] = useState(token || '');
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [group, setGroup] = useState<GroupJoinPreview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [joined, setJoined] = useState(false);

  // Catalog Flow
  const [catalog, setCatalog] = useState<CatalogBranchItem[]>([]);
  const [loadingCatalog, setLoadingCatalog] = useState(false);
  const [selectedSubject, setSelectedSubject] = useState<string>('all');
  const [joiningGroupId, setJoiningGroupId] = useState<number | null>(null);

  // If token is in URL, fetch preview immediately
  useEffect(() => {
    if (token) {
      setCodeInput(token);
      fetchPreview(token);
    }
  }, [token]);

  const fetchPreview = async (codeOrToken: string) => {
    const raw = codeOrToken.trim();
    if (!raw) return;
    setLoadingPreview(true);
    setError(null);
    try {
      const data = await GroupInviteApi.preview(raw);
      setGroup(data);
      if (data.is_member) setJoined(true);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : t('jg_not_found_text');
      setError(msg);
      setGroup(null);
    } finally {
      setLoadingPreview(false);
    }
  };

  const loadCatalog = async () => {
    try {
      setLoadingCatalog(true);
      const res = await SchoolBranchesCatalogApi.catalog();
      setCatalog(res || []);
    } catch (err) {
      toast.error('Kursxonalar katalogini yuklab bo‘lmadi');
    } finally {
      setLoadingCatalog(false);
    }
  };

  const handleTabChange = (tab: 'code' | 'catalog') => {
    setActiveTab(tab);
    if (tab === 'catalog' && catalog.length === 0) {
      loadCatalog();
    }
  };

  const handleJoin = async (targetTokenOrCode?: string) => {
    const code = targetTokenOrCode || group?.invite_token || group?.invite_code || codeInput.trim();
    if (!code) return;
    setSubmitting(true);
    try {
      const res = await GroupInviteApi.join(code);
      toast.success(res.message || t('jg_joined'));
      setJoined(true);
      const gid = res.group_id;
      setTimeout(() => {
        if (gid) {
          navigate(`/groups/${gid}`);
        } else {
          navigate('/dashboard');
        }
      }, 1000);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : t('jg_join_failed');
      toast.error(msg);
    } finally {
      setSubmitting(false);
      setJoiningGroupId(null);
    }
  };

  const handleCatalogGroupJoin = async (groupCode: string, gId: number) => {
    if (!user) {
      toast.error('Guruhga qo‘shilish uchun avval tizimga kiring');
      navigate(`/login?next=${encodeURIComponent('/join')}`);
      return;
    }
    setJoiningGroupId(gId);
    try {
      const res = await StudentGroupDetailApi.joinByCode(groupCode);
      toast.success(res.message || 'Guruhga muvaffaqiyatli qo‘shildingiz!');
      setTimeout(() => navigate(`/groups/${gId}`), 800);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Qo‘shilishda xatolik yuz berdi';
      toast.error(msg);
    } finally {
      setJoiningGroupId(null);
    }
  };

  const nextUrl = encodeURIComponent(codeInput ? `/join/${codeInput}` : '/join');

  return (
    <div style={{ maxWidth: 840, margin: '0 auto', padding: '30px 16px 80px' }}>
      {/* Brand Header */}
      <div style={{ textAlign: 'center', marginBottom: 28 }}>
        <Link to="/" style={{ display: 'inline-flex', alignItems: 'center', gap: 10, textDecoration: 'none' }}>
          <img src="/logo-mark.png" alt="" width={38} height={38} />
          <span style={{ fontSize: 20, fontWeight: 800, color: 'var(--text-primary, #F8FAFC)', letterSpacing: 0.5 }}>
            GRAND EDUCATION
          </span>
        </Link>
        <h1 style={{ fontSize: 22, fontWeight: 700, margin: '14px 0 6px' }}>
          Guruhga va Kursxonaga Qo‘shilish
        </h1>
        <p style={{ margin: 0, color: 'var(--text-secondary, #94A3B8)', fontSize: 14 }}>
          Ustozingiz bergan 6 xonali guruh kodi orqali yoki o‘z hududingizdagi filialni tanlab guruhga a‘zo bo‘ling.
        </p>
      </div>

      {/* Tabs */}
      <div
        style={{
          display: 'flex',
          background: 'var(--card-bg, #1E293B)',
          borderRadius: 14,
          padding: 4,
          marginBottom: 24,
          border: '1px solid var(--border-color, rgba(255,255,255,0.08))',
        }}
      >
        <button
          type="button"
          onClick={() => handleTabChange('code')}
          style={{
            flex: 1,
            padding: '11px 16px',
            borderRadius: 10,
            border: 'none',
            fontSize: 14,
            fontWeight: 600,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 8,
            background: activeTab === 'code' ? '#C8922A' : 'transparent',
            color: activeTab === 'code' ? '#fff' : '#94A3B8',
            transition: 'all 0.2s',
          }}
        >
          <KeyRound size={17} />
          Guruh Kodi Orqali (Masalan: BIO-104)
        </button>

        <button
          type="button"
          onClick={() => handleTabChange('catalog')}
          style={{
            flex: 1,
            padding: '11px 16px',
            borderRadius: 10,
            border: 'none',
            fontSize: 14,
            fontWeight: 600,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 8,
            background: activeTab === 'catalog' ? '#C8922A' : 'transparent',
            color: activeTab === 'catalog' ? '#fff' : '#94A3B8',
            transition: 'all 0.2s',
          }}
        >
          <Building2 size={17} />
          Filial va Fanlar Katalogi
        </button>
      </div>

      {/* TAB 1: CODE INPUT */}
      {activeTab === 'code' && (
        <div
          style={{
            background: 'var(--card-bg, #1E293B)',
            borderRadius: 20,
            padding: '28px 24px',
            border: '1px solid var(--border-color, rgba(255,255,255,0.08))',
            boxShadow: '0 8px 30px rgba(0,0,0,0.2)',
          }}
        >
          <form
            onSubmit={(e) => {
              e.preventDefault();
              fetchPreview(codeInput);
            }}
            style={{ display: 'flex', gap: 10, marginBottom: 20 }}
          >
            <input
              type="text"
              placeholder="Guruh kodini kiriting (masalan: BIO-104, KIM-205, HUQ-301)"
              value={codeInput}
              onChange={(e) => setCodeInput(e.target.value.toUpperCase())}
              style={{
                flex: 1,
                padding: '13px 16px',
                borderRadius: 12,
                background: 'rgba(255,255,255,0.05)',
                border: '1px solid rgba(255,255,255,0.15)',
                color: '#fff',
                fontSize: 15,
                fontWeight: 600,
                letterSpacing: 1,
              }}
            />
            <button
              type="submit"
              disabled={loadingPreview || !codeInput.trim()}
              style={{
                padding: '13px 24px',
                borderRadius: 12,
                background: '#C8922A',
                color: '#fff',
                fontWeight: 600,
                fontSize: 14,
                border: 'none',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                opacity: !codeInput.trim() ? 0.6 : 1,
              }}
            >
              <Search size={16} />
              {loadingPreview ? 'Qidirilmoqda...' : 'Topish'}
            </button>
          </form>

          {/* Error */}
          {error && (
            <div
              style={{
                padding: '14px 18px',
                borderRadius: 12,
                background: 'rgba(239, 68, 68, 0.12)',
                border: '1px solid rgba(239, 68, 68, 0.3)',
                color: '#F87171',
                fontSize: 14,
                marginBottom: 16,
                display: 'flex',
                alignItems: 'center',
                gap: 10,
              }}
            >
              <X size={18} />
              <span>{error}</span>
            </div>
          )}

          {/* Group Found Preview */}
          {group && (
            <div
              style={{
                padding: '22px',
                borderRadius: 16,
                background: 'linear-gradient(135deg, rgba(200,146,42,0.12) 0%, rgba(200,146,42,0.03) 100%)',
                border: '1px solid rgba(200,146,42,0.3)',
                marginTop: 10,
              }}
            >
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 12 }}>
                <span
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 6,
                    padding: '4px 10px',
                    borderRadius: 8,
                    background: 'rgba(200,146,42,0.2)',
                    color: '#F59E0B',
                    fontSize: 12,
                    fontWeight: 700,
                  }}
                >
                  <BookOpen size={13} /> {group.subject_display || group.subject}
                </span>

                <span
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 6,
                    padding: '4px 10px',
                    borderRadius: 8,
                    background: 'rgba(255,255,255,0.08)',
                    color: '#CBD5E1',
                    fontSize: 12,
                  }}
                >
                  <Users size={13} /> {group.student_count} nafar o‘quvchi
                </span>
              </div>

              <h2 style={{ fontSize: 20, fontWeight: 700, margin: '0 0 8px', color: '#F8FAFC' }}>
                {group.name}
              </h2>

              <p style={{ margin: '0 0 14px', fontSize: 14, color: '#CBD5E1', display: 'flex', alignItems: 'center', gap: 8 }}>
                <GraduationCap size={16} color="#C8922A" />
                Ustoz: <b>{group.teacher_name}</b>
              </p>

              {group.description && (
                <p style={{ margin: '0 0 16px', fontSize: 13, color: '#94A3B8' }}>
                  {group.description}
                </p>
              )}

              {/* Action Buttons */}
              {joined ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  <div style={{ color: '#10B981', fontWeight: 600, fontSize: 14, display: 'flex', alignItems: 'center', gap: 6 }}>
                    <CheckCircle2 size={18} /> Siz allaqachon ushbu guruh a‘zosisiz!
                  </div>
                  <button
                    onClick={() => navigate(`/groups/${group.id}`)}
                    style={{
                      padding: '12px 20px',
                      borderRadius: 12,
                      background: '#C8922A',
                      color: '#fff',
                      fontWeight: 700,
                      border: 'none',
                      cursor: 'pointer',
                      fontSize: 14,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: 8,
                    }}
                  >
                    Guruh Sahifasiga O‘tish <ArrowRight size={16} />
                  </button>
                </div>
              ) : user ? (
                <button
                  onClick={() => handleJoin()}
                  disabled={submitting}
                  style={{
                    width: '100%',
                    padding: '14px 20px',
                    borderRadius: 12,
                    background: 'linear-gradient(135deg, #C8922A 0%, #D97706 100%)',
                    color: '#fff',
                    fontWeight: 700,
                    border: 'none',
                    cursor: 'pointer',
                    fontSize: 15,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: 8,
                    boxShadow: '0 4px 15px rgba(200,146,42,0.3)',
                  }}
                >
                  <Sparkles size={18} />
                  {submitting ? 'Qo‘shilmoqda...' : 'Guruhga Qo‘shilish (1-klikda)'}
                </button>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  <Link
                    to={`/login?next=${nextUrl}`}
                    style={{
                      padding: '12px 20px',
                      borderRadius: 12,
                      background: '#C8922A',
                      color: '#fff',
                      fontWeight: 700,
                      textDecoration: 'none',
                      textAlign: 'center',
                      fontSize: 14,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: 8,
                    }}
                  >
                    <LogIn size={16} /> Kirish va Guruhga Qo‘shilish
                  </Link>
                  <Link
                    to={`/register?next=${nextUrl}`}
                    style={{
                      padding: '11px 20px',
                      borderRadius: 12,
                      background: 'rgba(255,255,255,0.06)',
                      color: '#CBD5E1',
                      textDecoration: 'none',
                      textAlign: 'center',
                      fontSize: 14,
                      border: '1px solid rgba(255,255,255,0.12)',
                    }}
                  >
                    Ro‘yxatdan o‘tish
                  </Link>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* TAB 2: CATALOG BROWSE */}
      {activeTab === 'catalog' && (
        <div>
          {/* Subject Filter Pills */}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 20 }}>
            {[
              { id: 'all', label: 'Barcha Fanlar' },
              { id: 'biology', label: '🧬 Biologiya' },
              { id: 'chemistry', label: '🧪 Kimyo' },
              { id: 'law', label: '⚖️ Huquqshunoslik' },
              { id: 'uzbek', label: '🇺🇿 Ona tili' },
              { id: 'english', label: '🇬🇧 Ingliz tili' },
            ].map((p) => {
              const active = selectedSubject === p.id;
              return (
                <button
                  key={p.id}
                  onClick={() => setSelectedSubject(p.id)}
                  style={{
                    padding: '8px 16px',
                    borderRadius: 10,
                    border: 'none',
                    fontSize: 13,
                    fontWeight: 600,
                    cursor: 'pointer',
                    background: active ? '#C8922A' : 'var(--card-bg, #1E293B)',
                    color: active ? '#fff' : '#94A3B8',
                  }}
                >
                  {p.label}
                </button>
              );
            })}
          </div>

          {loadingCatalog ? (
            <div style={{ textAlign: 'center', padding: '50px 0', color: '#94A3B8' }}>
              Kursxonalar yuklanmoqda...
            </div>
          ) : catalog.length === 0 ? (
            <div
              style={{
                background: 'var(--card-bg, #1E293B)',
                borderRadius: 16,
                padding: '40px 20px',
                textAlign: 'center',
                color: '#94A3B8',
              }}
            >
              Hozircha ochiq kursxonalar ro‘yxati topilmadi.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
              {catalog.map((b) => {
                const filteredGroups = (b.groups || []).filter(
                  (g) => selectedSubject === 'all' || g.subject === selectedSubject
                );

                if (selectedSubject !== 'all' && filteredGroups.length === 0) {
                  return null;
                }

                return (
                  <div
                    key={b.id}
                    style={{
                      background: 'var(--card-bg, #1E293B)',
                      borderRadius: 18,
                      padding: '22px',
                      border: '1px solid var(--border-color, rgba(255,255,255,0.08))',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
                      <div>
                        <span
                          style={{
                            padding: '3px 8px',
                            borderRadius: 6,
                            background: 'rgba(59,130,246,0.15)',
                            color: '#60A5FA',
                            fontSize: 11,
                            fontWeight: 700,
                          }}
                        >
                          {b.branch_code}
                        </span>
                        <h3 style={{ fontSize: 17, fontWeight: 700, margin: '6px 0 4px', color: '#F8FAFC' }}>
                          {b.name}
                        </h3>
                        <div style={{ fontSize: 12, color: '#94A3B8' }}>
                          📍 {b.region} {b.address ? `• ${b.address}` : ''}
                        </div>
                      </div>

                      {b.phone && (
                        <div style={{ fontSize: 12, color: '#10B981', display: 'flex', alignItems: 'center', gap: 4 }}>
                          <Phone size={13} /> {b.phone}
                        </div>
                      )}
                    </div>

                    {/* Groups under this branch */}
                    <div style={{ marginTop: 16, display: 'flex', flexDirection: 'column', gap: 10 }}>
                      <div style={{ fontSize: 12, fontWeight: 600, color: '#94A3B8' }}>
                        Filialdagi Ochiq Guruhlar ({filteredGroups.length}):
                      </div>

                      {filteredGroups.length === 0 ? (
                        <div style={{ fontSize: 13, color: '#64748B', fontStyle: 'italic' }}>
                          Bu fanda hozircha guruh ochilmagan.
                        </div>
                      ) : (
                        filteredGroups.map((g) => (
                          <div
                            key={g.id}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'space-between',
                              padding: '12px 16px',
                              borderRadius: 12,
                              background: 'rgba(255,255,255,0.04)',
                              border: '1px solid rgba(255,255,255,0.06)',
                            }}
                          >
                            <div>
                              <div style={{ fontSize: 14, fontWeight: 700, color: '#F8FAFC' }}>
                                {g.name}
                              </div>
                              <div style={{ fontSize: 12, color: '#94A3B8', marginTop: 2 }}>
                                Ustoz: <b>{g.teacher_name}</b> • {g.student_count} ta o‘quvchi • Kod:{' '}
                                <b style={{ color: '#F59E0B' }}>{g.invite_code}</b>
                              </div>
                            </div>

                            <button
                              onClick={() => handleCatalogGroupJoin(g.invite_code, g.id)}
                              disabled={joiningGroupId === g.id}
                              style={{
                                padding: '8px 16px',
                                borderRadius: 10,
                                background: '#C8922A',
                                color: '#fff',
                                border: 'none',
                                fontWeight: 600,
                                fontSize: 13,
                                cursor: 'pointer',
                                display: 'flex',
                                alignItems: 'center',
                                gap: 6,
                              }}
                            >
                              {joiningGroupId === g.id ? 'Qo‘shilmoqda...' : 'Guruhga kirish'}
                              <ArrowRight size={14} />
                            </button>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
