import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { useLang } from '../i18n/LangContext';
import { Panel, School, api } from '../lib/api';
import { num, str } from '../lib/billingPanelGames';

/**
 * Test create/edit — full TestAdminSerializer fields, parity with
 * templates/panel/test_form.html: title, description, course, module,
 * time_limit_minutes, max_attempts, pass_percentage, difficulty, status
 * + shuffle_questions / shuffle_choices / show_results_immediately.
 */
export default function PanelTestForm() {
  const { id } = useParams();
  const isNew = !id || id === 'new';
  const testId = isNew ? null : id;
  const navigate = useNavigate();
  const { t } = useLang();
  const [courses, setCourses] = useState<{ id: number; title: string }[]>([]);
  const [form, setForm] = useState<Record<string, unknown>>({
    title: '',
    description: '',
    course: '',
    module: '',
    time_limit_minutes: 30,
    max_attempts: 1,
    pass_percentage: 60,
    difficulty: 'medium',
    status: 'draft',
    show_results_immediately: true,
    shuffle_questions: false,
    shuffle_choices: true,
  });
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    School.importTestCourses()
      .then((r) => setCourses(r.courses))
      .catch(() => setCourses([]));
    if (testId) {
      // GET /api/v1/panel/tests/<id>/ (test_detail_view supports GET).
      api<Record<string, unknown>>(`/api/v1/panel/tests/${testId}/`)
        .then((found) => setForm((f) => ({ ...f, ...found })))
        .catch((e: unknown) => setErr(e instanceof Error ? e.message : 'Failed.'));
    }
  }, [testId]);

  const set =
    (k: string) =>
    (e: { target: { value: string; checked?: boolean; type?: string } }) => {
      const v = e.target.type === 'checkbox' ? !!e.target.checked : e.target.value;
      setForm((f) => ({ ...f, [k]: v }));
    };

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      const moduleRaw = str(form.module).trim();
      const payload: Record<string, unknown> = {
        title: str(form.title).trim(),
        description: str(form.description),
        course: Number(form.course),
        time_limit_minutes: num(form.time_limit_minutes),
        max_attempts: num(form.max_attempts),
        pass_percentage: num(form.pass_percentage),
        difficulty: str(form.difficulty) || 'medium',
        status: str(form.status) || 'draft',
        show_results_immediately: Boolean(form.show_results_immediately),
        shuffle_questions: Boolean(form.shuffle_questions),
        shuffle_choices: Boolean(form.shuffle_choices),
      };
      // module is an optional FK — omit when empty (serializer expects id).
      if (moduleRaw !== '' && !Number.isNaN(Number(moduleRaw))) {
        payload.module = Number(moduleRaw);
      }
      if (isNew) {
        const created = (await Panel.createTest(payload)) as Record<string, unknown>;
        navigate(`/panel/tests/${str(created.id)}/questions`);
      } else {
        await Panel.updateTest(testId as string, payload);
        navigate('/panel/tests');
      }
    } catch (e2) {
      setErr(e2 instanceof Error ? e2.message : 'Save failed.');
      setBusy(false);
    }
  };

  return (
    <div>
      <h1>{isNew ? t('panel_new_test') : t('panel_edit_test')}</h1>
      {err && <p className="error">{err}</p>}
      <form onSubmit={onSubmit} className="form">
        <label>
          {t('th_test_name')}
          <input value={str(form.title)} onChange={set('title')} required />
        </label>
        <label>
          {t('description')}
          <textarea value={str(form.description)} onChange={set('description')} rows={3} />
        </label>
        <div className="row">
          <label>
            {t('th_course')}
            <select
              value={str(form.course ?? '')}
              onChange={(e) => setForm((f) => ({ ...f, course: e.target.value }))}
              required
            >
              <option value="">—</option>
              {courses.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.title}
                </option>
              ))}
            </select>
          </label>
          <label>
            {t('module')} ({t('none')})
            <input
              value={str(form.module ?? '')}
              onChange={set('module')}
              placeholder="—"
              inputMode="numeric"
            />
          </label>
        </div>
        <div className="row">
          <label>
            {t('panel_time_limit')}
            <input
              type="number"
              min={0}
              value={num(form.time_limit_minutes)}
              onChange={set('time_limit_minutes')}
            />
          </label>
          <label>
            {t('panel_max_attempts')}
            <input
              type="number"
              min={0}
              value={num(form.max_attempts)}
              onChange={set('max_attempts')}
            />
          </label>
          <label>
            {t('panel_pass_pct')}
            <input
              type="number"
              min={0}
              max={100}
              value={num(form.pass_percentage)}
              onChange={set('pass_percentage')}
            />
          </label>
        </div>
        <div className="row">
          <label>
            {t('difficulty')}
            <select value={str(form.difficulty || 'medium')} onChange={set('difficulty')}>
              <option value="easy">easy</option>
              <option value="medium">medium</option>
              <option value="hard">hard</option>
            </select>
          </label>
          <label>
            {t('status')}
            <select value={str(form.status || 'draft')} onChange={set('status')}>
              <option value="draft">draft</option>
              <option value="published">published</option>
              <option value="archived">archived</option>
            </select>
          </label>
        </div>
        <div className="row">
          <label style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
            <input
              type="checkbox"
              checked={Boolean(form.shuffle_questions)}
              onChange={set('shuffle_questions')}
            />
            {t('panel_shuffle_questions')}
          </label>
          <label style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
            <input
              type="checkbox"
              checked={Boolean(form.shuffle_choices)}
              onChange={set('shuffle_choices')}
            />
            {t('panel_shuffle_choices')}
          </label>
          <label style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
            <input
              type="checkbox"
              checked={Boolean(form.show_results_immediately)}
              onChange={set('show_results_immediately')}
            />
            {t('panel_show_results')}
          </label>
        </div>
        <div className="row">
          <button className="btn primary" disabled={busy}>
            {busy ? t('loading') : isNew ? t('panel_create_and_questions') : t('save_changes')}
          </button>
          <Link className="btn" to="/panel/tests">
            {t('cancel')}
          </Link>
        </div>
      </form>
    </div>
  );
}
