import { useCallback, useEffect, useMemo, useState } from "react";
import type { PageProps } from "../App";
import type { FirmIndex, FirmRecord, SecurityRef } from "../lib/types";
import { loadFirmIndex, loadSecurity, securityLabel, securityList } from "../lib/store";
import { TimeSeriesChart, type ChartSeries } from "../components/TimeSeriesChart";
import { SecurityPicker } from "../components/SecurityPicker";
import { SpecPicker, specNote } from "../components/SpecPicker";
import { RangePicker } from "../components/RangePicker";
import { RangeBrush } from "../components/RangeBrush";
import { SeriesTable } from "../components/SeriesTable";
import {
  formatMarketCap,
  formatMonth,
  formatPercentile,
  formatWedge,
} from "../lib/format";
import toggleStyles from "../components/SpecPicker.module.css";
import styles from "./Explorer.module.css";

const MAX_SERIES = 8;
const SLOTS = [1, 2, 3, 4, 5, 6, 7, 8].map((i) => `var(--series-${i})`);

/** Apple is the paper's worked example, so it is what the page opens on. */
const SEED_TICKER = "AAPL";

export function Explorer({ manifest }: PageProps) {
  const [index, setIndex] = useState<FirmIndex | null>(null);
  const [securities, setSecurities] = useState<SecurityRef[]>([]);
  const [selected, setSelected] = useState<number[]>([]);
  const [records, setRecords] = useState<Map<number, FirmRecord>>(new Map());
  const [specId, setSpecId] = useState<string | null>(null);
  const [range, setRange] = useState<[number, number] | null>(null);
  const [showValue, setShowValue] = useState(true);
  const [valueScale, setValueScale] = useState<"dollars" | "logs">("dollars");
  const [showChars, setShowChars] = useState(false);
  const [showTable, setShowTable] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    loadFirmIndex().then(
      (idx) => {
        setIndex(idx);
        const list = securityList(idx);
        setSecurities(list);
        const seed = list.find((s) => s.ticker === SEED_TICKER && s.end === 201712);
        if (seed) setSelected([seed.id]);
      },
      (e: Error) => setLoadError(e.message),
    );
  }, []);

  useEffect(() => {
    if (manifest && !specId) {
      setSpecId((manifest.firm.specs.find((s) => s.default) ?? manifest.firm.specs[0]).id);
    }
  }, [manifest, specId]);

  useEffect(() => {
    if (!index) return;
    for (const securityId of selected) {
      if (records.has(securityId)) continue;
      loadSecurity(index, securityId).then(
        (rec) => setRecords((prev) => new Map(prev).set(securityId, rec)),
        (e: Error) => setLoadError(e.message),
      );
    }
  }, [index, selected, records]);

  // Colour is pinned to the entity by its position in the selection order, and
  // that position is never reused, so removing a line cannot repaint the rest.
  const [slotOf, setSlotOf] = useState<Map<number, number>>(new Map());
  const colorFor = useCallback(
    (securityId: number) => SLOTS[(slotOf.get(securityId) ?? 0) % SLOTS.length],
    [slotOf],
  );

  const addSecurity = (securityId: number) => {
    setSelected((prev) => (prev.includes(securityId) ? prev : [...prev, securityId]));
    setSlotOf((prev) => {
      if (prev.has(securityId)) return prev;
      const taken = new Set(prev.values());
      let slot = 0;
      while (taken.has(slot) && slot < SLOTS.length) slot += 1;
      return new Map(prev).set(securityId, slot);
    });
  };

  const removeSecurity = (securityId: number) => {
    setSelected((prev) => prev.filter((p) => p !== securityId));
    setSlotOf((prev) => {
      const next = new Map(prev);
      next.delete(securityId);
      return next;
    });
  };

  useEffect(() => {
    if (!selected.length) return;
    setSlotOf((prev) => {
      if (prev.size) return prev;
      return new Map(selected.map((p, i) => [p, i]));
    });
  }, [selected]);

  const labelFor = useCallback(
    (id: number) => securityLabel(securities[id], id),
    [securities],
  );

  const loaded = useMemo(
    () => selected.map((p) => records.get(p)).filter((r): r is FirmRecord => Boolean(r)),
    [selected, records],
  );

  const dataRange = useMemo<[number, number] | null>(() => {
    if (!loaded.length) return null;
    return [
      Math.min(...loaded.map((r) => r.months[0])),
      Math.max(...loaded.map((r) => r.months[r.months.length - 1])),
    ];
  }, [loaded]);

  const activeRange = range ?? dataRange;
  const single = loaded.length === 1;

  const wedgeSeries: ChartSeries[] = useMemo(() => {
    if (!specId) return [];
    return loaded.map((rec) => ({
      key: `${rec.id}-wedge`,
      label: labelFor(rec.id),
      color: colorFor(rec.id),
      months: rec.months,
      values: rec.series.get(specId) ?? new Float32Array(),
      format: (v) => formatWedge(v),
    }));
  }, [loaded, specId, colorFor, labelFor]);

  // Two ways to show the same pair of series.
  //
  // dollars  levels on a zero-anchored linear axis. Heights read as values, so
  //          a firm 40% overpriced has a market line exp(0.40) = 1.49x the
  //          height of its efficient line. Early history compresses toward the
  //          floor when the firm has grown by orders of magnitude.
  // logs     ln of each, as in Fig. 7 Panel B of the paper. The vertical gap is
  //          the price wedge by identity, ln(P) - ln(P-tilde) = PW, but it is a
  //          small share of the height when the series spans decades of growth.
  const valueSeries: ChartSeries[] = useMemo(() => {
    if (!specId || !single) return [];
    const rec = loaded[0];
    const cap = rec.series.get("mktcap");
    const wedge = rec.series.get(specId);
    if (!cap || !wedge) return [];

    const market = new Float32Array(cap.length);
    const efficient = new Float32Array(cap.length);
    for (let i = 0; i < cap.length; i += 1) {
      const usable = cap[i] > 0 && Number.isFinite(wedge[i]);
      const eff = usable ? cap[i] * Math.exp(-wedge[i]) : NaN;
      market[i] = usable ? (valueScale === "logs" ? Math.log(cap[i]) : cap[i]) : NaN;
      efficient[i] = usable ? (valueScale === "logs" ? Math.log(eff) : eff) : NaN;
    }

    const asDollars = (v: number) =>
      valueScale === "logs" ? formatMarketCap(Math.exp(v)) : formatMarketCap(v);

    return [
      {
        key: "observed",
        label: "Market value",
        color: "var(--series-1)",
        months: rec.months,
        values: market,
        format: (v: number, i: number) => `${asDollars(v)} · ${formatWedge(wedge[i])}`,
      },
      {
        key: "efficient",
        label: "Efficient value",
        color: "var(--series-2)",
        months: rec.months,
        values: efficient,
        format: (v: number) => asDollars(v),
        dashed: true,
      },
    ];
  }, [loaded, specId, single, valueScale]);

  const charSeries: ChartSeries[] = useMemo(() => {
    if (!manifest || !single) return [];
    const rec = loaded[0];
    return manifest.firm.characteristics
      .slice(0, 4)
      .map((c, i) => ({
        key: c.id,
        label: c.label,
        color: SLOTS[i],
        months: rec.months,
        values: rec.series.get(c.id) ?? new Float32Array(),
        format: formatPercentile,
      }))
      .filter((s) => Array.from(s.values).some(Number.isFinite));
  }, [loaded, manifest, single]);

  const spec = manifest?.firm.specs.find((s) => s.id === specId) ?? null;

  return (
    <div className={styles.root}>
      <section className={`page ${styles.intro}`}>
        <div>
          <p className="eyebrow">Firm-level mispricing estimates</p>
          <h1 className={styles.title}>
            Price Wedges:
            <br />
            Stock Mispricing
          </h1>
        </div>
        <div className={styles.introSide}>
          <p className="lede">
            The price wedge is the log gap between a firm’s market value and its
            informationally efficient value. Positive estimates indicate that the stock is
            overpriced; negative estimates indicate that it is underpriced.
          </p>
          <p className={styles.introMeta}>
            {manifest ? manifest.firm.securities.toLocaleString("en-US") : "19,476"} US stocks ·
            1964–2017 · eight specifications · <a href="/data">bulk download</a>
          </p>
        </div>
      </section>

      <section className={`page ${styles.controlsSection}`}>
        <div className={`card ${styles.controls}`}>
          <div className={styles.controlsGrid}>
            <SecurityPicker
              all={securities}
              selected={selected}
              colorFor={colorFor}
              labelFor={labelFor}
              onAdd={addSecurity}
              onRemove={removeSecurity}
              max={MAX_SERIES}
              hasNames={index?.identifiers === "names"}
            />
            {manifest && specId && (
              <SpecPicker manifest={manifest} specId={specId} onChange={setSpecId} />
            )}
            <RangePicker
              bounds={dataRange}
              value={activeRange}
              onChange={setRange}
              onReset={() => setRange(null)}
            />
          </div>
          <p className={styles.controlsNote}>
            {manifest && spec ? specNote(manifest, spec) : null}{" "}
            {selected.length === 1 && (
              <span className={styles.hint}>
                Add up to {MAX_SERIES - 1} more securities to overlay them on one axis.
              </span>
            )}
          </p>
        </div>
      </section>

      <section className={`page ${styles.charts}`}>
        {loadError && <p className={styles.error}>{loadError}</p>}

        {!selected.length ? (
          <div className={`card ${styles.placeholder}`}>
            <p>Search for a security above to plot its price wedge.</p>
          </div>
        ) : !loaded.length ? (
          <div className={`card ${styles.placeholder}`}>
            <p>Loading estimates…</p>
          </div>
        ) : (
          <>
            <figure className={`card ${styles.panel}`}>
              <figcaption className={styles.panelHead}>
                <div>
                  <h2 className={styles.panelTitle}>Price wedge</h2>
                  <p className={styles.panelSub}>
                    {spec?.label}
                    {single && (
                      <>
                        {" · "}
                        <span className={styles.poleKey}>
                          <span className={styles.poleOver} /> overpriced
                        </span>
                        <span className={styles.poleKey}>
                          <span className={styles.poleUnder} /> underpriced
                        </span>
                      </>
                    )}
                  </p>
                </div>
                {single && <Headline record={loaded[0]} specId={specId!} range={activeRange} />}
              </figcaption>

              {!single && (
                <Legend
                  items={wedgeSeries.map((s) => ({ label: s.label, color: s.color }))}
                />
              )}

              <TimeSeriesChart
                ariaLabel="Price wedge over time"
                series={wedgeSeries}
                mode={single ? "diverging" : "categorical"}
                domain={activeRange ?? undefined}
                height={320}
                symmetric
                baseline={0}
                yLabel="Price wedge"
                yFormat={(v) => `${(v * 100).toFixed(0)}%`}
              />

              {dataRange && activeRange && (
                <RangeBrush
                  bounds={dataRange}
                  value={activeRange}
                  onChange={setRange}
                  series={wedgeSeries}
                  diverging={single}
                />
              )}
            </figure>

            {single && (
              <div className={styles.optional}>
                <Disclosure
                  open={showValue}
                  onToggle={() => setShowValue((v) => !v)}
                  title="Market value versus efficient value"
                  hint={valueScale === "dollars" ? "dollars" : "natural logs"}
                >
                  <div className={styles.panelControls}>
                    <Legend items={valueSeries.map((s) => ({ label: s.label, color: s.color }))} />
                    <div className={toggleStyles.toggle}>
                      {(["dollars", "logs"] as const).map((mode) => (
                        <button
                          key={mode}
                          type="button"
                          className={toggleStyles.toggleButton}
                          aria-pressed={valueScale === mode}
                          onClick={() => setValueScale(mode)}
                        >
                          {mode === "dollars" ? "Dollars" : "Natural logs"}
                        </button>
                      ))}
                    </div>
                  </div>
                  <TimeSeriesChart
                    ariaLabel="Market value and efficient value"
                    series={valueSeries}
                    domain={activeRange ?? undefined}
                    height={240}
                    marginLeft={valueScale === "logs" ? 62 : 74}
                    bandBetween
                    includeZero={valueScale === "dollars"}
                    yLabel={valueScale === "logs" ? "ln(value, $m)" : "market value"}
                    yFormat={(v) => (valueScale === "logs" ? v.toFixed(1) : formatMarketCap(v))}
                  />
                  <p className={styles.note}>
                    {valueScale === "dollars" ? (
                      <>
                        Efficient value is the market value scaled by exp(−PW). The axis is
                        anchored at zero, so heights read as levels: a firm 40% overpriced
                        has a market line about 1.4 times the height of its efficient line.
                        The band is shaded red where the market value sits above the
                        efficient value and blue where it sits below. A firm that has grown
                        by orders of magnitude will press its early history against the
                        axis; switch to natural logs, or narrow the time window, to see it.
                      </>
                    ) : (
                      <>
                        Natural logs of both values, as in Fig. 7 of the paper. Here the
                        vertical gap between the lines <em>is</em> the price wedge — 0.40 log
                        units when the firm is 40% overpriced — and every era of the firm’s
                        history is equally legible. The trade-off is that the gap is a small
                        share of the plot height when the firm has grown a thousandfold.
                      </>
                    )}
                  </p>
                </Disclosure>

                <Disclosure
                  open={showChars}
                  onToggle={() => setShowChars((v) => !v)}
                  title="Characteristic percentiles"
                  hint="cross-sectional rank"
                >
                  <Legend items={charSeries.map((s) => ({ label: s.label, color: s.color }))} />
                  <TimeSeriesChart
                    ariaLabel="Characteristic percentiles"
                    series={charSeries}
                    domain={activeRange ?? undefined}
                    height={200}
                    yLabel="percentile"
                    yDomain={[0, 1]}
                    yTicks={() => [0, 0.25, 0.5, 0.75, 1]}
                    yFormat={(v) => `${(v * 100).toFixed(0)}`}
                  />
                  <p className={styles.note}>
                    Rank of the firm within all sortable US stocks that month. These are the
                    inputs the price wedge is built from — the wedge dated <em>t</em> uses
                    characteristics dated <em>t</em>−1.
                  </p>
                </Disclosure>

                <Disclosure
                  open={showTable}
                  onToggle={() => setShowTable((v) => !v)}
                  title="Table view"
                  hint="every observation"
                >
                  <SeriesTable
                    record={loaded[0]}
                    specId={specId!}
                    manifest={manifest}
                    range={activeRange}
                  />
                </Disclosure>
              </div>
            )}
          </>
        )}
      </section>
    </div>
  );
}

