export default function TaskCard({ task, role, onStart, onComplete, onReset }) {
  const statusColor = {
    pending: "#f59e0b",
    in_progress: "#3b82f6",
    completed: "#10b981",
  }[task.status] || "#888";

  return (
    <div className="card" style={{ borderLeft: `4px solid ${statusColor}` }}>
      <div className="row" style={{ justifyContent: "space-between", alignItems: "flex-start" }}>
        <strong style={{ fontSize: "1rem" }}>{task.title}</strong>
        <span className={`badge ${task.status}`} style={{ whiteSpace: "nowrap" }}>
          {task.status.replace("_", " ")}
        </span>
      </div>

      {task.description && (
        <p className="muted" style={{ margin: "0.4rem 0", fontSize: "0.9rem" }}>
          {task.description}
        </p>
      )}

      <div className="row" style={{ justifyContent: "space-between", marginTop: "0.5rem" }}>
        <span className={`badge ${task.priority}`}>{task.priority}</span>
        <span className="muted" style={{ fontSize: "0.85rem" }}>
          {role === "hr" ? `By: ${task.employer_name || "—"}` : `HR: ${task.assignee_name || "—"}`}
        </span>
      </div>

      {task.started_at && (
        <div className="muted" style={{ fontSize: "0.8rem", marginTop: "0.3rem" }}>
          Started: {new Date(task.started_at).toLocaleString()}
        </div>
      )}
      {task.completed_at && (
        <div className="muted" style={{ fontSize: "0.8rem" }}>
          Completed: {new Date(task.completed_at).toLocaleString()}
        </div>
      )}

      {/* HR buttons: Start / Complete */}
      {role === "hr" && (
        <div className="row" style={{ marginTop: "0.75rem", gap: "0.5rem" }}>
          {task.status === "pending" && onStart && (
            <button onClick={() => onStart(task.id)}>
              ▶ Start
            </button>
          )}
          {task.status === "in_progress" && onComplete && (
            <button onClick={() => onComplete(task.id)}>
              ✓ Complete
            </button>
          )}
          {task.status === "completed" && (
            <span className="muted">✓ Done</span>
          )}
        </div>
      )}

      {/* Employer button: Reset to pending */}
      {role === "employer" && task.status !== "pending" && onReset && (
        <div style={{ marginTop: "0.75rem" }}>
          <button className="secondary" onClick={() => onReset(task.id)}>
            ↺ Reset to Pending
          </button>
        </div>
      )}
    </div>
  );
}
