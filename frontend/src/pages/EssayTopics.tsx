import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useLang } from '../i18n/LangContext';
import { Essays } from '../lib/api';
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
  status: string;
  total_score: number | null;
  converted_score: number | null;
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

export default function EssayTopics() {
  const { t } = useLang();
  const [topics, setTopics] = useState<Topic[]>([]);
  const [subs, setSubs] = useState<Submission[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const [tj, sj] = await Promise.all([Essays.topics(), Essays.submissions()]);
        setTopics(((tj.topics as Topic[]) || []));
        setSubs((((sj.submissions as Submission[]) || []).slice(0, 10)));
      } catch (e) {
        setErr(e instanceof Error ? e.message : 'Failed.');
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) return <p className="muted">{t('loading')}</p>;

  return (
    <div>
      <h1>{t('essay_topics')}</h1>
      <p className="muted small">{t('essay_topics_intro')}</p>
      {err && <p className="error">{err}</p>}
      <div className="grid">
        {topics.map((topic) => (
          <div key={topic.id} className="card">
            <strong>{topic.title}</strong>
            <p className="muted small">{topic.description}</p>
            <p className="muted small">
              {topic.word_limit_min}–{topic.word_limit_max} {t('words_suffix')}
              {' · '}
              {topic.time_limit_minutes} {t('minutes_suffix')}
              {topic.has_password ? (
                <>
                  {' · '}
                  <LockIcon size={12} className="ico" /> {t('essay_password_protected')}
                </>
              ) : (
                ''
              )}
            </p>
            <TopicAction topic={topic} />
          </div>
        ))}
        {topics.length === 0 && !err && (
          <div className="card">
            <strong>{t('essay_no_topics')}</strong>
            <p className="muted small">{t('essay_no_topics_hint')}</p>
          </div>
        )}
      </div>
      <h2>{t('my_essays')}</h2>
      <div className="table-wrap">
        <table className="data">
          <thead>
            <tr>
              <th>{t('th_topic')}</th>
              <th>{t('status')}</th>
              <th>{t('score')}</th>
            </tr>
          </thead>
          <tbody>
            {subs.map((s) => (
              <tr key={s.id}>
                <td>
                  <Link to={`/essays/result/${s.id}`}>{s.topic_title}</Link>
                </td>
                <td>
                  <span className="badge">{s.status}</span>
                </td>
                <td>{s.converted_score ?? s.total_score ?? '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
