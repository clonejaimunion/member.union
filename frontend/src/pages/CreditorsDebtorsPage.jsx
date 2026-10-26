import { formatAmountPlain } from "@/lib/format";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ArrowRight, Home, LogOut, Scale, ShieldCheck, Users, Receipt, UserCheck, Gavel, Plane, Beef, HeartHandshake, Wallet } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ExportReportButtons } from "@/components/ExportReportButtons";
import { CreditLine } from "@/components/CreditLine";
import { useAuth } from "@/contexts/AuthContext";
import { api } from "@/lib/api";

const MONTHS = ["يناير", "فبراير", "مارس", "ابريل", "مايو", "يونيو", "يوليو", "اغسطس", "سبتمبر", "اكتوبر", "نوفمبر", "ديسمبر"];
const ACCOUNTS = [
  { id: "social_insurance", title: "حـ/ التامينات الاجتماعية", endpoint: "/creditors-debtors/social-insurance", icon: ShieldCheck },
  { id: "union_committee", title: "حـ/ لجنة نقابية", endpoint: "/creditors-debtors/union-committee", icon: Users },
  { id: "supplier_tax", title: "حـ/ ضرائب الموردين", endpoint: "/creditors-debtors/supplier-tax", icon: Receipt },
  { id: "legal_accountant", title: "حـ/ المحاسب القانوني", endpoint: "/creditors-debtors/legal-accountant", icon: UserCheck },
  { id: "penalties_fund", title: "حـ/ صندوق الجزاءات", endpoint: "/creditors-debtors/penalties-fund", icon: Gavel },
  { id: "hajj_umrah", title: "حـ/ جمعية الحج والعمرة", endpoint: "/creditors-debtors/hajj-umrah", icon: Plane },
  { id: "meat_installment", title: "حـ/ قسط لحوم", endpoint: "/creditors-debtors/meat-installment", icon: Beef },
  { id: "martyrs_fund", title: "حـ/ صندوق أسر الشهداء", endpoint: "/creditors-debtors/martyrs-fund", icon: HeartHandshake },
  { id: "employee_advances", title: "حـ/ سلف العاملين", endpoint: "/creditors-debtors/employee-advances", icon: Wallet },
];

const formatAmount = (value) => {
  const num = Number(value || 0);
  if (Math.abs(num) < 0.005) return "-";
  return formatAmountPlain(num);
};

const BayanCell = ({ row }) => {
  if (!row) return <TableCell className="border border-slate-200" />;
  if (row.is_opening) return <TableCell className="border border-slate-200 text-center font-extrabold text-emerald-800">{row.month_name}</TableCell>;
  const note = row.note ? ` - ${row.note}` : "";
  return (
    <TableCell className="border border-slate-200 text-center font-bold">
      <span className="print:hidden">{row.month_name}{note}</span>
      <span className="hidden print:inline">{row.month_name}{row.year ? ` ${row.year}` : ""}{note}</span>
    </TableCell>
  );
};

