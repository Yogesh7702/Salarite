import axios from "axios";
import { io } from "socket.io-client";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:5001";
const SOCKET_URL = import.meta.env.VITE_SOCKET_URL || "http://localhost:5001";

export const api = axios.create({ baseURL: API_URL });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export const socket = io(SOCKET_URL, {
  autoConnect: false,
  transports: ["websocket", "polling"],
  reconnection: true,
  reconnectionAttempts: Infinity,
  reconnectionDelay: 1000,
});

export function connectSocket() {
  if (!socket.connected) {
    socket.auth = { token: localStorage.getItem("token") };
    socket.connect();
  }
}

export function disconnectSocket() {
  if (socket.connected) socket.disconnect();
}

export default api;
