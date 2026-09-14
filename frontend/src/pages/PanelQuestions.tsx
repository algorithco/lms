import { useCallback, useEffect, useMemo, useState } from 'react';
import type { FormEvent } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useLang } from '../i18n/LangContext';
import { Panel } from '../lib/api';
import { num, str } from '../lib/billingPanelGames';

interface Choice {
  id?: number;
  text: string;
  is_correct: boolean;
  position: number;
}

interface QForm {
  passage: string;
  text: string;
  question_type: string;
  correct_text: string;
  points: number;
  position: number;
  explanation: string;
  choices: Choice[];
}

const EMPTY: QForm = {
  passage: '',
  text: '',
  question_type: 'single',
  correct_text: '',
  points: 1,
  position: 0,
  explanation: '',
  choices: [
    { text: '', is_correct: true, position: 0 },
    { text: '', is_correct: false, position: 1 },
  ],
};

/**
 * Questions manager — full QuestionAdminSerializer model, parity with
 * templates/panel/question_manage.html + question_form.html:
 * passage, text, question_type (single/multiple/text), correct_text,
 * points, position, explanation, nested choices[] + live preview.
 * Endpoints: GET/POST /panel/tests/<id>/questions/,
 * PATCH/DELETE /panel/tests/<id>/questions/<qid>/.
 */
