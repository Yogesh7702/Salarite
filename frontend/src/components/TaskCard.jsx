export default function TaskCard({ task, onStart, onComplete, role }) {
  return (
    <div className="card">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <strong>{task.title}</strong>
        <span className={`badge ${task.status}`}>{task.status.replace("_"," ")}</span>
      </div>
      {task.description && <p className="muted" style={{ margin: "0.4rem 0" }}>{task.description}</p>}
      <div className="row" style={{ justifyContent: "space-between", marginTop: "0.5rem" }}>
        <span className={`badge ${task.priority}`}>{task.priority}</span>
        <span className="muted">By: {task.employer_name || "—"}</span>
      </div>
      {role === "hr" && (
        <div className="row" style={{ marginTop: "0.75rem" }}>
          {task.status === "pending" && (
            <button onClick={() => onStart(task.id)}>Start</button>
          )}
          {task.status === "in_progress" && (
            <button className="success" onClick={() => onComplete(task.id)}>Complete</button>
          )}
        </div>
      )}
    </div>
  );
}
