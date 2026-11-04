import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { AlertTriangle, Camera, Clock, FileText, Lock, PenLine, RotateCcw, Search } from 'lucide-react';
import { useLang } from '../i18n/LangContext';
import { AuthExpiredError, Essays } from '../lib/api';
import { essayKind, essayStatus, filterMyEssays, filterTopics, scoreLabel, type EssayKind, type MineFilter } from '../lib/essays';
import { useSubject } from '../lib/useSubject';

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
  topic_id: number | null;
  topic_title: string;
  subject?: string;
  category?: string;
  rubric_type?: string;
  status: string;
  total_score: number | null;
  max_score?: number | null;
  overall_band?: number | null;
  updated_at?: string | null;
  graded_at?: string | null;
}

type Tab = 'topics' | 'mine';

const TYPE_FILTERS: Record<'uzbek' | 'english', ('all' | EssayKind)[]> = {
  uzbek: ['all', 'ona_tili', 'adabiyot'],
  english: ['all', 'ielts_task1', 'ielts_task2', 'multilevel'],
};

function Skeleton() {
  return (
    <div className="ui-card es-card" aria-hidden="true">
      <div className="ui-skel ui-skel-line" style={{ width: '75%', height: 16 }} />
      <div className="ui-skel ui-skel-line" style={{ width: '40%' }} />
      <div className="ui-skel" style={{ height: 44, borderRadius: 12, marginTop: 8 }} />
    </div>
  );
}

