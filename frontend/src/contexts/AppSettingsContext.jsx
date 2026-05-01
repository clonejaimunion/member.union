import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";

const defaultSettings = {
  system_name: "نظام محاسبي متكامل",
  shortcut_icon_url: null,
  shortcut_update_status: null,
  organizations: {},
  updated_at: null,
};

const AppSettingsContext = createContext({
  settings: defaultSettings,
  refreshSettings: async () => defaultSettings,
});

export const AppSettingsProvider = ({ children }) => {
  const [settings, setSettings] = useState(defaultSettings);

  const refreshSettings = useCallback(async () => {
    try {
      const response = await api.get("/app-settings/public");
      const nextSettings = { ...defaultSettings, ...response.data };
      setSettings(nextSettings);
      return nextSettings;
    } catch {
      setSettings(defaultSettings);
      return defaultSettings;
    }
  }, []);

  useEffect(() => {
    refreshSettings();
  }, [refreshSettings]);

  useEffect(() => {
    const iconUrl = settings.shortcut_icon_url;
    let favicon = document.querySelector('link[rel="icon"]');
    if (!favicon) {
      favicon = document.createElement("link");
      favicon.rel = "icon";
      document.head.appendChild(favicon);
    }
    if (iconUrl) favicon.href = iconUrl;
  }, [settings.shortcut_icon_url]);

  const value = useMemo(() => ({ settings, refreshSettings }), [settings, refreshSettings]);

  return <AppSettingsContext.Provider value={value}>{children}</AppSettingsContext.Provider>;
};

export const useAppSettings = () => useContext(AppSettingsContext);