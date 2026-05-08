export const moduleDefinitions = {
  membership: "العضوية",
  fixed_assets: "الأصول الثابتة",
  custody_advances: "العهد والسلف",
  financial_statements: "القوائم المالية",
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
  inventory: "دفتر المخزون",
  misc_creditors: "دفتر الدائنين المتنوعين",
  feasibility_study: "دراسة جدوى",
  actuarial_study: "دراسة اكتوارية",
};

export const isModuleEnabled = (user, moduleKey) => user?.organization_modules?.[moduleKey] !== false;