import React, { useMemo } from 'react';

interface FormulaTextProps {
  text?: string | null;
  className?: string;
  style?: React.CSSProperties;
  as?: 'span' | 'div' | 'p';
}

/*
 * SECURITY NOTE
 * -------------
 * This component NEVER builds HTML. Every result of `formatFormulaString` is
 * returned to React as a plain text child, which React escapes, so question /
 * answer text coming from teachers or AI generation cannot inject markup or
 * scripts (`<img onerror=…>` is rendered literally). Do not introduce
 * `dangerouslySetInnerHTML` here; use the Unicode sub/superscript maps below.
 */

/** Inputs longer than this are rendered verbatim: avoids regex work on abusive payloads. */
const MAX_FORMATTED_LENGTH = 20_000;

/**
 * Control characters and bidi overrides (U+202A–202E, U+2066–2069) can be used
 * to visually spoof text (e.g. flip a formula or an answer). Strip them.
 */
// eslint-disable-next-line no-control-regex
const UNSAFE_CHARS_RE = /[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F‪-‮⁦-⁩]/g;

const SUBSCRIPT_DIGITS: Readonly<Record<string, string>> = {
  '0': '₀',
  '1': '₁',
  '2': '₂',
  '3': '₃',
  '4': '₄',
  '5': '₅',
  '6': '₆',
  '7': '₇',
  '8': '₈',
  '9': '₉',
};

const SUPERSCRIPT_CHARS: Readonly<Record<string, string>> = {
  '0': '⁰',
  '1': '¹',
  '2': '²',
  '3': '³',
  '4': '⁴',
  '5': '⁵',
  '6': '⁶',
  '7': '⁷',
  '8': '⁸',
  '9': '⁹',
  '+': '⁺',
  '-': '⁻',
  '=': '⁼',
  '(': '⁽',
  ')': '⁾',
  n: 'ⁿ',
};

const mapChars = (value: string, table: Readonly<Record<string, string>>): string =>
  Array.from(value, (ch) => table[ch] ?? ch).join('');

/** Removes control / bidi-override characters from untrusted text. */
export function sanitizeFormulaInput(input: string): string {
  return input.replace(UNSAFE_CHARS_RE, '');
}

/**
 * Converts chemical & math notation into beautiful readable text:
 * - H2SO4 -> H₂SO₄
 * - Fe^3+ -> Fe³⁺, SO4^2- -> SO₄²⁻
 * - x_1, v_0 -> x₁, v₀
 * - ->, --> -> →
 * - <=>, <-> -> ⇌
 *
 * Pure string -> string; the result must only ever be rendered as a text node.
 */
export function formatFormulaString(input: string): string {
  if (!input) return '';

  const clean = sanitizeFormulaInput(input);
  if (clean.length > MAX_FORMATTED_LENGTH) return clean;

  let res = clean;

  // Arrows
  res = res.replace(/<[-=]>|<->/g, '⇌');
  res = res.replace(/-->|->/g, '→');

  // Degree celsius
  res = res.replace(/\^oC|\^o(?=[C\s]|$)/g, '°');

  // Explicit superscripts like ^3+, ^2-, ^+, ^-, ^2, ^3
  res = res.replace(/\^([0-9+\-n()]+)/g, (_match: string, chars: string) =>
    mapChars(chars, SUPERSCRIPT_CHARS),
  );

  // Explicit subscripts like x_1, a_i, v_0
  res = res.replace(/_([0-9]+)/g, (_match: string, digits: string) =>
    mapChars(digits, SUBSCRIPT_DIGITS),
  );

  // Chemical formulas: element symbol (or closing parenthesis) followed by digits,
  // e.g. H2SO4, Fe2O3, C6H12O6, Ca(OH)2
  const chemFormulaRegex = /\b([A-Z][a-z]?|\))([0-9]+)\b|\b([A-Z][a-z]?[0-9]+[A-Za-z0-9()]+)\b/g;

  res = res.replace(chemFormulaRegex, (match: string) => {
    if (/^[0-9]+$/.test(match)) return match;
    return match.replace(
      /([A-Za-z)])([0-9]+)/g,
      (_inner: string, letter: string, digits: string) => letter + mapChars(digits, SUBSCRIPT_DIGITS),
    );
  });

  return res;
}

const MATH_STYLE: React.CSSProperties = {
  fontFamily: 'KaTeX_Math, "Times New Roman", serif',
  fontStyle: 'italic',
  padding: '0 2px',
};

/** A segment is a `$…$` math span only if it has content between two dollar signs. */
const isMathSegment = (part: string): boolean =>
  part.length >= 3 && part.startsWith('$') && part.endsWith('$');

export default function FormulaText({
  text = '',
  className = '',
  style,
  as: Component = 'span',
}: FormulaTextProps) {
  const content = useMemo<React.ReactNode>(() => {
    if (!text) return null;

    if (text.includes('$') && text.length <= MAX_FORMATTED_LENGTH) {
      return text.split(/(\$[^$]+\$)/g).map((part, idx) =>
        isMathSegment(part) ? (
          <span key={idx} style={MATH_STYLE}>
            {formatFormulaString(part.slice(1, -1))}
          </span>
        ) : (
          <span key={idx}>{formatFormulaString(part)}</span>
        ),
      );
    }

    return formatFormulaString(text);
  }, [text]);

  if (!text) return null;

  return (
    <Component className={className} style={style}>
      {content}
    </Component>
  );
}
