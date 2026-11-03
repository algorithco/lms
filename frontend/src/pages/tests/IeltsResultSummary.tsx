import { useLang } from '../../i18n/LangContext';

export interface IeltsSummary {
  correct: number;
  total: number;
  band: number | null;
}

/**
 * IELTS result: raw score and an estimated band. The band comes from a public
 * raw-score conversion, not from IELTS itself, so it is always labelled as an
 * estimate. No certificate number, QR code or "official" wording.
 */
export default function IeltsResultSummary({ data }: { data: IeltsSummary }) {
  const { t } = useLang();
  return (
    <div className="card cefr-result">
      <p className="cefr-result-note">{t('ielts_result_estimate_note')}</p>
      <p className="cefr-result-overall">
        <span className="muted">{t('ielts_result_raw')}</span>
        <strong>
          {data.correct} / {data.total}
        </strong>
      </p>
      {data.band != null && (
        <p className="cefr-result-overall">
          <span className="muted">{t('ielts_result_band')}</span>
          <strong>{data.band.toFixed(1)}</strong>
        </p>
      )}
    </div>
  );
}
