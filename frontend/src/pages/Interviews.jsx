// Interviews.jsx
import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { api, socket } from "../api/client";
import { useAuth } from "../context/AuthContext";
 
export default function Interviews() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [success, setSuccess] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [form, setForm] = useState({
    candidate_name: "",
    candidate_email: "",
    scheduled_at: new Date().toISOString().slice(0, 16),
    mode: "video",
    notes: "",
  });
 
  const load = useCallback(async () => {
    try {
      setErr("");
      const { data } = await api.get("/api/interviews");
      setItems(Array.isArray(data) ? data : []);
    } catch (e) {
      const status = e?.response?.status;
      if (status === 401 || status === 403) {
        setErr("Session expired. Please log in again.");
      } else {
        setErr(e?.response?.data?.detail || "Failed to load interviews");
      }
    } finally {
      setLoading(false);
    }
  }, []);
 
  useEffect(() => {
    load();
 
    if (!socket.connected) {
      socket.auth = { token: localStorage.getItem("token") };
      socket.connect();
    }
 
    socket.on("interviews_changed", load);
    // Reload on reconnect so missed events are covered
    socket.on("connect", load);
 
    return () => {
      socket.off("interviews_changed", load);
      socket.off("connect", load);
    };
  }, [load]);
 
  const create = async (e) => {
    e.preventDefault();
    const email = form.candidate_email?.trim().toLowerCase();
    const emailPattern = /^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$/;
 
    setErr("");
    setSuccess("");
 
    if (!email) { setErr("Candidate email is required"); return; }
    if (!emailPattern.test(email)) { setErr("Enter a valid email address"); return; }
 
    try {
      setSubmitting(true);
 
      // Optimistic update — add to list immediately
      const optimistic = {
        id: `temp-${Date.now()}`,
        ...form,
        candidate_email: email,
        scheduled_at: new Date(form.scheduled_at).toISOString(),
        room_id: null,
        _pending: true,
      };
      setItems((prev) => [optimistic, ...prev]);
 
      await api.post("/api/interviews", { ...form, candidate_email: email });
 
      setSuccess("Interview scheduled successfully!");
      setForm((f) => ({
        ...f,
        candidate_name: "",
        candidate_email: "",
        notes: "",
      }));
 
      // Server emits interviews_changed → load() will replace optimistic entry
      // But also manually reload in case socket missed it
      await load();
    } catch (e) {
      // Remove optimistic entry on error
      setItems((prev) => prev.filter((i) => !i._pending));
      setErr(e?.response?.data?.detail || "Failed to schedule interview");
    } finally {
      setSubmitting(false);
    }
  };
 
  const handleJoin = (roomId) => {
    if (!roomId) {
      alert("Room ID missing. Interview may still be processing.");
      return;
    }
    navigate(`/call/${roomId}`);
  };
 
  if (loading)
    return (
      <div className="container">
        <h2>Interviews</h2>
        <div className="muted">Loading...</div>
      </div>
    );
 
  return (
    <div className="container">
      <h2>Interviews</h2>
 
      {err && (
        <div className="error" style={{ marginBottom: "1rem" }}>
          {err}
        </div>
      )}
      {success && (
        <div className="success" style={{ marginBottom: "1rem" }}>
          {success}
        </div>
      )}
 
      {user?.role === "hr" && (
        <div className="card">
          <h3>Schedule Interview</h3>
          <form onSubmit={create} className="grid grid-2">
            <input
              placeholder="Candidate name"
              value={form.candidate_name}
              onChange={(e) =>
                setForm({ ...form, candidate_name: e.target.value })
              }
            />
            <input
              type="email"
              placeholder="Candidate email"
              required
              value={form.candidate_email}
              onChange={(e) =>
                setForm({ ...form, candidate_email: e.target.value })
              }
            />
            <input
              type="datetime-local"
              value={form.scheduled_at}
              onChange={(e) =>
                setForm({ ...form, scheduled_at: e.target.value })
              }
            />
            <select
              value={form.mode}
              onChange={(e) => setForm({ ...form, mode: e.target.value })}
            >
              <option value="video">Video</option>
              <option value="voice">Voice</option>
              <option value="chat">Chat</option>
            </select>
            <input
              placeholder="Notes (optional)"
              value={form.notes}
              onChange={(e) => setForm({ ...form, notes: e.target.value })}
            />
            <button type="submit" disabled={submitting}>
              {submitting ? "Scheduling..." : "Schedule"}
            </button>
          </form>
        </div>
      )}
 
      <h3>
        {user?.role === "hr" ? "Scheduled Interviews" : "Your Interviews"} (
        {items.filter((i) => !i._pending).length})
      </h3>
 
      {items.length === 0 && (
        <div className="muted">No interviews yet.</div>
      )}
 
      <div className="grid grid-2">
        {items.map((i) => (
          <div
            key={i.id}
            className="card"
            style={{ opacity: i._pending ? 0.6 : 1 }}
          >
            <div
              className="row"
              style={{ justifyContent: "space-between" }}
            >
              <strong>{i.candidate_name || i.candidate_email}</strong>
              <span className="badge">{i.mode}</span>
            </div>
 
            {i.candidate_email && (
              <div className="muted" style={{ margin: "0.25rem 0" }}>
                {i.candidate_email}
              </div>
            )}
 
            <div className="muted" style={{ margin: "0.4rem 0" }}>
              {new Date(i.scheduled_at).toLocaleString()}
            </div>
 
            {i.notes && <div className="muted">{i.notes}</div>}
 
            {i._pending ? (
              <div className="muted" style={{ marginTop: "0.6rem" }}>
                Saving...
              </div>
            ) : (
              <button
                style={{ marginTop: "0.6rem" }}
                onClick={() => handleJoin(i.room_id)}
              >
                Join Call Room
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
 