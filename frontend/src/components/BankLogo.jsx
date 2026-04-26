import { Building2 } from "lucide-react";
import { bankPalette } from "@/lib/banks";

export const BankLogo = ({ bankId, bankName, logoUrl, className = "h-12 w-12", imageClassName = "h-full w-full object-contain", testId = "bank-logo" }) => {
  const palette = bankPalette[bankId];
  const source = logoUrl || palette?.logo;

  return (
    <div className={`flex shrink-0 items-center justify-center overflow-hidden rounded-lg border border-slate-200 bg-white p-1 shadow-sm ${className}`} data-testid={testId}>
      {source ? (
        <img src={source} alt={`شعار ${bankName || "البنك"}`} className={imageClassName} data-testid={`${testId}-image`} />
      ) : (
        <Building2 className="h-6 w-6 text-slate-700" data-testid={`${testId}-fallback-icon`} />
      )}
    </div>
  );
};
