/** Which one block a list page shows; exactly one is true at a time. */
export type ListState = 'loading' | 'error' | 'empty' | 'no_match' | 'list';

export function listState(s: { loading: boolean; error: unknown; total: number; visible: number }): ListState {
  if (s.loading) return 'loading';
  if (s.error) return 'error';
  if (s.total === 0) return 'empty';
  if (s.visible === 0) return 'no_match';
  return 'list';
}
