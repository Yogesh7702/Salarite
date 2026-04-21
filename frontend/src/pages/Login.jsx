import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [form, setForm] = useState({ email: "", password: "" });
  const [err, setErr] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    setErr("");
    try {
      const u = await login(form.email, form.password);
      nav(u.role === "employer" ? "/employer" : "/hr");
    } catch (e) {
      setErr(e.response?.data?.error || "Login failed");
    }
  };

  return (
    <div className="auth-shell">
      <form onSubmit={submit} className="card auth-card">
        <h2>Login</h2>
        <div style={{ marginBottom: "0.75rem" }}>
          <label className="muted">Email</label>
          <input type="email" required value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })} />
        </div>
        <div style={{ marginBottom: "0.75rem" }}>
          <label className="muted">Password</label>
          <input type="password" required value={form.password}
            onChange={(e) => setForm({ ...form, password: e.target.value })} />
        </div>
        {err && <div className="error">{err}</div>}
        <button type="submit" style={{ width: "100%", marginTop: "0.5rem" }}>Login</button>
        <p className="muted" style={{ marginTop: "0.75rem", textAlign: "center" }}>
          No account? <Link to="/signup">Sign up</Link>
        </p>
      </form>
    </div>
  );
}
