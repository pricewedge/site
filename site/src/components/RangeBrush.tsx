/** A navigator strip under the main chart: the whole sample in miniature, with
 *  a draggable window over it. Whatever the window covers is what every panel
 *  on the page shows, since they all read the same time range.
 *
 *  Three gestures, the ones this control has in every financial chart that has
 *  it: drag a handle to move one edge, drag the shaded middle to slide the
 *  window, drag on empty track to draw a new one. Handles are also focusable and
 *  respond to arrow keys, so the window is reachable without a pointer.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { line as d3line } from "d3-shape";
import { scaleLinear } from "d3-scale";
import type { ChartSeries } from "./TimeSeriesChart";
import { formatMonth, monthOrdinal, ordinalToYyyymm } from "../lib/format";
import styles from "./RangeBrush.module.css";

interface Props {
  /** Full extent of the data, yyyymm. */
  bounds: [number, number];
  /** Currently selected window, yyyymm. */
  value: [number, number];
  onChange: (range: [number, number]) => void;
  /** Drawn in miniature behind the window. */
  series: ChartSeries[];
  /** Colour the miniature as a single signed series rather than by identity. */
  diverging?: boolean;
}

const HEIGHT = 56;
const PAD = 6;
const MIN_MONTHS = 11; // a one-year window is the tightest that stays readable

type Drag = { kind: "start" | "end" | "window" | "new"; grabbedAt: number; from: number; to: number };

export function RangeBrush({ bounds, value, onChange, series, diverging = false }: Props) {
  const hostRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(880);
  const drag = useRef<Drag | null>(null);

  useEffect(() => {
    const node = hostRef.current;
    if (!node) return;
    const ro = new ResizeObserver(([e]) => setWidth(Math.max(240, e.contentRect.width)));
    ro.observe(node);
    return () => ro.disconnect();
  }, []);

  const lo = monthOrdinal(bounds[0]);
  const hi = monthOrdinal(bounds[1]);
  const x = useMemo(
    () => scaleLinear().domain([lo, hi]).range([PAD, Math.max(PAD + 1, width - PAD)]),
    [lo, hi, width],
  );

  const from = Math.max(lo, Math.min(hi, monthOrdinal(value[0])));
  const to = Math.max(lo, Math.min(hi, monthOrdinal(value[1])));

  const paths = useMemo(() => {
    const inner = HEIGHT - 12;
    const points = series.map((s) =>
      s.months
        .map((m, i) => ({ o: monthOrdinal(m), v: Number(s.values[i]) }))
        .filter((p) => Number.isFinite(p.v)),
    );
    const flat = points.flat();
    if (!flat.length) return [];
    const reach = Math.max(...flat.map((p) => Math.abs(p.v))) || 1;
    const y = scaleLinear().domain([-reach, reach]).range([HEIGHT - 6, HEIGHT - 6 - inner]);
    const gen = d3line<{ o: number; v: number }>().x((p) => x(p.o)).y((p) => y(p.v));
    return points.map((ps, i) => ({
      d: gen(ps) ?? "",
      color: diverging ? "var(--text-primary)" : series[i].color,
      zero: y(0),
    }));
  }, [series, x, diverging]);

  const monthAt = useCallback(
    (clientX: number) => {
      const rect = hostRef.current?.getBoundingClientRect();
      if (!rect) return lo;
      return Math.round(Math.max(lo, Math.min(hi, x.invert(clientX - rect.left))));
    },
    [x, lo, hi],
  );

  const commit = useCallback(
    (a: number, b: number) => {
      const start = Math.max(lo, Math.min(a, b));
      const end = Math.min(hi, Math.max(a, b));
      onChange([ordinalToYyyymm(start), ordinalToYyyymm(end)]);
    },
    [lo, hi, onChange],
  );

  useEffect(() => {
    const move = (e: PointerEvent) => {
      const d = drag.current;
      if (!d) return;
      const at = monthAt(e.clientX);
      if (d.kind === "start") commit(Math.min(at, d.to - MIN_MONTHS), d.to);
      else if (d.kind === "end") commit(d.from, Math.max(at, d.from + MIN_MONTHS));
      else if (d.kind === "new") commit(d.grabbedAt, at);
      else {
        const span = d.to - d.from;
        let start = d.from + (at - d.grabbedAt);
        start = Math.max(lo, Math.min(start, hi - span));
        commit(start, start + span);
      }
    };
    const up = () => {
      drag.current = null;
      document.body.classList.remove(styles.dragging);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
    return () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
  }, [monthAt, commit, lo, hi]);

  const begin = (kind: Drag["kind"]) => (e: React.PointerEvent) => {
    e.preventDefault();
    e.stopPropagation();
    drag.current = { kind, grabbedAt: monthAt(e.clientX), from, to };
    document.body.classList.add(styles.dragging);
  };

  const nudge = (edge: "start" | "end") => (e: React.KeyboardEvent) => {
    const step = e.shiftKey ? 12 : 1;
    let delta = 0;
    if (e.key === "ArrowLeft") delta = -step;
    else if (e.key === "ArrowRight") delta = step;
    else if (e.key === "Home") delta = -9999;
    else if (e.key === "End") delta = 9999;
    else return;
    e.preventDefault();
    if (edge === "start") commit(Math.min(from + delta, to - MIN_MONTHS), to);
    else commit(from, Math.max(to + delta, from + MIN_MONTHS));
  };

  const xa = x(from);
  const xb = x(to);
  const full = from <= lo && to >= hi;

  return (
    <div className={styles.wrap}>
      <div
        ref={hostRef}
        className={styles.track}
        style={{ height: HEIGHT }}
        onPointerDown={begin("new")}
      >
        <svg width={width} height={HEIGHT} className={styles.svg}>
          {paths[0] && (
            <line
              x1={PAD}
              x2={width - PAD}
              y1={paths[0].zero}
              y2={paths[0].zero}
              className={styles.zero}
            />
          )}
          {paths.map((p, i) => (
            <path key={i} d={p.d} fill="none" stroke={p.color} strokeWidth={1.2} opacity={0.85} />
          ))}
          <rect x={0} y={0} width={Math.max(0, xa)} height={HEIGHT} className={styles.mask} />
          <rect
            x={xb}
            y={0}
            width={Math.max(0, width - xb)}
            height={HEIGHT}
            className={styles.mask}
          />
          <rect
            x={xa}
            y={0}
            width={Math.max(1, xb - xa)}
            height={HEIGHT}
            className={styles.window}
            onPointerDown={begin("window")}
          />
        </svg>

        {(["start", "end"] as const).map((edge) => (
          <div
            key={edge}
            role="slider"
            tabIndex={0}
            aria-label={edge === "start" ? "Window start" : "Window end"}
            aria-valuemin={bounds[0]}
            aria-valuemax={bounds[1]}
            aria-valuenow={edge === "start" ? value[0] : value[1]}
            aria-valuetext={formatMonth(edge === "start" ? value[0] : value[1])}
            className={styles.handle}
            style={{ left: (edge === "start" ? xa : xb) - 5 }}
            onPointerDown={begin(edge)}
            onKeyDown={nudge(edge)}
          >
            <span className={styles.grip} />
          </div>
        ))}
      </div>

      <div className={styles.legend}>
        <span>{formatMonth(bounds[0])}</span>
        <span className={styles.selection}>
          {full ? "Full sample" : `${formatMonth(value[0])} – ${formatMonth(value[1])}`}
          <span className={styles.hint}>drag the handles, or the shaded window</span>
        </span>
        <span>{formatMonth(bounds[1])}</span>
      </div>
    </div>
  );
}
