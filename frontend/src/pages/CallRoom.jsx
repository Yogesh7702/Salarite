import { useEffect, useRef, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { api, socket } from "../api/client";
import { useAuth } from "../context/AuthContext";

const ICE = {
  iceServers: [{ urls: "stun:stun.l.google.com:19302" }],
};

export default function CallRoom() {
  const { roomId } = useParams();
  const { user } = useAuth();
  const nav = useNavigate();

  const localRef = useRef(null);
  const remoteRef = useRef(null);
  const pcRef = useRef(null);
  const localStreamRef = useRef(null);

  const [connected, setConnected] = useState(false);
  const [muted, setMuted] = useState(false);
  const [camOff, setCamOff] = useState(false);
  const [chat, setChat] = useState([]);
  const [msg, setMsg] = useState("");
  const [status, setStatus] = useState("Initializing...");

  useEffect(() => {
    let mounted = true;

    const start = async () => {
      try {
        setStatus("Requesting camera/mic...");

        const stream = await navigator.mediaDevices.getUserMedia({
          video: true,
          audio: true,
        });

        if (!mounted) {
          stream.getTracks().forEach((t) => t.stop());
          return;
        }

        localStreamRef.current = stream;

        if (localRef.current) {
          localRef.current.srcObject = stream;
        }

        const pc = new RTCPeerConnection(ICE);
        pcRef.current = pc;

        stream.getTracks().forEach((track) => {
          pc.addTrack(track, stream);
        });

        pc.ontrack = (e) => {
          if (remoteRef.current) {
            remoteRef.current.srcObject = e.streams[0];
          }
          setConnected(true);
          setStatus("Connected");
        };

        pc.onicecandidate = (e) => {
          if (e.candidate) {
            socket.emit("webrtc_ice", {
              room: roomId,
              candidate: e.candidate,
            });
          }
        };

        socket.emit("join_room", {
          room: roomId,
          user: user?.name || user?.email || "Guest",
          token: localStorage.getItem("token"),
        });

        setStatus("Waiting for the other participant...");

        socket.on("peer_joined", async () => {
          try {
            setStatus("Peer joined - sending offer...");
            const offer = await pc.createOffer();
            await pc.setLocalDescription(offer);

            socket.emit("webrtc_offer", {
              room: roomId,
              sdp: offer,
            });
          } catch (err) {
            setStatus("Offer error: " + err.message);
          }
        });

        socket.on("webrtc_offer", async (data) => {
          try {
            setStatus("Receiving offer...");
            await pc.setRemoteDescription(new RTCSessionDescription(data.sdp));

            const answer = await pc.createAnswer();
            await pc.setLocalDescription(answer);

            socket.emit("webrtc_answer", {
              room: roomId,
              sdp: answer,
            });
          } catch (err) {
            setStatus("Answer error: " + err.message);
          }
        });

        socket.on("webrtc_answer", async (data) => {
          try {
            await pc.setRemoteDescription(new RTCSessionDescription(data.sdp));
          } catch (err) {
            setStatus("Remote description error: " + err.message);
          }
        });

        socket.on("webrtc_ice", async (data) => {
          try {
            await pc.addIceCandidate(new RTCIceCandidate(data.candidate));
          } catch (err) {
            console.warn("ICE error", err);
          }
        });

        socket.on("peer_left", () => {
          setStatus("Peer left the call");
          setConnected(false);
          if (remoteRef.current) {
            remoteRef.current.srcObject = null;
          }
        });

        socket.on("chat_message", (data) => {
          setChat((prev) => [...prev, data]);
        });

        socket.on("room_error", (data) => {
          setStatus(data?.error || "Room access denied");
          nav("/interviews", { replace: true });
        });
      } catch (err) {
        setStatus("Error: " + err.message);
      }
    };

    const checkAccessAndStart = async () => {
      try {
        setStatus("Checking access...");
        await api.get(`/api/interviews/${roomId}/access`);

        if (!mounted) return;

        await start();
      } catch (err) {
        if (!mounted) return;

        setStatus("Access denied");
        nav("/interviews", { replace: true });
      }
    };

    checkAccessAndStart();

    return () => {
      mounted = false;

      socket.emit("leave_room", { room: roomId });

      socket.off("peer_joined");
      socket.off("webrtc_offer");
      socket.off("webrtc_answer");
      socket.off("webrtc_ice");
      socket.off("peer_left");
      socket.off("chat_message");
      socket.off("room_error");

      if (pcRef.current) {
        pcRef.current.close();
      }

      if (localStreamRef.current) {
        localStreamRef.current.getTracks().forEach((t) => t.stop());
      }
    };
  }, [roomId, user?.name, user?.email, nav]);

  const toggleMute = () => {
    const stream = localStreamRef.current;
    if (!stream) return;

    stream.getAudioTracks().forEach((track) => {
      track.enabled = muted;
    });

    setMuted(!muted);
  };

  const toggleCam = () => {
    const stream = localStreamRef.current;
    if (!stream) return;

    stream.getVideoTracks().forEach((track) => {
      track.enabled = camOff;
    });

    setCamOff(!camOff);
  };

  const leave = () => {
    nav("/interviews");
  };

  const sendMsg = (e) => {
    e.preventDefault();

    if (!msg.trim()) return;

    const data = {
      room: roomId,
      user: user?.name || user?.email || "Me",
      text: msg,
      ts: Date.now(),
    };

    socket.emit("chat_message", data);
    setChat((prev) => [...prev, { ...data, mine: true }]);
    setMsg("");
  };

  return (
    <div className="container">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h2>Call Room</h2>
        <span className="muted">
          Room: {roomId} · {status}
        </span>
      </div>

      <div className="video-grid">
        <div>
          <video ref={localRef} autoPlay playsInline muted />
          <div className="muted" style={{ textAlign: "center", marginTop: 4 }}>
            You ({user?.name || user?.email})
          </div>
        </div>

        <div>
          <video ref={remoteRef} autoPlay playsInline />
          <div className="muted" style={{ textAlign: "center", marginTop: 4 }}>
            {connected ? "Remote peer" : "Waiting..."}
          </div>
        </div>
      </div>

      <div className="card">
        <div className="row">
          <button className="secondary" onClick={toggleMute}>
            {muted ? "Unmute" : "Mute"}
          </button>

          <button className="secondary" onClick={toggleCam}>
            {camOff ? "Camera On" : "Camera Off"}
          </button>

          <button className="danger" onClick={leave}>
            Leave Call
          </button>
        </div>
      </div>

      <div className="chat-box">
        <strong>Chat</strong>

        <div className="chat-msgs">
          {chat.length === 0 && (
            <div className="muted">No messages yet.</div>
          )}

          {chat.map((m, i) => (
            <div key={i} className="chat-msg">
              <b>{m.mine ? "You" : m.user}:</b> {m.text}
            </div>
          ))}
        </div>

        <form onSubmit={sendMsg} className="row">
          <input
            value={msg}
            onChange={(e) => setMsg(e.target.value)}
            placeholder="Type a message..."
          />
          <button type="submit">Send</button>
        </form>
      </div>
    </div>
  );
}