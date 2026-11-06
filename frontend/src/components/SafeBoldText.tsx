import { Fragment } from 'react';

interface SafeBoldTextProps {
  text: string;
}

const MAX_LENGTH = 2000;
const TOKEN_RE = /(<\/?b>)/gi;

interface Segment {
  text: string;
  bold: boolean;
}

function parseBold(text: string): Segment[] {
  const segments: Segment[] = [];
  let bold = false;
  for (const part of text.slice(0, MAX_LENGTH).split(TOKEN_RE)) {
    const lower = part.toLowerCase();
    if (lower === '<b>') bold = true;
    else if (lower === '</b>') bold = false;
    else if (part) segments.push({ text: part, bold });
  }
  return segments;
}

/**
 * Renders server messages that may contain `<b>…</b>` and line breaks WITHOUT
 * `dangerouslySetInnerHTML`. Only the bold tag is understood; every other
 * character (including any other markup) is shown as plain, escaped text.
 */
export default function SafeBoldText({ text }: SafeBoldTextProps) {
  return (
    <span style={{ whiteSpace: 'pre-line' }}>
      {parseBold(text).map((seg, idx) =>
        seg.bold ? <strong key={idx}>{seg.text}</strong> : <Fragment key={idx}>{seg.text}</Fragment>,
      )}
    </span>
  );
}
