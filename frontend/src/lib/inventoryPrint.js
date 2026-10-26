import { formatAmountPlain, formatDate, toEasternArabicNumerals } from "@/lib/format";
import { injectPrintLogo } from "@/lib/printLogo";

const fd = (v) => toEasternArabicNumerals(formatDate(v));
const esc = (v) => String(v ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const qty = (v) => toEasternArabicNumerals(String(Math.round(Number(v || 0) * 10000) / 10000));
const amt = (v) => formatAmountPlain(v);
const sum = (rows, key) => rows.reduce((s, r) => s + Number(r[key] || 0), 0);

const STYLE = `@page{size:A4 landscape;margin:8mm}.head{min-height:42mm;padding-top:6mm;box-sizing:border-box}body{font-family:Tahoma,Arial,sans-serif;direction:rtl;color:#0f172a;margin:0;padding:4mm}h1{text-align:center;font-size:18px;margin:0}h2{text-align:center;font-size:15px;margin:3mm 0 1mm}.period{text-align:center;font-weight:700;font-size:12px;margin-bottom:5mm}.item{margin-bottom:6mm;break-inside:avoid-page}.item-title{background:#0f172a;color:#fff;padding:2mm 3mm;font-weight:800;font-size:12px;-webkit-print-color-adjust:exact;print-color-adjust:exact}table{width:100%;border-collapse:collapse;font-size:10.5px}th,td{border:1px solid #94a3b8;padding:1.4mm 2mm;text-align:center}th{background:#e2e8f0;-webkit-print-color-adjust:exact;print-color-adjust:exact}td.r{text-align:right}tr.sub td{font-weight:800;background:#f1f5f9;-webkit-print-color-adjust:exact;print-color-adjust:exact}tr.grand td{font-weight:900;background:#cbd5e1;font-size:12px;-webkit-print-color-adjust:exact;print-color-adjust:exact}.summary td{font-weight:700}.empty{text-align:center;padding:10mm;font-weight:700}`;

const header = (title, report, orgName) => `<div class="head"><h1>${esc(orgName)}</h1><h2>${esc(title)}</h2><p class="period">عن الفترة من ${esc(report.from_date ? fd(report.from_date) : "البداية")} إلى ${esc(report.to_date ? fd(report.to_date) : "تاريخه")}</p></div>`;

const itemTitle = (it) => `<div class="item-title">${esc(it.item_code)} — ${esc(it.item_name)} (${esc(it.unit)})</div>`;

const issuesHtml = (report) => {
  const items = report.items.filter((it) => it.movements.some((m) => m.movement_type === "out"));
  if (!items.length) return `<p class="empty">لا يوجد منصرف خلال الفترة</p>`;
  const blocks = items.map((it) => {
    const outs = it.movements.filter((m) => m.movement_type === "out");
    const rows = outs.map((m) => `<tr><td>${esc(fd(m.movement_date))}</td><td class="r">${esc(m.description)}</td><td>${esc(m.reference)}</td><td>${qty(m.quantity_before)}</td><td>${amt(m.value_before)}</td><td>${qty(m.quantity)}</td><td>${amt(m.unit_cost)}</td><td>${amt(m.total_value)}</td><td>${qty(m.quantity_after)}</td><td>${amt(m.value_after)}</td></tr>`).join("");
    return `<div class="item">${itemTitle(it)}<table><thead><tr><th rowspan="2">تاريخ الصرف</th><th rowspan="2">البيان</th><th rowspan="2">رقم المستند</th><th colspan="2">الرصيد قبل الصرف</th><th colspan="3">المنصرف</th><th colspan="2">الرصيد بعد الصرف</th></tr><tr><th>الكمية</th><th>القيمة</th><th>الكمية</th><th>سعر الوحدة</th><th>القيمة</th><th>الكمية</th><th>القيمة</th></tr></thead><tbody>${rows}<tr class="sub"><td colspan="5">إجمالي منصرف الصنف</td><td>${qty(sum(outs, "quantity"))}</td><td></td><td>${amt(sum(outs, "total_value"))}</td><td colspan="2"></td></tr></tbody></table></div>`;
  }).join("");
  const total = items.reduce((s, it) => s + Number(it.out_value || 0), 0);
  return `${blocks}<table><tbody><tr class="grand"><td>إجمالي قيمة المنصرف خلال الفترة</td><td>${amt(total)}</td></tr></tbody></table>`;
};

const balancesHtml = (report) => {
  if (!report.items.length) return `<p class="empty">لا توجد أرصدة أو حركات خلال الفترة</p>`;
  const blocks = report.items.map((it) => {
    const rows = it.movements.map((m) => {
      const isIn = m.movement_type === "in";
      return `<tr><td>${esc(fd(m.movement_date))}</td><td class="r">${esc(m.description)}</td><td>${esc(m.reference)}</td><td>${isIn ? qty(m.quantity) : "-"}</td><td>${isIn ? amt(m.total_value) : "-"}</td><td>${isIn ? "-" : qty(m.quantity)}</td><td>${isIn ? "-" : amt(m.total_value)}</td><td>${qty(m.quantity_after)}</td><td>${amt(m.value_after)}</td></tr>`;
    }).join("");
    return `<div class="item">${itemTitle(it)}<table class="summary"><thead><tr><th colspan="2">رصيد أول المدة</th><th colspan="2">الوارد خلال الفترة</th><th colspan="2">المنصرف خلال الفترة</th><th colspan="2">رصيد آخر المدة</th></tr><tr><th>الكمية</th><th>القيمة</th><th>الكمية</th><th>القيمة</th><th>الكمية</th><th>القيمة</th><th>الكمية</th><th>القيمة</th></tr></thead><tbody><tr><td>${qty(it.opening_quantity)}</td><td>${amt(it.opening_value)}</td><td>${qty(it.in_quantity)}</td><td>${amt(it.in_value)}</td><td>${qty(it.out_quantity)}</td><td>${amt(it.out_value)}</td><td>${qty(it.closing_quantity)}</td><td>${amt(it.closing_value)}</td></tr></tbody></table><table><thead><tr><th rowspan="2">التاريخ</th><th rowspan="2">البيان</th><th rowspan="2">رقم المستند</th><th colspan="2">وارد</th><th colspan="2">منصرف</th><th colspan="2">الرصيد بعد الحركة</th></tr><tr><th>الكمية</th><th>القيمة</th><th>الكمية</th><th>القيمة</th><th>الكمية</th><th>القيمة</th></tr></thead><tbody><tr class="sub"><td colspan="7">رصيد أول المدة</td><td>${qty(it.opening_quantity)}</td><td>${amt(it.opening_value)}</td></tr>${rows}<tr class="sub"><td colspan="7">رصيد آخر المدة</td><td>${qty(it.closing_quantity)}</td><td>${amt(it.closing_value)}</td></tr></tbody></table></div>`;
  }).join("");
  const t = (k) => amt(report.items.reduce((s, it) => s + Number(it[k] || 0), 0));
  return `${blocks}<table><thead><tr><th>الإجمالي العام</th><th>رصيد أول المدة</th><th>الوارد</th><th>المنصرف</th><th>رصيد آخر المدة</th></tr></thead><tbody><tr class="grand"><td>القيمة</td><td>${t("opening_value")}</td><td>${t("in_value")}</td><td>${t("out_value")}</td><td>${t("closing_value")}</td></tr></tbody></table>`;
};

export const printInventoryReport = (kind, report, orgName) => {
  const win = window.open("", "_blank", "width=1200,height=900");
  if (!win) return false;
  const title = kind === "issues" ? "تقرير المنصرف من المخزون خلال الفترة" : "تقرير أرصدة وحركة المخزون خلال الفترة";
  const body = kind === "issues" ? issuesHtml(report) : balancesHtml(report);
  win.document.write(`<!doctype html><html dir="rtl" lang="ar"><head><meta charset="utf-8"><title>${title}</title><style>${STYLE}</style></head><body>${header(title, report, orgName)}${body}</body></html>`);
  win.document.close();
  injectPrintLogo(win, 40, false);
  setTimeout(() => { win.focus(); win.print(); }, 600);
  return true;
};
