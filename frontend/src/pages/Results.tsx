import { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useLang } from '../i18n/LangContext';
import { Results as ResultsApi } from '../lib/api';
import {
  formatDuration,
  listResultsPage,
  num,
  type ResultListItem,
} from '../lib/testing';

interface QuestionDetail {
  question_id: number;
  question_text: string;
  question_type: string;
  points: number;
  correct_choices: { id: number; text: string }[];
  selected_choices: { id: number; text: string }[];
  is_correct: boolean | null;
  explanation?: string;
}

interface ResultDetailData extends ResultListItem {
  total_questions?: number;
  correct_answers?: number;
  wrong_answers?: number;
  unanswered?: number;
  question_details?: QuestionDetail[];
  certificate_info?: {
    certificate_number: string;
    status: string;
    issued_at?: string;
  } | null;
}

export default function Results() {
  const { t } = useLang();
  // Deep link parity with legacy /results/<id>/: /results/:id preselects it.
  const { id: idParam } = useParams();
  const [results, setResults] = useState<ResultListItem[]>([]);
  const [count, setCount] = useState(0);
  const [page, setPage] = useState(1);
  const [hasNext, setHasNext] = useState(false);
  const [hasPrev, setHasPrev] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [openId, setOpenId] = useState<number | null>(
    idParam && /^\d+$/.test(idParam) ? Number(idParam) : null,
  );
  const [detail, setDetail] = useState<ResultDetailData | null>(null);
  const [detailErr, setDetailErr] = useState<string | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const loadPage = useCallback(
    async (p: number) => {
      setLoading(true);
      setErr(null);
      try {
        const out = await listResultsPage(p);
        setResults((out.results ?? []) as ResultListItem[]);
        setCount(out.count ?? 0);
        setHasNext(Boolean(out.next));
        setHasPrev(Boolean(out.previous));
      } catch (e) {
        setErr(e instanceof Error ? e.message : t('err_retry_js'));
      } finally {
        setLoading(false);
      }
    },
    [t],
  );

  useEffect(() => {
    loadPage(page);
  }, [page, loadPage]);

  const toggleDetail = async (id: number) => {
    if (openId === id) {
      setOpenId(null);
      setDetail(null);
      return;
    }
    setOpenId(id);
    await loadDetail(id);
  };

  const loadDetail = async (id: number) => {
    setDetail(null);
    setDetailErr(null);
    setDetailLoading(true);
    try {
      const d = (await ResultsApi.detail(
        String(id),
      )) as unknown as ResultDetailData;
      setDetail(d);
    } catch (e) {
      setDetailErr(e instanceof Error ? e.message : t('err_retry_js'));
    } finally {
      setDetailLoading(false);
    }
  };

  // Deep-linked /results/:id — fetch its detail on mount.
  useEffect(() => {
    if (openId !== null) void loadDetail(openId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div>
      <h1>{t('my_results')}</h1>
      <p className="muted">
        <Link to="/certificates">{t('my_certificates')} →</Link>
        {' · '}
        <Link to="/verify/">{t('take_verify_link')} →</Link>
      </p>

      {loading && <p className="muted">{t('loading')}</p>}
      {err && (
        <p className="error">
          {err}{' '}
          <button className="btn sm ghost" onClick={() => loadPage(page)}>
            {t('essay_error_retry')}
          </button>
        </p>
      )}

      {!loading && !err && results.length === 0 && (
        <div className="card">
          <h3>{t('no_results_title')}</h3>
          <p className="muted">{t('no_results_hint')}</p>
          <Link className="btn primary" to="/tests">
            {t('view_tests')}
          </Link>
        </div>
      )}

      <div style={{ display: 'grid', gap: 12 }}>
        {results.map((r) => {
          const pct = num(r.percentage, 0);
          const open = openId === r.id;
          return (
            <div key={r.id} className="card">
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  gap: 12,
                  alignItems: 'center',
                  flexWrap: 'wrap',
                }}
              >
                <div>
                  <strong>{String(r.test_title ?? `Test #${r.test ?? r.id}`)}</strong>
                  <p className="muted small">
                    {String(r.course_title ?? '')}
                    {r.calculated_at
                      ? ` · ${new Date(String(r.calculated_at)).toLocaleString()}`
                      : ''}
                  </p>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <p
                    className="stat-value small"
                    style={{ color: r.is_passed ? undefined : 'var(--danger)' }}
                  >
                    {pct}%
                  </p>
                  <span className={`badge ${r.is_passed ? 'green' : 'rose'}`}>
                    {r.is_passed ? t('status_passed') : t('status_failed')}
                  </span>
                </div>
              </div>
              <div className="progress" style={{ margin: '8px 0' }}>
                <div style={{ width: `${Math.min(100, Math.max(0, pct))}%` }} />
              </div>
              <div className="toolbar">
                <span className="muted small">
                  {t('score')}: {String(r.score ?? '—')}/{String(r.max_score ?? '—')}
                  {' · '}
                  {t('rd_time_spent')}: {formatDuration(r.time_taken_seconds)}
                </span>
                <button className="btn sm ghost" onClick={() => toggleDetail(r.id)}>
                  {open ? t('take_hide_detail') : t('details')}
                </button>
              </div>

              {open && (
                <div style={{ marginTop: 12 }}>
                  {detailLoading && <p className="muted">{t('loading')}</p>}
                  {detailErr && <p className="error">{detailErr}</p>}
                  {detail && detail.id === r.id && (
                    <ResultDetailBody detail={detail} />
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {(hasNext || hasPrev) && (
        <div className="toolbar" style={{ marginTop: 16 }}>
          <button
            className="btn sm"
            disabled={!hasPrev}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
          >
            ← {t('back')}
          </button>
          <span className="muted small">
            {page} · {t('total_tests')}: {count}
          </span>
          <button
            className="btn sm"
            disabled={!hasNext}
            onClick={() => setPage((p) => p + 1)}
          >
            {t('next')} →
          </button>
        </div>
      )}
    </div>
  );
}

function ResultDetailBody({ detail }: { detail: ResultDetailData }) {
  const { t } = useLang();
  const pct = num(detail.percentage, 0);
  return (
    <div>
      <h3>
        {detail.is_passed ? t('rd_passed_msg') : t('rd_failed_msg')} — {pct}%
      </h3>
      <div className="toolbar">
        <span className="badge green">
          {t('rd_correct')}: {Number(detail.correct_answers ?? 0)}
        </span>
        <span className="badge rose">
          {t('rd_wrong')}: {Number(detail.wrong_answers ?? 0)}
        </span>
        <span className="badge">
          {t('rd_unanswered')}: {Number(detail.unanswered ?? 0)}
        </span>
        <span className="badge blue">
          {t('score')}: {String(detail.score ?? '—')}/{String(detail.max_score ?? '—')}
        </span>
      </div>
      <p className="muted small">
        {t('rd_time_spent')}: {formatDuration(detail.time_taken_seconds)}
      </p>
      {detail.certificate_info && (
        <p className="muted small">
          {t('mc_number')} {detail.certificate_info.certificate_number} (
          {detail.certificate_info.status}){' '}
          <Link to="/certificates">{t('my_certificates')} →</Link>
        </p>
      )}
      <h4>{t('rd_analysis')}</h4>
      <div style={{ display: 'grid', gap: 8 }}>
        {(detail.question_details ?? []).map((qd) => {
          const selectedIds = new Set((qd.selected_choices ?? []).map((c) => c.id));
          const correctIds = new Set((qd.correct_choices ?? []).map((c) => c.id));
          return (
            <div key={qd.question_id} className="card">
              <p>
                <span
                  className={`badge ${qd.is_correct ? 'green' : qd.is_correct === false ? 'rose' : ''}`}
                >
                  {qd.is_correct ? '✓' : qd.is_correct === false ? '✗' : '—'}
                </span>{' '}
                <strong>{qd.question_text}</strong>
              </p>
              <div style={{ display: 'grid', gap: 6, marginTop: 8 }}>
                {(qd.correct_choices ?? []).map((c) => (
                  <span key={`c-${c.id}`} className="quiz-opt right">
                    ✓ {c.text}
                    {selectedIds.has(c.id) ? ` · ${t('rd_your_choice')}` : ''}
                  </span>
                ))}
                {(qd.selected_choices ?? [])
                  .filter((c) => !correctIds.has(c.id))
                  .map((c) => (
                    <span key={`s-${c.id}`} className="quiz-opt wrong">
                      ✗ {c.text} · {t('rd_your_choice')}
                    </span>
                  ))}
                {(qd.selected_choices ?? []).length === 0 && (
                  <span className="muted small">{t('rd_unanswered')}</span>
                )}
              </div>
              {qd.explanation && qd.is_correct === false && (
                <p className="muted small">
                  {t('rd_explanation')} {qd.explanation}
                </p>
              )}
            </div>
          );
        })}
        {(detail.question_details ?? []).length === 0 && (
          <p className="muted">{t('take_no_analysis')}</p>
        )}
      </div>
    </div>
  );
}
