import { ArrowDownToLine, ArrowRightFromLine } from "lucide-react";
import { orientationOptions } from "@/lib/printOrientation";

const iconForOrientation = (value) => (value === "landscape" ? <ArrowRightFromLine className="h-3.5 w-3.5" /> : <ArrowDownToLine className="h-3.5 w-3.5" />);

export const PrintOrientationToggle = ({ orientation, onChange, testIdPrefix = "print-orientation", className = "" }) => (
  <div
    role="group"
    aria-label="اتجاه ورق الطباعة"
    className={`inline-flex h-11 items-stretch overflow-hidden rounded-lg border border-slate-300 bg-white text-xs font-extrabold ${className}`}
    data-testid={`${testIdPrefix}-group`}
  >
    <span className="flex items-center px-3 text-[11px] font-bold text-slate-500" data-testid={`${testIdPrefix}-label`}>اتجاه</span>
    {orientationOptions.map((option) => {
      const isActive = orientation === option.value;
      return (
        <button
          key={option.value}
          type="button"
          onClick={() => onChange(option.value)}
          className={`flex items-center gap-1 border-r border-slate-200 px-3 transition-colors ${isActive ? "bg-slate-950 text-white" : "bg-white text-slate-700 hover:bg-slate-100"}`}
          data-testid={`${testIdPrefix}-${option.value}-button`}
          aria-pressed={isActive}
        >
          {iconForOrientation(option.value)}
          <span>{option.label}</span>
        </button>
      );
    })}
  </div>
);