/** Essay studio: topics for the chosen subject, own topic / photo upload, and "my essays". */
export default function EssayTopics() {
  const { t, lang } = useLang();
  const navigate = useNavigate();
  const subject = useSubject();
  const [tab, setTab] = useState<Tab>('topics');
  const [type, setType] = useState<'all' | EssayKind>('all');
  const [query, setQuery] = useState('');
  const [mineFilter, setMineFilter] = useState<MineFilter>('all');
  const [topics, setTopics] = useState<Topic[]>([]);
  const [subs, setSubs] = useState<Submission[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [reload, setReload] = useState(0);

  useEffect(() => setType('all'), [subject]);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setErr(null);
    Promise.all([Essays.topics({ subject }), Essays.submissions({ subject })])
      .then(([tj, sj]) => {
        if (!alive) return;
        setTopics((tj.topics as Topic[]) || []);
        setSubs((sj.submissions as Submission[]) || []);
      })
      .catch((e) => {
        if (!alive) return;
        if (e instanceof AuthExpiredError) {
          navigate('/login');
          return;
        }
        setErr(e instanceof Error ? e.message : t('err_retry_js'));
      })
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, [subject, reload, navigate, t]);

  const visibleTopics = useMemo(() => filterTopics(topics, type, query), [topics, query, type]);

  const visibleSubs = useMemo(() => filterMyEssays(subs, mineFilter), [subs, mineFilter]);

  const dateOf = (iso?: string | null) => (iso ? new Date(iso).toLocaleDateString(lang) : '');

  const topicAction = (tp: Topic) => {
    const st = tp.user_status;
    const state = st ? essayStatus(st.status) : 'none';
    if (state === 'graded' && st) {
      return (
        <Link className="ui-btn ui-btn--block" to={`/essays/result/${st.submission_id}`}>
          {t('es_view_result')}
        </Link>
      );
    }
    if ((state === 'pending' || state === 'teacher') && st) {
      return (
        <Link className="ui-btn ui-btn--block" to={`/essays/result/${st.submission_id}`}>
          {t('es_status_pending')}
        </Link>
      );
    }
    return (
      <Link className="ui-btn ui-btn--primary ui-btn--block" to={`/essays/write/${tp.id}`}>
        {state === 'draft' ? t('es_continue') : state === 'error' ? t('es_retry') : t('es_write')}
      </Link>
    );
  };

  const statusChip = (raw: string) => {
    const st = essayStatus(raw);
    return <span className={`es-status is-${st}`}>{t(`es_status_${st}`)}</span>;
  };

  const showCefrNote = subject === 'english' && type === 'multilevel' && visibleTopics.length === 0;

  return (
    <div className="es">
      <div className="es-head">
        <h1>{t('tb_title_essays')}</h1>
        <p>{t(subject === 'english' ? 'es_sub_english' : 'es_sub_uzbek')}</p>
      </div>

      <div className={`es-actions${subject === 'english' ? ' es-actions--one' : ''}`}>
        {subject === 'uzbek' && (
          <Link to="/essays/new" className="ui-btn ui-btn--lg">
            <PenLine size={18} aria-hidden="true" /> {t('es_new')}
          </Link>
        )}
        <Link to={`/essays/upload?subject=${subject}`} className="ui-btn ui-btn--lg">
          <Camera size={18} aria-hidden="true" /> {t('es_upload')}
        </Link>
      </div>

      <div className="ui-seg" role="tablist" aria-label={t('tb_title_essays')}>
        <button type="button" role="tab" aria-selected={tab === 'topics'} onClick={() => setTab('topics')}>
          {t('es_tab_topics')}
        </button>
        <button type="button" role="tab" aria-selected={tab === 'mine'} onClick={() => setTab('mine')}>
          {t('es_tab_mine')}
          {subs.length > 0 && ` (${subs.length})`}
        </button>
      </div>

      {loading && (
        <div className="es-grid" aria-busy="true" aria-label={t('loading')}>
          <Skeleton />
          <Skeleton />
        </div>
      )}

      {!loading && err && (
        <div className="ui-state ui-state--error" role="alert">
          <span className="ic-chip ic-chip--danger">
            <AlertTriangle size={24} aria-hidden="true" />
          </span>
          <h3>{t('es_error_title')}</h3>
          <p>{err}</p>
          <button type="button" className="ui-btn ui-btn--primary" onClick={() => setReload((n) => n + 1)}>
            <RotateCcw size={16} aria-hidden="true" /> {t('error_retry')}
          </button>
        </div>
      )}

      {!loading && !err && tab === 'topics' && (
        <>
          <div className="ui-chip-row" role="group" aria-label={t('es_type')}>
            {TYPE_FILTERS[subject].map((k) => (
              <button key={k} type="button" className={`ui-chip${type === k ? ' is-on' : ''}`} aria-pressed={type === k} onClick={() => setType(k)}>
                {t(`es_kind_${k}`)}
              </button>
            ))}
          </div>
          <div className="es-tools">
            <label className="ui-search">
              <Search size={18} aria-hidden="true" />
              <input
                type="search"
                className="ui-input"
                placeholder={t('es_search')}
                aria-label={t('search')}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                enterKeyHint="search"
              />
            </label>
          </div>

          {showCefrNote ? (
            <div className="ui-state">
              <span className="ic-chip ic-chip--info">
                <FileText size={24} aria-hidden="true" />
              </span>
              <h3>{t('es_cefr_title')}</h3>
              <p>{t('es_cefr_text')}</p>
              <Link to="/tests" className="ui-btn ui-btn--primary">
                {t('es_cefr_btn')}
              </Link>
            </div>
          ) : visibleTopics.length === 0 ? (
            <div className="ui-state">
              <span className="ic-chip ic-chip--muted">
                <FileText size={24} aria-hidden="true" />
              </span>
              <h3>{t(query || type !== 'all' ? 'es_nomatch' : 'es_no_topics')}</h3>
              {(query || type !== 'all') && (
                <button
                  type="button"
                  className="ui-btn"
                  onClick={() => {
                    setQuery('');
                    setType('all');
                  }}
                >
                  {t('tl_clear_filters')}
                </button>
              )}
            </div>
          ) : (
            <div className="es-grid">
              {visibleTopics.map((tp) => {
                const kind = essayKind(tp);
                return (
                  <article key={tp.id} className="ui-card es-card">
                    <div className="es-card__top">
                      <span className="ic-chip">
                        <PenLine size={18} aria-hidden="true" />
                      </span>
                      <div style={{ minWidth: 0, flex: 1 }}>
                        <span className="es-card__type">{t(`es_kind_${kind}`)}</span>
                        <h3 className="es-card__title clamp-2">{tp.title}</h3>
                      </div>
                      {tp.has_password && <Lock size={16} aria-label={t('es_locked')} />}
                    </div>
                    <p className="es-card__meta">
                      <span>{t('es_words').replace('{min}', String(tp.word_limit_min)).replace('{max}', String(tp.word_limit_max))}</span>
                      {tp.time_limit_minutes > 0 && (
                        <span>
                          <Clock size={14} aria-hidden="true" /> {t('tl_minutes').replace('{n}', String(tp.time_limit_minutes))}
                        </span>
                      )}
                    </p>
                    <div className="es-card__actions">{topicAction(tp)}</div>
                  </article>
                );
              })}
            </div>
          )}
        </>
      )}

      {!loading && !err && tab === 'mine' && (
        <>
          <div className="ui-chip-row" role="group" aria-label={t('es_tab_mine')}>
            {(['all', 'draft', 'graded'] as MineFilter[]).map((f) => (
              <button key={f} type="button" className={`ui-chip${mineFilter === f ? ' is-on' : ''}`} aria-pressed={mineFilter === f} onClick={() => setMineFilter(f)}>
                {t(`es_mine_${f}`)}
              </button>
            ))}
          </div>
          {visibleSubs.length === 0 ? (
            <div className="ui-state">
              <span className="ic-chip ic-chip--muted">
                <PenLine size={24} aria-hidden="true" />
              </span>
              <h3>{t(subs.length ? 'es_nomatch' : 'es_mine_empty')}</h3>
              <button type="button" className="ui-btn ui-btn--primary" onClick={() => setTab('topics')}>
                {t('es_pick_topic')}
              </button>
            </div>
          ) : (
            <div className="es-grid">
              {visibleSubs.map((s) => {
                const st = essayStatus(s.status);
                const href = st === 'draft' && s.topic_id ? `/essays/write/${s.topic_id}` : `/essays/result/${s.id}`;
                const score = st === 'graded' ? scoreLabel(s, t) : '';
                return (
                  <Link key={s.id} to={href} className="ui-card es-card" style={{ textDecoration: 'none' }}>
                    <div className="es-card__top">
                      <div style={{ minWidth: 0, flex: 1 }}>
                        <span className="es-card__type">{t(`es_kind_${essayKind(s)}`)}</span>
                        <h3 className="es-card__title clamp-2">{s.topic_title || t('es_untitled')}</h3>
                      </div>
                      {statusChip(s.status)}
                    </div>
                    <p className="es-card__meta">
                      <span>{dateOf(s.graded_at || s.updated_at)}</span>
                      {score && <span className="es-score">{score}</span>}
                    </p>
                  </Link>
                );
              })}
            </div>
          )}
        </>
      )}
    </div>
  );
}
