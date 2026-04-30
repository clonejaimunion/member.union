export const moduleDefinitions = {
  fixed_assets: "الأصول الثابتة",
  chart_accounts: "شجرة الحسابات",
  trial_balance: "ميزان المراجعة",
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