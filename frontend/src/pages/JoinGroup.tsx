import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ArrowRight, BookOpen, LogIn, UserCheck, Users, X } from 'lucide-react';
import { useAuth } from '../auth/AuthContext';
import { useToast } from '../context/ToastContext';
import { useLang } from '../i18n/LangContext';
import { GroupInviteApi, type GroupJoinPreview } from '../lib/api';

/** Group invite: who the group is, then join (signed in) or sign in / register first. */
export default function JoinGroup() {
  const { token } = useParams<{ token: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();
  const toast = useToast();
  const { t } = useLang();

  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [group, setGroup] = useState<GroupJoinPreview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [joined, setJoined] = useState(false);

  useEffect(() => {
    if (!token) return;
    let alive = true;
    GroupInviteApi.preview(token)
      .then((data) => {
        if (!alive) return;
        setGroup(data);
        if (data.is_member) setJoined(true);
      })
      .catch((err: Error) => alive && setError(err.message || t('jg_not_found_text')))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, [token, t]);

  const next = encodeURIComponent(`/join/${token}`);

  const join = async () => {
    if (!token) return;
    setSubmitting(true);
    try {
      const res = await GroupInviteApi.join(token);
      toast.success(res.message || t('jg_joined'));
      setJoined(true);
      window.setTimeout(() => navigate('/dashboard'), 1200);
    } catch (err) {
      toast.error(err instanceof Error && err.message ? err.message : t('jg_join_failed'));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="jg">
      <Link to="/" className="jg-brand">
        <img src="/logo-mark.png" alt="" width={36} height={36} />
        <span>GRAND EDUCATION</span>
      </Link>

      <div className="ui-card jg-card">
        {loading ? (
          <div aria-busy="true" aria-label={t('loading')}>
            <div className="ui-skel ui-skel-line" style={{ width: '40%' }} />
            <div className="ui-skel ui-skel-line" style={{ width: '80%', height: 22 }} />
            <div className="ui-skel ui-skel-line" style={{ width: '60%' }} />
            <div className="ui-skel" style={{ height: 48, borderRadius: 12, marginTop: 16 }} />
          </div>
        ) : error || !group ? (
          <div className="ui-state" style={{ border: 0, padding: '8px 0' }}>
            <span className="ic-chip ic-chip--danger">
              <X size={24} aria-hidden="true" />
            </span>
            <h3>{t('jg_not_found')}</h3>
            <p>{error || t('jg_not_found_text')}</p>
            <Link to="/" className="ui-btn">
              {t('jg_home')}
            </Link>
          </div>
        ) : (
          <>
            <div className="jg-meta">
              <span className="jg-chip">
                <BookOpen size={14} aria-hidden="true" /> {group.subject_display || group.subject}
              </span>
              <span className="jg-count">
                <Users size={14} aria-hidden="true" /> {t('jg_students').replace('{n}', String(group.student_count))}
              </span>
            </div>
            <h1 className="jg-title">{group.name}</h1>
            <p className="jg-teacher">
              <UserCheck size={16} aria-hidden="true" /> {t('jg_teacher')}: <b>{group.teacher_name}</b>
            </p>
            {group.description && <p className="jg-desc">{group.description}</p>}

            {joined ? (
              <>
                <p className="jg-done" role="status">
                  <UserCheck size={16} aria-hidden="true" /> {t('jg_already')}
                </p>
                <button type="button" className="ui-btn ui-btn--primary ui-btn--block ui-btn--lg" onClick={() => navigate('/dashboard')}>
                  {t('jg_to_cabinet')} <ArrowRight size={16} aria-hidden="true" />
                </button>
              </>
            ) : user ? (
              <button type="button" className="ui-btn ui-btn--primary ui-btn--block ui-btn--lg" onClick={() => void join()} disabled={submitting}>
                {submitting ? t('loading') : t('jg_join')}
              </button>
            ) : (
              <div className="jg-auth">
                <Link to={`/login?next=${next}`} className="ui-btn ui-btn--primary ui-btn--block ui-btn--lg">
                  <LogIn size={18} aria-hidden="true" /> {t('jg_login_join')}
                </Link>
                <Link to={`/register?next=${next}`} className="ui-btn ui-btn--block">
                  {t('jg_register')}
                </Link>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
