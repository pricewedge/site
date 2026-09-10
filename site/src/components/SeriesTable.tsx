import { useMemo, useState } from "react";
import type { FirmRecord, Manifest } from "../lib/types";
import { formatMarketCap, formatMonth, formatPercentile, formatWedge } from "../lib/format";
import styles from "./SeriesTable.module.css";

const PAGE = 60;

/** The non-visual route to the same numbers. Required as relief for the
 *  light-mode series colours that sit below 3:1 against the surface, and it is
 *  how a researcher copies a handful of values without downloading the panel. */
export function SeriesTable({
  record,
  specId,
  manifest,
  range,
}: {
  record: FirmRecord;
  specId: string;
  manifest: Manifest | null;
  range: [number, number] | null;
}) {
  const [limit, setLimit] = useState(PAGE);

  const rows = useMemo(() => {
    const wedge = record.series.get(specId);
    const cap = record.series.get("mktcap");
    const chars = (manifest?.firm.characteristics ?? []).slice(0, 4);
    const out: {
      month: number;
      wedge: number;
      cap: number;
      chars: number[];
    }[] = [];
    record.months.forEach((month, i) => {
      if (range && (month < range[0] || month > range[1])) return;
      const value = wedge?.[i] ?? NaN;
      if (!Number.isFinite(value)) return;
      out.push({
        month,
        wedge: value,
        cap: cap?.[i] ?? NaN,
        chars: chars.map((c) => record.series.get(c.id)?.[i] ?? NaN),
      });
    });
    return out.reverse();
  }, [record, specId, manifest, range]);

  const chars = (manifest?.firm.characteristics ?? []).slice(0, 4);

  const csv = () => {
    const header = ["month", "price_wedge", "market_cap_musd", ...chars.map((c) => `${c.id}_pctile`)];
    const body = rows.map((r) =>
      [r.month, r.wedge.toFixed(6), r.cap.toFixed(2), ...r.chars.map((v) => v.toFixed(4))].join(","),
    );
    const blob = new Blob([[header.join(","), ...body].join("\n")], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    const slug = (record.ticker ?? record.name ?? `security-${record.id}`)
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "");
    a.download = `pricewedge_${slug}_${specId}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (!rows.length) return <p className={styles.empty}>No observations in this window.</p>;

  return (
    <div>
      <div className={styles.toolbar}>
        <span className={styles.count}>
          {rows.length.toLocaleString("en-US")} monthly observations
        </span>
        <button type="button" className={styles.download} onClick={csv}>
          Download this series (CSV)
        </button>
      </div>
      <div className={styles.scroller}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th scope="col">Month</th>
              <th scope="col">Price wedge</th>
              <th scope="col">Market value</th>
              {chars.map((c) => (
                <th key={c.id} scope="col">
                  {c.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.slice(0, limit).map((r) => (
              <tr key={r.month}>
                <th scope="row">{formatMonth(r.month)}</th>
                <td style={{ color: r.wedge >= 0 ? "var(--pole-over)" : "var(--pole-under)" }}>
                  {formatWedge(r.wedge, 2)}
                </td>
                <td>{formatMarketCap(r.cap)}</td>
                {r.chars.map((v, i) => (
                  <td key={chars[i].id}>{formatPercentile(v)}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {limit < rows.length && (
        <button type="button" className={styles.more} onClick={() => setLimit((l) => l + PAGE * 4)}>
          Show more ({(rows.length - limit).toLocaleString("en-US")} remaining)
        </button>
      )}
    </div>
  );
}
