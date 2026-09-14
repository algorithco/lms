import { useEffect, useState } from 'react';
import { useLang } from '../../i18n/LangContext';
import { TmaApi, tmaErrorMessage } from './api';
import type { TmaProfile, TmaResultItem, TmaTestSummary } from './api';

const DIFF_CLASS: Record<string, string> = {
  easy: 'tma-diff-easy',
  medium: 'tma-diff-medium',
  hard: 'tma-diff-hard',
};
const DIFF_LABEL: Record<string, string> = { easy: 'Oson', medium: "O'rta", hard: 'Qiyin' };

export default function Home({
  profile,
  onProfileLoaded,
  onOpenTest,
}: {
  profile: TmaProfile | null;
  onProfileLoaded: (p: TmaProfile) => void;
  onOpenTest: (testId: number) => void;
}) {
  const { t } = useLang();
  const [tests, setTests] = useState<TmaTestSummary[] | null>(null);
  const [results, setResults] = useState<TmaResultItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const [p, ts, rs] = await Promise.all([
          profile ? Promise.resolve(profile) : TmaApi.profile(),
          TmaApi.tests(),
          TmaApi.results(),
        ]);
        if (!alive) return;
        if (!profile) onProfileLoaded(p);
        setTests(ts.tests ?? []);
        setResults(rs.results ?? []);
      } catch (e) {
        if (alive) setError(tmaErrorMessage(e, t('tma_loading_error')));
      }
    })();
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (error) return <div className="tma-err">{error}</div>;
  if (!profile || !tests || !results) {
    return (
      <div className="tma-list">
        <div className="tma-skel" />
        <div className="tma-skel" />
      </div>
    );
  }

  return (
    <div className="tma-slide">
      <div className="tma-grid2">
        <div className="tma-stat">
          <p>{t('tma_tests')}</p>
          <b>{profile.stats.tests_taken ?? 0}</b>
        </div>
        <div className="tma-stat">
          <p>{t('tma_stats_essays')}</p>
          <b style={{ color: 'var(--tma-green)' }}>{profile.stats.essays_written ?? 0}</b>
        </div>
        <div className="tma-stat">
          <p>{t('tma_stats_passed')}</p>
          <b style={{ color: 'var(--tma-green)' }}>{profile.stats.tests_passed ?? 0}</b>
        </div>
        <div className="tma-stat">
          <p>{t('tma_stats_certs')}</p>
          <b style={{ color: 'var(--tma-gold)' }}>{profile.stats.certificates ?? 0}</b>
        </div>
      </div>

      <h3 className="tma-h3">{t('available_tests')}</h3>
      <div className="tma-list">
        {tests.length === 0 && <div className="tma-empty">{t('tma_no_tests')}</div>}
        {tests.slice(0, 10).map((item) => (
          <button key={item.id} onClick={() => onOpenTest(item.id)} className="tma-card tma-press">
            <div className="tma-row">
              <div className="tma-ico" style={{ background: 'rgba(59,130,246,0.2)' }}>📝</div>
              <div className="tma-grow">
                <p className="tma-title">{item.title}</p>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4 }}>
                  <span className={`tma-badge ${DIFF_CLASS[item.difficulty] ?? ''}`}>
                    {DIFF_LABEL[item.difficulty] ?? item.difficulty}
                  </span>
                  <span className="tma-sub">
                    {item.total_questions} savol · {item.time_limit_minutes} daqiqa
                  </span>
                </div>
              </div>
              <span style={{ color: '#6b7280', fontSize: 14 }}>→</span>
            </div>
          </button>
        ))}
      </div>

      <h3 className="tma-h3">{t('recent_results')}</h3>
      <div className="tma-list">
        {results.length === 0 && <div className="tma-empty">{t('tma_no_results')}</div>}
        {results.slice(0, 5).map((r, i) => (
          <div key={r.id ?? i} className="tma-card">
            <div className="tma-row">
              <div
                className="tma-ico"
                style={{ background: r.is_passed ? 'rgba(34,197,94,0.2)' : 'rgba(239,68,68,0.2)' }}
              >
                {r.is_passed ? '✅' : '❌'}
              </div>
              <div className="tma-grow">
                <p className="tma-title">{r.test_title}</p>
                <p className="tma-sub">
                  {r.correct_answers}/{r.total_questions} to‘g‘ri
                </p>
              </div>
              <span className={`tma-score ${r.is_passed ? 'tma-ok' : 'tma-bad'}`}>{r.percentage}%</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
