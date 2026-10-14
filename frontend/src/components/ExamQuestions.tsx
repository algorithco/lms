import { useLang } from '../i18n/LangContext';
import { ClockIcon } from './icons';

export interface GapDef {
  position: number;
}

export interface MatchingPromptDef {
  id: number;
  text: string;
  position: number;
}

export interface MatchingOptionDef {
  id: number;
  text: string;
}

export interface PassageDef {
  id: number;
  title: string;
  content: string;
  source?: string;
  order: number;
}

export interface SectionDef {
  id: number;
  name: string;
  code: string;
  order: number;
  duration_minutes: number;
  weight: string;
}

export interface SectionProgressDef {
  section_id: number;
  remaining_seconds: number | null;
  is_expired: boolean;
  completed: boolean;
}

export function AutosaveStatus({ saved, error }: { saved: boolean; error?: string }) {
  const { t } = useLang();
  if (error) return <span className="error small">{error}</span>;
  return (
    <span className="muted small">{saved ? `✓ ${t('essay_js_saved')}` : t('save')}</span>
  );
}

export function PassageCard({ passage }: { passage: PassageDef }) {
  const { t } = useLang();
  return (
    <div className="card passage-card" style={{ marginBottom: 12 }}>
      <p className="muted small">
        {t('exam_passage')}
        {passage.title ? ` · ${passage.title}` : ''}
      </p>
      <p style={{ whiteSpace: 'pre-line' }}>{passage.content}</p>
      {passage.source && <p className="muted small">{passage.source}</p>}
    </div>
  );
}

export function SectionNav({
  sections,
  progress,
  counts,
  onSelectSection,
  activeSectionId,
}: {
  sections: SectionDef[];
  progress: SectionProgressDef[];
  counts: Record<number, { answered: number; total: number }>;
  onSelectSection?: (sectionId: number) => void;
  activeSectionId?: number | null;
}) {
  const { t } = useLang();
  if (sections.length === 0) return null;
  const progBySection = new Map(progress.map((p) => [p.section_id, p]));
  return (
    <div className="toolbar" style={{ marginBottom: 12 }} aria-label={t('exam_sections')}>
      {sections.map((s) => {
        const c = counts[s.id] ?? { answered: 0, total: 0 };
        const p = progBySection.get(s.id);
        const isActive = activeSectionId === s.id;
        const className = `badge blue${isActive ? ' active-section' : ''}`;
        if (onSelectSection) {
          return (
            <button
              type="button"
              key={s.id}
              onClick={() => onSelectSection(s.id)}
              className={className}
              style={{
                cursor: 'pointer',
                border: isActive ? '2px solid #3b82f6' : '1px solid transparent',
                transform: isActive ? 'scale(1.05)' : 'none',
                transition: 'all 0.15s ease',
              }}
            >
              {s.name} · {c.answered}/{c.total}
              {p && p.remaining_seconds !== null && (
                <span style={{ marginLeft: 6 }}>
                  <ClockIcon size={12} className="ico" /> {Math.floor(p.remaining_seconds / 60)}:
                  {String(p.remaining_seconds % 60).padStart(2, '0')}
                </span>
              )}
            </button>
          );
        }
        return (
          <a key={s.id} href={`#section-${s.id}`} className={className}>
            {s.name} · {c.answered}/{c.total}
            {p && p.remaining_seconds !== null && (
              <span style={{ marginLeft: 6 }}>
                <ClockIcon size={12} className="ico" /> {Math.floor(p.remaining_seconds / 60)}:
                {String(p.remaining_seconds % 60).padStart(2, '0')}
              </span>
            )}
          </a>
        );
      })}
    </div>
  );
}

export function GapFillInput({
  text,
  gaps,
  values,
  disabled,
  onChange,
}: {
  text: string;
  gaps: GapDef[];
  values: Record<string, string>;
  disabled: boolean;
  onChange: (position: number, value: string) => void;
}) {
  const parts = text.split(/_{2,}/);
  const positions = [...gaps].map((g) => g.position).sort((a, b) => a - b);
  return (
    <div style={{ marginTop: 8, lineHeight: 2.2 }}>
      {parts.map((part, i) => (
        <span key={i}>
          {part}
          {i < parts.length - 1 && (
            <input
              aria-label={`gap-${positions[i] ?? i}`}
              disabled={disabled}
              value={values[String(positions[i] ?? i)] ?? ''}
              onChange={(e) => onChange(positions[i] ?? i, e.target.value)}
              style={{ width: 140, margin: '0 4px' }}
            />
          )}
        </span>
      ))}
      {parts.length === 1 &&
        positions.map((pos) => (
          <span key={pos} style={{ display: 'block', marginTop: 8 }}>
            <input
              aria-label={`gap-${pos}`}
              disabled={disabled}
              value={values[String(pos)] ?? ''}
              onChange={(e) => onChange(pos, e.target.value)}
              placeholder={`…${pos + 1}`}
              style={{ width: '100%' }}
            />
          </span>
        ))}
    </div>
  );
}

export function MatchingInput({
  prompts,
  options,
  values,
  disabled,
  onChange,
}: {
  prompts: MatchingPromptDef[];
  options: MatchingOptionDef[];
  values: Record<string, number | null>;
  disabled: boolean;
  onChange: (promptId: number, optionId: number | null) => void;
}) {
  const { t } = useLang();
  return (
    <div style={{ display: 'grid', gap: 8, marginTop: 8 }}>
      {prompts.map((p) => (
        <div key={p.id} className="toolbar" style={{ justifyContent: 'space-between' }}>
          <span style={{ fontWeight: 600 }}>{p.text}</span>
          <select
            aria-label={`match-${p.id}`}
            disabled={disabled}
            value={values[String(p.id)] ?? ''}
            onChange={(e) =>
              onChange(p.id, e.target.value === '' ? null : Number(e.target.value))
            }
          >
            <option value="">— {t('exam_choose')} —</option>
            {options.map((o) => (
              <option key={o.id} value={o.id}>
                {o.text}
              </option>
            ))}
          </select>
        </div>
      ))}
    </div>
  );
}

export function WrittenInput({
  value,
  minWords,
  maxWords,
  disabled,
  placeholder,
  onChange,
  onBlur,
}: {
  value: string;
  minWords: number;
  maxWords: number;
  disabled: boolean;
  placeholder: string;
  onChange: (value: string) => void;
  onBlur: () => void;
}) {
  const { t } = useLang();
  const words = value.trim() === '' ? 0 : value.trim().split(/\s+/).length;
  return (
    <div style={{ marginTop: 8 }}>
      <textarea
        rows={8}
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
        onBlur={onBlur}
        placeholder={placeholder}
        style={{ width: '100%' }}
      />
      <p className="muted small">
        {t('exam_words')}: {words}
        {minWords > 0 ? ` · ${t('exam_min')}: ${minWords}` : ''}
        {maxWords > 0 ? ` · ${t('exam_max')}: ${maxWords}` : ''}
      </p>
    </div>
  );
}
