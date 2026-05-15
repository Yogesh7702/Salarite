// api/client.js
import axios from "axios";
import { io } from "socket.io-client";
 
const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:5001";
 
// ─── Axios instance ───────────────────────────────────────────────────────────
export const api = axios.create({ baseURL: BASE_URL });
 
// Attach token on every request (always fresh from localStorage)
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});
 
// 401 → token expired → force re-login
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err?.response?.status === 401) {
      localStorage.removeItem("token");
      if (!window.location.pathname.includes("/login")) {
        window.location.href = "/login";
      }
    }
    return Promise.reject(err);
  }
);
 
// ─── Socket.io ────────────────────────────────────────────────────────────────
export const socket = io(BASE_URL, {
  autoConnect: false,                    // AuthContext connect/disconnect control karega
  transports: ["polling", "websocket"], // polling first — Render proxy ke liye zaroori
  reconnection: true,
  reconnectionAttempts: Infinity,
  reconnectionDelay: 1000,
  reconnectionDelayMax: 5000,
  timeout: 20000,
});
 
// Token refresh on every (re)connect
socket.on("connect", () => {
  socket.auth = { token: localStorage.getItem("token") };
});
 
socket.on("connect_error", (err) => {
  console.warn("Socket connect error:", err.message);
});
 
// ─── AuthContext ke liye helpers ──────────────────────────────────────────────
export function connectSocket() {
  socket.auth = { token: localStorage.getItem("token") };
  if (!socket.connected) socket.connect();
}
 
export function disconnectSocket() {
  if (socket.connected) socket.disconnect();
}