import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useLang } from '../i18n/LangContext';
import { useAuth } from '../auth/AuthContext';
import { AuthExpiredError, Essays } from '../lib/api';
import { LockIcon } from '../components/icons';

/**
 * Essay topics — mirrors apps/telegram_app/views.py tma_essay_topics_view
 * (GET /tma/api/essays/topics/, JWT) + tma_essay_submissions_view
 * (GET /tma/api/essays/, JWT).
 *
 * Per-status CTA parity with templates/essays/topic_list.html:
 *   graded/ai_evaluated/teacher_reviewed → view result (+score)
 *   pending                             → result page (polling spinner)
 *   draft                               → continue writing
 *   pending_teacher                     → teacher-reviewing state → result
 *   error                               → retry (write page)
 *   none                                → start writing
 */

interface UserStatus {
  submission_id: number;
  status: string;
  total_score: number | null;
}

interface Topic {
  id: number;
  subject?: string;
  category?: string;
  rubric_type?: string;
  title: string;
  description: string;
  word_limit_min: number;
  word_limit_max: number;
  time_limit_minutes: number;
  has_password: boolean;
  user_status: UserStatus | null;
}

interface Submission {
  id: number;
  topic_title: string;
  subject?: string;
  category?: string;
  rubric_type?: string;
  status: string;
  total_score: number | null;
  converted_score: number | null;
  overall_band?: number | null;
  cefr_level?: string | null;
  word_count: number;
}

const DONE = new Set(['graded', 'ai_evaluated', 'teacher_reviewed']);

function TopicAction({ topic }: { topic: Topic }) {
  const { t } = useLang();
  const st = topic.user_status;
  if (!st) {
    return (
      <Link className="btn primary sm" to={`/essays/write/${topic.id}`}>
        {t('write_essay')}
      </Link>
    );
  }
  if (DONE.has(st.status)) {
    return (
      <Link className="btn sm" to={`/essays/result/${st.submission_id}`}>
        {t('essay_view_result')}
        {st.total_score !== null && st.total_score !== undefined
          ? ` — ${st.total_score}`
          : ''}
      </Link>
    );
  }
  if (st.status === 'pending') {
    return (
      <Link className="btn sm" to={`/essays/result/${st.submission_id}`}>
        {t('essay_ai_grading_progress')}
      </Link>
    );
  }
  if (st.status === 'draft') {
    return (
      <Link className="btn primary sm" to={`/essays/write/${topic.id}`}>
        {t('essay_continue_writing')}
      </Link>
    );
  }
  if (st.status === 'pending_teacher') {
    return (
      <Link className="btn sm" to={`/essays/result/${st.submission_id}`}>
        {t('essay_teacher_reviewing')}
      </Link>
    );
  }
  if (st.status === 'error') {
    return (
      <Link className="btn primary sm" to={`/essays/write/${topic.id}`}>
        {t('essay_error_retry')}
      </Link>
    );
  }
  return (
    <Link className="btn sm" to={`/essays/result/${st.submission_id}`}>
      {t('essay_continue_writing')} ({st.status})
    </Link>
  );
}

function getTopicBadge(topic: { category?: string; rubric_type?: string; title: string }) {
  const cat = (topic.category || '').toLowerCase();
  const rubric = (topic.rubric_type || '').toLowerCase();
  const title = (topic.title || '').toLowerCase();

  if (cat === 'ielts_task1' || rubric === 'ielts_task1' || title.includes('task 1')) {
    return {
      label: '🎓 IELTS Task 1',
      bg: 'rgba(59, 130, 246, 0.15)',
      color: '#60a5fa',
      border: 'rgba(59, 130, 246, 0.35)',
    };
  }
  if (cat === 'ielts_task2' || rubric === 'ielts_task2' || title.includes('task 2')) {
    return {
      label: '🎓 IELTS Task 2',
      bg: 'rgba(245, 158, 11, 0.15)',
      color: '#fbbf24',
      border: 'rgba(245, 158, 11, 0.35)',
    };
  }
  if (cat === 'multilevel' || title.includes('multi-level') || title.includes('cefr')) {
    return {
      label: '🎯 CEFR Multi-level',
      bg: 'rgba(16, 185, 129, 0.15)',
      color: '#34d399',
      border: 'rgba(16, 185, 129, 0.35)',
    };
  }
  if (cat === 'adabiyot') {
    return {
      label: '📚 Adabiyot',
      bg: 'rgba(168, 85, 247, 0.15)',
      color: '#c084fc',
      border: 'rgba(168, 85, 247, 0.35)',
    };
  }
  return {
    label: '📜 Milliy sertifikat',
    bg: 'rgba(14, 165, 233, 0.15)',
    color: '#38bdf8',
    border: 'rgba(14, 165, 233, 0.35)',
  };
}

