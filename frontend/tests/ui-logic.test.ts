// UI logic tests. Run with `npm test` (Node's built-in runner, no extra libraries).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';

import {
  countEssayWords,
  essayKind,
  essayStatus,
  filterMyEssays,
  filterTopics,
  scoreLabel,
  wordZone,
} from '../src/lib/essays.ts';
import { listState } from '../src/lib/listState.ts';
import { formatPrice, planLines } from '../src/lib/planFeatures.ts';

// ── Tests page: exactly one of loading / error / empty / no match / list ──────
test('tests page shows an error, never "(0)", when the request failed', () => {
  assert.equal(listState({ loading: false, error: 'Network error', total: 0, visible: 0 }), 'error');
});

test('tests page: loading wins, then error, then empty, then no match', () => {
  assert.equal(listState({ loading: true, error: 'x', total: 5, visible: 5 }), 'loading');
  assert.equal(listState({ loading: false, error: null, total: 0, visible: 0 }), 'empty');
  assert.equal(listState({ loading: false, error: null, total: 4, visible: 0 }), 'no_match');
  assert.equal(listState({ loading: false, error: null, total: 4, visible: 2 }), 'list');
});

// ── Essay word counter: same rule as the server's WordCounter ─────────────────
test('word counter counts only tokens with a letter', () => {
  assert.equal(countEssayWords(''), 0);
  assert.equal(countEssayWords('   \n\t '), 0);
  assert.equal(countEssayWords('Kitob — bu   bilim manbai.'), 4);
  assert.equal(countEssayWords('2024 - 15 , !!'), 0);
  assert.equal(countEssayWords('Книга это знание'), 3);
  assert.equal(countEssayWords("o'quvchi\nmaktab\n\nustoz"), 3);
});

test('word zone: under below min, over above max, ok in between; no max means no upper bound', () => {
  assert.equal(wordZone(149, 150, 300), 'under');
  assert.equal(wordZone(150, 150, 300), 'ok');
  assert.equal(wordZone(300, 150, 300), 'ok');
  assert.equal(wordZone(301, 150, 300), 'over');
  assert.equal(wordZone(5000, 50, 0), 'ok');
});

// ── Essay states shown to students (never the raw server word) ───────────────
test('essay statuses map to the five student states', () => {
  assert.equal(essayStatus('draft'), 'draft');
  assert.equal(essayStatus('pending'), 'pending');
  assert.equal(essayStatus('submitted'), 'pending');
  assert.equal(essayStatus('pending_teacher'), 'teacher');
  for (const s of ['graded', 'ai_evaluated', 'teacher_reviewed']) assert.equal(essayStatus(s), 'graded');
  assert.equal(essayStatus('error'), 'error');
});

test('essay kind keeps subjects apart: IELTS tasks, CEFR, Ona tili, Adabiyot', () => {
  assert.equal(essayKind({ category: 'ielts_task1' }), 'ielts_task1');
  assert.equal(essayKind({ rubric_type: 'ielts_task2' }), 'ielts_task2');
  assert.equal(essayKind({ category: 'multilevel' }), 'multilevel');
  assert.equal(essayKind({ category: 'adabiyot' }), 'adabiyot');
  assert.equal(essayKind({ rubric_type: 'bmb_12' }), 'ona_tili');
  assert.equal(essayKind({}), 'ona_tili');
});

test('score label shows exactly what the server stored, nothing while grading', () => {
  const t = (k: string) => (k === 'es_band' ? 'Band' : k);
  assert.equal(scoreLabel({ overall_band: 6.5 }, t), 'Band 6.5');
  assert.equal(scoreLabel({ total_score: 48, max_score: 60 }, t), '48/60');
  assert.equal(scoreLabel({ total_score: null, max_score: null }, t), '');
});

// ── "My essays" list and topic filters ───────────────────────────────────────
const mine = [
  { id: 1, status: 'draft' },
  { id: 2, status: 'ai_evaluated' },
  { id: 3, status: 'pending' },
  { id: 4, status: 'teacher_reviewed' },
];

test('my essays filter: drafts, graded, all', () => {
  assert.deepEqual(filterMyEssays(mine, 'draft').map((e) => e.id), [1]);
  assert.deepEqual(filterMyEssays(mine, 'graded').map((e) => e.id), [2, 4]);
  assert.equal(filterMyEssays(mine, 'all').length, 4);
  assert.deepEqual(filterMyEssays([], 'graded'), []);
});

