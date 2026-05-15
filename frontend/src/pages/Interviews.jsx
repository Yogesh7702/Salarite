// import { useEffect, useState } from "react";
// import { useNavigate } from "react-router-dom";
// import { api, socket } from "../api/client";
// import { useAuth } from "../context/AuthContext";

// export default function Interviews() {
//   const { user } = useAuth();
//   const navigate = useNavigate();
//   const [items, setItems] = useState([]);
//   const [loading, setLoading] = useState(true);
//   const [creating, setCreating] = useState(false);
//   const [err, setErr] = useState("");
//   const [success, setSuccess] = useState("");
//   const [form, setForm] = useState({
//     candidate_name: "",
//     candidate_email: "",
//     scheduled_at: new Date(Date.now() + 3600000).toISOString().slice(0, 16),
//     mode: "video",
//     notes: "",
//   });

//   const load = async () => {
//     try {
//       const { data } = await api.get("/api/interviews");
//       setItems(Array.isArray(data) ? data : []);
//     } catch (e) {
//       console.error(e);
//     } finally {
//       setLoading(false);
//     }
//   };

//   useEffect(() => {
//     load();
//     if (!socket.connected) socket.connect();
//     socket.on("interviews_changed", load);
//     return () => socket.off("interviews_changed", load);
//   }, []);

//   const create = async (e) => {
//     e.preventDefault();
//     setErr(""); setSuccess("");
//     const email = form.candidate_email?.trim().toLowerCase();
//     if (!email) { setErr("Candidate email is required"); return; }
//     if (!/^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$/.test(email)) {
//       setErr("Enter a valid email address"); return;
//     }
//     try {
//       setCreating(true);
//       await api.post("/api/interviews", { ...form, candidate_email: email });
//       setSuccess("Interview scheduled!");
//       setForm(p => ({ ...p, candidate_name: "", candidate_email: "", notes: "" }));
//       load();
//     } catch (e) {
//       setErr(e.response?.data?.detail || e.response?.data?.error || "Failed to schedule interview");
//     } finally {
//       setCreating(false);
//     }
//   };

//   if (loading) return <div className="container"><div className="muted">Loading...</div></div>;

//   return (
//     <div className="container">
//       <h2>Interviews</h2>

//       {user?.role === "hr" && (
//         <div className="card">
//           <h3>Schedule Interview</h3>
//           {err && <div className="error" style={{ marginBottom: "12px" }}>{err}</div>}
//           {success && <div className="success" style={{ marginBottom: "12px" }}>{success}</div>}

//           <form onSubmit={create}>
//             <div style={{ marginBottom: "12px" }}>
//               <label className="muted">Candidate Name</label>
//               <input placeholder="Name (optional)" value={form.candidate_name}
//                 onChange={(e) => setForm(p => ({ ...p, candidate_name: e.target.value }))} />
//             </div>
//             <div style={{ marginBottom: "12px" }}>
//               <label className="muted">Candidate Email *</label>
//               <input type="email" required placeholder="candidate@example.com" value={form.candidate_email}
//                 onChange={(e) => setForm(p => ({ ...p, candidate_email: e.target.value }))} />
//             </div>
//             <div style={{ marginBottom: "12px" }}>
//               <label className="muted">Date & Time *</label>
//               <input type="datetime-local" required value={form.scheduled_at}
//                 onChange={(e) => setForm(p => ({ ...p, scheduled_at: e.target.value }))} />
//             </div>
//             <div style={{ marginBottom: "12px" }}>
//               <label className="muted">Mode</label>
//               <select value={form.mode} onChange={(e) => setForm(p => ({ ...p, mode: e.target.value }))}>
//                 <option value="video">Video</option>
//                 <option value="voice">Voice</option>
//                 <option value="chat">Chat</option>
//               </select>
//             </div>
//             <div style={{ marginBottom: "12px" }}>
//               <label className="muted">Notes</label>
//               <textarea placeholder="Any notes..." rows={2} value={form.notes}
//                 onChange={(e) => setForm(p => ({ ...p, notes: e.target.value }))} />
//             </div>
//             <button type="submit" disabled={creating}>
//               {creating ? "Scheduling..." : "Schedule Interview"}
//             </button>
//           </form>
//         </div>
//       )}

