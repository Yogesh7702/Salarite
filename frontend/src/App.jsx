import { Routes, Route } from "react-router-dom";
import Navbar from "./components/Navbar";
import ProtectedRoute from "./components/ProtectedRoute";
import Home from "./pages/Home";
import Login from "./pages/Login";
import Signup from "./pages/Signup";
import EmployerDashboard from "./pages/EmployerDashboard";
import HRDashboard from "./pages/HRDashboard";
import Interviews from "./pages/Interviews";
import CallRoom from "./pages/CallRoom";

export default function App() {
  return (
    <>
      <Navbar />
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/login" element={<Login />} />
        <Route path="/signup" element={<Signup />} />

        <Route
          path="/employer"
          element={
            <ProtectedRoute roles={["employer"]}>
              <EmployerDashboard />
            </ProtectedRoute>
          }
        />

        <Route
          path="/hr"
          element={
            <ProtectedRoute roles={["hr"]}>
              <HRDashboard />
            </ProtectedRoute>
          }
        />

        <Route
          path="/interviews"
          element={
            <ProtectedRoute roles={["employer", "hr", "candidate"]}>
              <Interviews />
            </ProtectedRoute>
          }
        />

        <Route
          path="/call/:roomId"
          element={
            <ProtectedRoute roles={["employer", "hr", "candidate"]}>
              <CallRoom />
            </ProtectedRoute>
          }
        />

        <Route
          path="*"
          element={
            <div className="container">
              <h2>404 — Not Found</h2>
            </div>
          }
        />
      </Routes>
    </>
  );
}