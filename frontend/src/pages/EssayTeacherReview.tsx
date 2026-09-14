import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { Link, Navigate, useParams } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { useLang } from '../i18n/LangContext';
import { TeacherEssays, canReviewEssays } from '../lib/api';
import type { TeacherEssayDetail } from '../lib/api';

const SCORE_STEPS = [0, 0.5, 1, 1.5, 2];

/** Single-essay teacher review (parity with legacy /essays/teacher/<id>/review/). */
export default function EssayTeacherReview() {
  const { t } = useLang();
  const { user, loading } = useAuth();
  const { id = '' } = useParams();
  const [data, setData] = useState<TeacherEssayDetail | null>(null);
  const [scores, setScores] = useState<Record<number, number>>({});
  const [comments, setComments] = useState('');
  const [err, setErr] = useState<string | null>(null);
  const [saved, setSaved] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    TeacherEssays.detail(id)
      .then((d) => {
        setData(d);
        const preset: Record<number, number> = {};
        if (d.existing_review) {
          for (const [k, v] of Object.entries(d.existing_review.criteria_scores)) {
            preset[Number(k)] = Number(v);
          }
          setComments(d.existing_review.teacher_comments);
        } else {
          for (const c of d.ai_criteria) preset[c.criterion_id] = c.score;
        }
        setScores(preset);
      })
      .catch((e) => setErr(e instanceof Error ? e.message : t('err_retry_js')));
  }, [id, t]);

  const total = Object.values(scores).reduce((a, b) => a + (Number(b) || 0), 0);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      const r = await TeacherEssays.submitReview(id, {
        criteria_scores: scores,
        teacher_comments: comments,
      });
      setSaved(r.final_score);
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : 'Failed.');
    } finally {
      setBusy(false);
    }
  };

  if (err && !data) return <p className="error">{err}</p>;
  if (!loading && user && !canReviewEssays(user)) {
    return <Navigate to="/dashboard" replace />;
  }
  if (!data) return <p className="muted">{t('loading')}</p>;

  const { submission } = data;

  return (
    <div>
      <p className="muted small">
        <Link to="/teacher/essays">← {t('tr_back_queue')}</Link>
      </p>
      <h1>
        {submission.student} · {submission.topic ?? '—'}
      </h1>
      <p className="muted small">
        {t('score')}: {submission.total_score}/{submission.max_score} ·{' '}
        {submission.word_count} {t('essay_words')}
      </p>

      <div className="card">
        <strong>{t('tr_essay_text')}</strong>
        <p style={{ whiteSpace: 'pre-wrap' }}>{submission.essay_text}</p>
      </div>

      {saved !== null && (
        <p className="ok">
          {t('tr_review_saved')}: {saved}/24
        </p>
      )}

      <form onSubmit={onSubmit}>
        <h2>
          {t('tr_your_score')} — {total}/24
        </h2>
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>#</th>
                <th>{t('th_criterion')}</th>
                <th>{t('tr_ai_score')}</th>
                <th>{t('tr_your_score')}</th>
              </tr>
            </thead>
            <tbody>
              {Array.from({ length: 12 }, (_, i) => i + 1).map((cid) => {
                const ai = data.ai_criteria.find((c) => c.criterion_id === cid);
                return (
                  <tr key={cid}>
                    <td>{cid}</td>
                    <td>{data.criterion_names[String(cid)] ?? ai?.name ?? '—'}</td>
                    <td>{ai ? `${ai.score}/2` : '—'}</td>
                    <td>
                      <select
                        value={scores[cid] ?? 0}
                        onChange={(e) =>
                          setScores((s) => ({ ...s, [cid]: Number(e.target.value) }))
                        }
                      >
                        {SCORE_STEPS.map((v) => (
                          <option key={v} value={v}>
                            {v}
                          </option>
                        ))}
                      </select>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <div className="form" style={{ marginTop: 16 }}>
          <label htmlFor="tr-comments">{t('tr_comments')}</label>
          <textarea
            id="tr-comments"
            rows={4}
            value={comments}
            onChange={(e) => setComments(e.target.value)}
          />
        </div>
        {err && <p className="error">{err}</p>}
        <button className="btn primary" disabled={busy} style={{ marginTop: 12 }}>
          {busy ? '…' : t('tr_save_review')}
        </button>
      </form>
    </div>
  );
}
