/** The chart every panel on the site is drawn with.
 *
 * Two encodings, picked by the job the data is doing:
 *
 *   diverging   one signed series against a meaningful zero — the area is
 *               filled red above zero (overpriced) and blue below
 *               (underpriced), because polarity *is* what a lone price wedge
 *               communicates.
 *   categorical two or more series whose job is identity — plain 2px lines in
 *               the fixed slot order, never cycled, with the slot pinned to the
 *               entity so adding or removing a line never repaints the others.
 *
 * Both carry a crosshair and a shared tooltip. Series are direct-labelled at the
 * right edge when there are four or fewer, which is also the relief the palette
 * requires for the light-mode slots that fall below 3:1 against the surface.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { line as d3line, area as d3area, curveLinear } from "d3-shape";
import { scaleLinear } from "d3-scale";
import { NBER_RECESSIONS } from "../lib/recessions";
import { formatMonth, formatYear, monthOrdinal, ordinalToYyyymm } from "../lib/format";
import styles from "./TimeSeriesChart.module.css";

export interface ChartSeries {
  key: string;
  label: string;
  /** CSS colour. Ignored in diverging mode. */
  color: string;
  months: number[];
  values: Float32Array | number[];
  /** Rendered in the tooltip. Receives the index into `months`/`values`, so a
   *  series can show something the plotted value alone does not carry -- the
   *  value panel plots percentages but reports dollars. */
  format?: (value: number, index: number) => string;
  dashed?: boolean;
}

interface Props {
  series: ChartSeries[];
  height?: number;
  mode?: "categorical" | "diverging";
  /** Inclusive yyyymm bounds. Defaults to the union of the series. */
  domain?: [number, number];
  yLabel?: string;
  yFormat?: (value: number) => string;
  /** Explicit tick positions. Needed when the values are logs and evenly spaced
   *  ticks would produce unreadable dollar labels. */
  yTicks?: (domain: [number, number]) => number[];
  /** Widen the gutter when the tick labels are long. */
  marginLeft?: number;
  /** Lock the y domain. Use for bounded quantities such as percentiles, where
   *  letting the data set the range would imply ranks below 0 or above 100. */
  yDomain?: [number, number];
  /** Draw a heavy rule at this y value. */
  baseline?: number | null;
  showRecessions?: boolean;
  /** Pad the y domain so the zero line is centred. Used by the wedge panel. */
  symmetric?: boolean;
  ariaLabel: string;
}

const MARGIN = { top: 14, right: 78, bottom: 30, left: 56 };
/** Minimum vertical gap between two direct labels before they are nudged apart. */
const LABEL_PITCH = 13;

interface Hover {
  ordinal: number;
  x: number;
  points: { series: ChartSeries; value: number; y: number; index: number }[];
}

