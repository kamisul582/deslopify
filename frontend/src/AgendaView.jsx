export function Quote({ q }) {
  return <blockquote className="quote">“{q}”</blockquote>;
}

// Used by both the live result and the shared page, so they can't drift apart.
export default function AgendaView({ agenda, droppedClaims = 0 }) {
  return (
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
        Each claim above is backed by a quote that was checked against the analysed text.
        {droppedClaims > 0 &&
          ` ${droppedClaims} claim(s) were hidden because their quote could not be found in the text.`}
      </p>
    </div>
  );
}
