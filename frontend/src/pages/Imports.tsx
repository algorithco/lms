import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { useLang } from '../i18n/LangContext';
import { School } from '../lib/api';
import { UploadIcon } from '../components/icons';
import type { ImportRowError, StudentImportResult, TestImportCourse, TestImportResult } from '../lib/school';
import {
  STUDENT_CSV_SAMPLE,
  TEST_CSV_SAMPLE,
  downloadCsv,
  errMessage,
  guardCsv,
  normaliseRowErrors,
} from '../lib/school';

export default function Imports() {
  const { t } = useLang();
  const [courses, setCourses] = useState<TestImportCourse[]>([]);
  const [err, setErr] = useState<string | null>(null);

  // ---- Students import (POST /api/v1/school/import-students/) ----
  const [sfile, setSfile] = useState<File | null>(null);
  const [sResult, setSResult] = useState<StudentImportResult | null>(null);

  // ---- Bulk test import (GET+POST /api/v1/school/import-test/) ----
  const [tfile, setTfile] = useState<File | null>(null);
  const [title, setTitle] = useState('');
  const [courseId, setCourseId] = useState('');
  const [timeLimit, setTimeLimit] = useState('30');
  const [passPct, setPassPct] = useState('60');
  const [tResult, setTResult] = useState<TestImportResult | null>(null);

  const [busyStudents, setBusyStudents] = useState(false);
  const [busyTest, setBusyTest] = useState(false);

  useEffect(() => {
    let alive = true;
    // GET /api/v1/school/import-test/ — course options for the teacher.
    School.importTestCourses()
      .then((r) => {
        if (alive) setCourses((r.courses as TestImportCourse[]) ?? []);
      })
      .catch(() => {
        if (alive) setCourses([]);
      });
    return () => {
      alive = false;
    };
  }, []);

  const pick = (setter: (f: File | null) => void) => (e: { target: { files: FileList | null } }) =>
    setter(e.target.files?.[0] ?? null);

  const importStudents = async (e: FormEvent) => {
    e.preventDefault();
    const g = guardCsv(sfile);
    if (g || !sfile) {
      setErr(g ?? t('import_no_file'));
      return;
    }
    setBusyStudents(true);
    setErr(null);
    setSResult(null);
    try {
      const r = (await School.importStudents(sfile)) as unknown as {
        created: number;
        skipped: number;
        errors: unknown;
      };
      setSResult({ created: r.created ?? 0, skipped: r.skipped ?? 0, errors: normaliseRowErrors(r.errors) });
    } catch (e2: unknown) {
      setErr(errMessage(e2));
    } finally {
      setBusyStudents(false);
    }
  };

  const importTest = async (e: FormEvent) => {
    e.preventDefault();
    const g = guardCsv(tfile);
    if (g || !tfile) {
      setErr(g ?? t('import_no_file'));
      return;
    }
    if (!title.trim()) {
      setErr(t('import_test_name_required'));
      return;
    }
    if (!courseId) {
      setErr(t('import_select_course'));
      return;
    }
    setBusyTest(true);
    setErr(null);
    setTResult(null);
    try {
      const fd = new FormData();
      fd.append('csv_file', tfile);
      fd.append('test_title', title.trim());
      fd.append('course_id', courseId);
      fd.append('time_limit', timeLimit || '30');
      fd.append('pass_percentage', passPct || '60');
      const r = (await School.importTest(fd)) as unknown as {
        success: boolean;
        test_id: number | null;
        questions_created: number;
        errors: unknown;
      };
      setTResult({
        success: !!r.success,
        test_id: r.test_id ?? null,
        questions_created: r.questions_created ?? 0,
        errors: normaliseRowErrors(r.errors),
      });
    } catch (e2: unknown) {
      setErr(errMessage(e2));
    } finally {
      setBusyTest(false);
    }
  };

  const errorTable = (errors: ImportRowError[]) => (
    <div className="card" style={{ borderColor: '#fca5a5' }}>
      <h3>
        ❌ {t('import_errors')} ({errors.length})
      </h3>
      <div className="table-wrap">
        <table className="data">
          <thead>
            <tr>
              <th>{t('import_row')}</th>
              <th>{t('import_error')}</th>
            </tr>
          </thead>
          <tbody>
            {errors.map((row) => (
              <tr key={row.row}>
                <td>{row.row}</td>
                <td>{row.message}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );

  return (
    <div>
      <h1>
        <UploadIcon size={24} className="ico" /> {t('import_students_title')}
      </h1>
      {err && <p className="error">{err}</p>}

      <div className="grid" style={{ gridTemplateColumns: '1fr' }}>
        {/* Students CSV import — parity with csv_import.html. */}
        <form onSubmit={importStudents} className="card form" style={{ maxWidth: '100%' }}>
          <h2>📥 {t('import_students_title')}</h2>
          <p className="muted small">{t('import_students_desc')}</p>
          <div className="card" style={{ background: '#eff6ff' }}>
            <p className="muted small" style={{ fontFamily: 'monospace' }}>
              email,first_name,last_name,phone
            </p>
            <ul className="muted small">
              <li>✅ {t('import_required_cols')}</li>
              <li>✅ {t('import_optional_phone')}</li>
              <li>✅ {t('import_duplicates_skip')}</li>
              <li>✅ {t('import_auto_password')}</li>
              <li>✅ {t('import_welcome_email')}</li>
            </ul>
          </div>
          <label>
            {t('import_choose_file')}
            <input type="file" accept=".csv,text/csv" onChange={pick(setSfile)} />
          </label>
          {sfile && <p className="muted small">📄 {sfile.name}</p>}
          <p className="muted small">{t('import_file_type')}</p>
          <div className="row">
            <button className="btn primary" disabled={busyStudents}>
              📥 {t('import_submit')}
            </button>
            <button
              type="button"
              className="btn sm ghost"
              onClick={() => downloadCsv('students_template.csv', STUDENT_CSV_SAMPLE)}
            >
              {t('import_download_sample')}
            </button>
          </div>
        </form>

        {/* Students result — parity with csv_import_result.html summary + errors. */}
        {sResult && (
          <>
            <div className="grid">
              <div className="card stat stat-gradient-blue">
                <span className="stat-label">{t('import_total_rows')}</span>
                <span className="stat-value">
                  {sResult.created + sResult.skipped + sResult.errors.length}
                </span>
              </div>
              <div className="card stat stat-gradient-green">
                <span className="stat-label">{t('import_created')}</span>
                <span className="stat-value">{sResult.created}</span>
              </div>
              <div className="card stat stat-gradient-amber">
                <span className="stat-label">{t('import_skipped')}</span>
                <span className="stat-value">{sResult.skipped}</span>
              </div>
            </div>
            <p className="badge green">
              ✅ {t('import_created_students')}: {sResult.created} · {t('import_created_hint')}
            </p>
            {sResult.errors.length > 0 && errorTable(sResult.errors)}
          </>
        )}

        {/* Bulk test import — parity with bulk_test_import.html. */}
        <form onSubmit={importTest} className="card form" style={{ maxWidth: '100%' }}>
          <h2>📝 {t('import_tests_title')}</h2>
          <p className="muted small">{t('import_tests_desc')}</p>
          <div className="card" style={{ background: '#eff6ff' }}>
            <p className="muted small" style={{ fontFamily: 'monospace' }}>
              question,choice_a,choice_b,choice_c,choice_d,correct,points,explanation
            </p>
            <ul className="muted small">
              <li>✅ {t('import_test_required')}</li>
              <li>✅ {t('import_test_optional')}</li>
              <li>✅ {t('import_correct_hint')}</li>
              <li>✅ {t('import_points_hint')}</li>
            </ul>
          </div>
          <label>
            {t('import_test_name')} *
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Masalan: Matematika testi - 1-qism"
              required
            />
          </label>
          <label>
            {t('import_course')} *
            <select value={courseId} onChange={(e) => setCourseId(e.target.value)} required>
              <option value="">{t('import_select_course')}</option>
              {courses.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.title}
                </option>
              ))}
            </select>
          </label>
          <div className="row">
            <label>
              {t('import_time_limit')}
              <input
                type="number"
                min={1}
                max={600}
                value={timeLimit}
                onChange={(e) => setTimeLimit(e.target.value)}
              />
            </label>
            <label>
              {t('import_pass_pct')}
              <input
                type="number"
                min={0}
                max={100}
                value={passPct}
                onChange={(e) => setPassPct(e.target.value)}
              />
            </label>
          </div>
          <label>
            {t('import_csv_file')} *
            <input type="file" accept=".csv,text/csv" onChange={pick(setTfile)} />
          </label>
          {tfile && <p className="muted small">📄 {tfile.name}</p>}
          <div className="row">
            <button className="btn primary" disabled={busyTest}>
              📝 {t('import_submit')}
            </button>
            <button
              type="button"
              className="btn sm ghost"
              onClick={() => downloadCsv('test_template.csv', TEST_CSV_SAMPLE)}
            >
              {t('import_download_sample')}
            </button>
          </div>
        </form>

        {/* Test import result — success summary + per-row errors. */}
        {tResult && (
          <>
            {tResult.success ? (
              <p className="badge green">
                ✅ {t('panel_msg_test_created')}
                {tResult.test_id ? ` · ID ${tResult.test_id}` : ''} ·{' '}
                {t('imp_questions_created')}: {tResult.questions_created}
              </p>
            ) : (
              <p className="error">❌ {t('error')}</p>
            )}
            {tResult.errors.length > 0 && errorTable(tResult.errors)}
          </>
        )}
      </div>
    </div>
  );
}
