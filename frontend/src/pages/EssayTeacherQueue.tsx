import { useEffect, useState } from 'react';
import { Link, Navigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { useLang } from '../i18n/LangContext';
import { TeacherEssays, canReviewEssays } from '../lib/api';
import type { TeacherEssayCard } from '../lib/api';

interface Queue {
  student_requested: TeacherEssayCard[];
  pending: TeacherEssayCard[];
  reviewed: {
    submission_id: number;
    student: string;
    topic: string | null;
    final_score: number;
    reviewed_at: string;
  }[];
}

function Section({
  title,
  items,
}: {
  title: string;
  items: TeacherEssayCard[];
}) {
  const { t } = useLang();
  if (items.length === 0) return null;
  return (
    <>
      <h2>{title}</h2>
      <div className="table-wrap">
        <table className="data">
          <thead>
            <tr>
              <th>{t('th_student')}</th>
              <th>{t('th_topic')}</th>
              <th>{t('score')}</th>
              <th>{t('date')}</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {items.map((s) => (
              <tr key={s.id}>
                <td>{s.student}</td>
                <td>{s.topic ?? '—'}</td>
                <td>
                  {s.total_score}/{s.max_score}
                </td>
                <td className="muted small">
                  {s.submitted_at ? s.submitted_at.slice(0, 16).replace('T', ' ') : '—'}
                </td>
                <td>
                  <Link className="btn sm" to={`/teacher/essays/${s.id}/review`}>
                    {t('tr_open_review')} →
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

/** Teacher essay review queue (parity with legacy /essays/teacher/queue/). */
export default function EssayTeacherQueue() {
  const { t } = useLang();
  const { user, loading } = useAuth();
  const [queue, setQueue] = useState<Queue | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    TeacherEssays.queue()
      .then((q) => setQueue(q as Queue))
      .catch((e) => setErr(e instanceof Error ? e.message : t('err_retry_js')));
  }, [t]);

  // Essays expose other students' work: teacher/platform-admin only
  // (is_staff alone is NOT enough — mirrors essays teacher_required).
  if (!loading && user && !canReviewEssays(user)) {
    return <Navigate to="/dashboard" replace />;
  }
  if (err) return <p className="error">{err}</p>;
  if (!queue) return <p className="muted">{t('loading')}</p>;

  const empty =
    queue.student_requested.length === 0 && queue.pending.length === 0;

  return (
    <div>
      <h1>{t('teacher_queue')}</h1>
      {empty && queue.reviewed.length === 0 && (
        <p className="muted">{t('tr_no_items')}</p>
      )}
      <Section title={t('tr_requested')} items={queue.student_requested} />
      <Section title={t('tr_pending')} items={queue.pending} />
      {queue.reviewed.length > 0 && (
        <>
          <h2>{t('tr_reviewed')}</h2>
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>{t('th_student')}</th>
                  <th>{t('th_topic')}</th>
                  <th>{t('score')}</th>
                  <th>{t('date')}</th>
                </tr>
              </thead>
              <tbody>
                {queue.reviewed.map((r) => (
                  <tr key={r.submission_id}>
                    <td>{r.student}</td>
                    <td>{r.topic ?? '—'}</td>
                    <td>{r.final_score}/24</td>
                    <td className="muted small">
                      {r.reviewed_at.slice(0, 16).replace('T', ' ')}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
