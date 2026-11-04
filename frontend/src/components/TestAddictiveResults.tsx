import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { useLang } from '../i18n/LangContext';
import { TestsApi } from '../lib/testing';
import { formatDisplayName } from '../lib/displayName';
import type { ReviewQuestion } from '../lib/review';
import ScoreCardModal from './ScoreCardModal';
import QuestionReview from './QuestionReview';
import QuestionIssueButton from './QuestionIssueButton';

export interface AddictiveResultProps {
  score: number;
  maxScore: number;
  percentage: number;
  correctCount: number;
  wrongCount: number;
  unansweredCount: number;
  timeSpentSeconds: number;
  raschScore?: number | string | null;
  raschGrade?: string | null;
  bmbGrade?: string | null;
  courseTitle?: string;
  subject?: string;
  attemptId?: string | number;
  resultId: number;
  testId?: number;
  questions?: ReviewQuestion[];
  /** Show the "estimate" banner (server flag SHOW_ESTIMATE_NOTICE, off by default). */
  showEstimateNotice?: boolean;
  onRetest?: () => void;
  children?: React.ReactNode;
}

export default function TestAddictiveResults({
  percentage,
  correctCount,
  wrongCount,
  unansweredCount,
  timeSpentSeconds,
  raschScore,
  raschGrade,
  bmbGrade,
  courseTitle,
  subject,
  attemptId,
  resultId,
  testId,
  questions = [],
  showEstimateNotice = false,
  onRetest,
  children,
}: AddictiveResultProps) {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { t } = useLang();
  const [retesting, setRetesting] = useState(false);
  const [retestMsg, setRetestMsg] = useState<string | null>(null);
  const [showScoreCard, setShowScoreCard] = useState(false);

  const pct = Math.round(percentage);
  const isBmb = subject !== 'english';
  const tone = pct >= 70 ? 'good' : pct >= 50 ? 'mid' : 'low';
  const grade = bmbGrade || raschGrade || '';

  const formatTime = (secs: number) => {
    if (!secs || secs <= 0) return `0 ${t('res_unit_sec')}`;
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return m === 0 ? `${s} ${t('res_unit_sec')}` : `${m} ${t('res_unit_min')} ${s} ${t('res_unit_sec')}`;
  };

  const handleRetestClick = async () => {
    if (onRetest) {
      onRetest();
      return;
    }
    if (!attemptId) {
      navigate('/tests');
      return;
    }
    setRetesting(true);
    setRetestMsg(null);
    try {
      const res = await TestsApi.generateRetest(String(attemptId));
      if (res.has_mistakes && res.attempt_id) {
        window.location.href = `/take/${res.attempt_id}`;
      } else {
        setRetestMsg(res.message || t('res_all_correct'));
      }
    } catch (e) {
      setRetestMsg(e instanceof Error ? e.message : t('res_retest_failed'));
    } finally {
      setRetesting(false);
    }
  };

  return (
    <div className="res">
      {showEstimateNotice && <p className="res-notice">{t('cefr_result_estimate_note')}</p>}

      <section className={`res-hero res-hero--${tone}`}>
        {courseTitle && <p className="res-hero__title">{courseTitle}</p>}
        <div className="res-hero__score" aria-label={`${pct}%`}>
          <strong>{pct}%</strong>
          <span>{t('res_score')}</span>
        </div>
        <div className="res-metrics">
          <div>
            <b>{correctCount}</b>
            <span>{t('rv_status_correct')}</span>
          </div>
          <div>
            <b>{wrongCount}</b>
            <span>{t('rv_status_wrong')}</span>
          </div>
          <div>
            <b>{unansweredCount}</b>
            <span>{t('rv_status_blank')}</span>
          </div>
          <div>
            <b>{formatTime(timeSpentSeconds)}</b>
            <span>{t('res_time')}</span>
          </div>
        </div>
        {isBmb && (grade || Number(raschScore) > 0) && (
          <div className="res-badges">
            {Number(raschScore) > 0 && (
              <span>
                {t('res_rasch')}: <b>{Number(raschScore).toFixed(1)}</b>
              </span>
            )}
            {grade && (
              <span>
                {t('res_grade')}: <b>{grade}</b>
              </span>
            )}
          </div>
        )}
      </section>

      <div className="res-actions">
        {wrongCount > 0 && (
          <button type="button" className="ui-btn ui-btn--primary" disabled={retesting} onClick={handleRetestClick}>
            {retesting ? t('res_retest_preparing') : t('res_retest').replace('{n}', String(wrongCount))}
          </button>
        )}
        <button type="button" className="ui-btn" onClick={() => setShowScoreCard(true)}>
          {t('res_share_story')}
        </button>
        <Link to="/tests" className="ui-btn">
          {t('res_new_test')}
        </Link>
      </div>
      {retestMsg && <p className="res-msg" role="status">{retestMsg}</p>}

      {children && <div className="res-extra">{children}</div>}

      <QuestionReview
        questions={questions}
        resultId={resultId}
        renderIssue={(q) => <QuestionIssueButton testId={testId} question={q} />}
      />

      <ScoreCardModal
        isOpen={showScoreCard}
        onClose={() => setShowScoreCard(false)}
        title={courseTitle || ''}
        studentName={user ? formatDisplayName(user.full_name, user.email) : ''}
        scorePercentage={pct}
        gradeBadge={grade}
        correctCount={correctCount}
        incorrectCount={wrongCount}
        totalQuestions={correctCount + wrongCount + unansweredCount}
        timeSpent={formatTime(timeSpentSeconds)}
      />
    </div>
  );
}
