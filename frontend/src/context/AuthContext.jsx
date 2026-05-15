// context/AuthContext.jsx
import { createContext, useContext, useEffect, useState } from "react";
import { api, connectSocket, disconnectSocket } from "../api/client";
 
const AuthContext = createContext(null);
 
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
 
  const loadMe = async () => {
    const token = localStorage.getItem("token");
    if (!token) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      // Token interceptor already handles this, but set explicitly for safety
      api.defaults.headers.common["Authorization"] = `Bearer ${token}`;
      const { data } = await api.get("/api/auth/me");
      setUser(data.user);
      connectSocket();
    } catch (error) {
      // Token invalid ya expired — saaf karo
      localStorage.removeItem("token");
      delete api.defaults.headers.common["Authorization"];
      setUser(null);
    } finally {
      setLoading(false);
    }
  };
 
  useEffect(() => {
    loadMe();
  }, []);
 
  const login = async (email, password) => {
    const { data } = await api.post("/api/auth/login", { email, password });
    localStorage.setItem("token", data.token);
    api.defaults.headers.common["Authorization"] = `Bearer ${data.token}`;
    setUser(data.user);
    connectSocket();
    return data.user;
  };
 
  const signup = async (name, email, password, role) => {
    const { data } = await api.post("/api/auth/signup", {
      name,
      email,
      password,
      role,
    });
    localStorage.setItem("token", data.token);
    api.defaults.headers.common["Authorization"] = `Bearer ${data.token}`;
    setUser(data.user);
    connectSocket();
    return data.user;
  };
 
  const logout = () => {
    localStorage.removeItem("token");
    delete api.defaults.headers.common["Authorization"];
    setUser(null);
    disconnectSocket();
  };
 
  return (
    <AuthContext.Provider
      value={{ user, loading, login, signup, logout, setUser, reloadUser: loadMe }}
    >
      {children}
    </AuthContext.Provider>
  );
}
 
export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}