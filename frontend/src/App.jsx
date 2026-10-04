import { useState } from "react";
import "./App.css";

const MAX_CHARS = 10000;
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
      let data = null;
      try {
        data = await res.json();
      } catch {
        // proxy/gateway error pages are not JSON
      }
      if (!res.ok) {
        setError(errorMessage(res.status, data, res.headers.get("X-Request-ID")));
      } else {
        setResult(data);
      }
    } catch {
      setError("Could not reach the server. Check your connection and try again.");
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
        <p className="reliability-note" role="note">
          ⚠ AI-text detection is unreliable. Treat results as a hint, never as proof that
          someone did or did not write something.
        </p>
      </header>

      <main>
        <section className="input-section">
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            maxLength={MAX_CHARS}
            placeholder="Paste a social media post, article, or any text you suspect was AI-generated…"
            rows={10}
          />
          <div className="input-meta">
            <button className="demo-btn" onClick={loadDemo}>
              Try a demo
            </button>
            <div className="input-actions">
              <span className="char-count">
                {text.length.toLocaleString()} / {MAX_CHARS.toLocaleString()} chars
              </span>
              <button
                onClick={handleAnalyze}
                disabled={loading || text.trim().length < 50}
              >
                {loading ? "Analyzing…" : "Analyze"}
              </button>
            </div>
          </div>
        </section>

        {error && <div className="error-box" role="alert">{error}</div>}

        {result && <Results result={result} />}
      </main>

      <footer>
        <details className="privacy">
          <summary>Privacy: what happens to the text you paste</summary>
          <ul>
            <li>
              <strong>Your text is not stored by this site.</strong> It is held in memory
              only while the analysis runs. It is not written to a database or to logs.
            </li>
            <li>
              To analyze it, the text is sent to the Anthropic API, which processes it under
              Anthropic&apos;s own terms and retention policy.
            </li>
            <li>
              Stored: anonymous counters (total analyses, AI / human / unclear), and a
              per-day request counter keyed by your IP address for rate limiting, which
              expires within 24 hours. Error monitoring (Sentry) receives error details, not
              your text.
            </li>
            <li>
              Page-view statistics come from Vercel Analytics, which does not use cookies.
              Hosting providers may keep standard access logs. This site sets no cookies and
              shows no ads.
            </li>
          </ul>
        </details>
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

function errorMessage(status, data, requestId) {
  const d = data?.detail;
  const msg = typeof d === "object" && d?.message ? d.message : null;
  const ref = requestId ? ` (ref: ${requestId})` : "";
  if (msg) return msg + (status >= 500 ? ref : "");
  if (status === 413) return "That text is too large.";
  if (status >= 500) return "The service is having trouble right now. Please try again in a moment." + ref;
  return "Something went wrong.";
}

function Remaining({ n }) {
  if (n === undefined || n === null) return null;
  return <p className="remaining">{n} free analyses left today</p>;
}

function Results({ result }) {
  const pct = Math.round(result.ai_probability * 100);

  if (result.verdict !== "ai") {
    const uncertain = result.verdict === "uncertain";
    return (
      <section className={`result-box ${uncertain ? "uncertain" : "not-ai"}`}>
        <h2>{uncertain ? "Can’t tell" : "No strong signs of AI generation"}</h2>
        <p className="confidence">Estimated AI probability: {pct}%</p>
        <p>{result.message}</p>
        <Injection result={result} />
        {result.signals?.length > 0 && (
          <ul className="signals">
            {result.signals.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ul>
        )}
        <Remaining n={result.remaining_today} />
        <Disclaimer result={result} />
      </section>
    );
  }

  const { agenda } = result;

  return (
    <section className="result-box is-ai">
      <div className="result-header">
        <h2>Signs of AI generation</h2>
        <span className="confidence-badge">{pct}% estimated probability</span>
      </div>
      <Injection result={result} />

      {result.signals?.length > 0 && (
        <div className="signals-row">
          {result.signals.map((s, i) => (
            <span className="signal-tag" key={i}>{s}</span>
          ))}
        </div>
      )}

      {agenda ? (
        <div className="agenda">
          <h3>The author&apos;s agenda</h3>
          <p className="summary">{agenda.summary}</p>

          <table className="agenda-table">
            <tbody>
              <tr>
                <th>Primary goal</th>
                <td>
                  {agenda.primary_goal.claim}
                  <Quote q={agenda.primary_goal.quote} />
                </td>
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
              {agenda.probable_cta && (
                <tr>
                  <th>Probable CTA</th>
                  <td>
                    {agenda.probable_cta.claim}
                    <Quote q={agenda.probable_cta.quote} />
                  </td>
                </tr>
              )}
            </tbody>
          </table>

          {agenda.persuasion_tactics?.length > 0 && (
            <div className="tactics">
              <h4>Persuasion tactics</h4>
              <ul>
                {agenda.persuasion_tactics.map((t, i) => (
                  <li key={i}>
                    {t.claim}
                    <Quote q={t.quote} />
                  </li>
                ))}
              </ul>
            </div>
          )}
          <p className="verification-note">
            Each claim above is backed by a quote that was checked against your text.
            {result.dropped_claims > 0 &&
              ` ${result.dropped_claims} claim(s) were hidden because their quote could not be found in your text.`}
          </p>
        </div>
      ) : (
        <p className="verification-note">{result.message}</p>
      )}

      <Remaining n={result.remaining_today} />
      <Disclaimer result={result} />
    </section>
  );
}

function Quote({ q }) {
  return <blockquote className="quote">“{q}”</blockquote>;
}

function Injection({ result }) {
  if (!result.injection_detected) return null;
  return (
    <p className="injection-note">
      This text contains instructions aimed at an AI analyzer. They were ignored and treated as
      part of the text.
    </p>
  );
}

function Disclaimer({ result }) {
  return (
    <p className="disclaimer">
      {result.disclaimer}
      {result.request_id && <span className="request-id"> Ref: {result.request_id}</span>}
    </p>
  );
}
