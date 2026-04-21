import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, socket } from "../api/client";
import { useAuth } from "../context/AuthContext";

export default function Interviews() {
  const { user } = useAuth();
  const [items, setItems] = useState([]);
  const [form, setForm] = useState({
    candidate_name: "",
    candidate_email: "",
    scheduled_at: new Date().toISOString().slice(0, 16),
    mode: "video",
    notes: "",
  });

  const load = async () => {
    const { data } = await api.get("/api/interviews");
    setItems(data);
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

    if (!email) {
      alert("Candidate email is required");
      return;
    }

    if (!emailPattern.test(email)) {
      alert("Enter a valid email address");
      return;
    }

    await api.post("/api/interviews", {
      ...form,
      candidate_email: email,
    });

    setForm({
      ...form,
      candidate_name: "",
      candidate_email: "",
      notes: "",
    });
  };

   const handleJoin = (roomId) => {
    if (!roomId) {
      alert("Room ID missing");
      return;
    }

    console.log("Joining room:", roomId);
    navigate(`/call/${roomId}`);
  };

  return (
    <div className="container">
      <h2>Interviews</h2>

      {/* HR only: Schedule form */}
      {user?.role === "hr" && (
        <div className="card">
          <h3>Schedule Interview</h3>
          <form onSubmit={create} className="grid grid-2">
            <input
              placeholder="Candidate name"
              value={form.candidate_name}
              onChange={(e) =>
                setForm({ ...form, candidate_name: e.target.value })
              }
            />

            <input
              type="email"
              placeholder="Candidate email"
              value={form.candidate_email}
              onChange={(e) =>
                setForm({ ...form, candidate_email: e.target.value })
              }
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

      {/* All users: Upcoming interviews */}
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

            <Link to={`/call/${i.room_id}`}>
              <button style={{ marginTop: "0.6rem" }} onClick={() => handleJoin(i.room_id)}>
                Join Call Room
              </button>
            </Link>
          </div>
        ))}
      </div>
    </div>
  );
}