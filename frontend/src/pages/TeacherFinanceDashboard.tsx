import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { BellRing, CreditCard, Sparkles, Users, Wallet } from 'lucide-react';

import { useToast } from '../context/ToastContext';
import { useLang } from '../i18n/LangContext';
import { apiFetch } from '../lib/api';

interface StudentFinanceRow {
  id: number;
  student_id: number;
  full_name: string;
  email: string;
  phone: string;
  parent_phone: string;
  parent_telegram_id: string;
  monthly_fee: number;
  billing_cycle_day: number;
  last_payment_date: string | null;
  next_payment_due: string | null;
  payment_status: 'paid' | 'due_soon' | 'overdue' | 'grace_period';
  days_left: number;
  has_pro: boolean;
}

interface GroupFinanceData {
  group_id: number;
  group_name: string;
  teacher_name: string;
  pro_quota_balance: number;
  premium_quota_balance: number;
  total_students: number;
  paid_count: number;
  overdue_count: number;
  due_soon_count: number;
  collected_amount: number;
  pending_amount: number;
  students: StudentFinanceRow[];
}

interface TeacherGroup {
  id: number;
  name: string;
}

const STATUS_TONE: Record<StudentFinanceRow['payment_status'], string> = {
  paid: 'ok',
  due_soon: 'warn',
  grace_period: 'warn',
  overdue: 'bad',
};

