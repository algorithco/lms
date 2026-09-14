import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useLang } from '../i18n/LangContext';
import { Panel } from '../lib/api';
import { str } from '../lib/billingPanelGames';

/**
 * Tests list — parity with templates/panel/test_list.html behaviour:
 * search (q), status filter, inline status change
 * (POST /api/v1/panel/tests/<id>/status/), edit, questions, delete.
 */
export default function PanelTests() {
  const { t } = useLang();
  const [tests, setTests] = useState<Record<string, unknown>[]>([]);
  const [statuses, setStatuses] = useState<{ value: string; label: string }[]>([]);
  const [q, setQ] = useState('');
  const [status, setStatus] = useState('');
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(() => {
    Panel.tests(q, status)
      .then((r) => {
        setTests(r.results as unknown as Record<string, unknown>[]);
        setStatuses(r.statuses);
        setErr(null);
      })
      .catch((e: unknown) => setErr(e instanceof Error ? e.message : 'Failed.'));
  }, [q, status]);

  useEffect(() => {
    const id = setTimeout(load, 300);
    return () => clearTimeout(id);
  }, [load]);

  const remove = async (id: number | string) => {
    if (!window.confirm(t('panel_confirm_delete'))) return;
    try {
      await Panel.deleteTest(id);
      load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : 'Failed.');
    }
  };

  const setSt = async (id: number | string, s: string) => {
    try {
      await Panel.setStatus(id, s);
      setErr(null);
      load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : t('panel_msg_invalid_status'));
    }
  };

  return (
    <div>
      <h1>{t('panel_test_list')}</h1>
      {err && <p className="error">{err}</p>}
      <div className="toolbar">
        <input
          placeholder={t('panel_search_tests')}
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <select value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">{t('all')}</option>
          {statuses.map((s) => (
            <option key={s.value} value={s.value}>
              {s.label}
            </option>
          ))}
        </select>
        <Link className="btn primary sm" to="/panel/tests/new">
          {t('panel_new_test')}
        </Link>
      </div>
      {tests.length === 0 ? (
        <div className="card">
          <p>
            <strong>{t('no_tests_created_title')}</strong>
          </p>
          <p className="muted small">{t('no_tests_created_hint')}</p>
        </div>
      ) : (
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th>{t('th_test_name')}</th>
                <th>{t('th_course')}</th>
                <th>{t('th_questions')}</th>
                <th>{t('status')}</th>
                <th>{t('th_actions')}</th>
              </tr>
            </thead>
            <tbody>
              {tests.map((x) => (
                <tr key={str(x.id)}>
                  <td>{str(x.title)}</td>
                  <td>{str(x.course_title)}</td>
                  <td>{str(x.q_count ?? '', '—')}</td>
                  <td>
                    <select
                      value={str(x.status)}
                      onChange={(e) => setSt(x.id as number, e.target.value)}
                      aria-label="status"
                    >
                      {statuses.map((s) => (
                        <option key={s.value} value={s.value}>
                          {s.label}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td style={{ whiteSpace: 'nowrap' }}>
                    <Link className="btn sm ghost" to={`/panel/tests/${str(x.id)}/questions`}>
                      {t('th_questions')}
                    </Link>{' '}
                    <Link className="btn sm ghost" to={`/panel/tests/${str(x.id)}/edit`}>
                      {t('edit')}
                    </Link>{' '}
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
