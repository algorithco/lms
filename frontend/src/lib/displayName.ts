/**
 * One place for how a person's name is shown: "komiljon ROZIYEV" -> "Komiljon Roziyev",
 * initials "KR". Every greeting, avatar, menu and header goes through these.
 */

const WORD = /[^\s-]+/g;

/** Title Case each word ("anna-maria o'neil" -> "Anna-Maria O'neil"). Empty when there is no name. */
export function titleCaseName(raw: string): string {
  return raw
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .map((part) => part.replace(WORD, (w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase()))
    .join(' ');
}

/** Name for display; falls back to the part of the e-mail before "@", then to `fallback`. */
export function formatDisplayName(name?: string | null, email?: string | null, fallback = ''): string {
  const raw = (name || '').trim() || (email ? email.split('@')[0] : '');
  return titleCaseName(raw) || fallback;
}

/** Up to two initials, upper case ("komiljon roziyev" -> "KR"). */
export function initialsOf(name?: string | null, email?: string | null): string {
  const words = formatDisplayName(name, email).split(/\s+/).filter(Boolean);
  if (words.length === 0) return '?';
  const letters = words.length === 1 ? words[0].slice(0, 2) : words[0][0] + words[1][0];
  return letters.toUpperCase();
}