export default function EssayTopics() {
  const { t } = useLang();
  const { user } = useAuth();
  const navigate = useNavigate();

  const [activeSubject, setActiveSubject] = useState<'uzbek' | 'english'>(() => {
    if (user?.active_subject === 'english') return 'english';
    const saved = localStorage.getItem('lms_subject');
    return saved === 'english' ? 'english' : 'uzbek';
  });

  const [englishTab, setEnglishTab] = useState<'ielts' | 'multilevel'>('ielts');
  const [topics, setTopics] = useState<Topic[]>([]);
  const [subs, setSubs] = useState<Submission[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // Sync when subject switches globally
  useEffect(() => {
    const handler = (e: Event) => {
      const customEvent = e as CustomEvent<'uzbek' | 'english'>;
      const next = customEvent.detail || (localStorage.getItem('lms_subject') as 'uzbek' | 'english') || 'uzbek';
      setActiveSubject(next);
    };
    window.addEventListener('subject-changed', handler);
    return () => window.removeEventListener('subject-changed', handler);
  }, []);

  // Fetch topics and submissions for current subject and subcategory
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setErr(null);

    const categoryParam = activeSubject === 'english' ? englishTab : undefined;

    Promise.all([
      Essays.topics({ subject: activeSubject, category: categoryParam }),
      Essays.submissions({ subject: activeSubject }),
    ])
      .then(([tj, sj]) => {
        if (cancelled) return;
        setTopics(((tj.topics as Topic[]) || []));
        setSubs((((sj.submissions as Submission[]) || []).slice(0, 15)));
      })
      .catch((e) => {
        if (cancelled) return;
        if (e instanceof AuthExpiredError) {
          navigate('/login');
          return;
        }
        setErr(e instanceof Error ? e.message : 'Failed to load essay topics.');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [activeSubject, englishTab, navigate]);

  // Strict client-side filter fallback
  const visibleTopics = useMemo(() => {
    return topics.filter((t) => {
      const title = (t.title || '').toLowerCase();
      const cat = (t.category || '').toLowerCase();
      const rubric = (t.rubric_type || '').toLowerCase();
      const isEnglish =
        t.subject === 'english' ||
        cat.includes('ielts') ||
        cat === 'multilevel' ||
        rubric.includes('ielts') ||
        title.includes('ielts') ||
        title.includes('multi-level') ||
        title.includes('cefr');

      if (activeSubject === 'uzbek') {
        return !isEnglish;
      }

      if (englishTab === 'ielts') {
        return (
          cat === 'ielts_task1' ||
          cat === 'ielts_task2' ||
          rubric.includes('ielts') ||
          title.includes('ielts') ||
          title.includes('task 1') ||
          title.includes('task 2')
        );
      }

      if (englishTab === 'multilevel') {
        return (
          cat === 'multilevel' ||
          title.includes('multi-level') ||
          title.includes('cefr')
        );
      }

      return true;
    });
  }, [topics, activeSubject, englishTab]);

  const visibleSubs = useMemo(() => {
    return subs.filter((s) => {
      const isEng =
        s.subject === 'english' ||
        (s.category && (s.category.includes('ielts') || s.category === 'multilevel')) ||
        (s.topic_title && (s.topic_title.toLowerCase().includes('ielts') || s.topic_title.toLowerCase().includes('cefr')));
      if (activeSubject === 'uzbek') return !isEng;
      if (englishTab === 'ielts') {
        return !s.category?.includes('multilevel') && !s.topic_title.toLowerCase().includes('multi-level');
      }
      if (englishTab === 'multilevel') {
        return s.category === 'multilevel' || s.topic_title.toLowerCase().includes('multi-level') || s.topic_title.toLowerCase().includes('cefr');
      }
      return true;
    });
  }, [subs, activeSubject, englishTab]);

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12 }}>
        <div>
          <h1 style={{ display: 'flex', alignItems: 'center', gap: 10, margin: '0 0 6px' }}>
            <span>{activeSubject === 'english' ? '🇬🇧' : '🇺🇿'}</span>
            <span>
              {activeSubject === 'english'
                ? 'English Writing Tasks & Essays'
                : 'Ona tili va adabiyot — Esse mavzulari'}
            </span>
          </h1>
          <p className="muted small" style={{ margin: 0 }}>
            {activeSubject === 'english'
              ? 'Official IELTS Writing (Task 1 & 2) and CEFR Multi-level criteria with instant AI evaluation.'
              : 'BMB (DTM) 12-mezonli rasmiy baholash tizimi bo‘yicha esse yozing va AI hamda ustozdan aniq ball oling.'}
          </p>
        </div>
      </div>

      {/* English Category Sub-tabs: IELTS & Multi-level */}
      {activeSubject === 'english' && (
        <div
          role="tablist"
          aria-label="English Exam Categories"
          style={{
            display: 'inline-flex',
            gap: '8px',
            margin: '20px 0 16px',
            background: 'rgba(15, 23, 42, 0.85)',
            padding: '4px',
            borderRadius: '14px',
            border: '1px solid rgba(51, 65, 85, 0.7)',
          }}
        >
          <button
            type="button"
            role="tab"
            aria-selected={englishTab === 'ielts'}
            onClick={() => setEnglishTab('ielts')}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '8px',
              padding: '8px 18px',
              borderRadius: '10px',
              fontWeight: 700,
              fontSize: '0.88rem',
              cursor: 'pointer',
              transition: 'all 0.2s ease',
              background: englishTab === 'ielts' ? '#f59e0b' : 'transparent',
              color: englishTab === 'ielts' ? '#0f172a' : '#94a3b8',
              border: 'none',
              boxShadow: englishTab === 'ielts' ? '0 2px 8px rgba(245, 158, 11, 0.35)' : 'none',
            }}
          >
            <span>🎓</span> IELTS (Academic & General)
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={englishTab === 'multilevel'}
            onClick={() => setEnglishTab('multilevel')}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '8px',
              padding: '8px 18px',
              borderRadius: '10px',
              fontWeight: 700,
              fontSize: '0.88rem',
              cursor: 'pointer',
              transition: 'all 0.2s ease',
              background: englishTab === 'multilevel' ? '#10b981' : 'transparent',
              color: englishTab === 'multilevel' ? '#0f172a' : '#94a3b8',
              border: 'none',
              boxShadow: englishTab === 'multilevel' ? '0 2px 8px rgba(16, 185, 129, 0.35)' : 'none',
            }}
          >
            <span>🎯</span> CEFR Multi-level (B2/C1)
          </button>
        </div>
      )}

      {loading && <p className="muted" style={{ marginTop: 20 }}>{t('loading')}</p>}
      {err && <p className="error" style={{ marginTop: 20 }}>{err}</p>}

      {!loading && (
        <div className="grid" style={{ marginTop: activeSubject === 'english' ? 8 : 20 }}>
          {visibleTopics.map((topic) => {
            const badge = getTopicBadge(topic);
            return (
              <div key={topic.id} className="card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8, gap: 8 }}>
                    <span
                      style={{
                        fontSize: '0.75rem',
                        fontWeight: 700,
                        padding: '3px 8px',
                        borderRadius: '6px',
                        background: badge.bg,
                        color: badge.color,
                        border: `1px solid ${badge.border}`,
                        display: 'inline-block',
                      }}
                    >
                      {badge.label}
                    </span>
                    {topic.has_password && (
                      <span className="muted small" style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                        <LockIcon size={12} className="ico" /> {t('essay_password_protected')}
                      </span>
                    )}
                  </div>
                  <strong style={{ fontSize: '1.05rem', lineHeight: 1.4, display: 'block', marginBottom: 6 }}>
                    {topic.title}
                  </strong>
                  <p className="muted small" style={{ marginBottom: 12 }}>
                    {topic.description}
                  </p>
                </div>
                <div>
                  <p className="muted small" style={{ marginBottom: 12 }}>
                    {topic.word_limit_min}–{topic.word_limit_max} {t('words_suffix')}
                    {' · '}
                    {topic.time_limit_minutes} {t('minutes_suffix')}
                  </p>
                  <TopicAction topic={topic} />
                </div>
              </div>
            );
          })}

          {visibleTopics.length === 0 && !err && (
            <div className="card" style={{ gridColumn: '1 / -1', padding: '32px 24px', textAlign: 'center' }}>
              <div style={{ fontSize: '2rem', marginBottom: 8 }}>
                {activeSubject === 'english' ? '📝' : '📖'}
              </div>
              <strong style={{ fontSize: '1.1rem' }}>
                {activeSubject === 'english'
                  ? englishTab === 'ielts'
                    ? 'No IELTS writing topics added yet'
                    : 'No CEFR Multi-level topics added yet'
                  : 'Hozircha faol esse mavzulari mavjud emas'}
              </strong>
              <p className="muted small" style={{ margin: '8px auto 0', maxWidth: 480 }}>
                {activeSubject === 'english'
                  ? 'Your instructor will create writing prompts here. Once added, you can practice under timed exam conditions.'
                  : 'Ustoz tomonidan yangi mavzular kiritilgach, ular bu yerda paydo bo‘ladi.'}
              </p>
            </div>
          )}
        </div>
      )}

      <h2 style={{ marginTop: 36, display: 'flex', alignItems: 'center', gap: 8 }}>
        <span>📊</span>
        <span>
          {activeSubject === 'english'
            ? 'My Writing Submissions'
            : t('my_essays')}
        </span>
      </h2>

      <div className="table-wrap">
        <table className="data">
          <thead>
            <tr>
              <th>{t('th_topic')}</th>
              <th>Toifa</th>
              <th>{t('status')}</th>
              <th>{activeSubject === 'english' ? 'Band / Score' : t('score')}</th>
            </tr>
          </thead>
          <tbody>
            {visibleSubs.map((s) => {
              const badge = getTopicBadge({
                category: s.category,
                rubric_type: s.rubric_type,
                title: s.topic_title,
              });
              return (
                <tr key={s.id}>
                  <td>
                    <Link to={`/essays/result/${s.id}`} style={{ fontWeight: 600 }}>
                      {s.topic_title || 'Nomsiz esse'}
                    </Link>
                  </td>
                  <td>
                    <span
                      style={{
                        fontSize: '0.72rem',
                        fontWeight: 700,
                        padding: '2px 7px',
                        borderRadius: '5px',
                        background: badge.bg,
                        color: badge.color,
                        border: `1px solid ${badge.border}`,
                        display: 'inline-block',
                      }}
                    >
                      {badge.label}
                    </span>
                  </td>
                  <td>
                    <span className="badge">{s.status}</span>
                  </td>
                  <td>
                    {s.subject === 'english' || activeSubject === 'english' ? (
                      s.overall_band !== null && s.overall_band !== undefined ? (
                        <strong>
                          Band {s.overall_band}{' '}
                          {s.cefr_level ? (
                            <span className="muted small">({s.cefr_level})</span>
                          ) : (
                            ''
                          )}
                        </strong>
                      ) : (
                        s.total_score !== null && s.total_score !== undefined ? (
                          `Band ${s.total_score}`
                        ) : (
                          '—'
                        )
                      )
                    ) : (
                      s.converted_score ?? s.total_score ?? '—'
                    )}
                  </td>
                </tr>
              );
            })}
            {visibleSubs.length === 0 && (
              <tr>
                <td colSpan={4} className="muted" style={{ textAlign: 'center', padding: '20px' }}>
                  {activeSubject === 'english'
                    ? 'No submissions yet for this category.'
                    : 'Hozircha topshirilgan esselar yo‘q.'}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
