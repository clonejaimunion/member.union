import "@/App.css";
import { useEffect } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import BankSelection from "@/pages/BankSelection";
import DepositRegistration from "@/pages/DepositRegistration";
import ReportPage from "@/pages/ReportPage";

function App() {
  useEffect(() => {
    document.documentElement.setAttribute("dir", "rtl");
    document.documentElement.setAttribute("lang", "ar");
  }, []);

  return (
    <div className="App" dir="rtl" data-testid="app-root">
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<BankSelection />} />
          <Route path="/bank/:bankId/register" element={<DepositRegistration />} />
          <Route path="/bank/:bankId/current-year" element={<ReportPage type="current-year" />} />
          <Route path="/bank/:bankId/previous-year" element={<ReportPage type="previous-year" />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
      <Toaster richColors position="top-center" />
    </div>
  );
}

export default App;
