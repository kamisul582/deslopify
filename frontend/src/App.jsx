import { useState } from "react";
import "./App.css";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

const DEMO_TEXT = `The #1 mistake people make with their morning routine?

They optimize for discipline instead of identity.

Here's what nobody tells you about high performers:

They don't wake up at 5am because they're disciplined.
They wake up at 5am because they've decided who they are.

I spent 3 years studying the routines of CEOs, athletes, and Navy SEALs.
The pattern was clear.

Discipline is a story you tell yourself after the habit is already formed.
Identity is what builds the habit in the first place.

So before you set another alarm, ask yourself:
Who is the person I'm trying to become?

Not what do I want to achieve.
Who do I want to BE.

Because when your habits match your identity, discipline becomes irrelevant.

The alarm goes off.
You get up.
Not because you have to.
Because that's what people like you do.

Start with identity. Everything else follows.

Save this. You'll need it on the hard days.

#MorningRoutine #Mindset #PersonalDevelopment #Success #Discipline #GrowthMindset #Productivity #Leadership #Motivation #SelfImprovement`;

export default function App() {
  const [text, setText] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  function loadDemo() {
    setText(DEMO_TEXT);
    setResult(null);
    setError(null);
  }

  async function handleAnalyze() {
    setLoading(true);
    setResult(null);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.detail?.message || "Something went wrong.");
      } else {
        setResult(data);
      }
    } catch {
      setError("Could not reach the server. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app">
      <header>
        <h1>Deslopify</h1>
        <p className="tagline">
          AI detectors tell you <em>if</em> text was AI-generated.<br />
          Deslopify tells you <em>why</em> — what the author actually wanted.
        </p>
      </header>

      <main>
        <section className="input-section">
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Paste a social media post, article, or any text you suspect was AI-generated…"
            rows={10}
          />
          <div className="input-meta">
            <button className="demo-btn" onClick={loadDemo}>
              Try a demo
            </button>
            <div className="input-actions">
              <span className="char-count">{text.length.toLocaleString()} chars</span>
              <button
                onClick={handleAnalyze}
                disabled={loading || text.trim().length < 50}
              >
                {loading ? "Analyzing…" : "Analyze"}
              </button>
            </div>
          </div>
        </section>

        {error && <div className="error-box">{error}</div>}

        {result && <Results result={result} />}

        {/* AdSense placeholder — replace data-ad-* attrs with real values from AdSense dashboard */}
        <div className="ad-placeholder" aria-hidden="true">
          Advertisement
        </div>
      </main>

      <footer>
        <p>
          This tool uses AI to analyze AI. It can be wrong.{" "}
          <a
            href="https://ko-fi.com/"
            target="_blank"
            rel="noopener noreferrer"
          >
            ☕ Support this tool
          </a>
        </p>
      </footer>
    </div>
  );
}

function Results({ result }) {
  if (!result.is_ai) {
    return (
      <section className="result-box not-ai">
        <h2>Probably not AI-generated</h2>
        <p className="confidence">
          Confidence: {Math.round((1 - result.confidence) * 100)}% human
        </p>
        <p>{result.message}</p>
        {result.signals?.length > 0 && (
          <ul className="signals">
            {result.signals.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ul>
        )}
        {result.remaining_today !== undefined && (
          <p className="remaining">
            {result.remaining_today} free analyses left today
          </p>
        )}
      </section>
    );
  }

  const { agenda } = result;

  return (
    <section className="result-box is-ai">
      <div className="result-header">
        <h2>AI-generated</h2>
        <span className="confidence-badge">
          {Math.round(result.confidence * 100)}% confidence
        </span>
      </div>

      {result.signals?.length > 0 && (
        <div className="signals-row">
          {result.signals.map((s, i) => (
            <span className="signal-tag" key={i}>{s}</span>
          ))}
        </div>
      )}

      <div className="agenda">
        <h3>The author&apos;s agenda</h3>
        <p className="summary">{agenda.summary}</p>

        <table className="agenda-table">
          <tbody>
            <tr>
              <th>Primary goal</th>
              <td>{agenda.primary_goal}</td>
            </tr>
            <tr>
              <th>Content type</th>
              <td>{agenda.content_type}</td>
            </tr>
            <tr>
              <th>Target platform</th>
              <td>{agenda.target_platform}</td>
            </tr>
            <tr>
              <th>Target audience</th>
              <td>{agenda.target_audience}</td>
            </tr>
            <tr>
              <th>Probable CTA</th>
              <td>{agenda.probable_cta}</td>
            </tr>
          </tbody>
        </table>

        {agenda.persuasion_tactics?.length > 0 && (
          <div className="tactics">
            <h4>Persuasion tactics</h4>
            <ul>
              {agenda.persuasion_tactics.map((t, i) => (
                <li key={i}>{t}</li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {result.remaining_today !== undefined && (
        <p className="remaining">
          {result.remaining_today} free analyses left today
        </p>
      )}
    </section>
  );
}