//       <div className="card">
//         <h3>{user?.role === "hr" ? "My Scheduled Interviews" : "Your Upcoming Interviews"}</h3>

//         {items.length === 0 ? (
//           <div className="muted">No interviews yet.</div>
//         ) : (
//           <div className="grid grid-2">
//             {items.map((i) => (
//               <div key={i.id} className="card">
//                 <div className="row" style={{ justifyContent: "space-between" }}>
//                   <strong>{i.candidate_name || i.candidate_email}</strong>
//                   <span className="badge">{i.mode}</span>
//                 </div>
//                 {i.candidate_email && (
//                   <div className="muted" style={{ margin: "0.25rem 0" }}>{i.candidate_email}</div>
//                 )}
//                 <div className="muted" style={{ margin: "0.4rem 0" }}>
//                   📅 {new Date(i.scheduled_at).toLocaleString()}
//                 </div>
//                 {i.notes && <div className="muted">📝 {i.notes}</div>}
//                 <button
//                   style={{ marginTop: "0.75rem", width: "100%" }}
//                   onClick={() => navigate(`/call/${i.room_id}`)}
//                 >
//                   Join Call Room
//                 </button>
//               </div>
//             ))}
//           </div>
//         )}
//       </div>
//     </div>
//   );
// }









import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, socket } from "../api/client";
import { useAuth } from "../context/AuthContext";

export default function Interviews() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [items, setItems] = useState([]);
  const [form, setForm] = useState({
    candidate_name: "",
    candidate_email: "",
    scheduled_at: new Date().toISOString().slice(0, 16),
    mode: "video",
    notes: "",
  });

  const load = async () => {
    try {
      const { data } = await api.get("/api/interviews");
      setItems(data);
    } catch (e) {
      console.error("Load interviews failed:", e);
    }
  };

  useEffect(() => {
    load();
    socket.on("interviews_changed", load);
    return () => socket.off("interviews_changed", load);
  }, []);

  const create = async (e) => {
    e.preventDefault();
    const email = form.candidate_email?.trim().toLowerCase();
    const emailPattern = /^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$/;

    if (!email) return alert("Candidate email is required");
    if (!emailPattern.test(email)) return alert("Enter a valid email address");

    try {
      await api.post("/api/interviews", { ...form, candidate_email: email });
      setForm({ ...form, candidate_name: "", candidate_email: "", notes: "" });
      load();
    } catch (err) {
      alert(err?.response?.data?.detail || "Failed to schedule interview");
    }
  };

  const handleJoin = (roomId) => {
    if (!roomId) return alert("Room ID missing");
    navigate(`/call/${roomId}`);
  };

  return (
    <div className="container">
      <h2>Interviews</h2>

      {user?.role === "hr" && (
        <div className="card">
          <h3>Schedule Interview</h3>
          <form onSubmit={create} className="grid grid-2">
            <input
              placeholder="Candidate name"
              value={form.candidate_name}
              onChange={(e) => setForm({ ...form, candidate_name: e.target.value })}
            />
            <input
              type="email"
              placeholder="Candidate email"
              value={form.candidate_email}
              onChange={(e) => setForm({ ...form, candidate_email: e.target.value })}
            />
            <input
              type="datetime-local"
              value={form.scheduled_at}
              onChange={(e) => setForm({ ...form, scheduled_at: e.target.value })}
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
              placeholder="Notes"
              value={form.notes}
              onChange={(e) => setForm({ ...form, notes: e.target.value })}
            />
            <button type="submit">Schedule</button>
          </form>
        </div>
      )}

      <h3>Upcoming</h3>
      {items.length === 0 && <div className="muted">No interviews yet.</div>}

      <div className="grid grid-2">
        {items.map((i) => (
          <div key={i.id} className="card">
            <div className="row" style={{ justifyContent: "space-between" }}>
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

            <button
              style={{ marginTop: "0.6rem" }}
              onClick={() => handleJoin(i.room_id)}
            >
              Join Call Room
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
