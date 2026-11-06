import React from 'react';

interface FormulaTextProps {
  text?: string | null;
  className?: string;
  style?: React.CSSProperties;
  as?: 'span' | 'div' | 'p';
}

const SUBSCRIPT_DIGITS: Record<string, string> = {
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

const SUPERSCRIPT_CHARS: Record<string, string> = {
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
  'n': 'ⁿ',
};

/**
 * Converts chemical & math notation into beautiful readable text:
 * - H2SO4 -> H₂SO₄
 * - Fe^3+ -> Fe³⁺, SO4^2- -> SO₄²⁻
 * - x_1, v_0 -> x₁, v₀
 * - ->, --> -> →
 * - <=>, <-> -> ⇌
 */
export function formatFormulaString(input: string): string {
  if (!input) return '';

  let res = input;

  // Replace arrows
  res = res.replace(/<[-=]>|<->/g, '⇌');
  res = res.replace(/-->|->/g, '→');

  // Replace degree celsius
  res = res.replace(/\^oC|\^o(?=[C\s]|$)/g, '°');

  // Replace explicit superscripts like ^3+, ^2-, ^+, ^-, ^2, ^3
  res = res.replace(/\^([0-9+\-n()]+)/g, (_, chars) => {
    return chars
      .split('')
      .map((ch: string) => SUPERSCRIPT_CHARS[ch] || ch)
      .join('');
  });

  // Replace explicit subscripts like x_1, a_i, v_0
  res = res.replace(/_([0-9]+)/g, (_, digits) => {
    return digits
      .split('')
      .map((d: string) => SUBSCRIPT_DIGITS[d] || d)
      .join('');
  });

  // Common chemical formula patterns:
  // Elements like H, He, Li, Be, B, C, N, O, F, Ne, Na, Mg, Al, Si, P, S, Cl, Ar, K, Ca, Fe, Cu, Zn, Br, Ag, I, Ba, Au, Hg, Pb
  // Followed by digits e.g. H2SO4, Fe2O3, C6H12O6, Ca(OH)2
  const chemFormulaRegex = /\b([A-Z][a-z]?|\))([0-9]+)\b|\b([A-Z][a-z]?[0-9]+[A-Za-z0-9()]+)\b/g;

  res = res.replace(chemFormulaRegex, (match) => {
    // If it's a known non-formula or simple number, skip
    if (/^[0-9]+$/.test(match)) return match;
    // Replace digits after uppercase/lowercase element or closing parenthesis with subscripts
    return match.replace(/([A-Za-z\)])([0-9]+)/g, (_, letter, digits) => {
      const sub = digits
        .split('')
        .map((d: string) => SUBSCRIPT_DIGITS[d] || d)
        .join('');
      return letter + sub;
    });
  });

  return res;
}

export default function FormulaText({
  text = '',
  className = '',
  style,
  as: Component = 'span',
}: FormulaTextProps) {
  if (!text) return null;

  // Check if string contains LaTeX blocks like $...$
  if (text.includes('$')) {
    const parts = text.split(/(\$[^$]+\$)/g);
    return (
      <Component className={className} style={style}>
        {parts.map((part, idx) => {
          if (part.startsWith('$') && part.endsWith('$')) {
            const inner = part.slice(1, -1);
            return (
              <span
                key={idx}
                style={{
                  fontFamily: 'KaTeX_Math, "Times New Roman", serif',
                  fontStyle: 'italic',
                  padding: '0 2px',
                }}
              >
                {formatFormulaString(inner)}
              </span>
            );
          }
          return <span key={idx}>{formatFormulaString(part)}</span>;
        })}
      </Component>
    );
  }

  return (
    <Component className={className} style={style}>
      {formatFormulaString(text)}
    </Component>
  );
}
