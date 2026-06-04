import { FileDown, FileSpreadsheet, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/contexts/AuthContext";
import { PrintOrientationToggle } from "@/components/PrintOrientationToggle";
import { usePrintOrientation, printWithOrientation } from "@/lib/printOrientation";

const escapeHtml = (value) => String(value ?? "")
  .replace(/&/g, "&amp;")
  .replace(/</g, "&lt;")
  .replace(/>/g, "&gt;")
  .replace(/"/g, "&quot;")
  .replace(/'/g, "&#039;");

const safeFileName = (value) => String(value || "report")
  .replace(/[\\/:*?"<>|]/g, "-")
  .replace(/\s+/g, "-")
  .slice(0, 140);

const downloadContent = (content, filename, type) => {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
};

const cloneReportContent = (selectors) => {
  const container = document.createElement("main");
  selectors.forEach((selector) => {
    const source = document.querySelector(selector);
    if (!source) return;
    const clone = source.cloneNode(true);
    clone.querySelectorAll("img").forEach((image) => {
      const imageSource = image.getAttribute("src") || image.src;
      if (!imageSource) return;
      try {
        image.setAttribute("src", new URL(imageSource, window.location.origin).href);
      } catch {
        image.setAttribute("src", imageSource);
      }
    });
    clone.querySelectorAll("button, input, select, textarea, [data-export-exclude='true']").forEach((node) => node.remove());
    clone.querySelectorAll("*").forEach((node) => {
      const className = typeof node.className === "string" ? node.className : "";
      if (className.includes("print:hidden")) node.remove();
    });
    container.appendChild(clone);
  });
  return container.innerHTML;
};

const buildOfficeHtml = ({ title, selectors, excel = false, orientation = "portrait" }) => {
  const bodyHtml = cloneReportContent(selectors);
  const isReconciliationMemo = (selectors || []).some((selector) => String(selector).includes("reconciliation-print-report"));
  const excelOrientation = orientation === "landscape" ? "Landscape" : "Portrait";
  const workbookMeta = excel
    ? `<xml><x:ExcelWorkbook><x:ExcelWorksheets><x:ExcelWorksheet><x:Name>${escapeHtml(title || "تقرير")}</x:Name><x:WorksheetOptions><x:DisplayRightToLeft/><x:Print><x:LeftToRight/></x:Print><x:PageSetup><x:Layout x:Orientation="${excelOrientation}"/></x:PageSetup></x:WorksheetOptions></x:ExcelWorksheet></x:ExcelWorksheets></x:ExcelWorkbook></xml>`
    : "";
  const pageSize = orientation === "landscape" ? "A4 landscape" : "A4 portrait";
  return `<!doctype html>
<html dir="rtl" lang="ar" xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:x="urn:schemas-microsoft-com:office:excel" xmlns:w="urn:schemas-microsoft-com:office:word">
<head>
  <meta charset="utf-8" />
  ${workbookMeta}
  <style>
    @page { size: ${pageSize}; margin: ${isReconciliationMemo ? "5mm" : "6mm"}; }
    @page expenses-analysis-landscape { size: ${pageSize}; margin: 7mm; }
    @page reconciliation-single-page { size: ${pageSize}; margin: 5mm; }
    body { direction: rtl; font-family: Tahoma, Arial, sans-serif; color: #111827; ${isReconciliationMemo ? "width:200mm;height:287mm;overflow:hidden;margin:0;padding:0;" : ""} }
    h1, h2, h3, p { margin: 0 0 6px; }
    ${isReconciliationMemo ? "body > h1 { display:none; }" : ""}
    section, article, div { box-sizing: border-box; }
    table { border-collapse: collapse; width: 100%; table-layout: auto; margin: 10px 0; }
    th, td { border: 1px solid #111827; padding: 6px; text-align: right; vertical-align: top; white-space: normal; }
    th { background: #111827; color: #ffffff; font-weight: 700; }
    .rounded-xl, .rounded-lg { border-radius: 4px; }
    [data-testid="reconciliation-print-report"] { ${isReconciliationMemo ? "width:190mm;height:277mm;max-height:277mm;min-height:277mm;overflow:hidden;margin:0 auto;padding:8mm 10mm;zoom:0.86;page-break-after:avoid;break-after:avoid;" : "max-height:285mm;overflow:visible;zoom:0.82;"} font-size: 8px; line-height: 1.12; }
    [data-testid="reconciliation-print-report"] h3 { font-size: 10px; margin: 2px 0; }
    [data-testid="reconciliation-print-report"] table { margin: 2px 0; table-layout: fixed; }
    [data-testid="reconciliation-print-report"] th,
    [data-testid="reconciliation-print-report"] td { padding: 3px; font-size: 7px; line-height: 1.08; }
  </style>
</head>
<body>
  <h1>${escapeHtml(title || "تقرير")}</h1>
  ${bodyHtml || "<p>لا توجد بيانات للتصدير</p>"}
</body>
</html>`;
};

export const exportReportToOffice = ({ title, fileName, selectors, type, orientation = "portrait" }) => {
  const excel = type === "excel";
  const extension = excel ? "xls" : "doc";
  const mimeType = excel ? "application/vnd.ms-excel;charset=utf-8" : "application/msword;charset=utf-8";
  downloadContent(buildOfficeHtml({ title, selectors, excel, orientation }), `${safeFileName(fileName || title)}.${extension}`, mimeType);
};

export const ExportReportButtons = ({ title, fileName, selectors, printSelectors = null, disabled = false, className = "", pdfLabel = "PDF", pdfTestId, excelTestId, wordTestId, showOrientationToggle = true, orientationTestIdPrefix }) => {
  const { user } = useAuth();
  const [orientation, setOrientation] = usePrintOrientation("portrait");
  const reportTitle = user?.organization_name ? `${user.organization_name} - ${title}` : title;
  const reportFileName = user?.organization_name ? `${user.organization_name}-${fileName || title}` : fileName;
  const exportExcel = () => exportReportToOffice({ title: reportTitle, fileName: reportFileName, selectors, type: "excel", orientation });
  const exportWord = () => exportReportToOffice({ title: reportTitle, fileName: reportFileName, selectors, type: "word", orientation });
  const printPdf = () => {
    if (!printSelectors) {
      printWithOrientation(orientation);
      return;
    }
    const printWindow = window.open("", "_blank", "width=1200,height=800");
    if (!printWindow) {
      printWithOrientation(orientation);
      return;
    }
    printWindow.document.write(buildOfficeHtml({ title: reportTitle, selectors: printSelectors, excel: false, orientation }));
    printWindow.document.close();
    printWindow.focus();
    setTimeout(() => {
      printWindow.print();
      printWindow.close();
    }, 250);
  };

  return (
    <div className={`flex flex-wrap items-center gap-2 print:hidden ${className}`} data-export-exclude="true" data-testid={`${pdfTestId || "report-export-pdf-button"}-group`}>
      {showOrientationToggle && (
        <PrintOrientationToggle orientation={orientation} onChange={setOrientation} testIdPrefix={orientationTestIdPrefix || `${pdfTestId || "report-export"}-orientation`} />
      )}
      <Button type="button" onClick={printPdf} disabled={disabled} className="h-11 rounded-lg bg-slate-950 px-5 text-white disabled:opacity-50" data-testid={pdfTestId || "report-export-pdf-button"}>
        <FileDown className="h-4 w-4" /> {pdfLabel}
      </Button>
      <Button type="button" onClick={exportExcel} disabled={disabled} variant="outline" className="h-11 rounded-lg bg-white px-5 disabled:opacity-50" data-testid={excelTestId || "report-export-excel-button"}>
        <FileSpreadsheet className="h-4 w-4" /> Excel
      </Button>
      <Button type="button" onClick={exportWord} disabled={disabled} variant="outline" className="h-11 rounded-lg bg-white px-5 disabled:opacity-50" data-testid={wordTestId || "report-export-word-button"}>
        <FileText className="h-4 w-4" /> Word
      </Button>
    </div>
  );
};