test('topic filter combines the type chip and search', () => {
  const topics = [
    { title: 'Kitob va inson', description: '', category: 'ona_tili' },
    { title: 'Charts: energy use', description: 'line graph', category: 'ielts_task1' },
    { title: 'Technology', description: 'Some people think', category: 'ielts_task2' },
  ];
  assert.equal(filterTopics(topics, 'all', '').length, 3);
  assert.deepEqual(filterTopics(topics, 'ielts_task1', '').map((t) => t.title), ['Charts: energy use']);
  assert.deepEqual(filterTopics(topics, 'all', 'GRAPH').map((t) => t.title), ['Charts: energy use']);
  assert.deepEqual(filterTopics(topics, 'ielts_task2', 'kitob'), []);
});

// ── i18n: every t('key') used in the app exists in uz, ru and en ─────────────
type Dict = Record<string, unknown>;
const SRC = join(import.meta.dirname, '..', 'src');
const translations = JSON.parse(readFileSync(join(SRC, 'i18n', 'translations.json'), 'utf8')) as Record<string, Dict>;

function has(dict: Dict, key: string): boolean {
  if (key in dict) return typeof dict[key] === 'string' && (dict[key] as string).trim() !== '';
  let cur: unknown = dict;
  for (const part of key.split('.')) {
    if (cur && typeof cur === 'object' && part in (cur as Dict)) cur = (cur as Dict)[part];
    else return false;
  }
  return typeof cur === 'string' && cur.trim() !== '';
}

function sources(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) return sources(p);
    return /\.tsx?$/.test(name) ? [p] : [];
  });
}

test('every t("key") without a fallback exists in uz, ru and en', () => {
  const missing: string[] = [];
  let seen = 0;
  for (const file of sources(SRC)) {
    const text = readFileSync(file, 'utf8');
    for (const m of text.matchAll(/\bt\(\s*'([A-Za-z0-9_.]+)'\s*\)/g)) {
      seen += 1;
      for (const lang of ['uz', 'ru', 'en']) {
        if (!has(translations[lang], m[1])) missing.push(`${lang}:${m[1]} (${file.slice(SRC.length + 1)})`);
      }
    }
  }
  assert.ok(seen > 500, `expected many keys, scanned ${seen}`);
  assert.deepEqual(missing, []);
});

test('the three languages have the same top-level keys', () => {
  const keys = (l: string) => new Set(Object.keys(translations[l]));
  const uz = keys('uz');
  for (const l of ['ru', 'en']) {
    const other = keys(l);
    assert.deepEqual([...uz].filter((k) => !other.has(k)), [], `missing in ${l}`);
    assert.deepEqual([...other].filter((k) => !uz.has(k)), [], `missing in uz (present in ${l})`);
  }
});

// ── Plan cards: lines come from the plan row only ─────────────────────────────
test('plan card lines follow the plan row, never invented limits', () => {
  const pro = planLines({
    test_limit: 30,
    text_essay_weekly_limit: 15,
    image_essay_weekly_limit: 15,
    text_essay_cooldown_hours: 1,
    duration_days: 30,
  });
  assert.deepEqual(pro, [
    { key: 'pl_tests_week', n: 30 },
    { key: 'pl_text_week', n: 15 },
    { key: 'pl_photo_week', n: 15 },
    { key: 'pl_cooldown', n: 1 },
    { key: 'pl_duration', n: 30 },
  ]);
  const starter = planLines({ test_limit: 5, text_essay_weekly_limit: 3, image_essay_weekly_limit: 0, text_essay_cooldown_hours: 2 });
  assert.equal(starter.find((l) => l.key.startsWith('pl_photo'))?.key, 'pl_photo_none');
  const premium = planLines({ is_unlimited_tests: true, is_unlimited_text_essays: true, is_unlimited_image_essays: true, text_essay_cooldown_hours: 0 });
  assert.deepEqual(premium.map((l) => l.key), ['pl_tests_unlimited', 'pl_text_unlimited', 'pl_photo_unlimited']);
  // a limit the admin left empty is not shown at all
  assert.deepEqual(planLines({}), []);
});

test('plan price is grouped in threes', () => {
  assert.equal(formatPrice(15000), '15 000');
  assert.equal(formatPrice('27000.00'), '27 000');
  assert.equal(formatPrice(null), '0');
});
