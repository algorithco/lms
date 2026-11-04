import { useLang } from '../i18n/LangContext';

/** Shown by the route guards while the saved session is being restored. */
export default function SessionLoading() {
  const { t } = useLang();
  return (
    <div className="exam-state exam-state--padded" role="status">
      <div className="exam-state__spinner" aria-hidden="true" />
      <p>{t('session_loading')}</p>
    </div>
  );
}
