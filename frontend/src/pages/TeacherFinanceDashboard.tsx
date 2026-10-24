import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

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
  monthly_fee: number;
  students_count?: number;
}

export default function TeacherFinanceDashboard() {
  const [groups, setGroups] = useState<TeacherGroup[]>([]);
  const [selectedGroupId, setSelectedGroupId] = useState<number | null>(null);
  const [financeData, setFinanceData] = useState<GroupFinanceData | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionBusy, setActionBusy] = useState(false);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  // Load Teacher Groups
  useEffect(() => {
    async function fetchGroups() {
      try {
        const res = await apiFetch<any>('/api/v1/school/overview/');
        const groupsList: TeacherGroup[] = (res?.groups || []).map((g: any) => ({
          id: g.id,
          name: g.name,
          monthly_fee: g.monthly_fee || 400000,
        }));
        setGroups(groupsList);
        if (groupsList.length > 0) {
          setSelectedGroupId(groupsList[0].id);
        } else {
          setLoading(false);
        }
      } catch (err) {
        console.error('Error fetching teacher groups:', err);
        setLoading(false);
      }
    }
    fetchGroups();
  }, []);

  // Load Finance Summary for Selected Group
  useEffect(() => {
    if (!selectedGroupId) return;
    async function fetchFinance() {
      setLoading(true);
      try {
        const data = await apiFetch<GroupFinanceData>(
          `/api/v1/courses/groups/${selectedGroupId}/finance-summary/`
        );
        setFinanceData(data);
      } catch (err: any) {
        showToast(err.message || 'Moliyaviy ma\'lumotlarni yuklashda xatolik.', 'error');
      } finally {
        setLoading(false);
      }
    }
    fetchFinance();
  }, [selectedGroupId]);

  const showToast = (message: string, type: 'success' | 'error') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 5000);
  };

  // 1-Click Reminder to all debtors
  const handleSendReminders = async () => {
    if (!selectedGroupId) return;
    setActionBusy(true);
    try {
      const res = await apiFetch<{ status: string; message: string }>(
        `/api/v1/courses/groups/${selectedGroupId}/send-payment-reminders/`,
        { method: 'POST' }
      );
      showToast(res.message || 'Eslatmalar muvaffaqiyatli yuborildi!', 'success');
    } catch (err: any) {
      showToast(err.message || 'Eslatma yuborishda xatolik yuz berdi.', 'error');
    } finally {
      setActionBusy(false);
    }
  };

  // Record Manual Payment
  const handleRecordPayment = async (studentId: number) => {
    if (!selectedGroupId) return;
    try {
      const res = await apiFetch<{ status: string; message: string }>(
        `/api/v1/courses/groups/${selectedGroupId}/record-payment/`,
        {
          method: 'POST',
          body: JSON.stringify({ student_id: studentId, extend_days: 30 }),
        }
      );
      showToast(res.message, 'success');
      // Refresh
      const data = await apiFetch<GroupFinanceData>(
        `/api/v1/courses/groups/${selectedGroupId}/finance-summary/`
      );
      setFinanceData(data);
    } catch (err: any) {
      showToast(err.message || 'To\'lovni qayd qilishda xatolik.', 'error');
    }
  };

  // Activate Quota for student
  const handleActivateQuota = async (studentId: number, planType: 'pro' | 'premium') => {
    if (!selectedGroupId) return;
    try {
      const res = await apiFetch<{ status: string; message: string; pro_quota_balance: number; premium_quota_balance: number }>(
        `/api/v1/courses/groups/${selectedGroupId}/students/${studentId}/activate-quota/`,
        {
          method: 'POST',
          body: JSON.stringify({ plan_type: planType }),
        }
      );
      showToast(res.message, 'success');
      // Refresh
      const data = await apiFetch<GroupFinanceData>(
        `/api/v1/courses/groups/${selectedGroupId}/finance-summary/`
      );
      setFinanceData(data);
    } catch (err: any) {
      showToast(err.message || 'Litsenziya kvotasini faollashtirib bo\'lmadi.', 'error');
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 py-8 space-y-6">
        {/* Toast Alert */}
        {toast && (
          <div
            className={`p-4 rounded-xl shadow-lg border flex items-center justify-between transition-all ${
              toast.type === 'success'
                ? 'bg-emerald-950/80 border-emerald-500/50 text-emerald-200'
                : 'bg-rose-950/80 border-rose-500/50 text-rose-200'
            }`}
          >
            <span>{toast.message}</span>
            <button
              onClick={() => setToast(null)}
              className="text-xs uppercase px-2 py-1 bg-white/10 rounded hover:bg-white/20"
            >
              Yopish
            </button>
          </div>
        )}

        {/* Top Header & Group Selector */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-slate-900/60 p-6 rounded-2xl border border-slate-800">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-2xl">💰</span>
              <h1 className="text-2xl font-bold text-white">Ustoz Moliya & Kurs To'lovlari CRM</h1>
            </div>
            <p className="text-slate-400 text-sm">
              O'quvchilar to'lov grafigi, qarzdorlik nazorati va ota-onalarga avtomatik eslatmalar tizimi.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            {/* Group Selector */}
            {groups.length > 0 && (
              <select
                value={selectedGroupId || ''}
                onChange={(e) => setSelectedGroupId(Number(e.target.value))}
                className="bg-slate-800 text-white border border-slate-700 rounded-xl px-4 py-2.5 text-sm font-medium focus:ring-2 focus:ring-amber-500"
              >
                {groups.map((g) => (
                  <option key={g.id} value={g.id}>
                    👥 {g.name}
                  </option>
                ))}
              </select>
            )}

            <Link
              to="/teacher/vocab-generator"
              className="px-4 py-2.5 rounded-xl bg-purple-600/20 text-purple-300 border border-purple-500/30 hover:bg-purple-600/30 font-medium text-sm transition-all"
            >
              ✨ AI Lug'at Generatori
            </Link>

            <Link
              to="/groups"
              className="px-4 py-2.5 rounded-xl bg-slate-800 text-slate-300 border border-slate-700 hover:bg-slate-700 font-medium text-sm transition-all"
            >
              Guruhlar ro'yxati
            </Link>
          </div>
        </div>

        {/* Quota & Financial KPI Cards */}
        {financeData && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Total Collected */}
            <div className="bg-slate-900/80 p-5 rounded-2xl border border-emerald-500/20 shadow-sm relative overflow-hidden">
              <div className="text-xs uppercase font-semibold text-emerald-400 mb-1">
                Yig'ilgan To'lov
              </div>
              <div className="text-2xl font-black text-white">
                {financeData.collected_amount.toLocaleString('uz-UZ')} so'm
              </div>
              <div className="text-xs text-slate-400 mt-2 flex items-center gap-1">
                <span className="inline-block w-2 h-2 rounded-full bg-emerald-500"></span>
                <span>{financeData.paid_count} ta o'quvchi to'lagan</span>
              </div>
            </div>

            {/* Overdue Debt */}
            <div className="bg-slate-900/80 p-5 rounded-2xl border border-rose-500/20 shadow-sm relative overflow-hidden">
              <div className="text-xs uppercase font-semibold text-rose-400 mb-1">
                Kutilayotgan Qarzdorlik
              </div>
              <div className="text-2xl font-black text-white">
                {financeData.pending_amount.toLocaleString('uz-UZ')} so'm
              </div>
              <div className="text-xs text-slate-400 mt-2 flex items-center gap-1">
                <span className="inline-block w-2 h-2 rounded-full bg-rose-500"></span>
                <span>{financeData.overdue_count + financeData.due_soon_count} nafar qarzdor</span>
              </div>
            </div>

            {/* Total Students */}
            <div className="bg-slate-900/80 p-5 rounded-2xl border border-slate-700/60 shadow-sm">
              <div className="text-xs uppercase font-semibold text-slate-400 mb-1">
                Guruhdagi O'quvchilar
              </div>
              <div className="text-2xl font-black text-white">
                {financeData.total_students} nafar
              </div>
              <div className="text-xs text-slate-400 mt-2">
                Oylik to'lov: {financeData.students[0]?.monthly_fee?.toLocaleString('uz-UZ') || '400 000'} so'm
              </div>
            </div>

            {/* Teacher Quotas */}
            <div className="bg-gradient-to-br from-amber-950/40 to-slate-900/80 p-5 rounded-2xl border border-amber-500/30 shadow-sm">
              <div className="text-xs uppercase font-semibold text-amber-400 mb-1">
                Litsenziya Kvotangiz
              </div>
              <div className="flex items-center gap-4 text-xl font-bold text-white mt-1">
                <span title="PRO kvota">⚡ {financeData.pro_quota_balance} PRO</span>
                <span className="text-slate-600">|</span>
                <span title="PREMIUM kvota">👑 {financeData.premium_quota_balance} VIP</span>
              </div>
              <div className="text-xs text-slate-400 mt-2">
                O'quvchilarga 30 kunlik obuna ulashish
              </div>
            </div>
          </div>
        )}

        {/* 1-Click Reminder Action Banner */}
        {financeData && (financeData.overdue_count > 0 || financeData.due_soon_count > 0) && (
          <div className="bg-gradient-to-r from-amber-950/50 via-slate-900 to-rose-950/50 p-5 rounded-2xl border border-amber-500/30 flex flex-col md:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-amber-500/20 text-amber-400 flex items-center justify-center text-xl shrink-0">
                📢
              </div>
              <div>
                <h3 className="font-semibold text-white">
                  {financeData.overdue_count + financeData.due_soon_count} ta o'quvchining to'lov muddati kelgan!
                </h3>
                <p className="text-xs text-slate-300">
                  Bitta klik orqali barcha qarzdor o'quvchilar va ularning ota-onalariga Telegram orqali rasmiy eslatma xabari yuboriladi.
                </p>
              </div>
            </div>
            <button
              onClick={handleSendReminders}
              disabled={actionBusy}
              className="px-6 py-3 rounded-xl bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-600 hover:to-amber-700 text-slate-950 font-bold text-sm shadow-md transition-all whitespace-nowrap disabled:opacity-50"
            >
              {actionBusy ? 'Yuborilmoqda...' : '📢 Barcha qarzdorlarga eslatma yuborish'}
            </button>
          </div>
        )}

        {/* Students Tuition Table */}
        <div className="bg-slate-900/60 rounded-2xl border border-slate-800 overflow-hidden">
          <div className="p-5 border-b border-slate-800 flex items-center justify-between">
            <h2 className="text-lg font-bold text-white flex items-center gap-2">
              <span>📋</span> O'quvchilar va Ota-onalar Nazorati
            </h2>
            <span className="text-xs text-slate-400">
              Jami: {financeData?.students.length || 0} ta o'quvchi
            </span>
          </div>

          {loading ? (
            <div className="p-12 text-center text-slate-400 animate-pulse">
              Moliyaviy ma'lumotlar yuklanmoqda...
            </div>
          ) : financeData && financeData.students.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm text-slate-300">
                <thead className="bg-slate-800/60 text-xs uppercase font-semibold text-slate-400 border-b border-slate-800">
                  <tr>
                    <th className="py-3.5 px-4">O'quvchi</th>
                    <th className="py-3.5 px-4">Telefon</th>
                    <th className="py-3.5 px-4">Ota-ona</th>
                    <th className="py-3.5 px-4">Oylik To'lov</th>
                    <th className="py-3.5 px-4">To'lov Sanasi</th>
                    <th className="py-3.5 px-4">Holat</th>
                    <th className="py-3.5 px-4 text-right">Litsenziya & Harakat</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {financeData.students.map((st) => (
                    <tr key={st.id} className="hover:bg-slate-800/30 transition-colors">
                      <td className="py-3.5 px-4">
                        <div className="font-semibold text-white">{st.full_name}</div>
                        <div className="text-xs text-slate-400">{st.email}</div>
                      </td>
                      <td className="py-3.5 px-4 text-xs font-mono">
                        {st.phone || '—'}
                      </td>
                      <td className="py-3.5 px-4 text-xs">
                        {st.parent_phone ? (
                          <div>
                            <div className="text-slate-200">{st.parent_phone}</div>
                            {st.parent_telegram_id && (
                              <span className="inline-block px-1.5 py-0.5 rounded text-[10px] bg-sky-950/60 text-sky-400 border border-sky-800/50 mt-0.5">
                                Telegram Ulangan
                              </span>
                            )}
                          </div>
                        ) : (
                          <span className="text-slate-500 italic">Kiritilmagan</span>
                        )}
                      </td>
                      <td className="py-3.5 px-4 font-medium text-white">
                        {st.monthly_fee.toLocaleString('uz-UZ')} so'm
                      </td>
                      <td className="py-3.5 px-4 text-xs">
                        <div className="text-white font-medium">
                          {st.next_payment_due || '—'}
                        </div>
                        {st.last_payment_date && (
                          <div className="text-[11px] text-slate-400">
                            Oxirgi: {st.last_payment_date}
                          </div>
                        )}
                      </td>
                      <td className="py-3.5 px-4">
                        {st.payment_status === 'paid' && (
                          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-950 text-emerald-300 border border-emerald-800/60">
                            ✓ To'langan
                          </span>
                        )}
                        {st.payment_status === 'due_soon' && (
                          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-amber-950 text-amber-300 border border-amber-800/60">
                            ⚠️ {st.days_left} kun qoldi
                          </span>
                        )}
                        {st.payment_status === 'overdue' && (
                          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium bg-rose-950 text-rose-300 border border-rose-800/60">
                            🔴 Muddati o'tgan
                          </span>
                        )}
                      </td>
                      <td className="py-3.5 px-4 text-right">
                        <div className="flex items-center justify-end gap-2">
                          {/* Record Payment Button */}
                          <button
                            onClick={() => handleRecordPayment(st.student_id)}
                            title="30 kunga to'lovni uzaytirish"
                            className="px-2.5 py-1 rounded-lg bg-emerald-950/80 hover:bg-emerald-800 text-emerald-200 border border-emerald-700/60 text-xs font-medium transition-all"
                          >
                            💳 To'landi (+30k)
                          </button>

                          {/* Quota activation buttons */}
                          <button
                            onClick={() => handleActivateQuota(st.student_id, 'pro')}
                            disabled={financeData.pro_quota_balance <= 0}
                            title="Ustoz kvotasi orqali 30 kunlik PRO litsenziya berish"
                            className="px-2.5 py-1 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 border border-amber-500/40 text-xs font-medium transition-all disabled:opacity-40"
                          >
                            ⚡ PRO
                          </button>

                          <button
                            onClick={() => handleActivateQuota(st.student_id, 'premium')}
                            disabled={financeData.premium_quota_balance <= 0}
                            title="Ustoz kvotasi orqali 30 kunlik PREMIUM litsenziya berish"
                            className="px-2.5 py-1 rounded-lg bg-purple-500/20 hover:bg-purple-500/30 text-purple-300 border border-purple-500/40 text-xs font-medium transition-all disabled:opacity-40"
                          >
                            👑 VIP
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="p-12 text-center text-slate-500">
              Bu guruhda hozircha o'quvchilar mavjud emas.
            </div>
          )}
        </div>
      </div>
  );
}
