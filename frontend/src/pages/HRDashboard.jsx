// HRDashboard.jsx
import { useEffect, useState, useMemo, useCallback } from "react";
import { api, socket } from "../api/client";
import TaskCard from "../components/TaskCard";
import { useAuth } from "../context/AuthContext";
 
export default function HRDashboard() {
  const { user } = useAuth();
  const [tasks, setTasks] = useState([]);
  const [filter, setFilter] = useState("all");
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
 
  const load = useCallback(async () => {
    try {
      setErr("");
      const { data } = await api.get("/api/tasks");
      setTasks(Array.isArray(data) ? data : []);
    } catch (e) {
      const status = e?.response?.status;
      if (status === 401 || status === 403) {
        setErr("Session expired. Please log in again.");
      } else {
        setErr(e?.response?.data?.detail || "Failed to load tasks");
      }
    } finally {
      setLoading(false);
    }
  }, []);
 
  useEffect(() => {
    load();
 
    // Connect socket if not already connected
    if (!socket.connected) {
      // Refresh auth before connecting (token might have changed)
      socket.auth = { token: localStorage.getItem("token") };
      socket.connect();
    }
 
    // Real-time: reload on task changes
    socket.on("tasks_changed", load);
 
    // IMPORTANT: also reload on reconnect — missed events during disconnect
    socket.on("connect", load);
 
    return () => {
      socket.off("tasks_changed", load);
      socket.off("connect", load);
    };
  }, [load]);
 
  const update = async (id, status) => {
    // Optimistic update — change UI instantly, revert on error
    setTasks((prev) =>
      prev.map((t) => (t.id === id ? { ...t, status } : t))
    );
 
    try {
      await api.patch(`/api/tasks/${id}`, { status });
      // Server will emit tasks_changed → load() will sync
    } catch (e) {
      // Revert optimistic update
      load();
      const status_code = e?.response?.status;
      if (status_code === 403) {
        alert("Permission denied. Make sure you are logged in as HR.");
      } else {
        alert(e?.response?.data?.detail || "Failed to update task");
      }
    }
  };
 
  const hrTasks = useMemo(() => {
    if (!user) return [];
    return tasks.filter((t) => Number(t.assigned_to) === Number(user.id));
  }, [tasks, user]);
 
  const filtered = useMemo(() => {
    if (filter === "all") return hrTasks;
    return hrTasks.filter((t) => t.status === filter);
  }, [hrTasks, filter]);
 
  const stats = {
    total: hrTasks.length,
    pending: hrTasks.filter((t) => t.status === "pending").length,
    in_progress: hrTasks.filter((t) => t.status === "in_progress").length,
    completed: hrTasks.filter((t) => t.status === "completed").length,
  };
 
  if (loading)
    return (
      <div className="container">
        <h2>HR Workspace</h2>
        <div className="muted">Loading...</div>
      </div>
    );
 
  return (
    <div className="container">
      <h2>Virtual HR Workspace</h2>
 
      {err && (
        <div className="error" style={{ marginBottom: "1rem" }}>
          {err}{" "}
          {err.includes("Session") && (
            <a href="/login" style={{ color: "inherit", fontWeight: "bold" }}>
              Login again →
            </a>
          )}
        </div>
      )}
 
      <div className="grid grid-4">
        <div className="card">
          <div className="muted">Total</div>
          <h3>{stats.total}</h3>
        </div>
        <div className="card">
          <div className="muted">Pending</div>
          <h3>{stats.pending}</h3>
        </div>
        <div className="card">
          <div className="muted">In Progress</div>
          <h3>{stats.in_progress}</h3>
        </div>
        <div className="card">
          <div className="muted">Completed</div>
          <h3>{stats.completed}</h3>
        </div>
      </div>
 
      <div className="card">
        <div className="row" style={{ gap: "0.5rem", flexWrap: "wrap" }}>
          {["all", "pending", "in_progress", "completed"].map((f) => (
            <button
              key={f}
              className={filter === f ? "" : "secondary"}
              onClick={() => setFilter(f)}
            >
              {f.replace("_", " ")}
            </button>
          ))}
        </div>
      </div>
 
      {hrTasks.length === 0 && !err && (
        <div className="card">
          <div className="muted">No tasks assigned to you yet.</div>
        </div>
      )}
 
      {hrTasks.length > 0 && filtered.length === 0 && (
        <div className="card">
          <div className="muted">No {filter.replace("_", " ")} tasks.</div>
        </div>
      )}
 
      <div className="grid grid-2">
        {filtered.map((t) => (
          <TaskCard
            key={t.id}
            task={t}
            role="hr"
            onStart={(id) => update(id, "in_progress")}
            onComplete={(id) => update(id, "completed")}
          />
        ))}
      </div>
    </div>
  );
}