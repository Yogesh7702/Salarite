import { useEffect, useState, useCallback } from "react";
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
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setError("");

      const [tasksRes, activityRes] = await Promise.all([
        api.get("/api/tasks"),
        api.get("/api/activities"),
      ]);

      setTasks(Array.isArray(tasksRes.data) ? tasksRes.data : []);
      setActivities(Array.isArray(activityRes.data) ? activityRes.data : []);
    } catch (err) {
      console.error("Employer dashboard load failed:", err);
      setError(err?.response?.data?.error || "Failed to load dashboard");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    socket.on("tasks_changed", load);
    socket.on("activity_new", load);

    return () => {
      socket.off("tasks_changed", load);
      socket.off("activity_new", load);
    };
  }, [load]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm((prev) => ({
      ...prev,
      [name]: value,
    }));
  };

  const createTask = async (e) => {
    e.preventDefault();
    setError("");
    setSuccess("");

    if (!form.title.trim()) {
      setError("Title is required");
      return;
    }

    if (!form.assigned_hr_email.trim()) {
      setError("Assignee required");
      return;
    }

    try {
      setCreating(true);

      const payload = {
        title: form.title.trim(),
        description: form.description.trim(),
        priority: form.priority,
        assigned_hr_email: form.assigned_hr_email.trim().toLowerCase(),
      };

      console.log("CREATE TASK PAYLOAD:", payload);

      await api.post("/api/tasks", payload);

      setSuccess("Task assigned successfully");
      setForm({
        title: "",
        description: "",
        priority: "medium",
        assigned_hr_email: "",
      });

      load();
    } catch (err) {
      console.error("Create task failed:", err?.response?.data || err.message);
      setError(err?.response?.data?.error || "Failed to create task");
    } finally {
      setCreating(false);
    }
  };

  const myTasks = tasks.filter((t) => Number(t.employer_id) === Number(user?.id));

  const stats = {
    total: myTasks.length,
    pending: myTasks.filter((t) => t.status === "pending").length,
    in_progress: myTasks.filter((t) => t.status === "in_progress").length,
    completed: myTasks.filter((t) => t.status === "completed").length,
  };

  if (loading) {
    return (
      <div className="container">
        <h2>Employer Dashboard</h2>
        <div className="muted">Loading dashboard...</div>
      </div>
    );
  }

  return (
    <div className="container">
      <h2>Employer Dashboard</h2>

      {error && <div className="error">{error}</div>}
      {success && <div className="success">{success}</div>}

      <div className="grid grid-4">
        <div className="card"><div className="muted">Total</div><h3>{stats.total}</h3></div>
        <div className="card"><div className="muted">Pending</div><h3>{stats.pending}</h3></div>
        <div className="card"><div className="muted">In Progress</div><h3>{stats.in_progress}</h3></div>
        <div className="card"><div className="muted">Completed</div><h3>{stats.completed}</h3></div>
      </div>

      <div className="card">
        <h3>Create Task</h3>

        <form onSubmit={createTask}>
          <div style={{ marginBottom: "12px" }}>
            <label>Title</label>
            <input
              type="text"
              name="title"
              placeholder="Enter task title"
              value={form.title}
              onChange={handleChange}
              style={{ width: "100%" }}
            />
          </div>

          <div style={{ marginBottom: "12px" }}>
            <label>Description</label>
            <textarea
              name="description"
              placeholder="Enter description"
              rows="4"
              value={form.description}
              onChange={handleChange}
              style={{ width: "100%" }}
            />
          </div>

          <div style={{ marginBottom: "12px" }}>
            <label>Assign to HR Email</label>
            <input
              type="email"
              name="assigned_hr_email"
              placeholder="hr@example.com"
              value={form.assigned_hr_email}
              onChange={handleChange}
              style={{ width: "100%" }}
            />
          </div>

          <div style={{ marginBottom: "12px" }}>
            <label>Priority</label>
            <select
              name="priority"
              value={form.priority}
              onChange={handleChange}
              style={{ width: "100%" }}
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
        <h3>My Tasks</h3>
        {myTasks.length === 0 ? (
          <div className="muted">No tasks yet.</div>
        ) : (
          myTasks.map((t) => <TaskCard key={t.id} task={t} role="employer" />)
        )}
      </div>

      <div className="card">
        <h3>Activity Feed</h3>
        {activities.length === 0 ? (
          <div className="muted">No activity yet.</div>
        ) : (
          activities.map((a) => (
            <div key={a.id} style={{ padding: "8px 0", borderBottom: "1px solid #eee" }}>
              <div>{a.message}</div>
              <div className="muted" style={{ fontSize: "12px" }}>
                {a.created_at}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}