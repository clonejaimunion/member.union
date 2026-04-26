import { creatorCredit } from "@/lib/banks";

export const CreditLine = ({ className = "text-center text-xs font-bold text-slate-500", testId = "creator-credit" }) => (
  <p className={className} data-testid={testId}>{creatorCredit}</p>
);
