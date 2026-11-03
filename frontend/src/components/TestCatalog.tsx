import { useLang } from '../i18n/LangContext';

export type CatalogKey = 'ona_tili' | 'adabiyot' | 'english' | 'attestatsiya';

const ITEMS: { key: CatalogKey; icon: string; tone: string }[] = [
  { key: 'ona_tili', icon: '📖', tone: 'amber' },
  { key: 'adabiyot', icon: '📚', tone: 'green' },
  { key: 'english', icon: '🎓', tone: 'blue' },
  { key: 'attestatsiya', icon: '🧑‍🏫', tone: 'violet' },
];

interface Props {
  selected: 'all' | CatalogKey;
  onSelect: (key: CatalogKey) => void;
  onClear: () => void;
}

/** Subject / exam picker for the test list. Names only: no counts or promises that the database cannot back. */
export default function TestCatalog({ selected, onSelect, onClear }: Props) {
  const { t } = useLang();
  return (
    <section className="catalog" aria-label={t('catalog_title')}>
      <div className="catalog__head">
        <h2>{t('catalog_title')}</h2>
        {selected !== 'all' && (
          <button type="button" className="catalog__clear" onClick={onClear}>
            {t('catalog_show_all')}
          </button>
        )}
      </div>
      <div className="catalog__grid">
        {ITEMS.map((item) => (
          <button
            key={item.key}
            type="button"
            className={`catalog__card catalog__card--${item.tone}${selected === item.key ? ' is-selected' : ''}`}
            aria-pressed={selected === item.key}
            onClick={() => onSelect(item.key)}
          >
            <span className="catalog__icon" aria-hidden="true">{item.icon}</span>
            <span className="catalog__name">{t(`catalog_${item.key}`)}</span>
            <span className="catalog__sub">{t(`catalog_${item.key}_sub`)}</span>
            {selected === item.key && <span className="catalog__tick">{t('catalog_selected')}</span>}
          </button>
        ))}
      </div>
    </section>
  );
}