export function TimeSeriesChart({
  series,
  height = 260,
  mode = "categorical",
  domain,
  yLabel,
  yFormat = (v) => v.toFixed(2),
  yTicks,
  marginLeft,
  yDomain: fixedDomain,
  baseline = null,
  showRecessions = true,
  symmetric = false,
  ariaLabel,
}: Props) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(880);
  const [hover, setHover] = useState<Hover | null>(null);

  useEffect(() => {
    const node = wrapRef.current;
    if (!node) return;
    const observer = new ResizeObserver(([entry]) => {
      setWidth(Math.max(260, entry.contentRect.width));
    });
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  // Below this the right-hand gutter costs more than the direct labels are
  // worth, so the labels are dropped (the legend still carries identity) and the
  // gutter shrinks to what the last data point needs.
  const narrow = width < 560;
  const left = marginLeft ?? MARGIN.left;
  const right = narrow ? 14 : MARGIN.right;
  const plotWidth = Math.max(1, width - left - right);
  const plotHeight = Math.max(1, height - MARGIN.top - MARGIN.bottom);

  const geom = useMemo(() => {
    const points = series.map((s) =>
      s.months
        .map((m, i) => ({ ordinal: monthOrdinal(m), value: Number(s.values[i]), i }))
        .filter((p) => Number.isFinite(p.value)),
    );

    const flat = points.flat();
    if (!flat.length) return null;

    const xExtent: [number, number] = domain
      ? [monthOrdinal(domain[0]), monthOrdinal(domain[1])]
      : [Math.min(...flat.map((p) => p.ordinal)), Math.max(...flat.map((p) => p.ordinal))];

    const visible = points.map((ps) =>
      ps.filter((p) => p.ordinal >= xExtent[0] && p.ordinal <= xExtent[1]),
    );
    const visibleFlat = visible.flat();
    if (!visibleFlat.length) return null;

    let lo = Math.min(...visibleFlat.map((p) => p.value));
    let hi = Math.max(...visibleFlat.map((p) => p.value));
    if (lo === hi) {
      lo -= 0.5;
      hi += 0.5;
    }

    const x = scaleLinear().domain(xExtent).range([0, plotWidth]);

    // A symmetric domain is set to the data's own reach plus a little headroom
    // and is deliberately *not* rounded outward: d3 picks round tick values
    // inside it anyway, and rounding the bound instead would leave a third of
    // the plot empty on a series that happens to peak just past a round number.
    const y = fixedDomain
      ? scaleLinear().domain(fixedDomain).range([plotHeight, 0])
      : symmetric
      ? scaleLinear()
          .domain([-1, 1].map((s) => s * Math.max(Math.abs(lo), Math.abs(hi)) * 1.08) as [number, number])
          .range([plotHeight, 0])
      : scaleLinear()
          .domain([lo - (hi - lo) * 0.08, hi + (hi - lo) * 0.08])
          .nice(5)
          .range([plotHeight, 0]);

    return { points: visible, x, y, xExtent };
  }, [series, domain, plotWidth, plotHeight, symmetric, fixedDomain]);

  const handleMove = useCallback(
    (event: React.PointerEvent<SVGRectElement>) => {
      if (!geom) return;
      const rect = event.currentTarget.getBoundingClientRect();
      const local = event.clientX - rect.left;
      const target = Math.round(geom.x.invert(local));

      const points: Hover["points"] = [];
      geom.points.forEach((ps, i) => {
        if (!ps.length) return;
        let best = ps[0];
        for (const p of ps) {
          if (Math.abs(p.ordinal - target) < Math.abs(best.ordinal - target)) best = p;
        }
        if (Math.abs(best.ordinal - target) <= 6) {
          points.push({
            series: series[i],
            value: best.value,
            y: geom.y(best.value),
            index: best.i,
          });
        }
      });
      if (!points.length) {
        setHover(null);
        return;
      }
      setHover({ ordinal: target, x: geom.x(target), points });
    },
    [geom, series],
  );

  if (!geom) {
    return (
      <div ref={wrapRef} className={styles.empty} style={{ height }}>
        No observations in this window.
      </div>
    );
  }

  const { x, y, points } = geom;
  const yDomain = y.domain() as [number, number];
  const tickValues = (yTicks ? yTicks(yDomain) : y.ticks(5)).filter(
    (t) => t >= yDomain[0] && t <= yDomain[1],
  );
  const xTicks = tickYears(geom.xExtent, plotWidth);
  const zero = y.domain()[0] <= 0 && y.domain()[1] >= 0 ? y(0) : null;
  const directLabels = series.length <= 4 && !narrow;

  const path = d3line<{ ordinal: number; value: number; i: number }>()
    .x((p) => x(p.ordinal))
    .y((p) => y(p.value))
    .curve(curveLinear);

  return (
    <div ref={wrapRef} className={styles.wrap}>
      <svg
        width={width}
        height={height}
        role="img"
        aria-label={ariaLabel}
        className={styles.svg}
      >
        <defs>
          <clipPath id={`clip-${ariaLabel.replace(/\W/g, "")}`}>
            <rect x={0} y={-4} width={plotWidth} height={plotHeight + 8} />
          </clipPath>
        </defs>

        <g transform={`translate(${left},${MARGIN.top})`}>
          {showRecessions &&
            NBER_RECESSIONS.map((r) => {
              const x0 = Math.max(x(monthOrdinal(r.peak)), 0);
              const x1 = Math.min(x(monthOrdinal(r.trough)), plotWidth);
              if (x1 <= 0 || x0 >= plotWidth) return null;
              return (
                <rect
                  key={r.peak}
                  x={x0}
                  y={0}
                  width={Math.max(1, x1 - x0)}
                  height={plotHeight}
                  className={styles.recession}
                />
              );
            })}

          {tickValues.map((t) => (
            <g key={t} transform={`translate(0,${y(t)})`}>
              <line x2={plotWidth} className={styles.grid} />
              <text x={-10} dy="0.32em" className={styles.axisLabel} textAnchor="end">
                {yFormat(t)}
              </text>
            </g>
          ))}

          {xTicks.map((t) => (
            <g key={t} transform={`translate(${x(t)},${plotHeight})`}>
              <line y2={5} className={styles.tick} />
              <text y={18} className={styles.axisLabel} textAnchor="middle">
                {formatYear(ordinalToYyyymm(t))}
              </text>
            </g>
          ))}

          {zero !== null && baseline !== null && (
            <line y1={zero} y2={zero} x2={plotWidth} className={styles.baseline} />
          )}

          <g clipPath={`url(#clip-${ariaLabel.replace(/\W/g, "")})`}>
            {mode === "diverging" && points[0] ? (
              <DivergingArea data={points[0]} x={x} y={y} width={plotWidth} />
            ) : null}

            {points.map((ps, i) => (
              <path
                key={series[i].key}
                d={path(ps) ?? undefined}
                fill="none"
                stroke={mode === "diverging" ? "var(--text-primary)" : series[i].color}
                strokeWidth={mode === "diverging" ? 1.75 : 2}
                strokeLinejoin="round"
                strokeLinecap="round"
                strokeDasharray={series[i].dashed ? "5 4" : undefined}
              />
            ))}
          </g>

          {directLabels &&
            mode === "categorical" &&
            spreadLabels(
              points.map((ps, i) =>
                ps.length ? { key: series[i].key, label: series[i].label, y: y(ps[ps.length - 1].value) } : null,
              ),
              plotHeight,
            ).map((label) => (
              <text
                key={label.key}
                x={plotWidth + 8}
                y={label.y}
                dy="0.32em"
                className={styles.directLabel}
              >
                {label.label}
              </text>
            ))}

          {hover && (
            <g>
              <line
                x1={hover.x}
                x2={hover.x}
                y1={0}
                y2={plotHeight}
                className={styles.crosshair}
              />
              {hover.points.map((p) => (
                <circle
                  key={p.series.key}
                  cx={hover.x}
                  cy={p.y}
                  r={4}
                  fill={mode === "diverging" ? "var(--text-primary)" : p.series.color}
                  className={styles.marker}
                />
              ))}
            </g>
          )}

          <rect
            x={0}
            y={0}
            width={plotWidth}
            height={plotHeight}
            fill="transparent"
            onPointerMove={handleMove}
            onPointerLeave={() => setHover(null)}
          />
        </g>

        {yLabel && (
          <text
            transform={`translate(13,${MARGIN.top + plotHeight / 2}) rotate(-90)`}
            className={styles.axisTitle}
            textAnchor="middle"
          >
            {yLabel}
          </text>
        )}
      </svg>

      {hover && (
        <div
          className={styles.tooltip}
          style={{
            left: Math.min(Math.max(hover.x + left, 90), width - 90),
            transform: "translateX(-50%)",
          }}
        >
          <div className={styles.tooltipMonth}>{formatMonth(ordinalToYyyymm(hover.ordinal))}</div>
          {hover.points.map((p) => (
            <div key={p.series.key} className={styles.tooltipRow}>
              <span
                className={styles.swatch}
                style={{ background: mode === "diverging" ? poleColor(p.value) : p.series.color }}
              />
              <span className={styles.tooltipLabel}>{p.series.label}</span>
              <span className={styles.tooltipValue}>
                {(p.series.format ?? ((v: number) => v.toFixed(3)))(p.value, p.index)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/** Push overlapping right-edge labels apart so two near-identical series stay
 *  legible, keeping them in value order and inside the plot. */
function spreadLabels(
  raw: ({ key: string; label: string; y: number } | null)[],
  plotHeight: number,
): { key: string; label: string; y: number }[] {
  const labels = raw.filter((l): l is { key: string; label: string; y: number } => l !== null);
  labels.sort((a, b) => a.y - b.y);
  for (let i = 1; i < labels.length; i += 1) {
    if (labels[i].y - labels[i - 1].y < LABEL_PITCH) labels[i].y = labels[i - 1].y + LABEL_PITCH;
  }
  const overflow = labels.length ? labels[labels.length - 1].y - plotHeight : 0;
  if (overflow > 0) for (const l of labels) l.y -= overflow;
  return labels;
}

function poleColor(value: number): string {
  return value >= 0 ? "var(--pole-over)" : "var(--pole-under)";
}

/** Fill between the series and zero, split at every crossing so the two poles
 *  never bleed into each other. */
function DivergingArea({
  data,
  x,
  y,
  width,
}: {
  data: { ordinal: number; value: number; i: number }[];
  x: (v: number) => number;
  y: (v: number) => number;
  width: number;
}) {
  const zero = y(0);
  const above = d3area<{ ordinal: number; value: number; i: number }>()
    .x((p) => x(p.ordinal))
    .y0(zero)
    .y1((p) => Math.min(y(p.value), zero));
  const below = d3area<{ ordinal: number; value: number; i: number }>()
    .x((p) => x(p.ordinal))
    .y0(zero)
    .y1((p) => Math.max(y(p.value), zero));

  return (
    <g>
      <path d={above(data) ?? undefined} fill="var(--pole-over-fill)" />
      <path d={below(data) ?? undefined} fill="var(--pole-under-fill)" />
      <line x1={0} x2={width} y1={zero} y2={zero} stroke="var(--rule-strong)" strokeWidth={1} />
    </g>
  );
}

/** Year ticks at a spacing that keeps labels from colliding. */
function tickYears([lo, hi]: [number, number], pixels: number): number[] {
  const firstYear = Math.ceil(lo / 12);
  const lastYear = Math.floor(hi / 12);
  const years = lastYear - firstYear + 1;
  const step = [1, 2, 5, 10, 20, 25, 50].find((s) => (years / s) * 46 <= pixels) ?? 50;
  const ticks: number[] = [];
  for (let yr = Math.ceil(firstYear / step) * step; yr <= lastYear; yr += step) {
    ticks.push(yr * 12);
  }
  return ticks;
}
