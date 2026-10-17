import { useState, useRef } from 'react';
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
  const [collapsed, setCollapsed] = useState(() =>
    typeof window !== 'undefined' ? window.innerWidth < 768 : false
  );

  return (
    <div className="card passage-card sticky-passage" style={{ marginBottom: 12 }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 10,
          borderBottom: '1px solid var(--border)',
          paddingBottom: 8,
          flexWrap: 'wrap',
          gap: 6,
        }}
      >
        <p className="small" style={{ margin: 0, fontWeight: 800, color: '#f59e0b', fontSize: '0.95rem' }}>
          📖 {t('exam_passage_title') || "Matnni ko'rish (Qismlar bo'yicha)"}
          {passage.title ? ` · ${passage.title}` : ''}
        </p>
        <button
          type="button"
          className="btn sm ghost"
          onClick={() => setCollapsed(!collapsed)}
          style={{ fontSize: '0.78rem', padding: '3px 8px' }}
        >
          {collapsed ? `📖 ${t('read_full_passage') || 'Matnni ochish'}` : `🔼 ${t('collapse_passage') || 'Yopish'}`}
        </button>
      </div>

      {!collapsed ? (
        <div
          className="passage-content-scroll"
          style={{
            whiteSpace: 'pre-line',
            lineHeight: 1.75,
            fontSize: '0.96rem',
            color: 'var(--ink)',
          }}
        >
          {passage.content}
        </div>
      ) : (
        <div
          onClick={() => setCollapsed(false)}
          style={{
            whiteSpace: 'pre-line',
            lineHeight: 1.6,
            fontSize: '0.9rem',
            color: 'var(--muted)',
            cursor: 'pointer',
            padding: '6px 8px',
            background: 'rgba(255, 255, 255, 0.02)',
            borderRadius: 6,
          }}
        >
          {passage.content.slice(0, 180)}... <span style={{ color: '#f59e0b', fontWeight: 600 }}>[To'liq matnni o'qish →]</span>
        </div>
      )}

      {passage.source && (
        <p className="muted small" style={{ marginTop: 10, borderTop: '1px dashed var(--border)', paddingTop: 6 }}>
          <em>{passage.source}</em>
        </p>
      )}
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
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [photoPreview, setPhotoPreview] = useState<string | null>(null);

  const words = value.trim() === '' ? 0 : value.trim().split(/\s+/).filter(Boolean).length;
  const targetMin = minWords > 0 ? minWords : 200;
  const targetMax = maxWords > 0 ? maxWords : 500;

  const handlePhotoSelect = (file: File | null) => {
    if (!file) return;
    const url = URL.createObjectURL(file);
    setPhotoPreview(url);
    const tag = `[Qo'lyozma rasm biriktirildi: ${file.name}]`;
    if (!value.includes(tag)) {
      const nextVal = value.trim() ? `${value}\n\n${tag}` : tag;
      onChange(nextVal);
    }
  };

  const isUnder = words < targetMin;
  const isOver = targetMax > 0 && words > targetMax;
  const isIdeal = !isUnder && !isOver;

  return (
    <div style={{ marginTop: 10 }}>
      {/* Word counter badge & photo upload button bar */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: 10,
          marginBottom: 10,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <span
            style={{
              padding: '6px 14px',
              borderRadius: 8,
              fontSize: '0.85rem',
              fontWeight: 700,
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              background: isUnder
                ? 'rgba(245, 158, 11, 0.15)'
                : isIdeal
                  ? 'rgba(16, 185, 129, 0.16)'
                  : 'rgba(239, 68, 68, 0.18)',
              color: isUnder ? '#f59e0b' : isIdeal ? '#10b981' : '#ef4444',
              border: `1px solid ${
                isUnder
                  ? 'rgba(245, 158, 11, 0.4)'
                  : isIdeal
                    ? 'rgba(16, 185, 129, 0.45)'
                    : 'rgba(239, 68, 68, 0.5)'
              }`,
              transition: 'all 0.2s ease',
            }}
          >
            <span>{isUnder ? '⚠️' : isIdeal ? '✓' : '❌'}</span>
            <span>
              {isUnder && (t('word_counter_under') ? t('word_counter_under').replace('{count}', String(words)).replace('{min}', String(targetMin)) : `Yetarli emas: ${words}/${targetMin} so'z`)}
              {isIdeal && (t('word_counter_ideal') ? t('word_counter_ideal').replace('{count}', String(words)) : `Ideal hajm: ${words} so'z ✓`)}
              {isOver && (t('word_counter_over') ? t('word_counter_over').replace('{count}', String(words)).replace('{max}', String(targetMax)) : `Hajm oshib ketdi: ${words}/${targetMax} so'z`)}
            </span>
          </span>
        </div>

        <div>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*"
            style={{ display: 'none' }}
            disabled={disabled}
            onChange={(e) => handlePhotoSelect(e.target.files?.[0] ?? null)}
          />
          <button
            type="button"
            className="btn sm ghost"
            disabled={disabled}
            onClick={() => fileInputRef.current?.click()}
            style={{
              fontSize: '0.82rem',
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              borderColor: '#f59e0b',
              color: '#f59e0b',
            }}
          >
            <span>📷</span>
            <span>{t('essay_ocr_upload_btn')}</span>
          </button>
        </div>
      </div>

      {photoPreview && (
        <div
          style={{
            marginBottom: 10,
            display: 'flex',
            alignItems: 'center',
            gap: 12,
            padding: 10,
            background: 'rgba(255, 255, 255, 0.04)',
            borderRadius: 10,
            border: '1px solid var(--border)',
          }}
        >
          <img
            src={photoPreview}
            alt="Handwritten essay preview"
            style={{ width: 64, height: 64, objectFit: 'cover', borderRadius: 8, border: '1px solid var(--border)' }}
          />
          <div style={{ flex: 1 }}>
            <span style={{ fontSize: '0.86rem', color: '#10b981', fontWeight: 700, display: 'block' }}>
              {t('essay_ocr_photo_attached')}
            </span>
            <button
              type="button"
              className="btn sm ghost"
              onClick={() => fileInputRef.current?.click()}
              style={{ padding: '3px 8px', fontSize: '0.75rem', marginTop: 4 }}
            >
              {t('essay_ocr_change_photo')}
            </button>
          </div>
        </div>
      )}

      <textarea
        rows={14}
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(e.target.value)}
        onBlur={onBlur}
        placeholder={placeholder}
        style={{
          width: '100%',
          lineHeight: 1.7,
          fontSize: '0.96rem',
          padding: '14px 16px',
          borderRadius: 10,
          border: '1px solid var(--border)',
          background: 'var(--card)',
          color: 'var(--ink)',
        }}
      />
      <p className="muted small" style={{ marginTop: 8 }}>
        {t('exam_words')}: <strong>{words}</strong>
        {targetMin > 0 ? ` · ${t('exam_min')}: ${targetMin}` : ''}
        {maxWords > 0 ? ` · ${t('exam_max')}: ${maxWords}` : ''}
      </p>
    </div>
  );
}
