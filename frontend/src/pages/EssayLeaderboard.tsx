import { useEffect, useState } from 'react';
import { useLang } from '../i18n/LangContext';
import { School } from '../lib/api';

/**
 * Essay leaderboard — mirrors GET /api/v1/school/essay-leaderboard/ (JWT):
 * top-20 writers by best GRADED score → {podium[3], rest, total_essays,
 * total_students}. Same queryset as the legacy essay-leaderboard view
 * (best_score, converted /75 score, essay_count, avg_score).
 */

interface Row {
  rank: number;
  name: string;
  best_score: number;
  converted_score: number;
  essay_count: number;
  avg_score: number;
}

export default function EssayLeaderboard() {
  const { t } = useLang();
  const [podium, setPodium] = useState<Row[]>([]);
  const [rest, setRest] = useState<Row[]>([]);
  const [totals, setTotals] = useState({ essays: 0, students: 0 });
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    School.essayLeaderboard()
      .then((r) => {
        setPodium(((r.podium as unknown as Row[]) || []));
        setRest(((r.rest as unknown as Row[]) || []));
        setTotals({
          essays: Number(r.total_essays ?? 0),
          students: Number(r.total_students ?? 0),
        });
      })
      .catch((e: unknown) => setErr(e instanceof Error ? e.message : 'Failed.'))
      .finally(() => setLoading(false));
  }, []);

  const medals = ['1', '2', '3'];
  const medalClass = ['podium-1', 'podium-2', 'podium-3'];

  if (loading) return <p className="muted">{t('loading')}</p>;

  return (
    <div>
      <h1>{t('lb_essay_title')}</h1>
      <p className="muted">
        {t('lb_total_essays')}: {totals.essays} · {t('lb_graded_students')}: {totals.students}
      </p>
      {err && <p className="error">{err}</p>}
      <div className="podium">
        {podium.map((r, i) => (
          <div key={r.rank} className={`card ${medalClass[i] ?? ''}`}>
            <span className="medal rank-badge">{medals[i] ?? `#${r.rank}`}</span>
            <h2>{r.name}</h2>
            <p className="stat-value">{r.converted_score}</p>
            <p className="muted small">
              {t('lb_best_score')}: {r.best_score} · {t('lb_essays_col')}: {r.essay_count}
            </p>
          </div>
        ))}
      </div>
      {podium.length === 0 && rest.length === 0 && !err && (
        <div className="card">
          <strong>{t('lb_empty_title')}</strong>
          <p className="muted small">{t('lb_empty_text')}</p>
        </div>
      )}
      {rest.length > 0 && (
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>{t('lb_rank')}</th>
                <th>{t('lb_student')}</th>
                <th>{t('lb_best_score')}</th>
                <th>{t('lb_score_75')}</th>
                <th>{t('lb_avg_col')}</th>
              </tr>
            </thead>
            <tbody>
              {rest.map((r) => (
                <tr key={r.rank}>
                  <td>{r.rank}</td>
                  <td>{r.name}</td>
                  <td>{r.best_score}</td>
                  <td>{r.converted_score}</td>
                  <td>{r.avg_score}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
