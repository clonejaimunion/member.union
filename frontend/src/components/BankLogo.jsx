import { Building2 } from "lucide-react";
import { bankPalette } from "@/lib/banks";

export const BankLogo = ({ bankId, bankName, className = "h-12 w-12", imageClassName = "h-full w-full object-contain", testId = "bank-logo" }) => {
  const palette = bankPalette[bankId] || bankPalette["industrial-development"];

  return (
    <div className={`flex shrink-0 items-center justify-center overflow-hidden rounded-lg border border-slate-200 bg-white p-1 shadow-sm ${className}`} data-testid={testId}>
      {palette.logo ? (
        <img src={palette.logo} alt={`شعار ${bankName || "البنك"}`} className={imageClassName} data-testid={`${testId}-image`} />
      ) : (
        <Building2 className="h-6 w-6 text-slate-700" data-testid={`${testId}-fallback-icon`} />
      )}
    </div>
  );
};
