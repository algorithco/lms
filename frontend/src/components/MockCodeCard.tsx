import { useState } from 'react';
import { KeyRound } from 'lucide-react';
import { useTranslation } from '../i18n/useTranslation';

interface Props {
  subject: 'english' | 'uzbek';
  busy: boolean;
  error: string | null;
  onJoin: (code: string) => void;
  onEdit: () => void;
}

/** "Join with a teacher's test code" — one card for every subject, text from i18n. */
export default function MockCodeCard({ subject, busy, error, onJoin, onEdit }: Props) {
  const { t } = useTranslation();
  const [code, setCode] = useState('');

  return (
    <section className="code-card" aria-label={t('mockcode_title')}>
      <div className="code-card__head">
        <KeyRound size={20} aria-hidden="true" />
        <div>
          <h3 className="code-card__title">
            {t(subject === 'english' ? 'mockcode_title_english' : 'mockcode_title')}
          </h3>
          <p className="code-card__desc">{t('mockcode_desc')}</p>
        </div>
      </div>
      <form
        className="code-card__form"
        onSubmit={(e) => {
          e.preventDefault();
          onJoin(code);
        }}
      >
        <input
          type="text"
          className="ui-input ui-input--mono code-card__input"
          value={code}
          onChange={(e) => {
            setCode(e.target.value);
            onEdit();
          }}
          placeholder={t('mockcode_placeholder')}
          aria-label={t('mockcode_label')}
          autoCapitalize="characters"
          autoCorrect="off"
          spellCheck={false}
          required
        />
        <button type="submit" className="ui-btn ui-btn--primary" disabled={busy}>
          {busy ? t('mockcode_connecting') : t('mockcode_start')}
        </button>
      </form>
      {error && (
        <p className="code-card__error" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}
