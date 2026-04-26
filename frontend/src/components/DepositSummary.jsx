import { CalendarClock, CreditCard, Landmark, Percent, ReceiptText, WalletCards } from "lucide-react";
import { formatCurrency, formatDateTime, formatNumber } from "@/lib/format";

export const DepositSummary = ({ deposit }) => {
  const items = [
    { label: "رقم الحساب", value: deposit?.account_number, icon: CreditCard, testId: "summary-account-number" },
    { label: "رقم الوديعة", value: deposit?.deposit_number, icon: ReceiptText, testId: "summary-deposit-number" },
    { label: "مبلغ الوديعة", value: formatCurrency(deposit?.amount), icon: WalletCards, testId: "summary-deposit-amount" },
    { label: "نسبة الفائدة الشهرية", value: `${formatNumber(deposit?.monthly_interest_rate)}%`, icon: Percent, testId: "summary-interest-rate" },
    { label: "تاريخ إنشاء الوديعة", value: formatDateTime(deposit?.creation_datetime), icon: CalendarClock, testId: "summary-creation-date" },
    { label: "تاريخ الاستحقاق", value: formatDateTime(deposit?.maturity_datetime), icon: Landmark, testId: "summary-maturity-date" },
  ];

  return (
    <section className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3" data-testid="deposit-summary-section">
      {items.map((item) => {
        const Icon = item.icon;
        return (
          <div key={item.testId} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm" data-testid={`${item.testId}-card`}>
            <div className="flex items-start gap-3">
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-slate-700" data-testid={`${item.testId}-icon`}>
                <Icon className="h-5 w-5" />
              </span>
              <div className="min-w-0">
                <p className="text-sm font-bold text-slate-500" data-testid={`${item.testId}-label`}>{item.label}</p>
                <p className="mt-1 break-words text-lg font-extrabold text-slate-950" data-testid={item.testId}>{item.value || "—"}</p>
              </div>
            </div>
          </div>
        );
      })}
    </section>
  );
};