function Headline({
  record,
  specId,
  range,
}: {
  record: FirmRecord;
  specId: string;
  range: [number, number] | null;
}) {
  const values = record.series.get(specId);
  if (!values) return null;

  let latest: { month: number; value: number } | null = null;
  let extreme: { month: number; value: number } | null = null;
  record.months.forEach((m, i) => {
    const v = values[i];
    if (!Number.isFinite(v)) return;
    if (range && (m < range[0] || m > range[1])) return;
    latest = { month: m, value: v };
    if (!extreme || Math.abs(v) > Math.abs(extreme.value)) extreme = { month: m, value: v };
  });
  if (!latest || !extreme) return null;

  const last = latest as { month: number; value: number };
  const peak = extreme as { month: number; value: number };

  return (
    <dl className={styles.headline}>
      <div>
        <dt>Latest</dt>
        <dd style={{ color: last.value >= 0 ? "var(--pole-over)" : "var(--pole-under)" }}>
          {formatWedge(last.value)}
        </dd>
        <dd className={styles.headlineMeta}>{formatMonth(last.month)}</dd>
      </div>
      <div>
        <dt>Largest</dt>
        <dd style={{ color: peak.value >= 0 ? "var(--pole-over)" : "var(--pole-under)" }}>
          {formatWedge(peak.value)}
        </dd>
        <dd className={styles.headlineMeta}>{formatMonth(peak.month)}</dd>
      </div>
    </dl>
  );
}

function Legend({ items }: { items: { label: string; color: string }[] }) {
  if (items.length < 2) return null;
  return (
    <ul className={styles.legend}>
      {items.map((item) => (
        <li key={item.label}>
          <span className={styles.legendDot} style={{ background: item.color }} />
          {item.label}
        </li>
      ))}
    </ul>
  );
}

function Disclosure({
  open,
  onToggle,
  title,
  hint,
  children,
}: {
  open: boolean;
  onToggle: () => void;
  title: string;
  hint: string;
  children: React.ReactNode;
}) {
  return (
    <section className={`card ${styles.panel}`}>
      <button type="button" className={styles.disclosure} onClick={onToggle} aria-expanded={open}>
        <span className={styles.disclosureIcon} data-open={open}>
          ›
        </span>
        <span className={styles.panelTitle}>{title}</span>
        <span className={styles.disclosureHint}>{hint}</span>
      </button>
      {open && <div className={styles.disclosureBody}>{children}</div>}
    </section>
  );
}
