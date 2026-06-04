import { useEffect, useState, useCallback } from "react";

const STORAGE_KEY = "report.print.orientation";
const STYLE_ID = "print-orientation-override-style";

export const orientationOptions = [
  { value: "portrait", label: "طولي" },
  { value: "landscape", label: "عرضي" },
];

export const orientationLabel = (value) => (value === "landscape" ? "عرضي" : "طولي");

const readSavedOrientation = (defaultValue) => {
  if (typeof window === "undefined") return defaultValue;
  try {
    const saved = window.localStorage.getItem(STORAGE_KEY);
    return saved === "landscape" || saved === "portrait" ? saved : defaultValue;
  } catch {
    return defaultValue;
  }
};

export const getSavedPrintOrientation = (defaultValue = "portrait") => readSavedOrientation(defaultValue);

export const usePrintOrientation = (defaultValue = "portrait") => {
  const [orientation, setOrientationState] = useState(() => readSavedOrientation(defaultValue));
  useEffect(() => {
    const handler = (event) => {
      if (event.key === STORAGE_KEY && (event.newValue === "landscape" || event.newValue === "portrait")) {
        setOrientationState(event.newValue);
      }
    };
    window.addEventListener("storage", handler);
    return () => window.removeEventListener("storage", handler);
  }, []);
  const setOrientation = useCallback((value) => {
    const safe = value === "landscape" ? "landscape" : "portrait";
    setOrientationState(safe);
    try {
      window.localStorage.setItem(STORAGE_KEY, safe);
    } catch {
      /* ignore quota errors */
    }
  }, []);
  return [orientation, setOrientation];
};

const buildOrientationStylesheet = (orientation) => `@page { size: A4 ${orientation}; }
@page expenses-analysis-landscape { size: A4 ${orientation}; }
@page reconciliation-single-page { size: A4 ${orientation}; }`;

export const buildOrientationStyleTag = (orientation) => `<style>${buildOrientationStylesheet(orientation)}</style>`;

export const injectPrintOrientationStyle = (orientation) => {
  const previous = document.getElementById(STYLE_ID);
  if (previous) previous.remove();
  const style = document.createElement("style");
  style.id = STYLE_ID;
  style.media = "print";
  style.textContent = buildOrientationStylesheet(orientation);
  document.head.appendChild(style);
  return style;
};

export const removePrintOrientationStyle = () => {
  const previous = document.getElementById(STYLE_ID);
  if (previous) previous.remove();
};

export const printWithOrientation = (orientation, action) => {
  const style = injectPrintOrientationStyle(orientation);
  const cleanup = () => {
    setTimeout(() => {
      if (document.body.contains(style)) style.remove();
    }, 1500);
  };
  if (typeof action === "function") {
    setTimeout(() => {
      try {
        action();
      } finally {
        cleanup();
      }
    }, 60);
    return;
  }
  setTimeout(() => {
    window.print();
    cleanup();
  }, 60);
};

export const printNow = () => {
  printWithOrientation(readSavedOrientation("portrait"));
};
