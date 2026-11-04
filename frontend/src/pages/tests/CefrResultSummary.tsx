import { useLang } from '../../i18n/LangContext';

/** One section of the certificate-card payload for a CEFR Multi-level test. */
export interface CefrSection {
  code: string;
  name: string;
  status: 'scored' | 'pending' | 'missing';
  score: number | null;
  level: string | null;
  earned?: number;
  maximum?: number;
}

export interface CefrSummary {
  scale: 'cefr_multilevel';
  scale_max: number;
  sections: CefrSection[];
  overall: { score: number; level: string } | null;
  missing_sections: string[];
  has_certificate: boolean;
}

const OBJECTIVE = new Set(['LISTENING', 'READING']);

/**
 * CEFR Multi-level result: per-section 0–75 score and level,
 * overall level only when all four sections are scored. Never shows an
 * IELTS band — IELTS is a separate exam type with its own tables.
 */
export default function CefrResultSummary({ data, showEstimateNotice = false }: { data: CefrSummary; showEstimateNotice?: boolean }) {
  const { t } = useLang();
  const levelLabel = (level: string | null) => (level ? t(`cefr_level_${level}`, level) : '—');
  const missingNames = data.sections
    .filter((s) => data.missing_sections.includes(s.code))
    .map((s) => s.name)
    .join(', ');

  return (
    <div className="card cefr-result">
      {showEstimateNotice && <p className="cefr-result-note">{t('cefr_result_estimate_note')}</p>}

      <div className="table-wrap">
        <table className="data">
          <thead>
            <tr>
              <th>{t('cefr_result_section')}</th>
              <th>{t('cefr_result_score', 'Ball').replace('{max}', String(data.scale_max))}</th>
              <th>{t('cefr_result_level')}</th>
            </tr>
          </thead>
          <tbody>
            {data.sections.map((s) => (
              <tr key={s.code}>
                <td>
                  {s.name}
                  {OBJECTIVE.has(s.code) && s.status === 'scored' && s.maximum != null && (
                    <span className="muted small"> · {s.earned}/{s.maximum}</span>
                  )}
                </td>
                <td>{s.status === 'scored' && s.score != null ? s.score : '—'}</td>
                <td>
                  {s.status === 'scored'
                    ? levelLabel(s.level)
                    : t(s.status === 'pending' ? 'cefr_result_pending' : 'cefr_result_missing')}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {data.overall ? (
        <div className="cefr-result-overall">
          <span className="muted">{t('cefr_result_overall')}</span>
          <strong>
            {data.overall.score} / {data.scale_max} · {levelLabel(data.overall.level)}
          </strong>
          {!data.has_certificate && <p className="muted small">{t('cefr_result_no_certificate')}</p>}
        </div>
      ) : (
        <p className="cefr-result-overall muted">
          {t('cefr_result_incomplete').replace('{sections}', missingNames)}
        </p>
      )}
    </div>
  );
}
