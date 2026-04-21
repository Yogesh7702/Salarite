import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function Signup() {
  const { signup } = useAuth();
  const nav = useNavigate();

  const [form, setForm] = useState({
    name: "",
    email: "",
    password: "",
    role: "employer",
  });

  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm((prev) => ({
      ...prev,
      [name]: value,
    }));
  };

  const submit = async (e) => {
    e.preventDefault();
    setErr("");
    setLoading(true);

    try {
      const u = await signup(
        form.name,
        form.email,
        form.password,
        form.role
      );

      if (u.role === "employer") {
        nav("/employer");
      } else if (u.role === "hr") {
        nav("/hr");
      } else {
        nav("/candidate");
      }
    } catch (e) {
      setErr(e.response?.data?.error || "Signup failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-shell">
      <form onSubmit={submit} className="card auth-card">
        <h2>Create Account</h2>

        <div style={{ marginBottom: "0.75rem" }}>
          <label className="muted" htmlFor="name">Name</label>
          <input
            id="name"
            name="name"
            required
            value={form.name}
            onChange={handleChange}
          />
        </div>

        <div style={{ marginBottom: "0.75rem" }}>
          <label className="muted" htmlFor="email">Email</label>
          <input
            id="email"
            name="email"
            type="email"
            required
            value={form.email}
            onChange={handleChange}
          />
        </div>

        <div style={{ marginBottom: "0.75rem" }}>
          <label className="muted" htmlFor="password">Password</label>
          <input
            id="password"
            name="password"
            type="password"
            required
            minLength={4}
            value={form.password}
            onChange={handleChange}
          />
        </div>

        <div style={{ marginBottom: "0.75rem" }}>
          <label className="muted" htmlFor="role">Role</label>
          <select
            id="role"
            name="role"
            value={form.role}
            onChange={handleChange}
          >
            <option value="employer">Employer</option>
            <option value="hr">Virtual HR</option>
            <option value="candidate">Candidate</option>
          </select>
        </div>

        {err && <div className="error">{err}</div>}

        <button
          type="submit"
          style={{ width: "100%", marginTop: "0.5rem" }}
          disabled={loading}
        >
          {loading ? "Creating..." : "Sign Up"}
        </button>

        <p className="muted" style={{ marginTop: "0.75rem", textAlign: "center" }}>
          Have account? <Link to="/login">Login</Link>
        </p>
      </form>
    </div>
  );
}