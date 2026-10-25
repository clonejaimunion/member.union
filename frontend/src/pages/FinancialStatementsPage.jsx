import { Fragment, useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { AlertTriangle, ArrowRight, FileSpreadsheet, FileWarning, Home, LogOut, Printer, Scale } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { ExportReportButtons } from "@/components/ExportReportButtons";
import { CreditLine } from "@/components/CreditLine";
import { useAuth } from "@/contexts/AuthContext";
import { useAppSettings } from "@/contexts/AppSettingsContext";
import { api } from "@/lib/api";
import { formatCurrency } from "@/lib/format";
import { printNow } from "@/lib/printOrientation";
import { injectPrintLogo } from "@/lib/printLogo";

const currentYear = new Date().getFullYear();
const years = Array.from({ length: 16 }, (_, index) => currentYear - 10 + index);

const AR_MONTHS = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو", "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"];
const monthRange = (year, fromMonth, toMonth) => {
  const from = `${year}-${String(fromMonth).padStart(2, "0")}-01`;
  const lastDay = new Date(Number(year), Number(toMonth), 0).getDate();
  const to = `${year}-${String(toMonth).padStart(2, "0")}-${String(lastDay).padStart(2, "0")}`;
  return { from_date: from, to_date: to };
};
const sectionTotal = (section) => Number(section?.total || 0);
const officialEmailOrEmpty = (email) => {
  const value = (email || "").trim();
  if (!value || value.toLowerCase().endsWith("@example.com") || value.toLowerCase().includes("+iter")) return "";
  return value;
};

// خريطة مقارنة بالسنة السابقة بالاسم
const buildPrevMap = (lines = []) => Object.fromEntries((lines || []).map((line) => [line.name, Number(line.amount || 0)]));

// وصف مصدر الرقم والأساس المحاسبي الذي وُضع عليه
const buildBasisText = (kind, periodText, dateLabel) => {
  switch (kind) {
    case "fixed_asset":
      return `قيمة شراء الأصل الثابت (التكلفة التاريخية) بالرصيد المدين المتراكم ${dateLabel}. مصدرها قيود بوابة الأصول الثابتة المرحّلة تلقائياً.`;
    case "bank":
      return `رصيد الحساب (البنك/النقدية/الوديعة) = صافي الإيداعات والسحوبات المتراكمة ${dateLabel}. مصدرها قيود الخزينة والبنوك والودائع.`;
    case "asset_cumulative":
      return `رصيد هذا الأصل (مدين) متراكم ${dateLabel}. مصدره قيود اليومية المرحّلة تلقائياً من بوابات البرنامج.`;
    case "provision":
      return `مجمع إهلاك الأصل (رصيد دائن متراكم) محسوب بطريقة القسط الثابت من بوابة الأصول الثابتة ${dateLabel}.`;
    case "liability":
      return `رصيد دائن (التزام على الصندوق) متراكم ${dateLabel}، من قيود المستحقات/السداد المرحّلة.`;
    case "equity":
      return `حقوق ملكية / رصيد مرحّل متراكم ${dateLabel}. يشمل الأرصدة الافتتاحية ونتائج الفترات السابقة.`;
    case "surplus":
      return `هذا الرقم ناتج الفترة = إجمالي الإيرادات − إجمالي المصروفات خلال ${periodText}. وهو سطر محسوب وليس حساباً مستقلاً.`;
    case "revenue":
      return `إجمالي ما تم تسجيله لهذا الحساب من إيراد خلال ${periodText}، من بوابة الإيرادات.`;
    case "expense":
      return `إجمالي ما تم صرفه على هذا الحساب خلال ${periodText}، من بوابة المصروفات.`;
    case "depreciation_expense":
      return `مصروف إهلاك الفترة لهذه الفئة محسوب بطريقة القسط الثابت، خلال ${periodText}.`;
    case "receipt_opening":
      return `رصيد البنك/الوديعة أول المدة (المتراكم قبل بداية الفترة).`;
    case "receipt_closing":
      return `رصيد البنك/الوديعة آخر المدة (المتراكم حتى نهاية الفترة).`;
    case "receipt_activity":
      return `إجمالي المقبوضات النقدية المرتبطة بهذا الحساب خلال ${periodText}.`;
    case "payment_activity":
      return `إجمالي المدفوعات النقدية المرتبطة بهذا الحساب خلال ${periodText}.`;
    default:
      return `تفاصيل مصدر الرقم خلال ${periodText}.`;
  }
};

// تحويل سطور الإيرادات حسب طلب المستخدم: تجميع كل ما يحتوي "اشتراك" في سطر واحد، وإخفاء دفع الكتروني/أوامر الدفع
const linesTotal = (lines = []) => Math.round((lines || []).reduce((sum, line) => sum + Number(line.amount || 0), 0) * 100) / 100;

function SignatureStrip({ testId }) {
  return (
    <div className="signature-strip mt-12 flex items-start justify-between font-extrabold" data-testid={testId}>
      <div className="w-1/2 px-4 text-center" data-testid={`${testId}-treasurer`}><p className="text-lg">أمين الصندوق</p><p className="mt-6 text-sm">........................</p></div>
      <div className="w-1/2 px-4 text-center" data-testid={`${testId}-chairman`}><p className="text-lg">رئيس النقابة العامة</p><p className="mt-6 text-sm">........................</p></div>
    </div>
  );
}

function ReportHeader({ title, subtitle, year, dateLabel, testId, unionName, projectName, email }) {
  return (
    <div className="mb-6 text-center" data-testid={testId}>
      <p className="text-lg font-extrabold" data-testid={`${testId}-organization`}>{unionName}</p>
      <p className="text-base font-bold" data-testid={`${testId}-project`}>{projectName}</p>
      {email && <p className="text-sm font-bold" data-testid={`${testId}-email`}>{email}</p>}
      <h2 className="mt-3 text-3xl font-extrabold" data-testid={`${testId}-title`}>{title}</h2>
      <p className="mt-1 text-xl font-extrabold" data-testid={`${testId}-date`}>{dateLabel || `في ${year}`}</p>
      {subtitle && <p className="mt-1 text-sm font-bold text-slate-500" data-testid={`${testId}-subtitle`}>{subtitle}</p>}
    </div>
  );
}

// أكواد شجرة الحسابات لتجميع بنود الميزانية بنفس أقسام نماذج الإكسل
const FIXED_ASSET_CODES = ["5", "101", "151", "155"];
const isAccumDepCode = (code) => String(code || "").endsWith("-م");
const isFixedAssetCode = (code) => FIXED_ASSET_CODES.includes(String(code || ""));
const isBankCashCode = (code) => { const c = String(code || ""); return c.startsWith("11") || c === "1250"; };
const isAccruedInterestCode = (code) => String(code || "") === "1300";
const isInventoryCode = (code) => String(code || "") === "1700";
const isAdvancesCode = (code) => String(code || "") === "1500";

const prevHasData = (p) => !!p && (
  Number(p?.balance_sheet?.assets?.total || 0) !== 0 ||
  (p?.revenues_expenses?.revenues?.lines || []).length > 0 ||
  (p?.receipts_payments?.receipts?.lines || []).length > 0
);

// جدول جانب واحد (مدين أو دائن) مقسّم إلى مجموعات بعناوين فرعية مثل نماذج الإكسل
function GroupedSideTable({ sideTitle, groups, total, year, prevYear, showPrev, prevMap = {}, prevTotal = 0, testId, onAmountClick }) {
  const cols = showPrev ? 3 : 2;
  const prevOf = (name) => Number(prevMap[name] ?? 0);
  let rowIndex = -1;
  return (
    <div className="rounded-lg border border-slate-300 bg-white" data-testid={`${testId}-box`}>
      <div className="border-b border-slate-300 bg-slate-900 px-4 py-2 text-center text-lg font-extrabold text-white" data-testid={`${testId}-title`}>{sideTitle}</div>
      <Table data-testid={testId}>
        <TableHeader>
          <TableRow className="bg-white hover:bg-white">
            <TableHead className="border border-slate-300 text-center font-extrabold text-slate-900">البيان</TableHead>
            <TableHead className="w-32 border border-slate-300 text-center font-extrabold text-slate-900">{year}</TableHead>
            {showPrev && <TableHead className="w-32 border border-slate-300 text-center font-extrabold text-slate-900">مقارن {prevYear}</TableHead>}
          </TableRow>
        </TableHeader>
        <TableBody>
          {groups.map((group, gi) => (
            <Fragment key={`g-${gi}`}>
              <TableRow className="bg-slate-100 hover:bg-slate-100" data-testid={`${testId}-group-${gi}`}>
                <TableCell colSpan={cols} className="border border-slate-300 font-extrabold text-slate-800">{group.title}</TableCell>
              </TableRow>
              {(group.rows || []).length === 0 && (
                <TableRow><TableCell colSpan={cols} className="border border-slate-300 py-2 text-center text-sm font-bold text-slate-400">—</TableCell></TableRow>
              )}
              {(group.rows || []).map((line) => {
                rowIndex += 1;
                return (
                  <TableRow key={`${line.code || ""}-${line.name}-${rowIndex}`} data-testid={`${testId}-row-${rowIndex}`}>
                    <TableCell className="border border-slate-300 pr-6 font-bold" data-testid={`${testId}-row-${rowIndex}-name`}>{line.name}</TableCell>
                    <TableCell className="border border-slate-300 text-center font-extrabold" data-testid={`${testId}-row-${rowIndex}-amount`}>
                      {onAmountClick ? (
                        <button type="button" onClick={() => onAmountClick(group, line)} className="w-full cursor-pointer text-center font-extrabold text-slate-900 underline decoration-dotted decoration-slate-400 underline-offset-4 transition-colors hover:text-emerald-700 print:no-underline" data-testid={`${testId}-row-${rowIndex}-amount-button`}>{formatCurrency(Number(line.amount || 0))}</button>
                      ) : formatCurrency(Number(line.amount || 0))}
                    </TableCell>
                    {showPrev && <TableCell className="border border-slate-300 text-center font-bold text-slate-600" data-testid={`${testId}-row-${rowIndex}-prev-amount`}>{formatCurrency(prevOf(line.name))}</TableCell>}
                  </TableRow>
                );
              })}
            </Fragment>
          ))}
          <TableRow className="bg-slate-200 font-extrabold hover:bg-slate-200" data-testid={`${testId}-total-row`}>
            <TableCell className="border border-slate-300">الإجمالي</TableCell>
            <TableCell className="border border-slate-300 text-center" data-testid={`${testId}-current-total`}>{formatCurrency(total || 0)}</TableCell>
            {showPrev && <TableCell className="border border-slate-300 text-center text-slate-600" data-testid={`${testId}-prev-total`}>{formatCurrency(prevTotal || 0)}</TableCell>}
          </TableRow>
        </TableBody>
      </Table>
    </div>
  );
}

function BalanceSheetPrint({ report, prevReport, year, dateLabel, unionName, projectName, email, onAmountClick }) {
  const prevYear = Number(year) - 1;
  const showPrev = Number(year) >= 2027 && prevHasData(prevReport);
  const assetLines = report?.balance_sheet?.assets?.lines || [];
  const liabilityLines = report?.balance_sheet?.liabilities?.lines || [];
  const equityLines = report?.balance_sheet?.equity?.lines || [];

  const pick = (lines, fn) => lines.filter((l) => fn(l.code));
  const sumAmt = (lines) => Math.round(lines.reduce((s, l) => s + Number(l.amount || 0), 0) * 100) / 100;

  const fixedAssetRows = pick(assetLines, isFixedAssetCode);
  const inventoryRows = pick(assetLines, isInventoryCode);
  const bankRows = pick(assetLines, isBankCashCode);
  const accruedRows = pick(assetLines, isAccruedInterestCode);
  const advanceRows = pick(assetLines, isAdvancesCode);
  const debtorRows = assetLines.filter((l) => !isFixedAssetCode(l.code) && !isInventoryCode(l.code) && !isBankCashCode(l.code) && !isAccruedInterestCode(l.code) && !isAdvancesCode(l.code) && !isAccumDepCode(l.code));
  const creditorLines = liabilityLines.filter((l) => l.name !== "مخصصات الاهلاك");
  const backendProvisionRows = liabilityLines.filter((l) => l.name === "مخصصات الاهلاك").map((l) => ({ code: l.code, name: l.name, amount: Math.abs(Number(l.amount || 0)), detail_source: l.detail_source, details: l.details }));
  const provisionRows = [...pick(assetLines, isAccumDepCode).map((l) => ({ code: l.code, name: l.name, amount: Math.abs(Number(l.amount || 0)), detail_source: l.detail_source, details: l.details })), ...backendProvisionRows];

  const assetDetail = { matchBy: "code", scope: "cumulative_to", kind: "asset_cumulative" };
  const assetGroups = [
    { title: "أصول ثابتة", rows: fixedAssetRows, detail: { ...assetDetail, kind: "fixed_asset" } },
    { title: "المخزون", rows: inventoryRows, detail: assetDetail },
    { title: "نقدية وبنوك", rows: bankRows, detail: { ...assetDetail, kind: "bank" } },
    { title: "فوائد ودائع مستحقة", rows: accruedRows, detail: assetDetail },
    { title: "حسابات مدينة", rows: [...debtorRows, ...advanceRows], detail: assetDetail },
  ];
  const creditGroups = [
    { title: "المخصصات", rows: provisionRows, detail: { matchBy: "code", scope: "cumulative_to", kind: "provision" } },
    { title: "حسابات دائنة", rows: creditorLines, detail: { matchBy: "code", scope: "cumulative_to", kind: "liability" } },
    { title: "الفائض", rows: equityLines, detail: { matchBy: "code", scope: "cumulative_to", kind: "equity" } },
  ];

  const assetsTotal = sumAmt([...fixedAssetRows, ...inventoryRows, ...bankRows, ...accruedRows, ...debtorRows, ...advanceRows]);
  const creditTotal = Math.round((sumAmt(provisionRows) + sumAmt(creditorLines) + sumAmt(equityLines)) * 100) / 100;

  const prevMap = {};
  (prevReport?.balance_sheet?.assets?.lines || []).forEach((l) => { prevMap[l.name] = isAccumDepCode(l.code) ? Math.abs(Number(l.amount || 0)) : Number(l.amount || 0); });
  [...(prevReport?.balance_sheet?.liabilities?.lines || []), ...(prevReport?.balance_sheet?.equity?.lines || [])].forEach((l) => { prevMap[l.name] = Number(l.amount || 0); });
  const prevAssetLines = prevReport?.balance_sheet?.assets?.lines || [];
  const prevAssetsTotal = sumAmt(prevAssetLines.filter((l) => !isAccumDepCode(l.code)));
  const prevCreditTotal = Math.round((Math.abs(sumAmt(prevAssetLines.filter((l) => isAccumDepCode(l.code)))) + Number(prevReport?.balance_sheet?.liabilities?.total || 0) + Number(prevReport?.balance_sheet?.equity?.total || 0)) * 100) / 100;

  const diff = Math.round((assetsTotal - creditTotal) * 100) / 100;
  return (
    <section className="financial-print-sheet" data-testid="balance-sheet-print-section">
      <ReportHeader title="الميزانية" year={year} dateLabel={dateLabel || `في 31 ديسمبر ${year}`} unionName={unionName} projectName={projectName} email={email} testId="balance-sheet-print-header" />
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2 print:grid-cols-2" data-testid="balance-sheet-print-grid">
        <GroupedSideTable sideTitle="الأصول" groups={assetGroups} total={assetsTotal} year={year} prevYear={prevYear} showPrev={showPrev} prevMap={prevMap} prevTotal={prevAssetsTotal} testId="balance-sheet-print-assets-table" onAmountClick={onAmountClick} />
        <GroupedSideTable sideTitle="المخصصات والالتزامات والفائض" groups={creditGroups} total={creditTotal} year={year} prevYear={prevYear} showPrev={showPrev} prevMap={prevMap} prevTotal={prevCreditTotal} testId="balance-sheet-print-liabilities-equity-table" onAmountClick={onAmountClick} />
      </div>
      <div className={`mt-5 border-2 p-3 text-center text-xl font-extrabold print:hidden ${diff === 0 ? "border-slate-400" : "border-red-600 text-red-700"}`} data-testid="balance-sheet-print-check">فرق اتزان الميزانية: {formatCurrency(diff)}</div>
      <SignatureStrip testId="balance-sheet-print-signatures" />
    </section>
  );
}

function IncomeExpensePrint({ report, prevReport, year, dateLabel, unionName, projectName, email, onAmountClick }) {
  const prevYear = Number(year) - 1;
  const showPrev = Number(year) >= 2027 && prevHasData(prevReport);
  const expenseLines = report?.revenues_expenses?.expenses?.lines || [];
  const revenueLines = report?.revenues_expenses?.revenues?.lines || [];
  const isDepExpense = (code) => String(code || "").startsWith("52");
  const depRows = expenseLines.filter((l) => isDepExpense(l.code));
  const opExpenseRows = expenseLines.filter((l) => !isDepExpense(l.code));
  const result = Math.round(Number(report?.revenues_expenses?.result?.total || 0) * 100) / 100;
  const expenseTotal = linesTotal(expenseLines);
  const revenueTotal = linesTotal(revenueLines);
  const expenseSideTotal = Math.round((expenseTotal + Math.max(result, 0)) * 100) / 100;
  const revenueSideTotal = Math.round((revenueTotal + Math.max(-result, 0)) * 100) / 100;

  const expenseGroups = [
    { title: "مصروفات النشاط", rows: opExpenseRows, detail: { matchBy: "code", scope: "period", kind: "expense" } },
    { title: "إهلاك الأصول الثابتة", rows: depRows, detail: { matchBy: "code", scope: "period", kind: "depreciation_expense" } },
    ...(result >= 0 ? [{ title: "الفائض", rows: [{ name: "الفائض", amount: result }], detail: { kind: "surplus" } }] : []),
  ];
  const OTHER_REV_SOURCES = new Set(["rev_dev_fee", "rev_publications", "rev_other"]);
  const mainRevenueLines = revenueLines.filter((l) => !OTHER_REV_SOURCES.has(l.detail_source));
  const otherRevenueLines = revenueLines.filter((l) => OTHER_REV_SOURCES.has(l.detail_source));
  const revenueGroups = [
    { title: "إيرادات النشاط", rows: result < 0 ? [...mainRevenueLines, { name: "العجز", amount: Math.abs(result) }] : mainRevenueLines, detail: { matchBy: "code", scope: "period", kind: "revenue" } },
    ...(otherRevenueLines.length ? [{ title: "(ايرادات اخري)", rows: otherRevenueLines, detail: { matchBy: "code", scope: "period", kind: "revenue" } }] : []),
  ];

  const prevMap = { ...buildPrevMap(prevReport?.revenues_expenses?.revenues?.lines), ...buildPrevMap(prevReport?.revenues_expenses?.expenses?.lines) };
  const prevResult = Math.round(Number(prevReport?.revenues_expenses?.result?.total || 0) * 100) / 100;
  prevMap["الفائض"] = Math.max(prevResult, 0);
  prevMap["العجز"] = Math.max(-prevResult, 0);
  const prevExpenseSideTotal = Math.round((linesTotal(prevReport?.revenues_expenses?.expenses?.lines) + Math.max(prevResult, 0)) * 100) / 100;
  const prevRevenueSideTotal = Math.round((linesTotal(prevReport?.revenues_expenses?.revenues?.lines) + Math.max(-prevResult, 0)) * 100) / 100;

  return (
    <section className="financial-print-sheet" data-testid="income-expense-print-section">
      <ReportHeader title="حساب الإيرادات والمصروفات" year={year} dateLabel={dateLabel || `عن السنة المنتهية في 31 ديسمبر ${year}`} unionName={unionName} projectName={projectName} email={email} testId="income-expense-print-header" />
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2 print:grid-cols-2" data-testid="income-expense-print-grid">
        <GroupedSideTable sideTitle="المصروفات" groups={expenseGroups} total={expenseSideTotal} year={year} prevYear={prevYear} showPrev={showPrev} prevMap={prevMap} prevTotal={prevExpenseSideTotal} testId="income-print-expenses-table" onAmountClick={onAmountClick} />
        <GroupedSideTable sideTitle="إيرادات النشاط" groups={revenueGroups} total={revenueSideTotal} year={year} prevYear={prevYear} showPrev={showPrev} prevMap={prevMap} prevTotal={prevRevenueSideTotal} testId="income-print-revenues-table" onAmountClick={onAmountClick} />
      </div>
      <div className="mt-5 border border-slate-400 bg-slate-100 p-3 text-center text-xl font-extrabold print:hidden" data-testid="income-expense-print-result">{result >= 0 ? "الفائض" : "العجز"}: {formatCurrency(Math.abs(result))}</div>
      <SignatureStrip testId="income-expense-print-signatures" />
    </section>
  );
}

function ReceiptsPaymentsPrint({ report, prevReport, year, dateLabel, unionName, projectName, email, onAmountClick }) {
  const prevYear = Number(year) - 1;
  const showPrev = Number(year) >= 2027 && prevHasData(prevReport);
  const receiptLines = report?.receipts_payments?.receipts?.lines || [];
  const paymentLines = report?.receipts_payments?.payments?.lines || [];
  const isOpening = (name) => String(name || "").startsWith("رصيد أول المدة");
  const isClosing = (name) => String(name || "").startsWith("رصيد آخر المدة") || String(name || "").startsWith("رصيد اخر المدة");
  const OTHER_RECEIPT_SOURCES = new Set(["rp_deposit_interest", "rev_other", "rp_cd_receipts"]);
  const isOtherReceipt = (l) => OTHER_RECEIPT_SOURCES.has(l.detail_source);
  const stripBank = (rows) => rows.map((l) => ({ ...l, name: String(l.name || "").replace(/^رصيد (أول|اول|آخر|اخر) المدة\s*-\s*/, "") }));

  const receiptGroups = [
    { title: "رصيد أول المدة", rows: stripBank(receiptLines.filter((l) => isOpening(l.name))), detail: { matchBy: "name", scope: "cumulative_before", kind: "receipt_opening" } },
    { title: "مقبوضات النشاط", rows: receiptLines.filter((l) => !isOpening(l.name) && !isOtherReceipt(l)), detail: { matchBy: "name", scope: "period", kind: "receipt_activity" } },
    { title: "مقبوضات اخري", rows: receiptLines.filter(isOtherReceipt), detail: { matchBy: "name", scope: "period", kind: "receipt_activity" } },
  ];
  const paymentGroups = [
    { title: "مصروفات النشاط", rows: paymentLines.filter((l) => !isClosing(l.name)), detail: { matchBy: "name", scope: "period", kind: "payment_activity" } },
    { title: "رصيد آخر المدة", rows: stripBank(paymentLines.filter((l) => isClosing(l.name))), detail: { matchBy: "name", scope: "cumulative_to", kind: "receipt_closing" } },
  ];

  const prevMap = { ...buildPrevMap(stripBank(prevReport?.receipts_payments?.receipts?.lines || [])), ...buildPrevMap(stripBank(prevReport?.receipts_payments?.payments?.lines || [])) };
  return (
    <section className="financial-print-sheet" data-testid="receipts-payments-print-section">
      <ReportHeader title="حساب المقبوضات والمدفوعات" year={year} dateLabel={dateLabel || `في 31 ديسمبر ${year}`} unionName={unionName} projectName={projectName} email={email} testId="receipts-payments-print-header" />
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2 print:grid-cols-2" data-testid="receipts-payments-print-grid">
        <GroupedSideTable sideTitle="المقبوضات" groups={receiptGroups} total={sectionTotal(report?.receipts_payments?.receipts)} year={year} prevYear={prevYear} showPrev={showPrev} prevMap={prevMap} prevTotal={sectionTotal(prevReport?.receipts_payments?.receipts)} testId="receipts-print-table" onAmountClick={onAmountClick} />
        <GroupedSideTable sideTitle="المدفوعات" groups={paymentGroups} total={sectionTotal(report?.receipts_payments?.payments)} year={year} prevYear={prevYear} showPrev={showPrev} prevMap={prevMap} prevTotal={sectionTotal(prevReport?.receipts_payments?.payments)} testId="payments-print-table" onAmountClick={onAmountClick} />
      </div>
      <div className="mt-5 border border-slate-400 bg-slate-100 p-3 text-center text-xl font-extrabold print:hidden" data-testid="receipts-payments-print-net">صافي المقبوضات والمدفوعات: {formatCurrency(report?.receipts_payments?.net_cash_flow?.total || 0)}</div>
      <SignatureStrip testId="receipts-payments-print-signatures" />
    </section>
  );
}

function AccountingErrorsPrint({ report }) {
  return (
    <section className="financial-print-sheet" data-testid="accounting-errors-print-section">
      <div className="mb-5 flex items-center gap-3"><FileWarning className="h-7 w-7 text-red-700" /><h2 className="text-3xl font-extrabold" data-testid="accounting-errors-print-title">تقرير الأخطاء المحاسبية</h2></div>
      <div className="overflow-x-auto rounded-lg border border-red-200" data-testid="accounting-errors-print-table-wrapper">
        <Table data-testid="accounting-errors-print-table"><TableHeader className="bg-red-900"><TableRow className="hover:bg-red-900"><TableHead className="text-right text-white">الخطورة</TableHead><TableHead className="text-right text-white">نوع الخطأ</TableHead><TableHead className="text-right text-white">مكان الخطأ</TableHead><TableHead className="text-right text-white">التفاصيل</TableHead><TableHead className="text-right text-white">الإجراء المقترح</TableHead></TableRow></TableHeader><TableBody>{(report?.accounting_errors || []).length === 0 && <TableRow data-testid="accounting-errors-print-empty-row"><TableCell colSpan={5} className="py-8 text-center font-extrabold text-emerald-700">لا توجد أخطاء محاسبية مكتشفة</TableCell></TableRow>}{(report?.accounting_errors || []).map((error, index) => <TableRow key={`${error.error_type}-${index}`} data-testid={`accounting-errors-print-row-${index}`}><TableCell className="font-extrabold">{error.severity === "critical" ? "حرج" : error.severity === "warning" ? "تنبيه" : "معلومة"}</TableCell><TableCell>{error.error_type}</TableCell><TableCell className="font-extrabold">{error.location}</TableCell><TableCell>{error.details}</TableCell><TableCell>{error.suggested_fix || "-"}</TableCell></TableRow>)}</TableBody></Table>
      </div>
    </section>
  );
}

function AccountingCorrectionsReview({ corrections = [] }) {
  return (
    <section className="rounded-xl border border-amber-200 bg-amber-50 p-6 print:hidden" data-testid="accounting-corrections-review-section">
      <div className="mb-4 flex items-center gap-3" data-testid="accounting-corrections-review-heading">
        <AlertTriangle className="h-6 w-6 text-amber-700" />
        <div data-testid="accounting-corrections-review-title-block">
          <h2 className="text-2xl font-extrabold" data-testid="accounting-corrections-review-title">مراجعة القيود التي تم تصحيح ربطها تلقائياً</h2>
          <p className="text-sm font-bold text-amber-800" data-testid="accounting-corrections-review-subtitle">راجع هذه السطور قبل الطباعة النهائية للقوائم المالية.</p>
        </div>
      </div>
      <div className="overflow-x-auto rounded-xl border border-amber-200 bg-white" data-testid="accounting-corrections-review-table-wrapper">
        <Table data-testid="accounting-corrections-review-table">
          <TableHeader className="bg-amber-900"><TableRow className="hover:bg-amber-900"><TableHead className="text-right text-white">رقم القيد</TableHead><TableHead className="text-right text-white">التاريخ</TableHead><TableHead className="text-right text-white">البيان</TableHead><TableHead className="text-right text-white">قبل التصحيح</TableHead><TableHead className="text-right text-white">بعد التصحيح</TableHead></TableRow></TableHeader>
          <TableBody>
            {corrections.length === 0 && <TableRow data-testid="accounting-corrections-review-empty-row"><TableCell colSpan={5} className="py-6 text-center font-extrabold text-emerald-700">لا توجد قيود احتاجت تصحيح ربط قبل الطباعة</TableCell></TableRow>}
            {corrections.map((item, index) => <TableRow key={`${item.entry_id}-${item.line_index}-${index}`} data-testid={`accounting-corrections-review-row-${index}`}><TableCell className="font-extrabold" data-testid={`accounting-corrections-review-row-${index}-entry-number`}>{item.entry_number || "-"}</TableCell><TableCell data-testid={`accounting-corrections-review-row-${index}-entry-date`}>{item.entry_date || "-"}</TableCell><TableCell data-testid={`accounting-corrections-review-row-${index}-description`}>{item.description || "-"}</TableCell><TableCell data-testid={`accounting-corrections-review-row-${index}-before`}>{item.before_account_name || "غير مرتبط"} {item.before_account_code ? `(${item.before_account_code})` : ""}</TableCell><TableCell className="font-extrabold text-emerald-700" data-testid={`accounting-corrections-review-row-${index}-after`}>{item.after_account_name || "-"} {item.after_account_code ? `(${item.after_account_code})` : ""}</TableCell></TableRow>)}
          </TableBody>
        </Table>
      </div>
    </section>
  );
}

export default function FinancialStatementsPage() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();
  const { settings } = useAppSettings();
  const unionName = settings.organizations?.["general-union"]?.name || "النقابة العامة للعاملين بالزراعة والري والصيد واستصلاح الأراضي";
  const projectName = settings.organizations?.["social-solidarity"]?.login_label || settings.organizations?.["social-solidarity"]?.name || "مشروع التكافل الاجتماعي";
  const reportEmail = officialEmailOrEmpty(settings.organizations?.[user?.organization_id]?.email);
  const [year, setYear] = useState(String(currentYear));
  const [fromMonth, setFromMonth] = useState(1);
  const [toMonth, setToMonth] = useState(12);
  const [report, setReport] = useState(null);
  const [prevReport, setPrevReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const loadReports = useCallback(async () => {
    setLoading(true);
    try {
      const selectedYear = Number(year);
      const fromM = Number(fromMonth);
      const toM = Math.max(Number(toMonth), fromM);
      const currentRange = monthRange(selectedYear, fromM, toM);
      const prevRange = monthRange(selectedYear - 1, fromM, toM);
      const [currentResponse, prevResponse] = await Promise.all([
        api.get(`/financial-statements?from_date=${currentRange.from_date}&to_date=${currentRange.to_date}`),
        api.get(`/financial-statements?from_date=${prevRange.from_date}&to_date=${prevRange.to_date}`).catch(() => ({ data: null })),
      ]);
      setReport(currentResponse.data);
      setPrevReport(prevResponse.data);
      if (currentResponse.data.accounting_errors?.length) toast.warning("تم اكتشاف ملاحظات محاسبية في التقرير");
    } catch (error) {
      toast.error("تعذر تحميل القوائم المالية");
    } finally {
      setLoading(false);
    }
  }, [year, fromMonth, toMonth]);

  useEffect(() => { loadReports(); }, [loadReports]);

  const fromM = Number(fromMonth);
  const toM = Math.max(Number(toMonth), fromM);
  const isFullYear = fromM === 1 && toM === 12;
  const periodText = isFullYear ? `سنة ${year}` : `الفترة من ${AR_MONTHS[fromM - 1]} ${year} إلى ${AR_MONTHS[toM - 1]} ${year}`;
  const balanceDateLabel = isFullYear ? `في 31 ديسمبر ${year}` : `عن ${periodText}`;
  const incomeDateLabel = isFullYear ? `عن السنة المنتهية في 31 ديسمبر ${year}` : `عن ${periodText}`;
  const receiptsDateLabel = isFullYear ? `في 31 ديسمبر ${year}` : `عن ${periodText}`;

  const handleAmountClick = useCallback(async (group, line) => {
    const cfg = group?.detail || {};
    const scopeLabel = cfg.scope === "period" ? periodText : (cfg.scope === "cumulative_before" ? `أول المدة (قبل ${AR_MONTHS[fromM - 1]} ${year})` : `حتى ${isFullYear ? `31 ديسمبر ${year}` : `نهاية ${AR_MONTHS[toM - 1]} ${year}`}`);
    const src = line?.detail_source;
    const basis = line?.details || buildBasisText(cfg.kind, periodText, scopeLabel);
    const matchValue = cfg.matchBy === "code" ? line.code : line.name;
    const base = { name: line.name, amount: Number(line.amount || 0), basis, rows: [], total: 0, hasLedger: false };
    if (!src && (!cfg.matchBy || !matchValue)) { setDetail(base); return; }
    setDetail({ ...base, hasLedger: true });
    setDetailLoading(true);
    try {
      const range = monthRange(Number(year), fromM, toM);
      const params = new URLSearchParams(src
        ? { source: src, scope: cfg.scope || "cumulative_to", from_date: range.from_date, to_date: range.to_date }
        : { match_by: cfg.matchBy, value: String(matchValue), scope: cfg.scope || "period", from_date: range.from_date, to_date: range.to_date });
      const response = await api.get(`/financial-statements/line-detail?${params.toString()}`);
      setDetail({ ...base, hasLedger: true, rows: response.data.rows || [], total: response.data.net ?? 0 });
    } catch (error) {
      setDetail({ ...base, hasLedger: true, rows: [], total: 0, error: true });
    } finally {
      setDetailLoading(false);
    }
  }, [year, fromM, toM, isFullYear, periodText]);

  const printDetail = useCallback(() => {
    if (!detail) return;
    const rowsHtml = (detail.rows || []).map((r) => `<tr><td>${r.entry_date || ""}</td><td>${r.entry_number || ""}</td><td style="text-align:right">${r.description || ""}</td><td style="text-align:center">${r.debit ? formatCurrency(r.debit) : "-"}</td><td style="text-align:center">${r.credit ? formatCurrency(r.credit) : "-"}</td></tr>`).join("");
    const win = window.open("", "_blank", "width=900,height=700");
    if (!win) return;
    win.document.write(`<!doctype html><html dir="rtl" lang="ar"><head><meta charset="utf-8"><title>مصدر الرقم - ${detail.name}</title><style>body{font-family:'Tahoma',Arial,sans-serif;padding:24px;color:#0f172a}h1{font-size:20px;margin:0 0 4px}h2{font-size:15px;color:#047857;margin:0 0 16px}.basis{background:#ecfdf5;border:1px solid #a7f3d0;border-radius:8px;padding:12px;font-weight:bold;margin-bottom:16px}table{width:100%;border-collapse:collapse;font-size:13px}th,td{border:1px solid #cbd5e1;padding:6px 8px}th{background:#0f172a;color:#fff}.total{margin-top:12px;background:#f1f5f9;padding:10px;font-weight:800;display:flex;justify-content:space-between;border-radius:8px}</style></head><body><h1>تفاصيل: ${detail.name}</h1><h2>المبلغ: ${formatCurrency(detail.amount || 0)}</h2><div class="basis"><div style="font-size:12px;color:#047857;margin-bottom:4px">مصدر الرقم والأساس المحاسبي</div>${detail.basis || ""}</div>${(detail.rows || []).length ? `<table><thead><tr><th>التاريخ</th><th>رقم القيد</th><th>البيان</th><th>مدين</th><th>دائن</th></tr></thead><tbody>${rowsHtml}</tbody></table><div class="total"><span>صافي الإجمالي</span><span>${formatCurrency(Math.abs(detail.total || 0))}</span></div>` : ""}</body></html>`);
    win.document.close();
    injectPrintLogo(win);
    win.focus();
    setTimeout(() => { win.print(); }, 300);
  }, [detail]);

  return (
    <main className="min-h-screen bg-slate-50 text-slate-950" data-testid="financial-statements-page">
      <style>{`.financial-print-sheet{position:relative}.financial-print-sheet::before{content:"";position:absolute;top:16px;left:16px;width:96px;height:96px;background:url(/assets/union-logo.jpeg) center/contain no-repeat;print-color-adjust:exact;-webkit-print-color-adjust:exact;pointer-events:none}@media print {@page{size:A4 portrait;margin:8mm}.print\\:hidden{display:none!important}[data-testid="print-organization-heading"],[data-testid="print-corner-logo"]{display:none!important}.financial-print-sheet::before{width:26mm!important;height:26mm!important;top:0!important;left:0!important}.financial-print-sheet{position:relative;break-after:page;break-inside:avoid;box-shadow:none!important;border:0!important;margin:0!important;padding:0!important;width:100%!important}.financial-print-sheet:last-child{break-after:auto}body{background:white!important}.financial-report-actions{display:none!important}.financial-print-sheet th,.financial-print-sheet td{font-size:14px!important;padding:5px 8px!important}.financial-print-sheet h2{font-size:24px!important}.signature-strip{margin-top:28px!important}} .financial-print-sheet{background:white;border:1px solid #d6d3d1;border-radius:10px;padding:24px;box-shadow:0 1px 2px rgba(0,0,0,.04)} .financial-print-sheet table{border-collapse:collapse!important} .financial-print-sheet th,.financial-print-sheet td{font-size:13px}`}</style>
      <header className="sticky top-0 z-20 border-b border-slate-200/70 bg-white/90 backdrop-blur-xl print:hidden" data-testid="financial-statements-header"><div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-4 sm:px-6 lg:px-8"><div className="flex items-center gap-3" data-testid="financial-statements-brand"><div className="flex h-11 w-11 items-center justify-center rounded-xl bg-slate-950 text-white"><Scale className="h-5 w-5" /></div><div><p className="text-xs font-extrabold text-emerald-700">القوائم المالية السنوية</p><h1 className="text-2xl font-extrabold" data-testid="financial-statements-title">الميزانية والحسابات الختامية</h1></div></div><div className="flex flex-wrap items-center gap-3" data-testid="financial-statements-actions"><Badge className="bg-white text-slate-700" data-testid="financial-statements-organization-badge">{user?.organization_name}</Badge><Button asChild variant="outline" className="h-11 bg-white" data-testid="financial-statements-home-button"><Link to="/"><Home className="h-4 w-4" /> الرئيسية</Link></Button><Button type="button" onClick={() => navigate(-1)} variant="outline" className="h-11 bg-white" data-testid="financial-statements-back-button"><ArrowRight className="h-4 w-4" /> رجوع</Button><Button type="button" onClick={logout} variant="outline" className="h-11 bg-white" data-testid="financial-statements-logout-button"><LogOut className="h-4 w-4" /> خروج</Button></div></div></header>
      <section className="mx-auto max-w-7xl space-y-6 px-4 py-8 sm:px-6 lg:px-8 print:max-w-none print:p-0" data-testid="financial-statements-content">
        <section className="financial-report-actions rounded-xl border border-slate-200 bg-white p-6 shadow-sm print:hidden" data-testid="financial-statements-year-section"><div className="mb-5 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between"><div><h2 className="text-2xl font-extrabold" data-testid="financial-statements-year-title">القوائم المالية — تحديد الفترة</h2><p className="text-sm font-bold text-slate-500" data-testid="financial-statements-year-subtitle">اختر السنة وفترة الطباعة (من شهر إلى شهر). افتراضياً من يناير إلى ديسمبر = السنة كاملة.</p></div><ExportReportButtons title={`الحسابات الختامية — ${periodText}`} fileName={`الحسابات-الختامية-${year}-${String(fromM).padStart(2, "0")}-${String(toM).padStart(2, "0")}`} selectors={["[data-testid='balance-sheet-print-section']", "[data-testid='income-expense-print-section']", "[data-testid='receipts-payments-print-section']", "[data-testid='accounting-errors-print-section']"]} disabled={loading || !report} pdfLabel="طباعة PDF" pdfTestId="print-financial-statements-button" excelTestId="export-financial-statements-excel-button" wordTestId="export-financial-statements-word-button" /></div><div className="grid grid-cols-1 gap-4 md:grid-cols-[1fr_1fr_1fr_auto_auto]" data-testid="financial-statements-year-controls"><label className="flex flex-col gap-1 text-xs font-bold text-slate-600">السنة<select value={year} onChange={(event) => setYear(event.target.value)} className="h-11 rounded-md border border-slate-300 bg-slate-50 px-3 font-bold" data-testid="financial-statements-year-select">{years.map((item) => <option key={item} value={item} label={String(item)} />)}</select></label><label className="flex flex-col gap-1 text-xs font-bold text-slate-600">من شهر<select value={fromMonth} onChange={(event) => setFromMonth(Number(event.target.value))} className="h-11 rounded-md border border-slate-300 bg-slate-50 px-3 font-bold" data-testid="financial-statements-from-month-select">{AR_MONTHS.map((name, index) => <option key={name} value={index + 1}>{name}</option>)}</select></label><label className="flex flex-col gap-1 text-xs font-bold text-slate-600">إلى شهر<select value={toMonth} onChange={(event) => setToMonth(Number(event.target.value))} className="h-11 rounded-md border border-slate-300 bg-slate-50 px-3 font-bold" data-testid="financial-statements-to-month-select">{AR_MONTHS.map((name, index) => <option key={name} value={index + 1}>{name}</option>)}</select></label><Button type="button" onClick={loadReports} className="h-11 self-end bg-slate-950 text-white" data-testid="generate-financial-statements-button"><FileSpreadsheet className="h-4 w-4" /> توليد</Button><Button type="button" onClick={() => printNow()} variant="outline" className="h-11 self-end bg-white" data-testid="print-annual-financial-statements-button"><Printer className="h-4 w-4" /> طباعة</Button></div></section>
        <section className="grid grid-cols-1 gap-4 md:grid-cols-4 print:hidden" data-testid="financial-statements-kpi-grid"><div className="rounded-xl bg-slate-950 p-4 text-white"><p className="text-xs font-bold text-slate-300">حالة القوائم</p><p className="text-xl font-extrabold" data-testid="financial-statements-valid-value">{report?.is_accounting_valid ? "سليمة" : "بها أخطاء"}</p></div><div className="rounded-xl bg-emerald-50 p-4"><p className="text-xs font-bold text-emerald-700">إجمالي الأصول</p><p className="text-xl font-extrabold" data-testid="financial-statements-assets-value">{formatCurrency(report?.balance_sheet?.assets?.total || 0)}</p></div><div className="rounded-xl bg-amber-50 p-4"><p className="text-xs font-bold text-amber-700">نتيجة السنة</p><p className="text-xl font-extrabold" data-testid="financial-statements-result-value">{formatCurrency(report?.revenues_expenses?.result?.total || 0)}</p></div><div className="rounded-xl bg-red-50 p-4"><p className="text-xs font-bold text-red-700">الأخطاء المكتشفة</p><p className="text-xl font-extrabold" data-testid="financial-statements-errors-value">{report?.accounting_errors?.length || 0}</p></div></section>
        <AccountingCorrectionsReview corrections={report?.accounting_corrections || []} />
        <BalanceSheetPrint report={report} prevReport={prevReport} year={year} dateLabel={balanceDateLabel} unionName={unionName} projectName={projectName} email={reportEmail} onAmountClick={handleAmountClick} />
        <IncomeExpensePrint report={report} prevReport={prevReport} year={year} dateLabel={incomeDateLabel} unionName={unionName} projectName={projectName} email={reportEmail} onAmountClick={handleAmountClick} />
        <ReceiptsPaymentsPrint report={report} prevReport={prevReport} year={year} dateLabel={receiptsDateLabel} unionName={unionName} projectName={projectName} email={reportEmail} onAmountClick={handleAmountClick} />
        <AccountingErrorsPrint report={report} />
      </section>
      <footer className="px-4 pb-5 print:hidden"><CreditLine testId="financial-statements-creator-credit" /></footer>

      <Dialog open={!!detail} onOpenChange={(open) => { if (!open) setDetail(null); }}>
        <DialogContent className="max-w-2xl" data-testid="line-detail-dialog">
          <DialogHeader>
            <DialogTitle data-testid="line-detail-dialog-title">تفاصيل: {detail?.name}</DialogTitle>
            <DialogDescription data-testid="line-detail-dialog-amount">المبلغ: {formatCurrency(detail?.amount || 0)}</DialogDescription>
            <div className="pt-2">
              <Button type="button" variant="outline" size="sm" className="h-9 bg-white" onClick={printDetail} data-testid="line-detail-print-button"><Printer className="h-4 w-4" /> طباعة مصدر الرقم</Button>
            </div>
          </DialogHeader>
          <div className="space-y-4">
            <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-sm font-bold text-emerald-900" data-testid="line-detail-basis">
              <p className="mb-1 text-xs font-extrabold text-emerald-700">مصدر الرقم والأساس المحاسبي</p>
              {detail?.basis}
            </div>
            {detail?.hasLedger && (
              <div data-testid="line-detail-ledger">
                <p className="mb-2 text-sm font-extrabold text-slate-700">الحركات المكوِّنة للرقم</p>
                {detailLoading ? (
                  <p className="py-6 text-center font-bold text-slate-500" data-testid="line-detail-loading">جارٍ التحميل…</p>
                ) : (
                  <div className="max-h-80 overflow-y-auto rounded-lg border border-slate-200">
                    <Table>
                      <TableHeader className="sticky top-0 bg-slate-900">
                        <TableRow className="hover:bg-slate-900"><TableHead className="text-right text-white">التاريخ</TableHead><TableHead className="text-right text-white">رقم القيد</TableHead><TableHead className="text-right text-white">البيان</TableHead><TableHead className="text-center text-white">مدين</TableHead><TableHead className="text-center text-white">دائن</TableHead></TableRow>
                      </TableHeader>
                      <TableBody>
                        {(detail?.rows || []).length === 0 && <TableRow><TableCell colSpan={5} className="py-6 text-center font-bold text-slate-400" data-testid="line-detail-empty">لا توجد حركات مطابقة لهذا الرقم في الفترة</TableCell></TableRow>}
                        {(detail?.rows || []).map((row, index) => (
                          <TableRow key={`${row.entry_number}-${index}`} data-testid={`line-detail-row-${index}`}>
                            <TableCell className="font-bold">{row.entry_date}</TableCell>
                            <TableCell className="font-bold">{row.entry_number}</TableCell>
                            <TableCell>{row.description}</TableCell>
                            <TableCell className="text-center font-bold tabular-nums">{row.debit ? formatCurrency(row.debit) : "-"}</TableCell>
                            <TableCell className="text-center font-bold tabular-nums">{row.credit ? formatCurrency(row.credit) : "-"}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                )}
                {!detailLoading && (detail?.rows || []).length > 0 && (
                  <div className="mt-2 flex items-center justify-between rounded-lg bg-slate-100 px-4 py-2 font-extrabold" data-testid="line-detail-total"><span>صافي الإجمالي</span><span className="tabular-nums">{formatCurrency(Math.abs(detail?.total || 0))}</span></div>
                )}
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </main>
  );
}