export const moduleDefinitions = {
  deposits: "فوائد الودائع",
  journal_entries: "القيود اليومية",
  reconciliations: "التسويات البنكية",
  revenues: "الإيرادات",
  expenses: "المصروفات",
  expenses_analysis: "تحليل المصروفات",
  banking_expenses: "المصروفات البنكية",
  ledger: "دفتر الأستاذ",
  electronic_invoice: "الفاتورة الإلكترونية",
};

export const isModuleEnabled = (user, moduleKey) => user?.organization_modules?.[moduleKey] !== false;