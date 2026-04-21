import { useEffect, useState, useMemo, useCallback } from "react";
import { api, socket } from "../api/client";
import TaskCard from "../components/TaskCard";
import { useAuth } from "../context/AuthContext";

export default function HRDashboard() {
  const { user } = useAuth();

  const [tasks, setTasks] = useState([]);
  const [filter, setFilter] = useState("pending");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setError("");

      const { data } = await api.get("/api/tasks");
      setTasks(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error("HR dashboard load failed:", err);
      setError(err?.response?.data?.error || "Failed to load HR dashboard");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    socket.on("tasks_changed", load);

    return () => {
      socket.off("tasks_changed", load);
    };
  }, [load]);

  const update = async (id, status) => {
    try {
      await api.patch(`/api/tasks/${id}`, { status });
      load();
    } catch (err) {
      console.error("Task update failed:", err);
      alert(err?.response?.data?.error || "Failed to update task");
    }
  };

  const hrTasks = useMemo(() => {
    if (!user) return [];

    return tasks.filter((t) => {
      const assignedIdMatch = Number(t.assigned_to) === Number(user.id);
      const assignedEmailMatch =
        t.assignee_email &&
        user.email &&
        String(t.assignee_email).toLowerCase() === String(user.email).toLowerCase();

      return assignedIdMatch || assignedEmailMatch;
    });
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

  if (loading) {
    return (
      <div className="container">
        <h2>Virtual HR Workspace</h2>
        <div className="muted">Loading tasks...</div>
      </div>
    );
  }

  return (
    <div className="container">
      <h2>Virtual HR Workspace</h2>

      {error && <div className="error">{error}</div>}

      <div className="grid grid-3">
        <div className="card"><div className="muted">Total</div><h3>{stats.total}</h3></div>
        <div className="card"><div className="muted">Pending</div><h3>{stats.pending}</h3></div>
        <div className="card"><div className="muted">In Progress</div><h3>{stats.in_progress}</h3></div>
        <div className="card"><div className="muted">Completed</div><h3>{stats.completed}</h3></div>
      </div>

      <div className="card">
        <div className="row" style={{ gap: "0.5rem", flexWrap: "wrap" }}>
          {["pending", "in_progress", "completed", "all"].map((f) => (
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

      {!error && hrTasks.length === 0 && (
        <div className="card">
          <div className="muted">No tasks assigned to you yet.</div>
        </div>
      )}

      {!error && hrTasks.length > 0 && filtered.length === 0 && (
        <div className="card">
          <div className="muted">No tasks found for this filter.</div>
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