export default function CreditorsDebtorsPage() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const currentYear = new Date().getFullYear();
  const [year, setYear] = useState(String(currentYear));
  const [month, setMonth] = useState("0");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [activeAccountId, setActiveAccountId] = useState(null);

  const activeAccount = useMemo(() => ACCOUNTS.find((a) => a.id === activeAccountId) || null, [activeAccountId]);
  const years = useMemo(() => Array.from({ length: 7 }, (_, i) => String(currentYear - 4 + i)), [currentYear]);

  const loadData = useCallback(async () => {
    if (!activeAccount) return;
    setLoading(true);
    try {
      const params = new URLSearchParams({ year, month });
      const response = await api.get(`${activeAccount.endpoint}?${params.toString()}`);
      setData(response.data);
    } catch (error) {
      toast.error("تعذر تحميل الحساب");
    } finally {
      setLoading(false);
    }
  }, [activeAccount, year, month]);

  useEffect(() => { loadData(); }, [loadData]);

  const periodLabel = month === "0" ? `سنة ${year}` : `${MONTHS[Number(month) - 1]} ${year}`;
  const debit = data?.debit || [];
  const credit = data?.credit || [];
  const rowCount = Math.max(debit.length, credit.length);

  return (
    <main className="min-h-screen bg-slate-50 text-slate-950" data-testid="creditors-debtors-page">
      <header className="sticky top-0 z-20 border-b border-slate-200/70 bg-white/90 backdrop-blur-xl print:hidden" data-testid="creditors-debtors-header">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-4 sm:px-6 lg:px-8">
          <div className="flex items-center gap-3"><div className="flex h-11 w-11 items-center justify-center rounded-xl bg-slate-950 text-white"><Scale className="h-5 w-5" /></div><div><p className="text-xs font-extrabold text-emerald-700">تقارير تلقائية</p><h1 className="text-2xl font-extrabold" data-testid="creditors-debtors-title">الدائنون و المدينون</h1></div></div>
          <div className="flex flex-wrap items-center gap-3"><Badge className="bg-white text-slate-700">{user?.organization_name}</Badge><Button asChild variant="outline" className="h-11 rounded-lg bg-white" data-testid="creditors-home-button"><Link to="/"><Home className="h-4 w-4" /> الرئيسية</Link></Button><Button onClick={() => navigate(-1)} variant="outline" className="h-11 rounded-lg bg-white" data-testid="creditors-back-button"><ArrowRight className="h-4 w-4" /> رجوع</Button><Button onClick={logout} variant="outline" className="h-11 rounded-lg bg-white" data-testid="creditors-logout-button"><LogOut className="h-4 w-4" /> خروج</Button></div>
        </div>
      </header>

      <section className="mx-auto max-w-7xl space-y-6 px-4 py-8 sm:px-6 lg:px-8" data-testid="creditors-debtors-content">
        {!activeAccount && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3" data-testid="creditors-debtors-grid">
            {ACCOUNTS.map((account) => (
              <button key={account.id} type="button" onClick={() => setActiveAccountId(account.id)} className="group flex items-center gap-4 rounded-2xl border border-slate-200 bg-white p-5 text-right shadow-sm transition-all hover:-translate-y-1 hover:border-slate-300 hover:shadow-xl" data-testid={`creditors-card-${account.id}`}>
                <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-xl bg-slate-950 text-white transition-transform group-hover:scale-105"><account.icon className="h-6 w-6" /></div>
                <div><h3 className="text-lg font-extrabold">{account.title}</h3><p className="text-xs font-bold text-slate-500">حساب أستاذ (مدين / دائن)</p></div>
              </button>
            ))}
          </div>
        )}

        {activeAccount && (
          <section className="space-y-4" data-testid="creditors-active-account">
            <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm print:hidden" data-testid="creditors-filters-section">
              <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
                <div><Label>السنة</Label><Select value={year} onValueChange={setYear}><SelectTrigger className="mt-2 h-11 bg-slate-50" data-testid="creditors-year-select"><SelectValue /></SelectTrigger><SelectContent>{years.map((y) => <SelectItem key={y} value={y}>{y}</SelectItem>)}</SelectContent></Select></div>
                <div><Label>الشهر</Label><Select value={month} onValueChange={setMonth}><SelectTrigger className="mt-2 h-11 bg-slate-50" data-testid="creditors-month-select"><SelectValue /></SelectTrigger><SelectContent><SelectItem value="0">كل الشهور (سنوي)</SelectItem>{MONTHS.map((m, i) => <SelectItem key={m} value={String(i + 1)}>{m}</SelectItem>)}</SelectContent></Select></div>
                <div className="flex items-end"><Button onClick={loadData} className="h-11 w-full bg-slate-950 text-white" data-testid="creditors-apply-button">تحديث</Button></div>
                <div className="flex items-end"><Button onClick={() => { setActiveAccountId(null); setData(null); }} variant="outline" className="h-11 w-full bg-white" data-testid="creditors-back-list-button"><ArrowRight className="h-4 w-4" /> كل الحسابات</Button></div>
              </div>
              <p className="mt-3 text-sm font-bold text-slate-500">الفترة: {periodLabel}{loading ? " — جاري التحميل..." : ""}</p>
            </section>

            <div className="flex flex-wrap items-center justify-end gap-3 print:hidden">
              <ExportReportButtons title={`${activeAccount.title} - ${periodLabel}`} fileName={`${activeAccount.title}-${periodLabel}`} selectors={["[data-testid='creditors-report-section']"]} disabled={loading} pdfLabel="طباعة PDF" pdfTestId="creditors-print-button" excelTestId="creditors-export-excel-button" wordTestId="creditors-export-word-button" />
            </div>

            <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm" data-testid="creditors-report-section">
              <div className="mb-4 text-center">
                <h2 className="text-xl font-extrabold text-slate-950" data-testid="creditors-report-heading">{activeAccount.title}</h2>
                <p className="text-sm font-bold text-slate-600">{periodLabel}</p>
              </div>
              <div className="overflow-x-auto rounded-xl border border-slate-300" data-testid="creditors-report-table-wrapper">
                <Table className="text-sm">
                  <TableHeader>
                    <TableRow className="bg-slate-950 hover:bg-slate-950">
                      <TableHead colSpan={3} className="border border-slate-300 text-center text-base text-white">جانب مدين</TableHead>
                      <TableHead colSpan={3} className="border border-slate-300 text-center text-base text-white">جانب دائن</TableHead>
                    </TableRow>
                    <TableRow className="bg-slate-800 hover:bg-slate-800">
                      <TableHead className="border border-slate-300 text-center text-xs text-white">المبلغ</TableHead>
                      <TableHead className="border border-slate-300 text-center text-xs text-white">البيان</TableHead>
                      <TableHead className="border border-slate-300 text-center text-xs text-white">التاريخ</TableHead>
                      <TableHead className="border border-slate-300 text-center text-xs text-white">المبلغ</TableHead>
                      <TableHead className="border border-slate-300 text-center text-xs text-white">البيان</TableHead>
                      <TableHead className="border border-slate-300 text-center text-xs text-white">التاريخ</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {rowCount === 0 && <TableRow><TableCell colSpan={6} className="py-6 text-center font-bold text-slate-500">لا توجد حركات خلال الفترة</TableCell></TableRow>}
                    {Array.from({ length: rowCount }).map((_, idx) => {
                      const d = debit[idx];
                      const c = credit[idx];
                      return (
                        <TableRow key={idx} data-testid={`creditors-row-${idx}`}>
                          <TableCell className="border border-slate-200 text-center tabular-nums" dir="ltr">{d ? formatAmount(d.amount) : ""}</TableCell>
                          <BayanCell row={d} />
                          <TableCell className="border border-slate-200 text-center tabular-nums" dir="ltr">{d ? d.date_label : ""}</TableCell>
                          <TableCell className="border border-slate-200 text-center tabular-nums" dir="ltr">{c ? formatAmount(c.amount) : ""}</TableCell>
                          <BayanCell row={c} />
                          <TableCell className="border border-slate-200 text-center tabular-nums" dir="ltr">{c ? c.date_label : ""}</TableCell>
                        </TableRow>
                      );
                    })}
                    {rowCount > 0 && (
                      <TableRow className="bg-emerald-50 font-extrabold hover:bg-emerald-50" data-testid="creditors-total-row">
                        <TableCell className="border border-slate-200 text-center font-extrabold tabular-nums" dir="ltr">{formatAmount(data?.debit_total)}</TableCell>
                        <TableCell className="border border-slate-200 text-center font-extrabold">الإجمالي</TableCell>
                        <TableCell className="border border-slate-200" />
                        <TableCell className="border border-slate-200 text-center font-extrabold tabular-nums" dir="ltr">{formatAmount(data?.credit_total)}</TableCell>
                        <TableCell className="border border-slate-200 text-center font-extrabold">الإجمالي</TableCell>
                        <TableCell className="border border-slate-200" />
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </div>
              {data?.difference != null && (
                <div className="mt-4 flex items-center justify-between rounded-xl border-2 border-emerald-300 bg-emerald-50 px-6 py-4" data-testid="creditors-difference-box">
                  <span className="text-base font-extrabold text-emerald-900">{data.difference_label || "الفرق / الرصيد الدائن المستحق"}</span>
                  <span className="text-lg font-extrabold tabular-nums text-emerald-900" dir="ltr">{formatAmount(data.difference)}</span>
                </div>
              )}
              {data?.warning_note && (
                <div className="mt-3 rounded-xl border-2 border-amber-300 bg-amber-50 px-6 py-3 text-center text-sm font-extrabold text-amber-900" data-testid="creditors-warning-note">
                  ⚠ {data.warning_note}
                </div>
              )}
            </section>
          </section>
        )}
      </section>

      <footer className="px-4 pb-5 print:hidden"><CreditLine testId="creditors-debtors-creator-credit" /></footer>
    </main>
  );
}
