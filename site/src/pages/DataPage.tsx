import type { PageProps } from "../App";
import { formatBytes, formatCount } from "../lib/format";
import styles from "./Content.module.css";

const BASE = (import.meta.env.VITE_DATA_BASE ?? "/data").replace(/\/$/, "");

const DESCRIPTIONS: Record<string, { title: string; body: string }> = {
  firm: {
    title: "Firm-level price wedges",
    body: "One row per PERMNO-month, with a column for each of the eight specifications. Equity-level series run 1964-07 to 2017-12; firm-value series run 1974-07 to 2016-12; out-of-sample series begin 1998-10.",
  },
  portfolio: {
    title: "Portfolio price wedges at formation",
    body: "All ten decile portfolios plus the aggregate market for each of the 57 characteristic sorts, under both cash-flow treatments. Reproduces the PW★ column of Table 1 and extends it to the intermediate deciles the paper does not print.",
  },
  portfolio_horizon: {
    title: "Portfolio price wedges by horizon",
    body: "The same wedges re-based at the end of each year after portfolio formation, holding the fifteen-year resolution assumption fixed. Year 0 equals the wedge at formation.",
  },
};

export function DataPage({ manifest }: PageProps) {
  const grouped = new Map<string, NonNullable<typeof manifest>["downloads"]>();
  for (const item of manifest?.downloads ?? []) {
    const list = grouped.get(item.dataset) ?? [];
    list.push(item);
    grouped.set(item.dataset, list);
  }

  return (
    <div className={`page ${styles.root}`}>
      <p className="eyebrow">Data</p>
      <h1>Download the estimates</h1>
      <p className="lede">
        Everything the explorer plots is available as a flat file. Files are versioned by
        vintage, and published URLs are permanent — a paper citing a specific file keeps
        resolving after we extend the sample.
      </p>

      {manifest && (
        <div className={styles.stats}>
          <Stat label="Securities" value={formatCount(manifest.firm.securities)} />
          <Stat label="Characteristic sorts" value={formatCount(manifest.portfolio.characteristics.length)} />
          <Stat label="Vintage" value={manifest.vintage} />
          <Stat label="Data version" value={manifest.dataVersion} />
        </div>
      )}

      {[...grouped.entries()].map(([dataset, files]) => (
        <section key={dataset} className={styles.dataset}>
          <h2>{DESCRIPTIONS[dataset]?.title ?? dataset}</h2>
          <p>{DESCRIPTIONS[dataset]?.body}</p>
          <ul className={styles.fileList}>
            {files.map((file) => (
              <li key={file.file}>
                <a
                  href={file.url.startsWith("http") ? file.url : `${BASE}/downloads/${file.file}`}
                  download={file.url.startsWith("http") ? undefined : file.file}
                  className={styles.file}
                >
                  <span className={styles.fileFormat}>
                    {file.file.endsWith(".parquet") ? "Parquet" : "CSV"}
                  </span>
                  <span className={styles.fileName}>{file.file}</span>
                  <span className={styles.fileMeta}>
                    {formatCount(file.rows)} rows · {formatBytes(file.bytes)}
                  </span>
                </a>
              </li>
            ))}
          </ul>
        </section>
      ))}

      <section className={styles.dataset}>
        <h2>Identifiers</h2>
        <p>
          Securities are identified by CRSP PERMNO. CRSP company names and tickers are
          licensed and are not redistributed here, so the download files and the search box
          carry PERMNOs only.
        </p>
      </section>

      <section className={styles.dataset}>
        <h2>Citation</h2>
        {manifest && (
          <pre className={styles.cite}>
{`@article{binsbergen_boons_opp_tamoni,
  title   = {${manifest.citation.title}},
  author  = {${manifest.citation.authors.join(" and ")}},
  journal = {${manifest.citation.journal}},
  note    = {Estimates vintage ${manifest.vintage}, data version ${manifest.dataVersion}, ${manifest.citation.url}}
}`}
          </pre>
        )}
      </section>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className={styles.stat}>
      <span className={styles.statValue}>{value}</span>
      <span className={styles.statLabel}>{label}</span>
    </div>
  );
}
