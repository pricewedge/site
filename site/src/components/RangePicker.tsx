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
  const toIso = (yyyymm: number) =>
    `${Math.floor(yyyymm / 100)}-${String(yyyymm % 100).padStart(2, "0")}`;

  return (
    <label className={styles.dateField}>
      <span className="visually-hidden">{label}</span>
      <input
        type="month"
        className={styles.dateInput}
        value={toIso(value)}
        min={toIso(min)}
        max={toIso(max)}
        onChange={(e) => {
          const [y, m] = e.target.value.split("-").map(Number);
          if (y && m) onChange(y * 100 + m);
        }}
      />
    </label>
  );
}
