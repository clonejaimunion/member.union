import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatCurrency, formatNumber } from "@/lib/format";

export const ReportTable = ({ rows, total }) => (
  <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm" data-testid="report-table-wrapper">
    <Table data-testid="monthly-interest-table">
      <TableHeader className="bg-slate-950">
        <TableRow data-testid="report-table-header-row" className="hover:bg-slate-950">
          <TableHead className="text-right font-extrabold text-white" data-testid="header-serial">مسلسل</TableHead>
          <TableHead className="text-right font-extrabold text-white" data-testid="header-month">الشهر</TableHead>
          <TableHead className="text-right font-extrabold text-white" data-testid="header-active-days">أيام الاستحقاق</TableHead>
          <TableHead className="text-right font-extrabold text-white" data-testid="header-interest-amount">مبلغ الفائدة</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((row) => (
          <TableRow key={row.serial} data-testid={`report-row-${row.serial}`} className="bg-white hover:bg-emerald-50/60">
            <TableCell className="font-bold text-slate-900" data-testid={`report-row-${row.serial}-serial`}>{row.serial}</TableCell>
            <TableCell className="font-bold text-slate-700" data-testid={`report-row-${row.serial}-month`}>{row.month}</TableCell>
            <TableCell className="text-slate-600" data-testid={`report-row-${row.serial}-active-days`}>{formatNumber(row.active_days)}</TableCell>
            <TableCell className="font-extrabold text-slate-950" data-testid={`report-row-${row.serial}-interest`}>{formatCurrency(row.interest_amount)}</TableCell>
          </TableRow>
        ))}
        <TableRow className="bg-amber-50 hover:bg-amber-50" data-testid="report-total-row">
          <TableCell colSpan={3} className="text-lg font-extrabold text-slate-950" data-testid="report-total-label">إجمالي العائد المستحق</TableCell>
          <TableCell className="text-lg font-extrabold text-slate-950" data-testid="report-total-amount">{formatCurrency(total)}</TableCell>
        </TableRow>
      </TableBody>
    </Table>
  </div>
);
