import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { Link, Navigate, useParams } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { useLang } from '../i18n/LangContext';
import { TeacherEssays, canReviewEssays, isPlatformAdmin } from '../lib/api';
import { PencilIcon } from '../components/icons';
import type { TeacherEssayDetail } from '../lib/api';

const isScoreMissing = (val: any) => val === undefined || val === null || val === '';

const CRITERION_MAX: Record<number, number> = {
  1: 2, 2: 2, 3: 2, 4: 1.5, 5: 1.5, 6: 1.5,
  7: 2, 8: 1.5, 9: 1.5, 10: 1.5, 11: 1.5, 12: 1.5,
};

const getScoreSteps = (cid: number) => {
  const max = CRITERION_MAX[cid] ?? 2;
  return max === 1.5 ? [0, 0.5, 1, 1.5] : [0, 0.5, 1, 1.5, 2];
};

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
  // Platform-admin whole-essay edit.
  const [editingText, setEditingText] = useState(false);
  const [draftText, setDraftText] = useState('');
  const [textBusy, setTextBusy] = useState(false);
  const [textSaved, setTextSaved] = useState(false);

  useEffect(() => {
    TeacherEssays.detail(id)
      .then((d) => {
        setData(d);
        const preset: Record<number, number> = {};
        for (let i = 1; i <= 12; i++) {
          preset[i] = 0;
        }
        if (d.existing_review?.criteria_scores) {
          for (const [k, v] of Object.entries(d.existing_review.criteria_scores)) {
            if (!isScoreMissing(v)) {
              preset[Number(k)] = Number(v);
            }
          }
          setComments(d.existing_review.teacher_comments || '');
        } else if (d.ai_criteria && d.ai_criteria.length > 0) {
          for (const c of d.ai_criteria) {
            if (!isScoreMissing(c.score)) {
              preset[c.criterion_id] = Number(c.score);
            }
          }
        }
        setScores(preset);
      })
      .catch((e) => setErr(e instanceof Error ? e.message : t('err_retry_js')));
  }, [id, t]);

  const total = Array.from({ length: 12 }, (_, i) => i + 1).reduce((a, cid) => {
    const val = scores[cid];
    return a + (isScoreMissing(val) ? 0 : Number(val));
  }, 0);

  const isAdmin = isPlatformAdmin(user);

  const startTextEdit = () => {
    if (!data) return;
    setDraftText(data.submission.essay_text);
    setTextSaved(false);
    setEditingText(true);
  };

  const saveText = async () => {
    if (!data || !draftText.trim()) return;
    setTextBusy(true);
    setErr(null);
    try {
      const updated = await TeacherEssays.updateText(id, draftText);
      setData((d) =>
        d ? { ...d, submission: { ...d.submission, ...updated } } : d,
      );
      setEditingText(false);
      setTextSaved(true);
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : 'Failed.');
    } finally {
      setTextBusy(false);
    }
  };

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr(null);

    // Strict validation: every criterion 1..12 must be present (0 is completely valid)
    const sanitizedScores: Record<number, number> = {};
    for (let cid = 1; cid <= 12; cid++) {
      const val = scores[cid];
      if (isScoreMissing(val)) {
        setErr(`Mezon #${cid}: ball kiritilmadi.`);
        setBusy(false);
        return;
      }
      const num = Number(val);
      if (isNaN(num) || num < 0) {
        setErr(`Mezon #${cid}: ball noto'g'ri kiritildi.`);
        setBusy(false);
        return;
      }
      sanitizedScores[cid] = num;
    }

    try {
      const r = await TeacherEssays.submitReview(id, {
        criteria_scores: sanitizedScores,
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
        {!editingText ? (
          <>
            <p style={{ whiteSpace: 'pre-wrap' }}>{submission.essay_text}</p>
            {isAdmin && (
              <button className="btn sm ghost" onClick={startTextEdit}>
                <PencilIcon size={13} className="ico" /> {t('tr_edit_text')}
              </button>
            )}
          </>
        ) : (
          <>
            <textarea
              rows={12}
              style={{ width: '100%', marginTop: 8 }}
              value={draftText}
              onChange={(e) => setDraftText(e.target.value)}
            />
            <p className="muted small">{t('tr_edit_text_hint')}</p>
            <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
              <button className="btn primary sm" disabled={textBusy || !draftText.trim()} onClick={() => void saveText()}>
                {textBusy ? '…' : t('save_changes')}
              </button>
              <button className="btn sm" onClick={() => setEditingText(false)}>
                {t('cancel')}
              </button>
            </div>
          </>
        )}
        {textSaved && <p className="ok">{t('tr_text_saved')}</p>}
      </div>

      {saved !== null && (
        <p className="ok">
          {t('tr_review_saved')}: {saved}/20
        </p>
      )}

      <form onSubmit={onSubmit}>
        <h2>
          {t('tr_your_score')} — {total.toFixed(1)}/20
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
                const max = CRITERION_MAX[cid] ?? 2;
                const steps = getScoreSteps(cid);
                const currentVal = isScoreMissing(scores[cid]) ? 0 : scores[cid];
                return (
                  <tr key={cid}>
                    <td>{cid}</td>
                    <td>{data.criterion_names[String(cid)] ?? ai?.name ?? '—'}</td>
                    <td>{ai ? `${ai.score}/${max}` : `—/${max}`}</td>
                    <td>
                      <select
                        value={currentVal}
                        onChange={(e) => {
                          const val = Number(e.target.value);
                          setScores((s) => ({ ...s, [cid]: val }));
                        }}
                      >
                        {steps.map((v) => (
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
