import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertCircle, Camera, CheckCircle2, RefreshCw, ScanLine } from 'lucide-react';
import { useLang } from '../i18n/LangContext';
import {
  OmrApi,
  type ApiError,
  type OmrAvailableTest,
  type OmrMarkStatus,
  type OmrReviewItem,
  type OmrScanReview,
} from '../lib/api';

const ACCEPT = 'image/jpeg,image/png,image/webp';
const STATUS_BADGE: Record<OmrMarkStatus, string> = {
  clear: 'green',
  blank: 'blue',
  multiple: 'amber',
  unread: 'rose',
};

/**
 * Paper answer sheet check in three steps: photo → the student reviews and
 * corrects what was read → the confirmed answers are graded exactly like an
 * online attempt and the regular result page opens. Unread or ambiguous
 * marks are never filled in automatically.
 */
export default function ScanOMR() {
  const { t } = useLang();
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [tests, setTests] = useState<OmrAvailableTest[]>([]);
  const [testId, setTestId] = useState<number | null>(null);
  const [query, setQuery] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [busy, setBusy] = useState<'scan' | 'confirm' | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [review, setReview] = useState<OmrScanReview | null>(null);
  const [values, setValues] = useState<Record<number, string>>({});
  const [resolved, setResolved] = useState<Set<number>>(new Set());

  useEffect(() => {
    OmrApi.getAvailableTests()
      .then((data) => {
        setTests(data.tests || []);
        if (data.tests?.length) setTestId(data.tests[0].id);
      })
      .catch(() => setTests([]));
  }, []);

  useEffect(() => () => {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
  }, [previewUrl]);

  const filteredTests = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return tests;
    return tests.filter(
      (x) => x.title.toLowerCase().includes(q) || (x.mock_code || '').toLowerCase().includes(q),
    );
  }, [tests, query]);

  const errorText = (err: unknown) => {
    const e = err as ApiError;
    if (e?.code) return t(`omr_err_${e.code}`, e.message);
    return e instanceof Error ? e.message : t('omr_err_scan_failed');
  };

  const pickFile = (selected: File | undefined) => {
    if (!selected) return;
    setFile(selected);
    setPreviewUrl(URL.createObjectURL(selected));
    setError(null);
    setReview(null);
  };

  const handleScan = async () => {
    if (!file || !testId) return;
    setBusy('scan');
    setError(null);
    setReview(null);
    const fd = new FormData();
    fd.append('image', file);
    fd.append('test_id', String(testId));
    try {
      const res = await OmrApi.scan(fd);
      setReview(res);
      setValues(Object.fromEntries(res.items.map((i) => [i.question_id, i.value])));
      setResolved(new Set());
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(null);
    }
  };

  const needsDecision = (item: OmrReviewItem) =>
    (item.status === 'unread' || item.status === 'multiple') && !resolved.has(item.question_id);

  const setAnswer = (item: OmrReviewItem, value: string) => {
    setValues((prev) => ({ ...prev, [item.question_id]: value }));
    setResolved((prev) => new Set(prev).add(item.question_id));
  };

  const pending = review ? review.items.filter(needsDecision).length : 0;

  const handleConfirm = async () => {
    if (!review || pending) return;
    setBusy('confirm');
    setError(null);
    try {
      const res = await OmrApi.confirm(review.test_id, values);
      navigate(res.result_id ? `/results/${res.result_id}` : '/results');
    } catch (err) {
      setError(errorText(err));
      setBusy(null);
    }
  };

  const reset = () => {
    setReview(null);
    setFile(null);
    setPreviewUrl(null);
    setError(null);
  };

  const groups = useMemo(() => {
    const out: { code: string; items: OmrReviewItem[] }[] = [];
    for (const item of review?.items ?? []) {
      const last = out[out.length - 1];
      if (last && last.code === item.section_code) last.items.push(item);
      else out.push({ code: item.section_code, items: [item] });
    }
    return out;
  }, [review]);

  return (
    <div className="omr-page">
      <header className="omr-head">
        <h1>{t('omr_title')}</h1>
        <p className="muted">{t('omr_subtitle')}</p>
      </header>

      {!review && (
        <div className="omr-grid">
          <section className="card omr-card">
            <h2>{t('omr_step_test')}</h2>
            {tests.length > 5 && (
              <input
                className="omr-input"
                type="search"
                placeholder={t('omr_search_test')}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            )}
            {tests.length === 0 ? (
              <p className="muted small">{t('omr_no_tests')}</p>
            ) : (
              <select
                className="omr-input"
                value={testId ?? ''}
                onChange={(e) => setTestId(Number(e.target.value))}
              >
                {filteredTests.map((x) => (
                  <option key={x.id} value={x.id}>
                    {x.title} · {t('omr_questions_count').replace('{n}', String(x.total_questions))}
                  </option>
                ))}
              </select>
            )}

            <h2>{t('omr_step_photo')}</h2>
            <button
              type="button"
              className="omr-drop"
              onClick={() => fileInputRef.current?.click()}
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault();
                pickFile(e.dataTransfer.files?.[0]);
              }}
            >
              {previewUrl ? (
                <>
                  <img src={previewUrl} alt={t('omr_photo_alt')} />
                  <span className="muted small">{t('omr_photo_change')}</span>
                </>
              ) : (
                <>
                  <Camera size={28} aria-hidden />
                  <strong>{t('omr_photo_pick')}</strong>
                  <span className="muted small">{t('omr_photo_formats')}</span>
                </>
              )}
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept={ACCEPT}
              capture="environment"
              hidden
              onChange={(e) => pickFile(e.target.files?.[0])}
            />

            {error && (
              <div className="omr-error" role="alert">
                <AlertCircle size={16} aria-hidden />
                <span>{error}</span>
              </div>
            )}

            <button
              type="button"
              className="btn primary omr-wide"
              disabled={!file || !testId || busy !== null}
              onClick={handleScan}
            >
              {busy === 'scan' ? <RefreshCw size={16} className="animate-spin" /> : <ScanLine size={16} />}
              {busy === 'scan' ? t('omr_scanning') : t('omr_scan')}
            </button>
          </section>

          <section className="card omr-card">
            <h2>{t('omr_tips_title')}</h2>
            <ol className="omr-tips">
              <li>{t('omr_tip_light')}</li>
              <li>{t('omr_tip_whole')}</li>
              <li>{t('omr_tip_marks')}</li>
              <li>{t('omr_tip_review')}</li>
            </ol>
          </section>
        </div>
      )}

      {review && (
        <section className="card omr-card">
          <div className="omr-review-head">
            <div>
              <h2>{t('omr_review_title')}</h2>
              <p className="muted small">{review.test_title}</p>
            </div>
            <div className="omr-counts">
              {(['clear', 'blank', 'multiple', 'unread'] as OmrMarkStatus[]).map((s) => (
                <span key={s} className={`badge ${STATUS_BADGE[s]}`}>
                  {t(`omr_status_${s}`)}: {review.counts[s]}
                </span>
              ))}
            </div>
          </div>
          <p className="omr-note">{t('omr_review_hint')}</p>

          {groups.map((g) => (
            <div key={g.code || 'all'} className="omr-section">
              {g.code && <h3>{t(`omr_section_${g.code}`, g.code)}</h3>}
              <div className="omr-rows">
                {g.items.map((item) => {
                  const value = values[item.question_id] ?? '';
                  const flagged = needsDecision(item);
                  return (
                    <div key={item.question_id} className={`omr-row${flagged ? ' flagged' : ''}`}>
                      <span className="omr-num">{item.number}</span>
                      {item.kind === 'choice' ? (
                        <div className="omr-options" role="group" aria-label={t('omr_question_n').replace('{n}', item.key)}>
                          {item.options.map((opt) => (
                            <button
                              key={opt}
                              type="button"
                              className={`omr-opt${value === opt ? ' on' : ''}`}
                              aria-pressed={value === opt}
                              onClick={() => setAnswer(item, opt)}
                            >
                              {opt}
                            </button>
                          ))}
                          <button
                            type="button"
                            className={`omr-opt${value === '' && !flagged ? ' on' : ''}`}
                            aria-pressed={value === '' && !flagged}
                            title={t('omr_mark_blank')}
                            onClick={() => setAnswer(item, '')}
                          >
                            —
                          </button>
                        </div>
                      ) : (
                        <input
                          className="omr-input omr-text"
                          value={value}
                          placeholder={t('omr_text_placeholder')}
                          aria-label={t('omr_question_n').replace('{n}', item.key)}
                          onChange={(e) => setAnswer(item, e.target.value)}
                        />
                      )}
                      {item.status !== 'clear' && (
                        <span className={`badge ${STATUS_BADGE[item.status]}`}>{t(`omr_status_${item.status}`)}</span>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          ))}

          {error && (
            <div className="omr-error" role="alert">
              <AlertCircle size={16} aria-hidden />
              <span>{error}</span>
            </div>
          )}

          <p className="muted small">{t('omr_no_xp_note')}</p>
          <div className="omr-actions">
            <button type="button" className="btn ghost" onClick={reset} disabled={busy !== null}>
              <RefreshCw size={15} /> {t('omr_rescan')}
            </button>
            <button
              type="button"
              className="btn primary"
              disabled={pending > 0 || busy !== null}
              onClick={handleConfirm}
            >
              <CheckCircle2 size={16} />
              {pending > 0
                ? t('omr_pending_left').replace('{n}', String(pending))
                : busy === 'confirm'
                  ? t('omr_confirming')
                  : t('omr_confirm')}
            </button>
          </div>
        </section>
      )}
    </div>
  );
}
