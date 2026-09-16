import { useCallback, useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { useLang } from '../i18n/LangContext';
import { Panel } from '../lib/api';
import { num, str } from '../lib/billingPanelGames';
import { AwardIcon, LockIcon } from '../components/icons';

interface TopicForm {
  title: string;
  description: string;
  category: string;
  word_limit_min: number;
  word_limit_max: number;
  time_limit_minutes: number;
  sample_outline: string;
  grammar_strictness: number;
  national_cert_scale: boolean;
  password: string;
  is_active: boolean;
}

const EMPTY: TopicForm = {
  title: '',
  description: '',
  category: 'ona_tili',
  word_limit_min: 150,
  word_limit_max: 500,
  time_limit_minutes: 60,
  sample_outline: '',
  grammar_strictness: 50,
  national_cert_scale: false,
  password: '',
  is_active: true,
};

/**
 * Essay topics — full EssayTopicSerializer fields, parity with
 * templates/panel/essay_topic_list.html + essay_topic_form.html:
 * title, description, category, word limits, time limit, outline,
 * grammar strictness, national_cert_scale, password (write-only),
 * is_active. GET/POST /panel/topics/, GET/PATCH/DELETE /panel/topics/<id>/.
 */
export default function PanelTopics() {
  const { t } = useLang();
  const [topics, setTopics] = useState<Record<string, unknown>[]>([]);
  const [categories, setCategories] = useState<{ value: string; label: string }[]>([]);
  const [q, setQ] = useState('');
  const [category, setCategory] = useState('');
  const [err, setErr] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<number | string | null>(null);
  const [form, setForm] = useState<TopicForm>(EMPTY);

  const load = useCallback(() => {
    Panel.topics(q, category)
      .then((r) => {
        setTopics(r.results as unknown as Record<string, unknown>[]);
        setCategories(r.categories);
        setErr(null);
      })
      .catch((e: unknown) => setErr(e instanceof Error ? e.message : 'Failed.'));
  }, [q, category]);

  useEffect(() => {
    const id = setTimeout(load, 300);
    return () => clearTimeout(id);
  }, [load]);

  const startCreate = () => {
    setEditingId(null);
    setForm({ ...EMPTY, category: category || 'ona_tili' });
    setShowForm(true);
  };

  const startEdit = (x: Record<string, unknown>) => {
    setEditingId(x.id as number);
    setForm({
      title: str(x.title),
      description: str(x.description),
      category: str(x.category, 'ona_tili'),
      word_limit_min: num(x.word_limit_min, 150),
      word_limit_max: num(x.word_limit_max, 500),
      time_limit_minutes: num(x.time_limit_minutes, 60),
      sample_outline: str(x.sample_outline),
      grammar_strictness: num(x.grammar_strictness, 50),
      national_cert_scale: Boolean(x.national_cert_scale),
      password: '',
      is_active: x.is_active === undefined ? true : Boolean(x.is_active),
    });
    setShowForm(true);
  };

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setErr(null);
    // password is write-only: only send when the admin typed a new one.
    const payload: Record<string, unknown> = { ...form };
    if (str(payload.password).trim() === '') delete payload.password;
    try {
      if (editingId === null) {
        await Panel.createTopic(payload);
      } else {
        await Panel.updateTopic(editingId, payload);
      }
      setForm(EMPTY);
      setEditingId(null);
      setShowForm(false);
      load();
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : 'Save failed.');
    }
  };

  const remove = async (id: number | string) => {
    if (!window.confirm(t('panel_confirm_delete'))) return;
    try {
      await Panel.deleteTopic(id);
      load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : 'Failed.');
    }
  };

  const removePassword = async (id: number | string) => {
    if (!window.confirm(t('panel_topic_password_remove_confirm'))) return;
    try {
      // Empty string clears the stored hash (backend treats "" as clear,
      // omitted key as keep).
      await Panel.updateTopic(id, { password: '' });
      load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : 'Failed.');
    }
  };

  const set =
    (k: keyof TopicForm) =>
    (e: { target: { value: string; checked?: boolean; type?: string } }) => {
      const v =
        e.target.type === 'checkbox'
          ? !!e.target.checked
          : e.target.type === 'number'
            ? Number(e.target.value)
            : e.target.value;
      setForm((f) => ({ ...f, [k]: v }) as TopicForm);
    };

  return (
    <div>
      <h1>{t('essay_topics')}</h1>
      {err && <p className="error">{err}</p>}
      <div className="toolbar">
        <input placeholder={t('panel_search_topics')} value={q} onChange={(e) => setQ(e.target.value)} />
        <select value={category} onChange={(e) => setCategory(e.target.value)}>
          <option value="">{t('all')}</option>
          {categories.map((c) => (
            <option key={c.value} value={c.value}>
              {c.label}
            </option>
          ))}
        </select>
        <button className="btn primary sm" onClick={showForm ? () => setShowForm(false) : startCreate}>
          {showForm ? t('cancel') : t('panel_new_topic')}
        </button>
      </div>

      {showForm && (
        <form onSubmit={onSubmit} className="card form" style={{ maxWidth: '100%' }}>
          <h2>{editingId === null ? t('panel_new_topic') : t('panel_edit_topic')}</h2>
          <label>
            {t('th_topic')}
            <input value={form.title} onChange={set('title')} required />
          </label>
          <label>
            {t('description')}
            <textarea value={form.description} onChange={set('description')} required rows={3} />
          </label>
          <div className="row">
            <label>
              {t('panel_category')}
              <select value={form.category} onChange={set('category')}>
                {(categories.length > 0
                  ? categories
                  : [{ value: 'ona_tili', label: 'ona_tili' }]
                ).map((c) => (
                  <option key={c.value} value={c.value}>
                    {c.label}
                  </option>
                ))}
              </select>
            </label>
            <label style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
              <input type="checkbox" checked={form.is_active} onChange={set('is_active')} />
              {t('panel_topic_active')}
            </label>
          </div>
          <div className="row">
            <label>
              {t('panel_word_min')}
              <input type="number" min={0} value={form.word_limit_min} onChange={set('word_limit_min')} />
            </label>
            <label>
              {t('panel_word_max')}
              <input type="number" min={0} value={form.word_limit_max} onChange={set('word_limit_max')} />
            </label>
            <label>
              {t('panel_time_limit')}
              <input
                type="number"
                min={0}
                value={form.time_limit_minutes}
                onChange={set('time_limit_minutes')}
              />
            </label>
            <label>
              {t('panel_grammar_short')} (%)
              <input
                type="number"
                min={0}
                max={100}
                value={form.grammar_strictness}
                onChange={set('grammar_strictness')}
              />
            </label>
          </div>
          <label>
            {t('panel_sample_outline')}
            <textarea value={form.sample_outline} onChange={set('sample_outline')} rows={2} />
          </label>
          <label>
            {t('panel_topic_password')}
            <input
              value={form.password}
              onChange={set('password')}
              placeholder={t('panel_topic_password_hint')}
              autoComplete="new-password"
            />
            <small className="muted">{t('panel_topic_password_keep_hint')}</small>
          </label>
          <label style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
            <input
              type="checkbox"
              checked={form.national_cert_scale}
              onChange={set('national_cert_scale')}
            />
            <AwardIcon size={13} className="ico" /> {t('panel_national_cert_scale')}
          </label>
          <p className="muted small">{t('panel_national_cert_hint')}</p>
          <div className="row">
            <button className="btn primary">
              {editingId === null ? t('panel_create_topic_btn') : t('save_changes')}
            </button>
            <button
              type="button"
              className="btn"
              onClick={() => {
                setShowForm(false);
                setEditingId(null);
              }}
            >
              {t('cancel')}
            </button>
          </div>
        </form>
      )}

      {topics.length === 0 && !showForm ? (
        <div className="card">
          <p>
            <strong>{t('panel_no_topics')}</strong>
          </p>
          <p className="muted small">{t('panel_no_topics_hint')}</p>
        </div>
      ) : (
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>{t('th_topic')}</th>
                <th>{t('panel_category')}</th>
                <th>{t('words')}</th>
                <th>{t('status')}</th>
                <th>{t('th_actions')}</th>
              </tr>
            </thead>
            <tbody>
              {topics.map((x) => (
                <tr key={str(x.id)}>
                  <td>
                    <strong>{str(x.title)}</strong>
                    <br />
                    <small className="muted">
                      {str(x.description).slice(0, 100)}
                      {x.national_cert_scale ? (
                        <>
                          {' · '}
                          <AwardIcon size={12} className="ico" /> {t('panel_national_cert')}
                        </>
                      ) : ''}
                    </small>
                  </td>
                  <td>
                    <span className="badge">{str(x.category)}</span>
                  </td>
                  <td className="muted small">
                    {str(x.word_limit_min)}-{str(x.word_limit_max)} {t('words')} ·{' '}
                    {str(x.time_limit_minutes)} {t('minutes')} · {t('panel_grammar_short')}{' '}
                    {str(x.grammar_strictness)}%
                  </td>
                  <td>
                    <span className={`badge ${x.is_active ? 'green' : ''}`}>
                      {x.is_active ? t('panel_active') : t('status_inactive')}
                    </span>{' '}
                    {x.has_password ? (
                      <span className="badge" title={t('panel_topic_password_set_hint')}>
                        <LockIcon size={12} className="ico" /> {t('panel_topic_password_set')}
                      </span>
                    ) : null}
                  </td>
                  <td style={{ whiteSpace: 'nowrap' }}>
                    <button className="btn sm ghost" onClick={() => startEdit(x)}>
                      {t('edit')}
                    </button>{' '}
                    {x.has_password ? (
                      <>
                        <button className="btn sm ghost" onClick={() => void removePassword(x.id as number)}>
                          {t('panel_topic_password_remove')}
                        </button>{' '}
                      </>
                    ) : null}
                    <button className="btn sm danger" onClick={() => remove(x.id as number)}>
                      {t('delete')}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
