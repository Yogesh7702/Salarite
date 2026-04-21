import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function Home() {
  const { user } = useAuth();
  return (
    <div className="container">
      <div className="card" style={{ background: "linear-gradient(135deg, #4f46e5, #7c3aed)", color: "white" }}>
        <h1 style={{ margin: 0 }}>Salarite Virtual HR + ATS</h1>
        <p style={{ opacity: 0.9 }}>
          Assign HR tasks, monitor live progress, and conduct video interviews — all in one place.
        </p>
      </div>

      {!user && (
        <div className="card">
          <h3>Get Started</h3>
          <p className="muted">Sign in or create an account to use the dashboard.</p>
          <div className="row">
            <Link to="/login"><button>Login</button></Link>
            <Link to="/signup"><button className="secondary">Sign Up</button></Link>
          </div>
        </div>
      )}

      {user && (
        <div className="grid grid-2">
          {user.role === "employer" && (
            <div className="card">
              <h3>Employer Dashboard</h3>
              <p className="muted">Create tasks and monitor HR progress live.</p>
              <Link to="/employer"><button>Open</button></Link>
            </div>
          )}
          {user.role === "hr" && (
            <div className="card">
              <h3>Virtual HR Workspace</h3>
              <p className="muted">Pick up tasks and update progress.</p>
              <Link to="/hr"><button>Open</button></Link>
            </div>
          )}
          <div className="card">
            <h3>Interviews</h3>
            <p className="muted">Schedule and join video interviews.</p>
            <Link to="/interviews"><button>Open</button></Link>
          </div>
        </div>
      )}
    </div>
  );
}
