import { useCallback, useEffect, useMemo, useState } from 'react';
import { useLang } from '../i18n/LangContext';
import {
  apiErrorBody,
  School,
  type AttendanceReport,
  type AttendanceRosterRow,
  type AttendanceSessionDetail,
  type AttendanceSessionSummary,
  type AttendanceStatus,
} from '../lib/api';
import { errMessage } from '../lib/school';

/**
 * Teacher attendance workspace.
 *
 * Loads the teacher's own groups, opens (or resolves) the register for a
 * group/date, lets the teacher mark each student 4-way, and finalizes.
 *
 * Two deliberate behaviours:
 *  - a student with `status === null` is UNMARKED and is never silently
 *    treated as absent;
 *  - finalizing with unmarked students returns 409, and the panel requires an
 *    explicit confirmation before retrying with `mark_unmarked_as_absent`.
 */

const STATUS_ORDER: AttendanceStatus[] = ['present', 'absent', 'late', 'excused'];

const STATUS_I18N: Record<AttendanceStatus, string> = {
  present: 'attendance_present',
  absent: 'attendance_absent',
  late: 'attendance_late',
  excused: 'attendance_excused',
};

const STATUS_LABEL_FALLBACK: Record<AttendanceStatus, string> = {
  present: 'Keldi',
  absent: 'Kelmadi',
  late: 'Kechikdi',
  excused: 'Sababli',
};

interface LocalMark {
  status: AttendanceStatus;
  late_minutes: number;
  note: string;
}

interface GroupOption {
  id: number;
  name: string;
}

/** Local (unsaved) edits, keyed by student id, layered over the server roster. */
type DraftMarks = Record<number, LocalMark>;

function todayIso(): string {
  const now = new Date();
  const offsetMs = now.getTimezoneOffset() * 60_000;
  return new Date(now.getTime() - offsetMs).toISOString().slice(0, 10);
}

function statusLabel(t: (k: string) => string, status: AttendanceStatus): string {
  const key = STATUS_I18N[status];
  const translated = t(key);
  // `t()` returns the key itself when a translation is missing; fall back to
  // the canonical Uzbek label rather than rendering a raw key.
  return translated === key ? STATUS_LABEL_FALLBACK[status] : translated;
}

