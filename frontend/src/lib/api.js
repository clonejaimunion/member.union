import axios from "axios";

const configuredBackendUrl = process.env.REACT_APP_BACKEND_URL;
const isBrowserLanHost = window.location.protocol.startsWith("http") && !["localhost", "127.0.0.1"].includes(window.location.hostname);
const isConfiguredLocalhost = configuredBackendUrl?.includes("localhost") || configuredBackendUrl?.includes("127.0.0.1");
const isLocalBackendServedBuild =
  window.location.protocol.startsWith("http") &&
  ["localhost", "127.0.0.1"].includes(window.location.hostname) &&
  window.location.port === "8001";

const BACKEND_URL = isLocalBackendServedBuild || (isBrowserLanHost && isConfiguredLocalhost) ? window.location.origin : configuredBackendUrl;
export const API = `${BACKEND_URL}/api`;

export const api = axios.create({ baseURL: API });

export const setAuthToken = (token) => {
  if (token) {
    api.defaults.headers.common.Authorization = `Bearer ${token}`;
  } else {
    delete api.defaults.headers.common.Authorization;
  }
};

const storedToken = window.localStorage.getItem("bank_auth_token");
if (storedToken) setAuthToken(storedToken);

