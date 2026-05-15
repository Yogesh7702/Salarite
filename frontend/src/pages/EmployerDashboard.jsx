
import { useEffect, useState, useMemo, useCallback } from "react";
import { api, socket } from "../api/client";
import TaskCard from "../components/TaskCard";
import { useAuth } from "../context/AuthContext";
 
export default function EmployerDashboard() {
  const { user } = useAuth();
  const [tasks, setTasks] = useState([]);
  const [activities, setActivities] = useState([]);
  const [form, setForm] = useState({
    title: "",
    description: "",
    priority: "medium",
    assigned_hr_email: "",
  });
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [err, setErr] = useState("");
  const [success, setSuccess] = useState("");
 
  const load = useCallback(async () => {
    try {
      const [t, a] = await Promise.all([
        api.get("/api/tasks"),
        api.get("/api/activities"),
      ]);
      setTasks(Array.isArray(t.data) ? t.data : []);
      setActivities(Array.isArray(a.data) ? a.data : []);
    } catch (e) {
      console.error(e);
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
 
    socket.on("tasks_changed", load);
    socket.on("activity_new", load);
    // Reload on reconnect to catch missed events
    socket.on("connect", load);
 
    return () => {
      socket.off("tasks_changed", load);
      socket.off("activity_new", load);
      socket.off("connect", load);
    };
  }, [load]);
 
  const createTask = async (e) => {
    e.preventDefault();
    setErr("");
    setSuccess("");
 
    if (!form.title.trim()) { setErr("Title is required"); return; }
    if (!form.assigned_hr_email.trim()) { setErr("HR email is required"); return; }
 
    try {
      setCreating(true);
      await api.post("/api/tasks", {
        title: form.title.trim(),
        description: form.description.trim(),
        priority: form.priority,
        assigned_hr_email: form.assigned_hr_email.trim().toLowerCase(),
      });
      setSuccess("Task assigned successfully!");
      setForm({ title: "", description: "", priority: "medium", assigned_hr_email: "" });
      await load();
    } catch (e) {
      const status = e?.response?.status;
      const detail = e?.response?.data?.detail;
 
      if (status === 403) {
        setErr("Access denied (403). Your session may have expired — please log out and log in again.");
      } else if (status === 400) {
        setErr(detail || "Invalid input. Make sure the HR email is correct and belongs to an HR user.");
      } else {
        setErr(detail || "Failed to create task");
      }
    } finally {
      setCreating(false);
    }
  };
 
  const resetTask = async (id) => {
    try {
      await api.patch(`/api/tasks/${id}`, { status: "pending" });
      load();
    } catch (e) {
      const status = e?.response?.status;
      if (status === 403) {
        alert("Session expired. Please log out and log in again.");
      } else {
        alert(e?.response?.data?.detail || "Failed to reset task");
      }
    }
  };
 
  const myTasks = useMemo(
    () => tasks.filter((t) => Number(t.employer_id) === Number(user?.id)),
    [tasks, user]
  );
 
  const stats = {
    total: myTasks.length,
    pending: myTasks.filter((t) => t.status === "pending").length,
    in_progress: myTasks.filter((t) => t.status === "in_progress").length,
    completed: myTasks.filter((t) => t.status === "completed").length,
  };
 
  if (loading)
    return (
      <div className="container">
        <h2>Employer Dashboard</h2>
        <div className="muted">Loading...</div>
      </div>
    );
 
  return (
    <div className="container">
      <h2>Employer Dashboard</h2>
 
      <div className="grid grid-4">
        <div className="card"><div className="muted">Total</div><h3>{stats.total}</h3></div>
        <div className="card"><div className="muted">Pending</div><h3>{stats.pending}</h3></div>
        <div className="card"><div className="muted">In Progress</div><h3>{stats.in_progress}</h3></div>
        <div className="card"><div className="muted">Completed</div><h3>{stats.completed}</h3></div>
      </div>
 
      <div className="card">
        <h3>Assign Task to HR</h3>
 
        {err && (
          <div className="error" style={{ marginBottom: "12px" }}>
            {err}
            {err.includes("session") && (
              <span>
                {" "}
                <a href="/login" style={{ color: "inherit", fontWeight: "bold" }}>
                  Login →
                </a>
              </span>
            )}
          </div>
        )}
        {success && (
          <div className="success" style={{ marginBottom: "12px" }}>
            {success}
          </div>
        )}
 
        <form onSubmit={createTask}>
          <div style={{ marginBottom: "12px" }}>
            <label className="muted">Title *</label>
            <input
              placeholder="Task title"
              required
              value={form.title}
              onChange={(e) => setForm((p) => ({ ...p, title: e.target.value }))}
            />
          </div>
          <div style={{ marginBottom: "12px" }}>
            <label className="muted">Description</label>
            <textarea
              placeholder="Description (optional)"
              rows={3}
              value={form.description}
              onChange={(e) => setForm((p) => ({ ...p, description: e.target.value }))}
            />
          </div>
          <div style={{ marginBottom: "12px" }}>
            <label className="muted">HR Email *</label>
            <input
              type="email"
              placeholder="hr@example.com"
              required
              value={form.assigned_hr_email}
              onChange={(e) =>
                setForm((p) => ({ ...p, assigned_hr_email: e.target.value }))
              }
            />
          </div>
          <div style={{ marginBottom: "12px" }}>
            <label className="muted">Priority</label>
            <select
              value={form.priority}
              onChange={(e) => setForm((p) => ({ ...p, priority: e.target.value }))}
            >
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
            </select>
          </div>
          <button type="submit" disabled={creating}>
            {creating ? "Assigning..." : "Assign Task"}
          </button>
        </form>
      </div>
 
      <div className="card">
        <h3>My Tasks ({myTasks.length})</h3>
        {myTasks.length === 0 ? (
          <div className="muted">No tasks yet.</div>
        ) : (
          <div className="grid grid-2">
            {myTasks.map((t) => (
              <TaskCard key={t.id} task={t} role="employer" onReset={resetTask} />
            ))}
          </div>
        )}
      </div>
 
      <div className="card">
        <h3>Activity Feed</h3>
        {activities.length === 0 ? (
          <div className="muted">No activity yet.</div>
        ) : (
          activities.map((a) => (
            <div
              key={a.id}
              style={{ padding: "8px 0", borderBottom: "1px solid #eee" }}
            >
              <div>{a.message}</div>
              <div className="muted" style={{ fontSize: "12px" }}>
                {new Date(a.created_at).toLocaleString()}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
 