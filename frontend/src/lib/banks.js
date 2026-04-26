export const bankPalette = {
  "industrial-development": {
    tone: "border-slate-300 bg-slate-900 text-white",
    accent: "bg-slate-900",
    ring: "ring-slate-300",
  },
  "banque-misr": {
    tone: "border-red-200 bg-red-700 text-white",
    accent: "bg-red-700",
    ring: "ring-red-200",
  },
  "agricultural-bank": {
    tone: "border-emerald-200 bg-emerald-700 text-white",
    accent: "bg-emerald-700",
    ring: "ring-emerald-200",
  },
};

export const fallbackBanks = [
  { id: "industrial-development", name: "بنك التنمية الصناعية", short_name: "IDB", code: "IDB-EG" },
  { id: "banque-misr", name: "بنك مصر", short_name: "BM", code: "BM-EG" },
  { id: "agricultural-bank", name: "البنك الزراعي", short_name: "ABE", code: "ABE-EG" },
];
