// pages/Login.jsx
import { useState } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const location = useLocation();
  const [form, setForm] = useState({ email: "", password: "" });
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setErr("");
    setLoading(true);
    try {
      const u = await login(form.email, form.password);

      // Login ke baad user jahan tha wahan wapas bhejo, warna role-based redirect
      const from = location.state?.from?.pathname;
      if (from && from !== "/login") {
        nav(from, { replace: true });
      } else if (u.role === "employer") {
        nav("/employer", { replace: true });
      } else if (u.role === "hr") {
        nav("/hr", { replace: true });
      } else {
        // candidate
        nav("/interviews", { replace: true });
      }
    } catch (e) {
      setErr(
        e?.response?.data?.detail ||
        e?.response?.data?.error ||
        "Login failed. Check your email and password."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-shell">
      <form onSubmit={submit} className="card auth-card">
        <h2>Login</h2>

        <div style={{ marginBottom: "0.75rem" }}>
          <label className="muted">Email</label>
          <input
            type="email"
            required
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
          />
        </div>

        <div style={{ marginBottom: "0.75rem" }}>
          <label className="muted">Password</label>
          <input
            type="password"
            required
            value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })}
          />
        </div>

        {err && <div className="error" style={{ marginBottom: "0.5rem" }}>{err}</div>}

        <button
          type="submit"
          style={{ width: "100%", marginTop: "0.5rem" }}
          disabled={loading}
        >
          {loading ? "Logging in..." : "Login"}
        </button>

        <p className="muted" style={{ marginTop: "0.75rem", textAlign: "center" }}>
          No account? <Link to="/signup">Sign up</Link>
        </p>
      </form>
    </div>
  );
}