/** Teacher tuition tracking: per group totals, debtors, one-click reminders, manual payments, quota licences. */
export default function TeacherFinanceDashboard() {
  const { t, lang } = useLang();
  const toast = useToast();
  const [groups, setGroups] = useState<TeacherGroup[] | null>(null);
  const [groupsFailed, setGroupsFailed] = useState(false);
  const [selectedGroupId, setSelectedGroupId] = useState<number | null>(null);
  const [financeData, setFinanceData] = useState<GroupFinanceData | null>(null);
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);
  const [actionBusy, setActionBusy] = useState(false);
  const [rowBusy, setRowBusy] = useState<number | null>(null);
  const [reload, setReload] = useState(0);

  const money = (n: number) => `${Number(n || 0).toLocaleString(lang)} ${t('tf_sum')}`;
  const errText = (err: unknown, key: string) => (err instanceof Error && err.message ? err.message : t(key));

  const loadGroups = useCallback(() => {
    setGroupsFailed(false);
    setGroups(null);
    apiFetch<unknown>('/api/v1/school/groups/')
      .then((res) => {
        const list = (Array.isArray(res) ? res : []).map((g: { id: number; name: string }) => ({ id: g.id, name: g.name }));
        setGroups(list);
        setSelectedGroupId((cur) => cur ?? list[0]?.id ?? null);
      })
      .catch(() => setGroupsFailed(true));
  }, []);

  useEffect(() => {
    loadGroups();
  }, [loadGroups]);

  const loadFinance = useCallback(async (groupId: number) => {
    const data = await apiFetch<GroupFinanceData>(`/api/v1/courses/groups/${groupId}/finance-summary/`);
    setFinanceData(data);
  }, []);

  useEffect(() => {
    if (!selectedGroupId) return;
    let alive = true;
    setLoading(true);
    setFailed(false);
    loadFinance(selectedGroupId)
      .catch(() => alive && setFailed(true))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, [selectedGroupId, loadFinance, reload]);

  const handleSendReminders = async () => {
    if (!selectedGroupId) return;
    setActionBusy(true);
    try {
      const res = await apiFetch<{ status: string; message: string }>(
        `/api/v1/courses/groups/${selectedGroupId}/send-payment-reminders/`,
        { method: 'POST' },
      );
      toast.success(res.message || t('tf_remind_sent'));
    } catch (err) {
      toast.error(errText(err, 'tf_remind_failed'));
    } finally {
      setActionBusy(false);
    }
  };

  const handleRecordPayment = async (studentId: number) => {
    if (!selectedGroupId) return;
    setRowBusy(studentId);
    try {
      const res = await apiFetch<{ status: string; message: string }>(
        `/api/v1/courses/groups/${selectedGroupId}/record-payment/`,
        { method: 'POST', body: JSON.stringify({ student_id: studentId, extend_days: 30 }) },
      );
      toast.success(res.message || t('tf_paid_saved'));
      await loadFinance(selectedGroupId);
    } catch (err) {
      toast.error(errText(err, 'tf_paid_failed'));
    } finally {
      setRowBusy(null);
    }
  };

  const handleActivateQuota = async (studentId: number, planType: 'pro' | 'premium') => {
    if (!selectedGroupId) return;
    setRowBusy(studentId);
    try {
      const res = await apiFetch<{ status: string; message: string }>(
        `/api/v1/courses/groups/${selectedGroupId}/students/${studentId}/activate-quota/`,
        { method: 'POST', body: JSON.stringify({ plan_type: planType }) },
      );
      toast.success(res.message || t('tf_quota_done'));
      await loadFinance(selectedGroupId);
    } catch (err) {
      toast.error(errText(err, 'tf_quota_failed'));
    } finally {
      setRowBusy(null);
    }
  };

  const debtors = financeData ? financeData.overdue_count + financeData.due_soon_count : 0;

  const statusLabel = (st: StudentFinanceRow) => {
    if (st.payment_status === 'paid') return t('tf_st_paid');
    if (st.payment_status === 'overdue') return t('tf_st_overdue');
    return t('tf_st_due').replace('{n}', String(st.days_left));
  };

  return (
    <div className="tf">
      <header className="tf-head">
        <div className="tf-head__text">
          <h1>{t('tf_title')}</h1>
          <p>{t('tf_sub')}</p>
        </div>
        <div className="tf-head__actions">
          {groups && groups.length > 0 && (
            <select
              className="ui-input tf-select"
              value={selectedGroupId ?? ''}
              onChange={(e) => setSelectedGroupId(Number(e.target.value))}
              aria-label={t('tf_group')}
            >
              {groups.map((g) => (
                <option key={g.id} value={g.id}>
                  {g.name}
                </option>
              ))}
            </select>
          )}
          <Link to="/teacher/vocab-generator" className="ui-btn ui-btn--sm">
            <Sparkles size={16} aria-hidden="true" /> {t('tf_vocab')}
          </Link>
          <Link to="/groups" className="ui-btn ui-btn--sm">
            <Users size={16} aria-hidden="true" /> {t('tf_groups')}
          </Link>
        </div>
      </header>

      {groupsFailed ? (
        <div className="ui-state" role="alert">
          <h3>{t('tf_error')}</h3>
          <button type="button" className="ui-btn" onClick={loadGroups}>
            {t('error_retry')}
          </button>
        </div>
      ) : groups === null ? (
        <div className="tf-kpis" aria-busy="true">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="ui-skel" style={{ height: 96, borderRadius: 16 }} />
          ))}
        </div>
      ) : groups.length === 0 ? (
        <div className="ui-state">
          <span className="ic-chip">
            <Users size={24} aria-hidden="true" />
          </span>
          <h3>{t('tf_no_groups')}</h3>
          <p>{t('tf_no_groups_text')}</p>
          <Link to="/groups" className="ui-btn ui-btn--primary">
            {t('tf_groups')}
          </Link>
        </div>
      ) : (
        <>
          {financeData && !failed && (
            <section className="tf-kpis" aria-label={t('tf_title')}>
              <div className="ui-card tf-kpi tf-kpi--ok">
                <span className="tf-kpi__label">{t('tf_collected')}</span>
                <strong className="tf-kpi__value">{money(financeData.collected_amount)}</strong>
                <span className="tf-kpi__note">{t('tf_paid_count').replace('{n}', String(financeData.paid_count))}</span>
              </div>
              <div className="ui-card tf-kpi tf-kpi--bad">
                <span className="tf-kpi__label">{t('tf_pending')}</span>
                <strong className="tf-kpi__value">{money(financeData.pending_amount)}</strong>
                <span className="tf-kpi__note">{t('tf_debtors').replace('{n}', String(debtors))}</span>
              </div>
              <div className="ui-card tf-kpi">
                <span className="tf-kpi__label">{t('tf_students')}</span>
                <strong className="tf-kpi__value">{financeData.total_students}</strong>
              </div>
              <div className="ui-card tf-kpi">
                <span className="tf-kpi__label">{t('tf_quota')}</span>
                <strong className="tf-kpi__value">
                  {financeData.pro_quota_balance} PRO · {financeData.premium_quota_balance} PREMIUM
                </strong>
                <span className="tf-kpi__note">{t('tf_quota_note')}</span>
              </div>
            </section>
          )}

          {financeData && !failed && debtors > 0 && (
            <div className="ui-card tf-remind">
              <span className="ic-chip">
                <BellRing size={22} aria-hidden="true" />
              </span>
              <div className="tf-remind__text">
                <strong>{t('tf_remind_title').replace('{n}', String(debtors))}</strong>
                <p>{t('tf_remind_text')}</p>
              </div>
              <button type="button" className="ui-btn ui-btn--primary" onClick={() => void handleSendReminders()} disabled={actionBusy}>
                {actionBusy ? t('tf_sending') : t('tf_remind_btn')}
              </button>
            </div>
          )}

          <section className="ui-card tf-list">
            <div className="tf-list__head">
              <h2>{t('tf_list_title')}</h2>
              {financeData && <small>{t('tf_total').replace('{n}', String(financeData.students.length))}</small>}
            </div>

            {loading ? (
              <div className="tf-rows" aria-busy="true">
                {[0, 1, 2].map((i) => (
                  <div key={i} className="ui-skel" style={{ height: 88, borderRadius: 12 }} />
                ))}
              </div>
            ) : failed ? (
              <div className="ui-state" role="alert" style={{ border: 0 }}>
                <h3>{t('tf_error')}</h3>
                <button type="button" className="ui-btn" onClick={() => setReload((n) => n + 1)}>
                  {t('error_retry')}
                </button>
              </div>
            ) : financeData && financeData.students.length > 0 ? (
              <ul className="tf-rows">
                {financeData.students.map((st) => (
                  <li key={st.id} className="tf-row">
                    <div className="tf-row__who">
                      <strong className="clamp-1">{st.full_name}</strong>
                      <span className="clamp-1">{st.email}</span>
                    </div>
                    <span className={`tf-status tf-status--${STATUS_TONE[st.payment_status] || 'warn'}`}>{statusLabel(st)}</span>
                    <dl className="tf-row__facts">
                      <div>
                        <dt>{t('tf_phone')}</dt>
                        <dd>{st.phone || '—'}</dd>
                      </div>
                      <div>
                        <dt>{t('tf_parent')}</dt>
                        <dd>
                          {st.parent_phone || t('tf_not_set')}
                          {st.parent_telegram_id && <span className="tf-tg">{t('tf_tg_linked')}</span>}
                        </dd>
                      </div>
                      <div>
                        <dt>{t('tf_fee')}</dt>
                        <dd>{money(st.monthly_fee)}</dd>
                      </div>
                      <div>
                        <dt>{t('tf_due')}</dt>
                        <dd>
                          {st.next_payment_due || '—'}
                          {st.last_payment_date && (
                            <small>{t('tf_last').replace('{d}', st.last_payment_date)}</small>
                          )}
                        </dd>
                      </div>
                    </dl>
                    <div className="tf-row__actions">
                      <button
                        type="button"
                        className="ui-btn ui-btn--sm"
                        onClick={() => void handleRecordPayment(st.student_id)}
                        disabled={rowBusy === st.student_id}
                        title={t('tf_mark_paid_hint')}
                      >
                        <CreditCard size={14} aria-hidden="true" /> {t('tf_mark_paid')}
                      </button>
                      <button
                        type="button"
                        className="ui-btn ui-btn--sm"
                        onClick={() => void handleActivateQuota(st.student_id, 'pro')}
                        disabled={financeData.pro_quota_balance <= 0 || rowBusy === st.student_id}
                        title={t('tf_give_hint').replace('{plan}', 'PRO')}
                      >
                        <Wallet size={14} aria-hidden="true" /> PRO
                      </button>
                      <button
                        type="button"
                        className="ui-btn ui-btn--sm"
                        onClick={() => void handleActivateQuota(st.student_id, 'premium')}
                        disabled={financeData.premium_quota_balance <= 0 || rowBusy === st.student_id}
                        title={t('tf_give_hint').replace('{plan}', 'PREMIUM')}
                      >
                        <Wallet size={14} aria-hidden="true" /> PREMIUM
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="tf-empty">{t('tf_empty')}</p>
            )}
          </section>
        </>
      )}
    </div>
  );
}
