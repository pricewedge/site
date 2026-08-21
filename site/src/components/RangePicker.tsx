import { formatMonth } from "../lib/format";
import styles from "./SpecPicker.module.css";

const PRESETS = [10, 20, 30] as const;

export function RangePicker({
  bounds,
  value,
  onChange,
  onReset,
}: {
  bounds: [number, number] | null;
  value: [number, number] | null;
  onChange: (range: [number, number]) => void;
  onReset: () => void;
}) {
  if (!bounds) {
    return (
      <div className={styles.wrap}>
        <span className={styles.label}>Time window</span>
        <p className={styles.note}>Select a security to set a window.</p>
      </div>
    );
  }

  const [lo, hi] = bounds;
  const setYears = (years: number) => {
    const start = Math.max(lo, hi - years * 100);
    onChange([start, hi]);
  };
  const isFull = !value || (value[0] === lo && value[1] === hi);

  return (
    <div className={styles.wrap}>
      <span className={styles.label} id="range-label">
        Time window
      </span>
      <div className={styles.groups} role="group" aria-labelledby="range-label">
        <div className={styles.toggle}>
          <button
            type="button"
            className={styles.toggleButton}
            aria-pressed={isFull}
            onClick={onReset}
          >
            Full
          </button>
          {PRESETS.map((years) => (
            <button
              key={years}
              type="button"
              className={styles.toggleButton}
              aria-pressed={
                !isFull && value !== null && value[0] === Math.max(lo, hi - years * 100)
              }
              onClick={() => setYears(years)}
            >
              {years}y
            </button>
          ))}
        </div>
        <div className={styles.dates}>
          <MonthInput
            label="From"
            value={value?.[0] ?? lo}
            min={lo}
            max={value?.[1] ?? hi}
            onChange={(v) => onChange([v, value?.[1] ?? hi])}
          />
          <span className={styles.dateSep}>–</span>
          <MonthInput
            label="To"
            value={value?.[1] ?? hi}
            min={value?.[0] ?? lo}
            max={hi}
            onChange={(v) => onChange([value?.[0] ?? lo, v])}
          />
        </div>
      </div>
      <p className={styles.note}>
        Observed {formatMonth(lo)} – {formatMonth(hi)}.
      </p>
    </div>
  );
}

const MONTHS = [
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
];

/** A native <input type="month"> renders its own label -- "December 2017" -- in
 *  a format the page cannot override, and that is wide enough to overflow the
 *  control panel. Two small selects give the same precision in a third of the
 *  width, with month names we control. */
function MonthInput({
  label,
  value,
  min,
  max,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  onChange: (value: number) => void;
}) {
  const year = Math.floor(value / 100);
  const month = value % 100;
  const years: number[] = [];
  for (let y = Math.floor(min / 100); y <= Math.floor(max / 100); y += 1) years.push(y);

  const clamp = (v: number) => Math.max(min, Math.min(max, v));

  return (
    <span className={styles.dateField}>
      <span className="visually-hidden">{label}</span>
      <select
        className={styles.dateSelect}
        aria-label={`${label} month`}
        value={month}
        onChange={(e) => onChange(clamp(year * 100 + Number(e.target.value)))}
      >
        {MONTHS.map((name, i) => {
          const candidate = year * 100 + i + 1;
          return (
            <option key={name} value={i + 1} disabled={candidate < min || candidate > max}>
              {name}
            </option>
          );
        })}
      </select>
      <select
        className={`${styles.dateSelect} ${styles.dateYear}`}
        aria-label={`${label} year`}
        value={year}
        onChange={(e) => onChange(clamp(Number(e.target.value) * 100 + month))}
      >
        {years.map((y) => (
          <option key={y} value={y}>
            {y}
          </option>
        ))}
      </select>
    </span>
  );
}
