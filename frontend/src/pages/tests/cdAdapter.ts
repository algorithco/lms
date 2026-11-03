import type { CdAttempt } from './CdExamInterface';

interface LegacyPassage { id: number; title?: string; content?: string }

/**
 * Tests created before the CD format (IELTS / plain CEFR mocks, "single"
 * questions linked to reading passages) carry no section → part → group
 * structure. This builds one so the same, tested exam screen runs them:
 * one part per reading passage (or a single part when there are none),
 * questions numbered 1…N in test order. Nothing here touches answers.
 */
export function withSyntheticStructure(attempt: CdAttempt): CdAttempt {
  if (attempt.structure?.length) return attempt;

  const pos = (q: unknown) => (q as { position?: number }).position ?? 0;
  const ordered = [...attempt.questions].sort((a, b) => pos(a) - pos(b));
  const passageOf = (q: (typeof ordered)[number]): LegacyPassage | null =>
    ((q as unknown as { passage?: LegacyPassage | null }).passage as LegacyPassage | null) ?? null;

  // Part key: passage id, or 0 for questions without a passage.
  const order: number[] = [];
  const byKey = new Map<number, typeof ordered>();
  const passages = new Map<number, LegacyPassage>(
    ((attempt.passages as LegacyPassage[] | undefined) ?? []).map((p) => [p.id, p]),
  );
  for (const q of ordered) {
    const p = passageOf(q);
    const key = p?.id ?? 0;
    if (p && !passages.has(p.id)) passages.set(p.id, p);
    if (!byKey.has(key)) {
      byKey.set(key, []);
      order.push(key);
    }
    byKey.get(key)!.push(q);
  }

  let n = 0;
  const questions: CdAttempt['questions'] = [];
  const parts = order.map((key, i) => {
    const groupId = -(i + 1); // negative: never collides with a real group id
    for (const q of byKey.get(key) ?? []) {
      n += 1;
      questions.push({ ...q, group_id: groupId, config: { ...q.config, number: q.config?.number ?? n } });
    }
    return {
      id: groupId,
      number: String(i + 1),
      title: key ? passages.get(key)?.title ?? '' : '',
      instructions: '',
      audio_url: '',
      groups: [
        {
          id: groupId,
          title: '',
          instructions: '',
          answer_rule: '',
          passage_id: key || null,
          image_url: '',
          options_label: '',
          each_option_once: false,
        },
      ],
    };
  });

  return {
    ...attempt,
    questions,
    passages: [...passages.values()].map((p) => ({ id: p.id, title: p.title ?? '', content: p.content ?? '' })),
    structure: [{ section_id: 0, code: '', name: '', duration_minutes: 0, parts }],
  };
}
