import type { PageProps } from "../App";
import styles from "./Content.module.css";

const AUTHORS = [
  { name: "Jules H. van Binsbergen", affiliation: "The Wharton School, University of Pennsylvania" },
  { name: "Martijn Boons", affiliation: "Tilburg University" },
  { name: "Christian C. Opp", affiliation: "Simon Business School, University of Rochester" },
  { name: "Andrea Tamoni", affiliation: "Rutgers Business School" },
];

export function About({ manifest }: PageProps) {
  return (
    <div className={`page ${styles.root}`}>
      <p className="eyebrow">About</p>
      <h1>{manifest?.citation.title ?? "Build-up versus Resolution Anomalies"}</h1>
      <p className="lede">
        This site publishes the price wedge estimates from the paper, so that they can be
        inspected one security at a time and downloaded in bulk.
      </p>

      <div className="prose">
        <h2>Authors</h2>
        <ul className={styles.authors}>
          {AUTHORS.map((author) => (
            <li key={author.name}>
              <strong>{author.name}</strong>
              <span>{author.affiliation}</span>
            </li>
          ))}
        </ul>

        <h2>Abstract</h2>
        <p>
          We study the dynamic evolution of price wedges — log deviations of market prices
          from their informationally efficient values. One-month abnormal returns identify
          neither the direction nor the magnitude of mispricing and its dynamics. Of 57
          commonly studied return anomalies, about one third drive prices further away from
          fundamental value, which we call <em>build-up</em> anomalies; the remainder are
          associated with the <em>resolution</em> of an existing wedge. The estimates also
          yield a decomposition of Tobin's <em>q</em> whose mispricing component has
          substantial explanatory power for firm investment.
        </p>

        <h2>Updates</h2>
        <p>
          Estimates are versioned by vintage. The current vintage ends in December 2017, the
          last month of the sample used in the published paper. Extending it requires a fresh
          CRSP and Compustat pull and a re-run of the portfolio sorts; when that happens the
          new files appear alongside the existing ones rather than replacing them.
        </p>

        <h2>Corrections and questions</h2>
        <p>
          If you find something that looks wrong, please get in touch. Reproduction details
          are on the <a href="/methodology">methodology page</a>, and the underlying
          replication package accompanies the published article.
        </p>
      </div>
    </div>
  );
}