export default function PanelQuestions() {
  const { id = '' } = useParams();
  const { t } = useLang();
  const [test, setTest] = useState<Record<string, unknown> | null>(null);
  const [questions, setQuestions] = useState<Record<string, unknown>[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<number | string | null>(null);
  const [form, setForm] = useState<QForm>(EMPTY);

  const load = useCallback(() => {
    Panel.questions(id)
      .then((r) => {
        setTest(r.test as unknown as Record<string, unknown>);
        setQuestions(r.results as unknown as Record<string, unknown>[]);
        setErr(null);
      })
      .catch((e: unknown) => setErr(e instanceof Error ? e.message : 'Failed.'));
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  const startCreate = () => {
    setEditingId(null);
    setForm({ ...EMPTY, position: questions.length });
    setShowForm(true);
  };

  const startEdit = (q: Record<string, unknown>) => {
    const ch = ((q.choices ?? []) as Choice[]).map((c, i) => ({
      id: c.id,
      text: str(c.text),
      is_correct: Boolean(c.is_correct),
      position: num(c.position, i),
    }));
    setEditingId(q.id as number);
    setForm({
      passage: str(q.passage),
      text: str(q.text),
      question_type: str(q.question_type, 'single'),
      correct_text: str(q.correct_text),
      points: num(q.points, 1),
      position: num(q.position),
      explanation: str(q.explanation),
      choices:
        ch.length > 0
          ? ch
          : [
              { text: '', is_correct: true, position: 0 },
              { text: '', is_correct: false, position: 1 },
            ],
    });
    setShowForm(true);
  };

  const setF = (k: keyof QForm, v: QForm[keyof QForm]) =>
    setForm((f) => ({ ...f, [k]: v }) as QForm);

  const addChoice = () =>
    setForm((f) => ({
      ...f,
      choices: [...f.choices, { text: '', is_correct: false, position: f.choices.length }],
    }));

  const removeChoice = (i: number) =>
    setForm((f) => ({
      ...f,
      choices: f.choices.filter((_, j) => j !== i).map((c, j) => ({ ...c, position: j })),
    }));

  const previewChoices = useMemo(
    () => form.choices.filter((c) => c.text.trim()),
    [form.choices],
  );

  const typeLabel = (v: unknown) => {
    const s = str(v);
    if (s === 'multiple') return t('panel_type_multiple');
    if (s === 'text') return t('panel_type_text');
    return t('panel_type_single');
  };

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setErr(null);
    const isText = form.question_type === 'text';
    const kept = form.choices
      .map((c, i) => ({ ...c, position: i }))
      .filter((c) => c.text.trim());
    if (!isText && kept.length < 2) {
      setErr(t('panel_choices_hint'));
      return;
    }
    if (!isText && !kept.some((c) => c.is_correct)) {
      setErr(t('panel_choices_hint'));
      return;
    }
    const payload: Record<string, unknown> = {
      passage: form.passage,
      text: form.text,
      question_type: form.question_type,
      correct_text: isText ? form.correct_text : '',
      points: form.points,
      position: form.position,
      explanation: form.explanation,
      choices: isText ? [] : kept.map(({ text, is_correct, position }) => ({ text, is_correct, position })),
    };
    try {
      if (editingId === null) {
        await Panel.createQuestion(id, payload);
      } else {
        await Panel.updateQuestion(id, editingId, payload);
      }
      setShowForm(false);
      setEditingId(null);
      setForm(EMPTY);
      load();
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : 'Save failed.');
    }
  };

  const remove = async (qid: number | string) => {
    if (!window.confirm(t('panel_confirm_delete'))) return;
    try {
      await Panel.deleteQuestion(id, qid);
      load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : 'Failed.');
    }
  };

  const status = str(test?.status);

  return (
    <div>
      <p>
        <Link to="/panel/tests">← {t('back')}</Link>
      </p>
      <h1>
        {t('questions')}: {test ? str(test.title) : `#${id}`}
      </h1>
      {status && (
        <p className="muted small">
          <span className="badge">{status}</span> · {questions.length} {t('questions')}
        </p>
      )}
      {err && <p className="error">{err}</p>}
      <div className="toolbar">
        <button className="btn primary sm" onClick={showForm ? () => setShowForm(false) : startCreate}>
          {showForm ? t('cancel') : t('panel_new_question')}
        </button>
      </div>

      {showForm && (
        <div className="grid" style={{ gridTemplateColumns: '1fr', gap: 16 }}>
          <form onSubmit={onSubmit} className="card form" style={{ maxWidth: '100%' }}>
            <h2>{editingId === null ? t('panel_new_question') : t('panel_edit_question')}</h2>
            <div className="row">
              <label>
                {t('panel_question_type')}
                <select
                  value={form.question_type}
                  onChange={(e) => setF('question_type', e.target.value)}
                >
                  <option value="single">{t('panel_type_single')}</option>
                  <option value="multiple">{t('panel_type_multiple')}</option>
                  <option value="text">{t('panel_type_text')}</option>
                </select>
              </label>
              <label>
                {t('panel_points')}
                <input
                  type="number"
                  min={1}
                  value={form.points}
                  onChange={(e) => setF('points', Number(e.target.value))}
                />
              </label>
              <label>
                {t('panel_position')}
                <input
                  type="number"
                  min={0}
                  value={form.position}
                  onChange={(e) => setF('position', Number(e.target.value))}
                />
              </label>
            </div>
            <label>
              {t('panel_passage')}
              <textarea
                value={form.passage}
                onChange={(e) => setF('passage', e.target.value)}
                rows={2}
                placeholder={t('panel_passage_hint')}
              />
            </label>
            <label>
              {t('panel_question_text')}
              <textarea
                value={form.text}
                onChange={(e) => setF('text', e.target.value)}
                required
                rows={3}
              />
            </label>
            {form.question_type === 'text' ? (
              <label>
                {t('panel_correct_text')}
                <input
                  value={form.correct_text}
                  onChange={(e) => setF('correct_text', e.target.value)}
                />
              </label>
            ) : (
              <>
                {form.choices.map((c, i) => (
                  <div key={i} className="row" style={{ alignItems: 'center' }}>
                    <span className="badge">{String.fromCharCode(65 + i)}</span>
                    <input
                      style={{ flex: 3 }}
                      placeholder={t('panel_choice_placeholder')}
                      value={c.text}
                      onChange={(e) =>
                        setForm((f) => ({
                          ...f,
                          choices: f.choices.map((x, j) =>
                            j === i ? { ...x, text: e.target.value } : x,
                          ),
                        }))
                      }
                    />
                    <label
                      style={{ flex: 1, flexDirection: 'row', alignItems: 'center', gap: 6 }}
                    >
                      <input
                        type="checkbox"
                        checked={c.is_correct}
                        onChange={(e) =>
                          setForm((f) => ({
                            ...f,
                            choices: f.choices.map((x, j) =>
                              j === i ? { ...x, is_correct: e.target.checked } : x,
                            ),
                          }))
                        }
                      />
                      {t('panel_correct')}
                    </label>
                    {form.choices.length > 2 && (
                      <button
                        type="button"
                        className="btn sm danger"
                        onClick={() => removeChoice(i)}
                      >
                        ✕
                      </button>
                    )}
                  </div>
                ))}
                {form.choices.length < 6 && (
                  <button type="button" className="btn sm ghost" onClick={addChoice}>
                    + {t('panel_add_choice')}
                  </button>
                )}
                <p className="muted small">{t('panel_choices_hint')}</p>
              </>
            )}
            <label>
              {t('panel_explanation')}
              <textarea
                value={form.explanation}
                onChange={(e) => setF('explanation', e.target.value)}
                rows={2}
              />
            </label>
            <div className="row">
              <button className="btn primary">
                {editingId === null ? t('panel_add_question_btn') : t('save_changes')}
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

          {/* Live preview — mirrors question_form.html preview pane. */}
          <div className="card">
            <h3>👁 {t('panel_live_preview')}</h3>
            <p className="muted small">
              <span className="badge">{typeLabel(form.question_type)}</span> {form.points}{' '}
              {t('points')}
            </p>
            {form.passage.trim() && (
              <p className="muted small" style={{ fontStyle: 'italic' }}>
                📖 {form.passage}
              </p>
            )}
            <p>
              <strong>{form.text || t('panel_preview_placeholder')}</strong>
            </p>
            {form.question_type === 'text' ? (
              form.correct_text.trim() && <p className="muted small">✓ {form.correct_text}</p>
            ) : (
              <div className="row" style={{ flexWrap: 'wrap' }}>
                {previewChoices.map((c, i) => (
                  <span key={i} className={`badge ${c.is_correct ? 'green' : ''}`}>
                    {c.is_correct ? '✓ ' : ''}
                    {c.text}
                  </span>
                ))}
              </div>
            )}
            <p className="muted small">{t('panel_preview_hint')}</p>
          </div>
        </div>
      )}

      <div className="grid" style={{ marginTop: 16 }}>
        {questions.map((q, i) => (
          <div key={str(q.id)} className="card">
            <strong>
              Q{i + 1}. {str(q.text).slice(0, 160)}
            </strong>
            <p className="muted small">
              <span className="badge">{typeLabel(q.question_type)}</span> {str(q.points)}{' '}
              {t('points')}
              {num(q.position) > 0 ? ` · #${str(q.position)}` : ''}
            </p>
            {str(q.passage) && (
              <p className="muted small" style={{ fontStyle: 'italic' }}>
                📖 {str(q.passage).slice(0, 200)}
              </p>
            )}
            {str(q.question_type) === 'text' ? (
              <p className="muted small">✓ {str(q.correct_text)}</p>
            ) : (
              <ul className="muted small">
                {((q.choices as Choice[]) || []).map((c) => (
                  <li key={str(c.id ?? c.text)}>
                    {c.is_correct ? '✓ ' : '· '}
                    {c.text}
                  </li>
                ))}
              </ul>
            )}
            {str(q.explanation) && (
              <p className="muted small">
                {t('panel_explanation')}: {str(q.explanation).slice(0, 200)}
              </p>
            )}
            <div className="row">
              <button className="btn sm ghost" onClick={() => startEdit(q)}>
                {t('edit')}
              </button>
              <button className="btn sm danger" onClick={() => remove(q.id as number)}>
                {t('delete')}
              </button>
            </div>
          </div>
        ))}
      </div>
      {questions.length === 0 && !showForm && (
        <div className="card">
          <p>
            <strong>{t('panel_no_questions')}</strong>
          </p>
          <p className="muted small">{t('panel_no_questions_hint')}</p>
        </div>
      )}
    </div>
  );
}
