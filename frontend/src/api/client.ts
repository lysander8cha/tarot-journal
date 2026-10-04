import axios from 'axios';

/** Base URL for the Flask API server */
// The API always lives at our own origin: in the packaged app Flask
// serves the frontend itself (which keeps alternate-port launches —
// the scratch-database mode — working), and in development the Vite
// dev server proxies /api to Flask (see vite.config.ts).
const API_BASE = window.location.origin;

/** Pre-configured axios instance for all API calls */
const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

export default api;
export { API_BASE };
