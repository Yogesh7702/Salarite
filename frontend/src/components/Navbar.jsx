import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function Navbar() {
  const { user, logout } = useAuth();
  const nav = useNavigate();

  const handleLogout = () => { logout(); nav("/login"); };

  return (
    <header className="navbar">
      <div style={{ fontWeight: 700, color: "#4f46e5" }}>Salarite</div>
      <nav>
        <NavLink to="/" end className={({isActive}) => isActive ? "active" : ""}>Home</NavLink>

        {/* Role-aware buttons */}
        {user?.role === "employer" && (
          <NavLink to="/employer" className={({isActive}) => isActive ? "active" : ""}>
            Employer Dashboard
          </NavLink>
        )}
        {user?.role === "hr" && (
          <NavLink to="/hr" className={({isActive}) => isActive ? "active" : ""}>
            HR Dashboard
          </NavLink>
        )}

        {user && (
          <NavLink to="/interviews" className={({isActive}) => isActive ? "active" : ""}>
            Interviews
          </NavLink>
        )}
      </nav>
      <div className="row">
        {user ? (
          <>
            <span className="muted">{user.name} ({user.role})</span>
            <button className="secondary" onClick={handleLogout}>Logout</button>
          </>
        ) : (
          <>
            <NavLink to="/login"><button className="secondary">Login</button></NavLink>
            <NavLink to="/signup"><button>Sign Up</button></NavLink>
          </>
        )}
      </div>
    </header>
  );
}
