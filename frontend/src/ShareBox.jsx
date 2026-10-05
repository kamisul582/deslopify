import { useState } from "react";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

function rememberDeleteKey(id, key) {
  try {
    const all = JSON.parse(localStorage.getItem("deslopify_delete_keys") || "{}");
    all[id] = key;
    localStorage.setItem("deslopify_delete_keys", JSON.stringify(all));
  } catch {
    // storage unavailable: the user still sees the key once
  }
}

export default function ShareBox({ share }) {
  const [stage, setStage] = useState("idle"); // idle | confirm | creating | done
  const [ack, setAck] = useState(false);
  const [created, setCreated] = useState(null);
  const [error, setError] = useState(null);
  const [copied, setCopied] = useState(false);

  async function create() {
    setStage("creating");
    setError(null);
    try {
      const res = await fetch(`${API_URL}/share`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(share),
      });
      const data = await res.json().catch(() => null);
      if (!res.ok) {
        setError(data?.detail?.message || "Could not create the link.");
        setStage("confirm");
        return;
      }
      rememberDeleteKey(data.id, data.delete_key);
      setCreated({ ...data, url: `${window.location.origin}${data.path}` });
      setStage("done");
    } catch {
      setError("Could not reach the server. Please try again.");
      setStage("confirm");
    }
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(created.url);
      setCopied(true);
    } catch {
      // user can still select the text
    }
  }

  if (stage === "idle") {
    return (
      <div className="share-box">
        <button className="demo-btn" onClick={() => setStage("confirm")}>
          Create share link
        </button>
      </div>
    );
  }

  if (stage === "done") {
    return (
      <div className="share-box">
        <p>
          <strong>Link created.</strong> It is public for 30 days. Share it as an estimate, not as
          proof.
        </p>
        <div className="share-link">
          <input readOnly value={created.url} onFocus={(e) => e.target.select()} />
          <button onClick={copy}>{copied ? "Copied" : "Copy"}</button>
        </div>
        <p className="share-note">
          Delete key (shown once, save it if you want to delete from another device):{" "}
          <code>{created.delete_key}</code>. In this browser you can delete it from the link page.
        </p>
      </div>
    );
  }

  return (
    <div className="share-box">
      <p>
        Creating a link makes this result <strong>public</strong>: anyone with the link can see
        the verdict, the estimate and the short quotes from the text, for 30 days. Your full text
        is not stored. You can delete the link at any time.
      </p>
      <label className="share-ack">
        <input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} />
        <span>
          I understand this is an unreliable automated estimate, not proof, and I won&apos;t
          present it as evidence of who wrote something.
        </span>
      </label>
      {error && <p className="injection-note">{error}</p>}
      <div className="share-actions">
        <button onClick={create} disabled={!ack || stage === "creating"}>
          {stage === "creating" ? "Creating…" : "Create link"}
        </button>
        <button className="demo-btn" onClick={() => setStage("idle")}>
          Cancel
        </button>
      </div>
    </div>
  );
}
