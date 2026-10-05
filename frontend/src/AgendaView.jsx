export function Quote({ q }) {
  return <blockquote className="quote">“{q}”</blockquote>;
}

// Used by both the live result and the shared page, so they can't drift apart.
export default function AgendaView({ agenda, droppedClaims = 0 }) {
  return (
    <div className="agenda">
      <div className="tldr">
        <span className="label">TL;DR</span>
        <p>{agenda.tldr}</p>
        <p className="context">{agenda.context}</p>
      </div>

      <div className="likely-prompt">
        <span className="label">A plausible prompt behind it</span>
        <p className="guess-note">
          A guess reconstructed from the text, not something the author is known to have written.
        </p>
        <blockquote lang="und">{agenda.likely_prompt}</blockquote>
      </div>

      <div className="evidence">
        <span className="label">Evidence</span>
        <dl>
          <dt>Main goal</dt>
          <dd>
            {agenda.primary_goal.claim}
            <Quote q={agenda.primary_goal.quote} />
          </dd>
          {agenda.persuasion_tactics?.length > 0 && (
            <>
              <dt>Tactics</dt>
              <dd>
                <ul>
                  {agenda.persuasion_tactics.map((t, i) => (
                    <li key={i}>
                      {t.claim}
                      <Quote q={t.quote} />
                    </li>
                  ))}
                </ul>
              </dd>
            </>
          )}
          {agenda.probable_cta && (
            <>
              <dt>Call to action</dt>
              <dd>
                {agenda.probable_cta.claim}
                <Quote q={agenda.probable_cta.quote} />
              </dd>
            </>
          )}
        </dl>
        <p className="verification-note">
          Every quote above was checked against the analysed text.
          {droppedClaims > 0 &&
            ` ${droppedClaims} claim(s) were hidden because their quote could not be found in the text.`}
        </p>
      </div>
    </div>
  );
}
