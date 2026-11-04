import { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { Tests as TestsApi } from '../../lib/api';
import { useLang } from '../../i18n/LangContext';
import CdExamInterface, { type CdAttempt } from './CdExamInterface';
import { withSyntheticStructure } from './cdAdapter';

/**
 * Entry point of /english-exam/:attemptId. Every English exam (CEFR, IELTS)
 * runs on the CD engine: this component only loads the attempt and shows
 * loading / error / empty states around it.
 */
export default function EnglishExamInterface() {
  const { attemptId = '' } = useParams<{ attemptId: string }>();
  const { t } = useLang();
  const [attempt, setAttempt] = useState<CdAttempt | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const data = (await TestsApi.attempt(attemptId)) as unknown as CdAttempt;
      setAttempt(data);
    } catch (e) {
      setErr(e instanceof Error ? e.message : t('error_retry'));
    } finally {
      setLoading(false);
    }
  }, [attemptId, t]);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) {
    return (
      <div className="exam-state" role="status">
        <div className="exam-state__spinner" aria-hidden="true" />
        <p>{t('exam_loading')}</p>
      </div>
    );
  }

  if (err || !attempt) {
    return (
      <div className="error-boundary" role="alert">
        <div className="card error-boundary-card">
          <div className="error-boundary-icon" aria-hidden="true">⚠️</div>
          <h2>{t('error_boundary_exam_title')}</h2>
          <p className="muted">{err}</p>
          <div className="error-boundary-actions">
            <button type="button" className="btn primary" onClick={() => void load()}>
              {t('error_retry')}
            </button>
            <Link to="/tests" className="btn">{t('error_boundary_back')}</Link>
          </div>
        </div>
      </div>
    );
  }

  if (!attempt.questions?.length) {
    return (
      <div className="error-boundary" role="alert">
        <div className="card error-boundary-card">
          <h2>{t('exam_no_questions')}</h2>
          <div className="error-boundary-actions">
            <Link to="/tests" className="btn primary">{t('error_boundary_back')}</Link>
          </div>
        </div>
      </div>
    );
  }

  return <CdExamInterface attempt={withSyntheticStructure(attempt)} />;
}
