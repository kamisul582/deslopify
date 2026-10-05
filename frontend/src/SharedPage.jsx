import { useEffect, useState } from "react";
import AgendaView from "./AgendaView";
import "./App.css";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

const HEADINGS = {
  ai: "Shows some signs often linked to AI-written text",
  uncertain: "Inconclusive",
  human: "No strong signs of AI writing",
};

const fmt = (unix) => new Date(unix * 1000).toLocaleDateString(undefined, { dateStyle: "medium" });

function deleteKeyFor(id) {
  try {
    return JSON.parse(localStorage.getItem("deslopify_delete_keys") || "{}")[id] || null;
  } catch {
    return null;
  }
}

export default function SharedPage({ id }) {
  const [state, setState] = useState({ status: "loading" });
  const [note, setNote] = useState(null);

  useEffect(() => {
    document.title = "Shared analysis (automated estimate) · Deslopify";
    const meta = document.createElement("meta");
    meta.name = "robots";
    meta.content = "noindex, nofollow";
    document.head.appendChild(meta);
    return () => meta.remove();
  }, []);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API_URL}/r/${id}`)
      .then(async (res) => {
        if (cancelled) return;
        if (res.status === 404) return setState({ status: "gone" });
        if (!res.ok) return setState({ status: "error" });
        setState({ status: "ok", data: await res.json() });
      })
      .catch(() => !cancelled && setState({ status: "error" }));
    return () => {
      cancelled = true;
    };
  }, [id]);

  async function report() {
    const res = await fetch(`${API_URL}/r/${id}/report`, { method: "POST" });
    const data = await res.json().catch(() => null);
    setNote(res.ok ? data.message : "Could not send the report. Please try again.");
  }

  async function remove() {
    const res = await fetch(`${API_URL}/r/${id}`, {
      method: "DELETE",
      headers: { "X-Delete-Key": deleteKeyFor(id) },
    });
    if (res.ok) setState({ status: "gone" });
    else setNote("Could not delete this result.");
  }

  const { status, data } = state;

  return (
    <div className="app">
      <header>
        <h1>
          <a href="/" className="home-link">Deslopify</a>
        </h1>
      </header>

      <div className="estimate-banner" role="note">
        <strong>This is an automated estimate, not a finding and not proof.</strong> An
        experimental tool produced it. It cannot tell who wrote a text or whether AI was used, and
        tools like it are often wrong. Wrongly calling someone&apos;s writing &ldquo;AI-generated&rdquo;
        can harm them. Please don&apos;t use this page as evidence against anyone.
      </div>

      <main>
        {status === "loading" && <p className="muted">Loading…</p>}
        {status === "gone" && (
          <div className="result-box">
            <h2>This result isn&apos;t available</h2>
            <p>It doesn&apos;t exist, has expired, or was removed.</p>
          </div>
        )}
        {status === "error" && <div className="error-box">Could not load this result. Please try again later.</div>}

        {status === "ok" && (
          <section className="result-box uncertain-neutral">
            <h2>{HEADINGS[data.record.verdict]}</h2>
            <p className="confidence">
              The tool&apos;s estimate: {Math.round(data.record.ai_probability * 100)}%. This is a
              rough score, not a measured probability.
            </p>
            {data.record.injection_detected && (
              <p className="injection-note">
                The analysed text contained instructions aimed at an AI analyzer. They were ignored.
              </p>
            )}
            {data.record.signals.length > 0 && (
              <div className="signals-row">
                {data.record.signals.map((s, i) => (
                  <span className="signal-tag" key={i}>{s}</span>
                ))}
              </div>
            )}
            {data.record.agenda && data.schema_version === 2 && (
              <AgendaView agenda={data.record.agenda} droppedClaims={data.record.dropped_claims} />
            )}
            {data.record.agenda && data.schema_version !== 2 && (
              <p className="verification-note">
                This result was created with an older version of the tool and its details can no
                longer be displayed.
              </p>
            )}
            <p className="disclaimer">
              Created {fmt(data.created_at)} by whoever ran the analysis; expires {fmt(data.expires_at)}.
              The author of the analysed text had no part in it. Model {data.record.model}, prompts{" "}
              {Object.entries(data.record.prompt_versions).map(([k, v]) => `${k} ${v}`).join(", ")}.
            </p>
            <div className="share-actions">
              <button className="demo-btn" onClick={report}>Report or request removal</button>
              {deleteKeyFor(id) && (
                <button className="demo-btn" onClick={remove}>Delete this result</button>
              )}
              <a href="/" className="demo-btn link-btn">Analyze a text yourself</a>
            </div>
            {note && <p className="verification-note">{note}</p>}
          </section>
        )}
      </main>
    </div>
  );
}
