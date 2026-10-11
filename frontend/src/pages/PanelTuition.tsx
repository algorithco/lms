import { useCallback, useEffect, useMemo, useState } from 'react';
import type { FormEvent } from 'react';
import { useLang } from '../i18n/LangContext';
import {
  School,
  TuitionAdmin,
  type TuitionAuditRow,
  type TuitionInvoice,
  type TuitionPaymentRow,
  type TuitionPolicy,
  type TuitionReminderPolicy,
} from '../lib/api';
import { formatDate, formatDateTime, num, str } from '../lib/billingPanelGames';
import {
  CreditCardIcon,
  ReceiptIcon,
  ScrollTextIcon,
  ShieldCheckIcon,
} from '../components/icons';

/**
 * Staff course-tuition desk — billing policies, invoice review, the payment
 * confirmation queue and the reminder ladder, in one place.
 *
 * Everything here is the React SPA talking to the *canonical* service layer
 * through `/api/v1/school/tuition/...`; the page owns no money rules of its own:
 *
 * * the backend gates every call on `tuition.view_courseinvoice` /
 *   `tuition.change_courseinvoice` (a platform admin holds both), so a 403 is
 *   rendered rather than worked around;
 * * a submitted receipt is never presented as money — an invoice keeps its
 *   balance and its `awaiting_confirmation` flag until an operator approves it
 *   in the queue tab;
 * * waiving, adjusting or re-dating an invoice always demands a stated reason,
 *   because each one writes an immutable audit row.
 */

type Tab = 'policies' | 'invoices' | 'queue' | 'reminders';

type ActionKind = 'record' | 'adjust' | 'waive' | 'duedate';

const PAYMENT_METHODS = ['cash', 'card', 'bank', 'online', 'other'] as const;

const METHOD_KEYS: Record<string, string> = {
  cash: 'tuition_method_cash',
  card: 'tuition_method_card',
  bank: 'tuition_method_bank',
  online: 'tuition_method_online',
  other: 'tuition_method_other',
};

const FREQUENCIES = ['monthly', 'quarterly', 'annual', 'one_time'] as const;
const MID_MONTH = ['skip', 'full', 'prorated'] as const;
const INVOICE_STATUSES = [
  'unpaid',
  'partially_paid',
  'pending_verification',
  'paid',
  'overdue',
  'waived',
  'cancelled',
  'refunded',
  'adjusted',
] as const;

/** Status badge tone; the design system only has these three. */
const STATUS_TONE: Record<string, string> = {
  paid: 'green',
  waived: 'green',
  overdue: 'rose',
  cancelled: 'rose',
};

const localDate = (value = new Date()) =>
  `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, '0')}-${String(value.getDate()).padStart(2, '0')}`;

/** "3, 7, 14" → [3, 7, 14]; anything non-numeric is dropped, never guessed. */
function parseDays(raw: string): number[] {
  const out: number[] = [];
  for (const chunk of str(raw).split(',')) {
    const trimmed = chunk.trim();
    if (!trimmed) continue;
    const value = Number(trimmed);
    if (!Number.isInteger(value) || value < 0 || value > 365) continue;
    if (!out.includes(value)) out.push(value);
  }
  return out.sort((a, b) => a - b);
}

const showDays = (days: number[] | undefined) => (days ?? []).join(', ');

interface PolicyForm {
  name: string;
  scope: 'group' | 'course';
  scopeId: string;
  amount: string;
  dueDay: string;
  grace: string;
  frequency: string;
  midMonth: string;
  installmentsOn: boolean;
  installments: string;
  effectiveFrom: string;
  effectiveUntil: string;
  instructions: string;
  methods: string[];
  active: boolean;
}

const EMPTY_POLICY = (): PolicyForm => ({
  name: '',
  scope: 'group',
  scopeId: '',
  amount: '0',
  dueDay: '10',
  grace: '0',
  frequency: 'monthly',
  midMonth: 'skip',
  installmentsOn: false,
  installments: '2',
  effectiveFrom: localDate(),
  effectiveUntil: '',
  instructions: '',
  methods: [],
  active: true,
});

interface ReminderForm {
  before: string;
  due: string;
  overdue: string;
  quietStart: string;
  quietEnd: string;
}

const reminderForm = (policy: TuitionPolicy): ReminderForm => {
  const ladder: TuitionReminderPolicy = policy.reminder_policy ?? {};
  return {
    before: showDays(ladder.before),
    due: showDays(ladder.due),
    overdue: showDays(ladder.overdue),
    quietStart: String(ladder.quiet_start ?? 21),
    quietEnd: String(ladder.quiet_end ?? 8),
  };
};

