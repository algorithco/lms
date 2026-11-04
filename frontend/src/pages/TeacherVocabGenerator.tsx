import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { BookOpen, Send, Sparkles, Wallet } from 'lucide-react';

import { useToast } from '../context/ToastContext';
import { useLang } from '../i18n/LangContext';
import { apiFetch } from '../lib/api';

interface ExerciseQuiz {
  id: number;
  word: string;
  question: string;
  options: string[];
  correct_answer: string;
  explanation: string;
}

interface ExerciseSpelling {
  id: number;
  word: string;
  prompt: string;
  hint_pattern: string;
  scrambled_letters: string[];
  correct_word: string;
}

interface ExerciseTranslation {
  id: number;
  word?: string;
  uzbek_word?: string;
  options: string[];
  correct_answer: string;
}

interface GeneratedExercises {
  format_1_quiz: ExerciseQuiz[];
  format_2_spelling: ExerciseSpelling[];
  format_3_eng_uzb: ExerciseTranslation[];
  format_4_uzb_eng: ExerciseTranslation[];
}

type Tab = 'quiz' | 'spelling' | 'eng_uzb' | 'uzb_eng';
const TABS: Tab[] = ['quiz', 'spelling', 'eng_uzb', 'uzb_eng'];

/** Teacher tool: a word list becomes four exercise formats, then a group homework. */
export default function TeacherVocabGenerator() {
  const { t } = useLang();
  const toast = useToast();
  const [title, setTitle] = useState('');
  const [rawText, setRawText] = useState('');
  const [groups, setGroups] = useState<{ id: number; name: string }[]>([]);
  const [selectedGroupId, setSelectedGroupId] = useState<number | null>(null);

  const [loading, setLoading] = useState(false);
  const [assigning, setAssigning] = useState(false);
  const [activeTab, setActiveTab] = useState<Tab>('quiz');
  const [exercises, setExercises] = useState<GeneratedExercises | null>(null);
  const [packId, setPackId] = useState<number | null>(null);

  useEffect(() => {
    apiFetch<unknown>('/api/v1/school/groups/')
      .then((res) => {
        const list = (Array.isArray(res) ? res : []).map((g: { id: number; name: string }) => ({ id: g.id, name: g.name }));
        setGroups(list);
        if (list.length > 0) setSelectedGroupId(list[0].id);
      })
      .catch(() => undefined);
  }, []);

  const errText = (err: unknown, key: string) => (err instanceof Error && err.message ? err.message : t(key));

  const wordCount = rawText
    .split(/[\n,]+/)
    .map((w) => w.trim())
    .filter((w) => w.length > 1).length;

  const handleGenerate = async () => {
    if (wordCount === 0) {
      toast.error(t('tv_need_words'));
      return;
    }
    setLoading(true);
    setExercises(null);
    setPackId(null);
    try {
      const res = await apiFetch<{ id: number; word_count: number; exercises_data?: GeneratedExercises }>(
        '/api/v1/vocabulary/generate/',
        {
          method: 'POST',
          body: JSON.stringify({
            raw_text: rawText,
            title: title.trim() || t('tv_default_title'),
            group_id: selectedGroupId,
            save: true,
          }),
        },
      );
      if (res.exercises_data) {
        setExercises(res.exercises_data);
        setPackId(res.id);
        toast.success(t('tv_ready').replace('{n}', String(res.word_count)));
      }
    } catch (err) {
      toast.error(errText(err, 'tv_gen_failed'));
    } finally {
      setLoading(false);
    }
  };

  const handleAssignHomework = async () => {
    if (!packId || !selectedGroupId) return;
    setAssigning(true);
    try {
      const res = await apiFetch<{ message?: string }>('/api/v1/vocabulary/assign-homework/', {
        method: 'POST',
        body: JSON.stringify({ pack_id: packId, group_id: selectedGroupId, due_days: 3 }),
      });
      toast.success(res.message || t('tv_assigned'));
    } catch (err) {
      toast.error(errText(err, 'tv_assign_failed'));
    } finally {
      setAssigning(false);
    }
  };

  const options = (opts: string[], correct: string) => (
    <div className="tv-opts">
      {opts.map((opt, i) => (
        <span key={i} className={`tv-opt${opt === correct ? ' is-correct' : ''}`}>
          {opt}
        </span>
      ))}
    </div>
  );

  return (
    <div className="tf">
      <header className="tf-head">
        <div className="tf-head__text">
          <h1>{t('tv_title')}</h1>
          <p>{t('tv_sub')}</p>
        </div>
        <div className="tf-head__actions">
          <Link to="/teacher/finance" className="ui-btn ui-btn--sm">
            <Wallet size={16} aria-hidden="true" /> {t('tf_title')}
          </Link>
        </div>
      </header>

      <div className="tv-grid">
        <section className="ui-card tv-form">
          <label className="tv-field">
            <span>{t('tv_pack_name')}</span>
            <input className="ui-input" value={title} onChange={(e) => setTitle(e.target.value)} placeholder={t('tv_default_title')} />
          </label>
          <label className="tv-field">
            <span>{t('tv_group')}</span>
            {groups.length > 0 ? (
              <select className="ui-input" value={selectedGroupId ?? ''} onChange={(e) => setSelectedGroupId(Number(e.target.value))}>
                {groups.map((g) => (
                  <option key={g.id} value={g.id}>
                    {g.name}
                  </option>
                ))}
              </select>
            ) : (
              <small className="tv-muted">{t('tv_no_groups')}</small>
            )}
          </label>
          <label className="tv-field">
            <span className="tv-field__row">
              {t('tv_words').replace('{n}', String(wordCount))}
              <small>{t('tv_words_hint')}</small>
            </span>
            <textarea
              className="ui-input tv-words"
              rows={10}
              value={rawText}
              onChange={(e) => setRawText(e.target.value)}
              placeholder={t('tv_words_ph')}
            />
          </label>
          <button
            type="button"
            className="ui-btn ui-btn--primary ui-btn--block"
            onClick={() => void handleGenerate()}
            disabled={loading || wordCount === 0}
          >
            <Sparkles size={16} aria-hidden="true" /> {loading ? t('tv_generating') : t('tv_generate')}
          </button>
        </section>

        <section className="ui-card tv-preview">
          <div className="tv-preview__head">
            <div className="ui-chip-row" role="tablist" aria-label={t('tv_formats')}>
              {TABS.map((tab, i) => (
                <button
                  key={tab}
                  type="button"
                  role="tab"
                  aria-selected={activeTab === tab}
                  className={`ui-chip${activeTab === tab ? ' is-on' : ''}`}
                  onClick={() => setActiveTab(tab)}
                >
                  {i + 1}. {t(`tv_tab_${tab}`)}
                </button>
              ))}
            </div>
            {packId && selectedGroupId && (
              <button type="button" className="ui-btn ui-btn--sm ui-btn--primary" onClick={() => void handleAssignHomework()} disabled={assigning}>
                <Send size={14} aria-hidden="true" /> {assigning ? t('loading') : t('tv_assign')}
              </button>
            )}
          </div>

          {loading ? (
            <div className="tv-items" aria-busy="true">
              {[0, 1, 2].map((i) => (
                <div key={i} className="ui-skel" style={{ height: 96, borderRadius: 12 }} />
              ))}
            </div>
          ) : !exercises ? (
            <div className="ui-state" style={{ border: 0 }}>
              <span className="ic-chip">
                <BookOpen size={24} aria-hidden="true" />
              </span>
              <p>{t('tv_empty')}</p>
            </div>
          ) : (
            <ol className="tv-items">
              {activeTab === 'quiz' &&
                exercises.format_1_quiz.map((q, idx) => (
                  <li key={idx} className="tv-item">
                    <strong>{q.question}</strong>
                    {options(q.options, q.correct_answer)}
                  </li>
                ))}
              {activeTab === 'spelling' &&
                exercises.format_2_spelling.map((s, idx) => (
                  <li key={idx} className="tv-item">
                    <small>{s.prompt}</small>
                    <span className="tv-pattern">{s.hint_pattern}</span>
                    <div className="tv-letters">
                      {s.scrambled_letters.map((l, i) => (
                        <span key={i}>{l}</span>
                      ))}
                    </div>
                  </li>
                ))}
              {activeTab === 'eng_uzb' &&
                exercises.format_3_eng_uzb.map((item, idx) => (
                  <li key={idx} className="tv-item">
                    <strong>{item.word}</strong>
                    {options(item.options, item.correct_answer)}
                  </li>
                ))}
              {activeTab === 'uzb_eng' &&
                exercises.format_4_uzb_eng.map((item, idx) => (
                  <li key={idx} className="tv-item">
                    <strong>{item.uzbek_word}</strong>
                    {options(item.options, item.correct_answer)}
                  </li>
                ))}
            </ol>
          )}
        </section>
      </div>
    </div>
  );
}