export default function AttendancePanel() {
  const { t } = useLang();

  const [groups, setGroups] = useState<GroupOption[]>([]);
  const [groupId, setGroupId] = useState<number | null>(null);
  const [lessonDate, setLessonDate] = useState<string>(todayIso());
  const [session, setSession] = useState<AttendanceSessionDetail | null>(null);
  const [sessions, setSessions] = useState<AttendanceSessionSummary[]>([]);
  const [report, setReport] = useState<AttendanceReport | null>(null);
  const [draft, setDraft] = useState<DraftMarks>({});
  const [unmarkedWarning, setUnmarkedWarning] = useState<string[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [ready, setReady] = useState(false);

  // -- Load the teacher's groups once --------------------------------------
  useEffect(() => {
    let alive = true;
    School.groups()
      .then((rows) => {
        if (!alive) return;
        const list: GroupOption[] = (rows ?? [])
          .map((row) => {
            const r = row as { id?: unknown; name?: unknown };
            return { id: Number(r.id), name: String(r.name ?? '') };
          })
          .filter((g) => Number.isFinite(g.id));
        setGroups(list);
        setGroupId((current) => current ?? (list.length > 0 ? list[0].id : null));
        setReady(true);
      })
      .catch((e: unknown) => {
        if (alive) {
          setErr(errMessage(e));
          setReady(true);
        }
      });
    return () => {
      alive = false;
    };
  }, []);

  const loadForGroup = useCallback(
    async (targetGroupId: number, date: string) => {
      setErr(null);
      setNotice(null);
      setUnmarkedWarning([]);
      try {
        const [sessionList, reportData] = await Promise.all([
          School.attendanceSessions({ group_id: targetGroupId, start: date, end: date }),
          School.attendanceReport({ group_id: targetGroupId, daily: true }),
        ]);
        setSessions(Array.isArray(sessionList) ? sessionList : []);
        setReport(reportData);
        const sameDay = (Array.isArray(sessionList) ? sessionList : []).find(
          (s) => s.lesson_date === date,
        );
        if (sameDay) {
          const detail = await School.attendanceSession(sameDay.session_id);
          setSession(detail);
          setDraft({});
        } else {
          setSession(null);
          setDraft({});
        }
      } catch (e: unknown) {
        setErr(errMessage(e));
      }
    },
    [],
  );

  useEffect(() => {
    if (groupId === null) return;
    void loadForGroup(groupId, lessonDate);
  }, [groupId, lessonDate, loadForGroup]);

  // -- Derived roster with local edits applied -----------------------------
  const roster: AttendanceRosterRow[] = useMemo(() => {
    if (!session) return [];
    // Defensive: the finalize response is a summary without a roster, so never
    // assume `roster` is present.
    return (session.roster ?? []).map((row) => {
      const local = draft[row.student_id];
      if (!local) return row;
      return {
        ...row,
        status: local.status,
        status_label: statusLabel(t, local.status),
        late_minutes:
          local.status === 'late' ? local.late_minutes : 0,
        note: local.note,
        marked: true,
      };
    });
  }, [session, draft, t]);

  const counts = useMemo(() => {
    const base = {
      roster_size: roster.length,
      marked: 0,
      unmarked: 0,
      present: 0,
      late: 0,
      absent: 0,
      excused: 0,
    };
    for (const row of roster) {
      if (!row.status) {
        base.unmarked += 1;
        continue;
      }
      base.marked += 1;
      base[row.status] += 1;
    }
    return base;
  }, [roster]);

  const isFinalized = session?.status === 'finalized';

  // -- Actions -------------------------------------------------------------
  async function openSession() {
    if (groupId === null) return;
    setBusy(true);
    setErr(null);
    setNotice(null);
    try {
      const detail = await School.attendanceOpenSession({
        group_id: groupId,
        lesson_date: lessonDate,
      });
      setSession(detail);
      setDraft({});
      setUnmarkedWarning([]);
      await loadForGroup(groupId, lessonDate);
    } catch (e: unknown) {
      setErr(errMessage(e));
    } finally {
      setBusy(false);
    }
  }

  function setStatus(studentId: number, status: AttendanceStatus) {
    setDraft((prev) => {
      const existing = prev[studentId];
      return {
        ...prev,
        [studentId]: {
          status,
          late_minutes: status === 'late' ? existing?.late_minutes ?? 0 : 0,
          note: existing?.note ?? '',
        },
      };
    });
  }

  function setLateMinutes(studentId: number, minutes: number) {
    setDraft((prev) => ({
      ...prev,
      [studentId]: {
        status: 'late',
        late_minutes: Number.isFinite(minutes) ? Math.max(0, minutes) : 0,
        note: prev[studentId]?.note ?? '',
      },
    }));
  }

  async function saveMarks() {
    if (!session) return;
    const marks = Object.entries(draft).map(([studentId, mark]) => ({
      student_id: Number(studentId),
      status: mark.status,
      late_minutes: mark.status === 'late' ? mark.late_minutes : 0,
      note: mark.note,
    }));
    if (marks.length === 0) return;
    setBusy(true);
    setErr(null);
    setNotice(null);
    try {
      const detail = await School.attendanceMark(session.session_id, marks);
      setSession(detail);
      setDraft({});
      setNotice(t('attendance_saved'));
      if (groupId !== null) {
        setReport(await School.attendanceReport({ group_id: groupId, daily: true }));
      }
    } catch (e: unknown) {
      setErr(errMessage(e));
    } finally {
      setBusy(false);
    }
  }

  async function markAllPresent() {
    if (!session) return;
    setBusy(true);
    setErr(null);
    setNotice(null);
    try {
      const detail = await School.attendanceMarkAllPresent(session.session_id);
      setSession(detail);
      setDraft({});
      setNotice(t('attendance_saved'));
    } catch (e: unknown) {
      setErr(errMessage(e));
    } finally {
      setBusy(false);
    }
  }

  async function finalize(confirmAbsences: boolean) {
    if (!session) return;
    setBusy(true);
    setErr(null);
    setNotice(null);
    try {
      const summary = await School.attendanceFinalize(session.session_id, confirmAbsences);
      setUnmarkedWarning([]);
      setDraft({});
      setNotice(t('attendance_finalized'));
      if (groupId !== null) {
        // Re-fetch the full register (with roster) rather than rendering the
        // summary response, which has no roster.
        await loadForGroup(groupId, lessonDate);
      } else {
        setSession((prev) => (prev ? { ...prev, ...summary, roster: prev.roster } : prev));
      }
    } catch (e: unknown) {
      const body = apiErrorBody(e) as unknown as
        | { reason?: unknown; unmarked?: Array<{ name?: unknown }> }
        | null;
      if (body && body.reason === 'unmarked_students' && Array.isArray(body.unmarked)) {
        setUnmarkedWarning(body.unmarked.map((u) => String(u?.name ?? '')));
      } else {
        setErr(errMessage(e));
      }
    } finally {
      setBusy(false);
    }
  }

  if (!ready) return <p className="muted">{t('loading')}</p>;

  if (groups.length === 0) {
    return (
      <div className="card">
        <p className="muted small">{t('td_no_groups_hint')}</p>
      </div>
    );
  }

  const percent = report?.attendance_percentage;

  return (
    <div className="card">
      <div className="row" style={{ justifyContent: 'space-between', flexWrap: 'wrap' }}>
        <strong>{t('attendance_title')}</strong>
        {percent !== null && percent !== undefined ? (
          <span className="muted small">
            {t('attendance_percentage')}: <b>{percent}%</b>
          </span>
        ) : (
          <span className="muted small">{t('attendance_not_configured')}</span>
        )}
      </div>

      {err && <p className="error" role="alert">{err}</p>}
      {notice && <p className="muted small" role="status">{notice}</p>}

      <div className="row" style={{ gap: 8, flexWrap: 'wrap', marginTop: 8 }}>
        <label className="muted small">
          {t('attendance_group')}
          <select
            value={groupId ?? ''}
            onChange={(e) => setGroupId(Number(e.target.value))}
            disabled={busy}
          >
            {groups.map((g) => (
              <option key={g.id} value={g.id}>{g.name}</option>
            ))}
          </select>
        </label>
        <label className="muted small">
          {t('attendance_date')}
          <input
            type="date"
            value={lessonDate}
            onChange={(e) => setLessonDate(e.target.value)}
            disabled={busy}
          />
        </label>
        <button className="btn sm" type="button" onClick={openSession} disabled={busy}>
          {t('attendance_take')}
        </button>
      </div>

      {/* Already-taken registers for this day (several periods stay distinct). */}
      {sessions.length > 1 && (
        <p className="muted small">
          {t('attendance_report')}: {sessions.length} — {sessions
            .map((s) => `${s.time_label} (${s.status_label})`)
            .join(', ')}
        </p>
      )}

      {!session ? (
        <p className="muted small">{t('attendance_no_session')}</p>
      ) : (
        <>
          <p className="muted small">
            {session.group_name} · {session.lesson_date}
            {session.time_label !== '—' ? ` · ${session.time_label}` : ''} ·{' '}
            <span className={`badge ${isFinalized ? 'green' : 'amber'}`}>
              {session.status_label}
            </span>
          </p>

          {/* Live counts. */}
          <div className="grid">
            <div className="card stat">
              <span className="stat-label">{t('attendance_roster_size')}</span>
              <span className="stat-value">{counts.roster_size}</span>
            </div>
            <div className="card stat">
              <span className="stat-label">{t('attendance_marked')}</span>
              <span className="stat-value">{counts.marked}</span>
            </div>
            <div className="card stat">
              <span className="stat-label">{t('attendance_present')}</span>
              <span className="stat-value">{counts.present}</span>
            </div>
            <div className="card stat">
              <span className="stat-label">{t('attendance_late')}</span>
              <span className="stat-value">{counts.late}</span>
            </div>
            <div className="card stat">
              <span className="stat-label">{t('attendance_absent')}</span>
              <span className="stat-value">{counts.absent}</span>
            </div>
            <div className="card stat">
              <span className="stat-label">{t('attendance_excused')}</span>
              <span className="stat-value">{counts.excused}</span>
            </div>
            <div className="card stat">
              <span className="stat-label">{t('attendance_unmarked')}</span>
              <span className="stat-value">{counts.unmarked}</span>
            </div>
          </div>

          {unmarkedWarning.length > 0 && (
            <div className="card" style={{ background: '#fff7ed' }}>
              <p className="error small" role="alert">
                {t('attendance_unmarked_warning')}
              </p>
              <ul className="muted small">
                {unmarkedWarning.map((name, i) => (
                  <li key={`${name}-${i}`}>{name}</li>
                ))}
              </ul>
              <button
                className="btn sm"
                type="button"
                onClick={() => finalize(true)}
                disabled={busy}
              >
                {t('attendance_finalize')}
              </button>
            </div>
          )}

          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>{t('th_student')}</th>
                  <th>{t('status')}</th>
                  <th>{t('attendance_late_minutes')}</th>
                </tr>
              </thead>
              <tbody>
                {roster.map((row) => {
                  const disabled = busy || isFinalized;
                  return (
                    <tr key={row.student_id}>
                      <td>
                        {row.name}
                        {!row.marked && (
                          <span className="muted small"> · {t('attendance_unmarked')}</span>
                        )}
                      </td>
                      <td>
                        {STATUS_ORDER.map((status) => (
                          <button
                            key={status}
                            type="button"
                            className={`btn sm ${row.status === status ? 'primary' : ''}`}
                            aria-pressed={row.status === status}
                            onClick={() => setStatus(row.student_id, status)}
                            disabled={disabled}
                            style={{ marginRight: 4 }}
                          >
                            {statusLabel(t, status)}
                          </button>
                        ))}
                      </td>
                      <td>
                        {row.status === 'late' ? (
                          <input
                            type="number"
                            min={0}
                            value={row.late_minutes}
                            onChange={(e) =>
                              setLateMinutes(row.student_id, Number(e.target.value))
                            }
                            disabled={disabled}
                            aria-label={t('attendance_late_minutes')}
                            style={{ width: 72 }}
                          />
                        ) : (
                          <span className="muted small">—</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {!isFinalized && (
            <div className="row" style={{ gap: 8, flexWrap: 'wrap' }}>
              <button
                className="btn sm"
                type="button"
                onClick={markAllPresent}
                disabled={busy || counts.unmarked === 0}
              >
                {t('attendance_all_present')}
              </button>
              <button
                className="btn primary sm"
                type="button"
                onClick={saveMarks}
                disabled={busy || Object.keys(draft).length === 0}
              >
                {t('attendance_save')}
              </button>
              <button
                className="btn sm"
                type="button"
                onClick={() => finalize(false)}
                disabled={busy}
              >
                {t('attendance_finalize')}
              </button>
            </div>
          )}

          {/* Recent daily history for this group. */}
          {report?.daily && report.daily.length > 0 && (
            <>
              <h3>{t('attendance_report')}</h3>
              <div className="table-wrap">
                <table className="data">
                  <thead>
                    <tr>
                      <th>{t('date')}</th>
                      <th>{t('attendance_present')}</th>
                      <th>{t('attendance_late')}</th>
                      <th>{t('attendance_absent')}</th>
                      <th>{t('attendance_excused')}</th>
                      <th>{t('attendance_percentage')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {report.daily.map((d) => (
                      <tr key={d.date}>
                        <td className="muted small">{d.date}</td>
                        <td>{d.present}</td>
                        <td>{d.late}</td>
                        <td>{d.absent}</td>
                        <td>{d.excused}</td>
                        <td>
                          {d.attendance_percentage !== null
                            ? `${d.attendance_percentage}%`
                            : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}