export default function PanelTuition() {
  const { t } = useLang();
  const [tab, setTab] = useState<Tab>('policies');
  const [err, setErr] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const [groups, setGroups] = useState<{ id: number; name: string }[]>([]);
  const [courses, setCourses] = useState<{ id: number; title: string }[]>([]);

  const [policies, setPolicies] = useState<TuitionPolicy[]>([]);
  const [invoices, setInvoices] = useState<TuitionInvoice[]>([]);
  const [invoiceCount, setInvoiceCount] = useState(0);
  // Only ever set after a response, so nothing here sets state synchronously
  // while an effect is running; before the first response the empty state is
  // the loading state.
  const [invoicesLoaded, setInvoicesLoaded] = useState(false);
  const [queue, setQueue] = useState<TuitionPaymentRow[]>([]);
  const [audit, setAudit] = useState<TuitionAuditRow[] | null>(null);
  const [auditInvoice, setAuditInvoice] = useState<TuitionInvoice | null>(null);

  const [statusFilter, setStatusFilter] = useState('');
  const [groupFilter, setGroupFilter] = useState('');
  const [openOnly, setOpenOnly] = useState(false);
  const [queueStatus, setQueueStatus] = useState('pending_verification');
  const [queueReason, setQueueReason] = useState('');

  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState<PolicyForm>(EMPTY_POLICY);

  const [action, setAction] = useState<{ kind: ActionKind; invoice: TuitionInvoice } | null>(
    null,
  );
  const [actionAmount, setActionAmount] = useState('');
  const [actionMethod, setActionMethod] = useState<string>('cash');
  const [actionReference, setActionReference] = useState('');
  const [actionReason, setActionReason] = useState('');
  const [actionDueDate, setActionDueDate] = useState('');
  const [actionGraceUntil, setActionGraceUntil] = useState('');

  const [reminders, setReminders] = useState<Record<number, ReminderForm>>({});

  const fail = (e: unknown, fallback = 'Failed.') =>
    setErr(e instanceof Error ? e.message : fallback);

  const money = useCallback(
    (value: unknown) => `${num(value).toLocaleString()} ${t('uzs_short')}`,
    [t],
  );

  const statusLabel = useCallback(
    (status: string) => {
      const key = `tuition_status_${status}`;
      const value = t(key);
      return value === key ? status : value;
    },
    [t],
  );

  /**
   * The API ships an Uzbek `status_label` for every row; prefer the caller's own
   * language and fall back to the server label (never to a raw enum) when a
   * status is new and has no key yet.
   */
  const rowStatus = useCallback(
    (status: string, serverLabel: string) => {
      const key = `tuition_status_${status}`;
      const value = t(key);
      return value === key ? serverLabel || status : value;
    },
    [t],
  );

  // -- lookups ------------------------------------------------------------
  useEffect(() => {
    School.groups()
      .then((rows) =>
        setGroups(rows.map((row) => ({ id: num(row.id), name: str(row.name) }))),
      )
      .catch(() => undefined);
    School.courses()
      .then((r) => setCourses(r.courses))
      .catch(() => undefined);
  }, []);

  const loadPolicies = useCallback(() => {
    TuitionAdmin.policies()
      .then((r) => {
        setPolicies(r.results);
        setReminders((current) => {
          const next: Record<number, ReminderForm> = {};
          for (const policy of r.results) {
            next[policy.id] = current[policy.id] ?? reminderForm(policy);
          }
          return next;
        });
        setErr(null);
      })
      .catch((e: unknown) => fail(e));
  }, []);

  const loadInvoices = useCallback(() => {
    const params: Record<string, string> = {};
    if (openOnly) params.status = 'open';
    else if (statusFilter) params.status = statusFilter;
    if (groupFilter) params.group_id = groupFilter;
    TuitionAdmin.invoices(params)
      .then((r) => {
        setInvoices(r.results);
        setInvoiceCount(r.count);
        setInvoicesLoaded(true);
        setErr(null);
      })
      .catch((e: unknown) => fail(e));
  }, [openOnly, statusFilter, groupFilter]);

  const loadQueue = useCallback(() => {
    TuitionAdmin.paymentQueue(queueStatus)
      .then((r) => {
        setQueue(r.results);
        setErr(null);
      })
      .catch((e: unknown) => fail(e));
  }, [queueStatus]);

  // Load every section on mount: the hero figures cover invoices, policies and
  // the confirmation queue at once, so they must not depend on which tab the
  // operator happens to open first. Filter changes re-run their own loader.
  useEffect(() => {
    loadPolicies();
    loadQueue();
  }, [loadPolicies, loadQueue]);

  useEffect(() => {
    loadInvoices();
  }, [loadInvoices]);

  const summary = useMemo(() => {
    const openStatuses = ['unpaid', 'partially_paid', 'pending_verification', 'overdue'];
    const open = invoices.filter((row) => openStatuses.includes(row.status));
    return {
      open: open.length,
      outstanding: open.reduce((total, row) => total + num(row.balance_uzs), 0),
      // Any receipt still being checked, not only one that covers the whole
      // balance — the operator's question is "how many do I have to review?".
      awaiting: invoices.filter((row) => num(row.pending_amount_uzs) > 0).length,
    };
  }, [invoices]);

  // -- policy form --------------------------------------------------------
  const startCreate = () => {
    const base = EMPTY_POLICY();
    base.scope = groups.length > 0 ? 'group' : 'course';
    base.scopeId = String(groups.length > 0 ? groups[0].id : courses[0]?.id ?? '');
    setEditingId(null);
    setForm(base);
    setShowForm(true);
  };

  const startEdit = (policy: TuitionPolicy) => {
    setEditingId(policy.id);
    setForm({
      name: policy.name,
      scope: policy.group ? 'group' : 'course',
      scopeId: String(policy.group ?? policy.course ?? ''),
      amount: String(policy.amount_uzs),
      dueDay: String(policy.due_day),
      grace: String(policy.grace_days),
      frequency: policy.billing_frequency,
      midMonth: policy.mid_month_policy,
      installmentsOn: policy.installment_allowed,
      installments: String(policy.installments),
      effectiveFrom: policy.effective_from,
      effectiveUntil: policy.effective_until ?? '',
      instructions: policy.payment_instructions ?? '',
      methods: policy.accepted_methods ?? [],
      active: policy.is_active,
    });
    setShowForm(true);
  };

  const submitPolicy = async (e: FormEvent) => {
    e.preventDefault();
    setErr(null);
    setNotice(null);
    if (!form.scopeId) {
      setErr(t('tuition_scope_required'));
      return;
    }
    const payload: Partial<TuitionPolicy> = {
      name: form.name.trim(),
      group: form.scope === 'group' ? Number(form.scopeId) : null,
      course: form.scope === 'course' ? Number(form.scopeId) : null,
      amount_uzs: Math.max(0, Math.round(num(form.amount))),
      due_day: Math.min(31, Math.max(1, Math.round(num(form.dueDay, 10)))),
      grace_days: Math.max(0, Math.round(num(form.grace))),
      billing_frequency: form.frequency,
      mid_month_policy: form.midMonth,
      installment_allowed: form.installmentsOn,
      installments: form.installmentsOn
        ? Math.max(2, Math.round(num(form.installments, 2)))
        : 1,
      effective_from: form.effectiveFrom || localDate(),
      effective_until: form.effectiveUntil || null,
      payment_instructions: form.instructions,
      accepted_methods: form.methods,
      is_active: form.active,
    };
    try {
      if (editingId === null) await TuitionAdmin.createPolicy(payload);
      else await TuitionAdmin.updatePolicy(editingId, payload);
      setShowForm(false);
      setEditingId(null);
      setForm(EMPTY_POLICY());
      setNotice(t('tuition_saved'));
      loadPolicies();
    } catch (e2) {
      fail(e2, 'Save failed.');
    }
  };

  const scopeLabel = (policy: TuitionPolicy) => {
    if (policy.group) {
      const group = groups.find((g) => g.id === policy.group);
      return `${t('tuition_scope_group')}: ${group ? group.name : `#${policy.group}`}`;
    }
    const course = courses.find((c) => c.id === policy.course);
    return `${t('tuition_scope_course')}: ${course ? course.title : `#${policy.course ?? '—'}`}`;
  };

  // -- invoice actions ----------------------------------------------------
  const openAction = (kind: ActionKind, invoice: TuitionInvoice) => {
    setAction({ kind, invoice });
    setErr(null);
    setNotice(null);
    setActionReason('');
    setActionMethod('cash');
    setActionReference('');
    setActionAmount(
      kind === 'adjust'
        ? String(invoice.amount_due_uzs)
        : String(Math.max(0, num(invoice.balance_uzs))),
    );
    setActionDueDate(invoice.due_date ?? '');
    setActionGraceUntil(invoice.grace_until ?? '');
  };

  const submitAction = async (e: FormEvent) => {
    e.preventDefault();
    if (!action) return;
    if (action.kind !== 'duedate') {
      if (actionReason.trim().length < 3) {
        setErr(t('tuition_reason_required'));
        return;
      }
    }
    setErr(null);
    setNotice(null);
    try {
      if (action.kind === 'record') {
        await TuitionAdmin.recordInvoicePayment(action.invoice.id, {
          amount: num(actionAmount),
          method: actionMethod,
          reference: actionReference,
          reason: actionReason.trim(),
        });
      } else if (action.kind === 'adjust') {
        await TuitionAdmin.adjustInvoice(action.invoice.id, {
          amount: num(actionAmount),
          reason: actionReason.trim(),
        });
      } else if (action.kind === 'waive') {
        await TuitionAdmin.waiveInvoice(action.invoice.id, actionReason.trim());
      } else {
        await TuitionAdmin.setInvoiceDueDate(action.invoice.id, {
          due_date: actionDueDate,
          grace_until: actionGraceUntil || null,
        });
      }
      setNotice(t('tuition_saved'));
      setAction(null);
      loadInvoices();
      loadQueue();
    } catch (e2) {
      fail(e2, 'Action failed.');
    }
  };

  const showAudit = async (invoice: TuitionInvoice) => {
    setAuditInvoice(invoice);
    setAudit(null);
    try {
      const r = await TuitionAdmin.audit({ invoice_id: String(invoice.id), limit: '50' });
      setAudit(r.results);
    } catch (e) {
      fail(e);
    }
  };

  // -- queue decisions ----------------------------------------------------
  const decide = async (row: TuitionPaymentRow, kind: 'verify' | 'reject') => {
    if (queueReason.trim().length < 3) {
      setErr(t('tuition_reason_required'));
      return;
    }
    const question = kind === 'verify' ? t('tuition_verify_confirm') : t('tuition_reject_confirm');
    if (!window.confirm(question)) return;
    setErr(null);
    setNotice(null);
    try {
      if (kind === 'verify') await TuitionAdmin.verifyPayment(row.id, queueReason.trim());
      else await TuitionAdmin.rejectPayment(row.id, queueReason.trim());
      setNotice(kind === 'verify' ? t('tuition_verified_ok') : t('tuition_rejected_ok'));
      loadQueue();
      // Confirming money changes an invoice balance, so the hero figures and the
      // invoice rows have to be re-read as well — not just the queue.
      loadInvoices();
    } catch (e) {
      fail(e);
    }
  };

  // -- reminders ----------------------------------------------------------
  const setReminder = (id: number, patch: Partial<ReminderForm>) =>
    setReminders((current) => ({
      ...current,
      [id]: { ...(current[id] ?? { before: '', due: '', overdue: '', quietStart: '21', quietEnd: '8' }), ...patch },
    }));

  const saveReminder = async (policy: TuitionPolicy) => {
    const row = reminders[policy.id];
    if (!row) return;
    const quietStart = Math.min(23, Math.max(0, Math.round(num(row.quietStart, 21))));
    const quietEnd = Math.min(23, Math.max(0, Math.round(num(row.quietEnd, 8))));
    const reminder_policy: TuitionReminderPolicy = {
      before: parseDays(row.before),
      due: parseDays(row.due),
      overdue: parseDays(row.overdue),
      quiet_start: quietStart,
      quiet_end: quietEnd,
    };
    setErr(null);
    setNotice(null);
    try {
      await TuitionAdmin.updatePolicy(policy.id, { reminder_policy });
      setNotice(t('tuition_reminder_saved'));
      loadPolicies();
    } catch (e) {
      fail(e);
    }
  };

  // The scope picker mixes two shapes; normalise before rendering so the
  // dropdown never has to branch on which lookup it came from.
  const scopeOptions: { id: number; label: string }[] =
    form.scope === 'group'
      ? groups.map((group) => ({ id: group.id, label: group.name }))
      : courses.map((course) => ({ id: course.id, label: course.title }));

  const tabs: { key: Tab; label: string }[] = [
    { key: 'policies', label: t('tuition_tab_policies') },
    { key: 'invoices', label: t('tuition_tab_invoices') },
    { key: 'queue', label: t('tuition_tab_queue') },
    { key: 'reminders', label: t('tuition_tab_reminders') },
  ];

  return (
    <div>
      <div className="card admin-hero">
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span className="admin-hero-badge">
            <CreditCardIcon size={28} className="ico" />
          </span>
          <div>
            <h1 style={{ margin: 0 }}>{t('tuition_title')}</h1>
            <p className="muted" style={{ margin: '4px 0 0' }}>
              {t('tuition_admin_sub')}
            </p>
          </div>
        </div>
        <div className="admin-hero-stats">
          <div>
            <span className="stat-value">{num(policies.length)}</span>
            <span className="stat-label">{t('tuition_tab_policies')}</span>
          </div>
          <div>
            <span className="stat-value">{num(summary.open)}</span>
            <span className="stat-label">{t('tuition_open_invoices')}</span>
          </div>
          <div>
            <span className="stat-value">{money(summary.outstanding)}</span>
            <span className="stat-label">{t('tuition_outstanding')}</span>
          </div>
          <div>
            <span className="stat-value">{num(summary.awaiting)}</span>
            <span className="stat-label">{t('tuition_pending')}</span>
          </div>
        </div>
      </div>

      <div className="toolbar" role="tablist">
        {tabs.map((item) => (
          <button
            key={item.key}
            role="tab"
            aria-selected={tab === item.key}
            className={`btn sm ${tab === item.key ? 'primary' : 'ghost'}`}
            onClick={() => {
              setTab(item.key);
              setNotice(null);
            }}
          >
            {item.label}
          </button>
        ))}
      </div>

      {err && (
        <p className="error" role="alert">
          {err}
        </p>
      )}
      {notice && (
        <p className="muted" role="status" aria-live="polite">
          {notice}
        </p>
      )}

      {/* ------------------------------------------------------------------ */}
      {/* Policies                                                            */}
      {/* ------------------------------------------------------------------ */}
      {tab === 'policies' && (
        <section>
          <div className="toolbar">
            <button className="btn primary sm" onClick={showForm ? () => setShowForm(false) : startCreate}>
              {showForm ? t('cancel') : t('tuition_policy_new')}
            </button>
            <button className="btn ghost sm" onClick={loadPolicies}>
              {t('tuition_refresh')}
            </button>
          </div>

          {showForm && (
            <form onSubmit={submitPolicy} className="card form" style={{ maxWidth: '100%' }}>
              <h2>{editingId === null ? t('tuition_policy_new') : t('tuition_policy_edit')}</h2>
              <div className="row">
                <label>
                  {t('tuition_policy_name')}
                  <input
                    value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                    required
                  />
                </label>
                <label>
                  {t('tuition_policy_scope')}
                  <select
                    value={form.scope}
                    onChange={(e) => {
                      const scope = e.target.value === 'course' ? 'course' : 'group';
                      const options = scope === 'group' ? groups : courses;
                      setForm({
                        ...form,
                        scope,
                        scopeId: options.length > 0 ? String(options[0].id) : '',
                      });
                    }}
                  >
                    <option value="group">{t('tuition_scope_group')}</option>
                    <option value="course">{t('tuition_scope_course')}</option>
                  </select>
                </label>
                <label>
                  {form.scope === 'group' ? t('tuition_scope_group') : t('tuition_scope_course')}
                  <select
                    value={form.scopeId}
                    onChange={(e) => setForm({ ...form, scopeId: e.target.value })}
                    required
                  >
                    <option value="">—</option>
                    {scopeOptions.map((option) => (
                      <option key={option.id} value={option.id}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <div className="row">
                <label>
                  {t('tuition_policy_amount')}
                  <input
                    type="number"
                    min={0}
                    value={form.amount}
                    onChange={(e) => setForm({ ...form, amount: e.target.value })}
                  />
                  <small className="muted">{t('tuition_amount_unset')}</small>
                </label>
                <label>
                  {t('tuition_policy_due_day')}
                  <input
                    type="number"
                    min={1}
                    max={31}
                    value={form.dueDay}
                    onChange={(e) => setForm({ ...form, dueDay: e.target.value })}
                  />
                </label>
                <label>
                  {t('tuition_policy_grace')}
                  <input
                    type="number"
                    min={0}
                    value={form.grace}
                    onChange={(e) => setForm({ ...form, grace: e.target.value })}
                  />
                </label>
              </div>
              <div className="row">
                <label>
                  {t('tuition_policy_frequency')}
                  <select
                    value={form.frequency}
                    onChange={(e) => setForm({ ...form, frequency: e.target.value })}
                  >
                    {FREQUENCIES.map((value) => (
                      <option key={value} value={value}>
                        {t(`tuition_freq_${value}`)}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  {t('tuition_policy_mid_month')}
                  <select
                    value={form.midMonth}
                    onChange={(e) => setForm({ ...form, midMonth: e.target.value })}
                  >
                    {MID_MONTH.map((value) => (
                      <option key={value} value={value}>
                        {t(`tuition_mid_${value}`)}
                      </option>
                    ))}
                  </select>
                </label>
                <label style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                  <input
                    type="checkbox"
                    checked={form.installmentsOn}
                    onChange={(e) => setForm({ ...form, installmentsOn: e.target.checked })}
                  />
                  {t('tuition_policy_installments')}
                </label>
                {form.installmentsOn && (
                  <label>
                    {t('tuition_policy_installments_count')}
                    <input
                      type="number"
                      min={2}
                      value={form.installments}
                      onChange={(e) => setForm({ ...form, installments: e.target.value })}
                    />
                  </label>
                )}
              </div>
              <div className="row">
                <label>
                  {t('tuition_policy_effective_from')}
                  <input
                    type="date"
                    value={form.effectiveFrom}
                    onChange={(e) => setForm({ ...form, effectiveFrom: e.target.value })}
                  />
                </label>
                <label>
                  {t('tuition_policy_effective_until')}
                  <input
                    type="date"
                    value={form.effectiveUntil}
                    onChange={(e) => setForm({ ...form, effectiveUntil: e.target.value })}
                  />
                </label>
                <label style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                  <input
                    type="checkbox"
                    checked={form.active}
                    onChange={(e) => setForm({ ...form, active: e.target.checked })}
                  />
                  {t('panel_active')}
                </label>
              </div>
              <fieldset className="card" style={{ padding: 12 }}>
                <legend>{t('tuition_policy_methods')}</legend>
                <div className="row">
                  {PAYMENT_METHODS.map((method) => (
                    <label
                      key={method}
                      style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}
                    >
                      <input
                        type="checkbox"
                        checked={form.methods.includes(method)}
                        onChange={(e) =>
                          setForm({
                            ...form,
                            methods: e.target.checked
                              ? [...form.methods, method]
                              : form.methods.filter((m) => m !== method),
                          })
                        }
                      />
                      {t(METHOD_KEYS[method])}
                    </label>
                  ))}
                </div>
                <small className="muted">{t('tuition_policy_methods_hint')}</small>
              </fieldset>
              <label>
                {t('tuition_payment_instructions')}
                <textarea
                  value={form.instructions}
                  onChange={(e) => setForm({ ...form, instructions: e.target.value })}
                  rows={2}
                />
              </label>
              <div className="row">
                <button className="btn primary">
                  {editingId === null ? t('tuition_policy_new') : t('save_changes')}
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

          {policies.length === 0 ? (
            <div className="card">
              <p>
                <strong>{t('tuition_no_policies')}</strong>
              </p>
              <p className="muted small">{t('tuition_no_policies_hint')}</p>
            </div>
          ) : (
            <div className="table-wrap">
              <table className="data">
                <thead>
                  <tr>
                    <th>{t('tuition_policy_name')}</th>
                    <th>{t('tuition_policy_scope')}</th>
                    <th>{t('tuition_policy_amount')}</th>
                    <th>{t('tuition_policy_frequency')}</th>
                    <th>{t('tuition_policy_due_day')}</th>
                    <th>{t('tuition_policy_installments')}</th>
                    <th>{t('status')}</th>
                    <th>{t('th_actions')}</th>
                  </tr>
                </thead>
                <tbody>
                  {policies.map((policy) => (
                    <tr key={policy.id}>
                      <td>
                        <strong>{policy.name}</strong>
                        <br />
                        <small className="muted">
                          {formatDate(policy.effective_from)}
                          {policy.effective_until ? ` — ${formatDate(policy.effective_until)}` : ''}
                        </small>
                      </td>
                      <td>{scopeLabel(policy)}</td>
                      <td>
                        {policy.amount_uzs > 0 ? (
                          money(policy.amount_uzs)
                        ) : (
                          <span className="badge rose">{t('tuition_amount_unset')}</span>
                        )}
                      </td>
                      <td>{t(`tuition_freq_${policy.billing_frequency}`)}</td>
                      <td className="muted small">
                        {policy.due_day}
                        {policy.grace_days > 0 ? ` (+${policy.grace_days})` : ''}
                      </td>
                      <td className="muted small">
                        {policy.installment_allowed ? policy.installments : '—'}
                      </td>
                      <td>
                        <span className={`badge ${policy.is_active ? 'green' : ''}`}>
                          {policy.is_active ? t('panel_active') : t('status_inactive')}
                        </span>
                      </td>
                      <td style={{ whiteSpace: 'nowrap' }}>
                        <button className="btn sm ghost" onClick={() => startEdit(policy)}>
                          {t('edit')}
                        </button>{' '}
                        <button
                          className="btn sm ghost"
                          onClick={() => {
                            setTab('reminders');
                          }}
                        >
                          {t('tuition_tab_reminders')}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      {/* ------------------------------------------------------------------ */}
      {/* Invoices                                                            */}
      {/* ------------------------------------------------------------------ */}
      {tab === 'invoices' && (
        <section>
          <div className="toolbar">
            <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
              <option value="">
                {t('all')} · {t('tuition_filter_status')}
              </option>
              {INVOICE_STATUSES.map((status) => (
                <option key={status} value={status}>
                  {statusLabel(status)}
                </option>
              ))}
            </select>
            <select value={groupFilter} onChange={(e) => setGroupFilter(e.target.value)}>
              <option value="">
                {t('all')} · {t('tuition_filter_group')}
              </option>
              {groups.map((group) => (
                <option key={group.id} value={group.id}>
                  {group.name}
                </option>
              ))}
            </select>
            <label style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
              <input
                type="checkbox"
                checked={openOnly}
                onChange={(e) => setOpenOnly(e.target.checked)}
              />
              {t('tuition_filter_open')}
            </label>
            <button className="btn ghost sm" onClick={loadInvoices}>
              {t('tuition_refresh')}
            </button>
            <span className="muted small">
              {t('tuition_total')}: {num(invoiceCount)}
            </span>
          </div>

          {invoices.length === 0 ? (
            <div className="card">
              <p>
                <strong>{invoicesLoaded ? t('tuition_no_invoices') : t('loading')}</strong>
              </p>
              <p className="muted small">{t('tuition_no_invoices_hint')}</p>
            </div>
          ) : (
            <div className="table-wrap">
              <table className="data">
                <thead>
                  <tr>
                    <th>{t('th_student')}</th>
                    <th>{t('tuition_period')}</th>
                    <th>{t('tuition_amount')}</th>
                    <th>{t('tuition_paid')}</th>
                    <th>{t('tuition_outstanding')}</th>
                    <th>{t('tuition_deadline')}</th>
                    <th>{t('status')}</th>
                    <th>{t('th_actions')}</th>
                  </tr>
                </thead>
                <tbody>
                  {invoices.map((invoice) => (
                    <tr key={invoice.id}>
                      <td>{invoice.student_name}</td>
                      <td>
                        {invoice.period_label}
                        {invoice.course ? (
                          <>
                            <br />
                            <small className="muted">{invoice.course}</small>
                          </>
                        ) : null}
                      </td>
                      <td>{money(invoice.amount_due_uzs)}</td>
                      <td>{money(invoice.paid_amount_uzs)}</td>
                      <td>
                        <strong>{money(invoice.balance_uzs)}</strong>
                        {num(invoice.pending_amount_uzs) > 0 ? (
                          <>
                            <br />
                            <small className="muted">
                              {t('tuition_pending')}: {money(invoice.pending_amount_uzs)}
                            </small>
                          </>
                        ) : null}
                      </td>
                      <td className="muted small">{formatDate(invoice.due_date)}</td>
                      <td>
                        <span className={`badge ${STATUS_TONE[invoice.status] ?? ''}`}>
                          {statusLabel(invoice.status)}
                        </span>
                        {invoice.awaiting_confirmation ? (
                          <>
                            {' '}
                            <span className="badge">{t('tuition_pending')}</span>
                          </>
                        ) : null}
                      </td>
                      <td style={{ whiteSpace: 'nowrap' }}>
                        <button className="btn sm ghost" onClick={() => openAction('record', invoice)}>
                          {t('tuition_action_record')}
                        </button>{' '}
                        <button className="btn sm ghost" onClick={() => openAction('adjust', invoice)}>
                          {t('tuition_action_adjust')}
                        </button>{' '}
                        <button className="btn sm ghost" onClick={() => openAction('duedate', invoice)}>
                          {t('tuition_action_duedate')}
                        </button>{' '}
                        <button className="btn sm ghost" onClick={() => openAction('waive', invoice)}>
                          {t('tuition_action_waive')}
                        </button>{' '}
                        <button className="btn sm ghost" onClick={() => showAudit(invoice)}>
                          {t('tuition_action_history')}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {action && (
            <form onSubmit={submitAction} className="card form" style={{ maxWidth: '100%' }}>
              <h2>
                {action.kind === 'record'
                  ? t('tuition_action_record')
                  : action.kind === 'adjust'
                    ? t('tuition_action_adjust')
                    : action.kind === 'waive'
                      ? t('tuition_action_waive')
                      : t('tuition_action_duedate')}
                {' · '}
                {action.invoice.student_name} · {action.invoice.period_label}
              </h2>
              <div className="row">
                {(action.kind === 'record' || action.kind === 'adjust') && (
                  <label>
                    {t('tuition_policy_amount')}
                    <input
                      type="number"
                      min={0}
                      value={actionAmount}
                      onChange={(e) => setActionAmount(e.target.value)}
                      required
                    />
                  </label>
                )}
                {action.kind === 'record' && (
                  <>
                    <label>
                      {t('tuition_queue_col_method')}
                      <select value={actionMethod} onChange={(e) => setActionMethod(e.target.value)}>
                        {PAYMENT_METHODS.map((method) => (
                          <option key={method} value={method}>
                            {t(METHOD_KEYS[method])}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label>
                      {t('tuition_queue_col_reference')}
                      <input
                        value={actionReference}
                        onChange={(e) => setActionReference(e.target.value)}
                      />
                    </label>
                  </>
                )}
                {action.kind === 'duedate' && (
                  <>
                    <label>
                      {t('tuition_deadline')}
                      <input
                        type="date"
                        value={actionDueDate}
                        onChange={(e) => setActionDueDate(e.target.value)}
                        required
                      />
                    </label>
                    <label>
                      {t('tuition_policy_grace')}
                      <input
                        type="date"
                        value={actionGraceUntil}
                        onChange={(e) => setActionGraceUntil(e.target.value)}
                      />
                    </label>
                  </>
                )}
              </div>
              {action.kind !== 'duedate' && (
                <label>
                  {t('tuition_reason')}
                  <input
                    value={actionReason}
                    onChange={(e) => setActionReason(e.target.value)}
                    placeholder={t('tuition_reason_required')}
                    minLength={3}
                    required
                  />
                </label>
              )}
              <div className="row">
                <button className="btn primary">{t('save_changes')}</button>
                <button type="button" className="btn" onClick={() => setAction(null)}>
                  {t('cancel')}
                </button>
              </div>
            </form>
          )}

          {auditInvoice && (
            <section className="card">
              <div className="toolbar">
                <h2 style={{ margin: 0 }}>
                  <ScrollTextIcon size={16} className="ico" /> {t('tuition_audit_title')} ·{' '}
                  {auditInvoice.student_name} · {auditInvoice.period_label}
                </h2>
                <button className="btn ghost sm" onClick={() => setAuditInvoice(null)}>
                  {t('cancel')}
                </button>
              </div>
              {audit === null ? (
                <p className="muted">{t('loading')}</p>
              ) : audit.length === 0 ? (
                <p className="muted">{t('tuition_audit_empty')}</p>
              ) : (
                <div className="table-wrap">
                  <table className="data">
                    <thead>
                      <tr>
                        <th>{t('date')}</th>
                        <th>{t('tuition_audit_col_actor')}</th>
                        <th>{t('tuition_audit_col_change')}</th>
                        <th>{t('tuition_policy_name')}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {audit.map((row) => (
                        <tr key={row.id}>
                          <td className="muted small">{formatDateTime(row.created_at)}</td>
                          <td>{row.actor_name || '—'}</td>
                          <td>
                            <span className="badge">{row.action_label || row.action}</span>
                            <br />
                            <small className="muted">
                              {row.field}: {row.old_value || '—'} → {row.new_value || '—'}
                            </small>
                          </td>
                          <td className="muted small">{row.reason}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>
          )}
        </section>
      )}

      {/* ------------------------------------------------------------------ */}
      {/* Payment queue                                                       */}
      {/* ------------------------------------------------------------------ */}
      {tab === 'queue' && (
        <section>
          <p className="muted">{t('tuition_queue_hint')}</p>
          <div className="toolbar">
            <select value={queueStatus} onChange={(e) => setQueueStatus(e.target.value)}>
              <option value="">
                {t('all')} · {t('tuition_filter_status')}
              </option>
              <option value="pending_verification">{statusLabel('pending_verification')}</option>
              <option value="verified">{statusLabel('verified')}</option>
              <option value="rejected">{statusLabel('rejected')}</option>
            </select>
            <input
              placeholder={t('tuition_reason_required')}
              value={queueReason}
              onChange={(e) => setQueueReason(e.target.value)}
            />
            <button className="btn ghost sm" onClick={loadQueue}>
              {t('tuition_refresh')}
            </button>
          </div>

          {queue.length === 0 ? (
            <div className="card">
              <p>
                <strong>{t('tuition_queue_empty')}</strong>
              </p>
            </div>
          ) : (
            <div className="table-wrap">
              <table className="data">
                <thead>
                  <tr>
                    <th>{t('th_student')}</th>
                    <th>{t('tuition_period')}</th>
                    <th>{t('tuition_amount')}</th>
                    <th>{t('tuition_queue_col_method')}</th>
                    <th>{t('tuition_queue_col_reference')}</th>
                    <th>{t('date')}</th>
                    <th>{t('status')}</th>
                    <th>{t('th_actions')}</th>
                  </tr>
                </thead>
                <tbody>
                  {queue.map((row) => (
                    <tr key={row.id}>
                      <td>{row.student_name || `#${row.student_id}`}</td>
                      <td className="muted small">{row.invoice_period ?? '—'}</td>
                      <td>{money(row.amount_uzs)}</td>
                      <td>{t(METHOD_KEYS[row.method] ?? '') || row.method_label}</td>
                      <td className="muted small">{row.reference || '—'}</td>
                      <td className="muted small">{formatDateTime(row.created_at)}</td>
                      <td>
                        <span className={`badge ${row.status === 'verified' ? 'green' : ''}`}>
                          {rowStatus(row.status, row.status_label)}
                        </span>
                      </td>
                      <td style={{ whiteSpace: 'nowrap' }}>
                        {row.status === 'pending_verification' ? (
                          <>
                            <button className="btn sm primary" onClick={() => void decide(row, 'verify')}>
                              <ShieldCheckIcon size={13} className="ico" /> {t('tuition_verify')}
                            </button>{' '}
                            <button className="btn sm danger" onClick={() => void decide(row, 'reject')}>
                              {t('tuition_reject')}
                            </button>
                          </>
                        ) : (
                          <span className="muted small">
                            <ReceiptIcon size={13} className="ico" /> {row.verified_at ? formatDate(row.verified_at) : '—'}
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      {/* ------------------------------------------------------------------ */}
      {/* Reminders                                                           */}
      {/* ------------------------------------------------------------------ */}
      {tab === 'reminders' && (
        <section>
          <p className="muted">{t('tuition_reminder_intro')}</p>
          <p className="muted small">{t('tuition_reminder_offsets_hint')}</p>
          <p className="muted small">{t('tuition_reminder_off_hint')}</p>
          {policies.length === 0 ? (
            <div className="card">
              <p>
                <strong>{t('tuition_reminder_needs_policy')}</strong>
              </p>
            </div>
          ) : (
            policies.map((policy) => {
              const row = reminders[policy.id] ?? reminderForm(policy);
              return (
                <section key={policy.id} className="card">
                  <div className="toolbar">
                    <h2 style={{ margin: 0 }}>
                      <CreditCardIcon size={16} className="ico" /> {policy.name}
                    </h2>
                    <span className="badge">{scopeLabel(policy)}</span>
                    <span className="muted small">
                      {t('tuition_deadline')}: {policy.due_day}
                    </span>
                  </div>
                  <div className="row">
                    <label>
                      {t('tuition_reminder_before')}
                      <input
                        value={row.before}
                        placeholder="3, 7"
                        onChange={(e) => setReminder(policy.id, { before: e.target.value })}
                      />
                    </label>
                    <label>
                      {t('tuition_reminder_due')}
                      <input
                        value={row.due}
                        placeholder="0"
                        onChange={(e) => setReminder(policy.id, { due: e.target.value })}
                      />
                    </label>
                    <label>
                      {t('tuition_reminder_overdue')}
                      <input
                        value={row.overdue}
                        placeholder="3, 7, 14"
                        onChange={(e) => setReminder(policy.id, { overdue: e.target.value })}
                      />
                    </label>
                  </div>
                  <div className="row">
                    <label>
                      {t('tuition_reminder_quiet_start')}
                      <input
                        type="number"
                        min={0}
                        max={23}
                        value={row.quietStart}
                        onChange={(e) => setReminder(policy.id, { quietStart: e.target.value })}
                      />
                    </label>
                    <label>
                      {t('tuition_reminder_quiet_end')}
                      <input
                        type="number"
                        min={0}
                        max={23}
                        value={row.quietEnd}
                        onChange={(e) => setReminder(policy.id, { quietEnd: e.target.value })}
                      />
                    </label>
                    <button className="btn primary" onClick={() => void saveReminder(policy)}>
                      {t('save_changes')}
                    </button>
                  </div>
                  <p className="muted small">
                    {parseDays(row.before).join(', ') || '—'} · {parseDays(row.due).join(', ') || '—'} ·{' '}
                    {parseDays(row.overdue).join(', ') || '—'} ({t('tuition_reminder_quiet_start')}{' '}
                    {row.quietStart}:00–{row.quietEnd}:00 {t('tuition_hour_short')})
                  </p>
                </section>
              );
            })
          )}
        </section>
      )}
    </div>
  );
}
