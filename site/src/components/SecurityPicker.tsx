import { useEffect, useMemo, useRef, useState } from "react";
import type { SecurityRef } from "../lib/types";
import { searchSecurities } from "../lib/store";
import { formatMonth } from "../lib/format";
import styles from "./SecurityPicker.module.css";

interface Props {
  all: SecurityRef[];
  selected: number[];
  colorFor: (securityId: number) => string;
  labelFor: (securityId: number) => string;
  onAdd: (securityId: number) => void;
  onRemove: (securityId: number) => void;
  max: number;
  hasNames: boolean;
}

export function SecurityPicker({
  all,
  selected,
  colorFor,
  labelFor,
  onAdd,
  onRemove,
  max,
  hasNames,
}: Props) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [cursor, setCursor] = useState(0);
  const boxRef = useRef<HTMLDivElement>(null);

  const results = useMemo(
    () => searchSecurities(all, query).filter((r) => !selected.includes(r.id)),
    [all, query, selected],
  );

  useEffect(() => setCursor(0), [query]);

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (!boxRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  const commit = (securityId: number) => {
    onAdd(securityId);
    setQuery("");
    setOpen(false);
  };

  const full = selected.length >= max;

  return (
    <div className={styles.wrap} ref={boxRef}>
      <label className={styles.label} htmlFor="security-search">
        {hasNames ? "Company or ticker" : "CRSP PERMNO"}
      </label>

      <div className={styles.inputRow}>
        <svg className={styles.icon} viewBox="0 0 16 16" aria-hidden="true">
          <circle cx="7" cy="7" r="4.75" fill="none" stroke="currentColor" strokeWidth="1.5" />
          <path d="M10.5 10.5 L14 14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
        <input
          id="security-search"
          className={styles.input}
          type="search"
          autoComplete="off"
          spellCheck={false}
          disabled={full}
          placeholder={
            full
              ? `Remove a security to add another (max ${max})`
              : hasNames
                ? "e.g. Apple, AAPL"
                : "e.g. 14593"
          }
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") {
              e.preventDefault();
              setCursor((c) => Math.min(c + 1, results.length - 1));
            } else if (e.key === "ArrowUp") {
              e.preventDefault();
              setCursor((c) => Math.max(c - 1, 0));
            } else if (e.key === "Enter" && results[cursor]) {
              e.preventDefault();
              commit(results[cursor].id);
            } else if (e.key === "Escape") {
              setOpen(false);
            }
          }}
          role="combobox"
          aria-expanded={open && results.length > 0}
          aria-controls="security-results"
          aria-autocomplete="list"
        />
      </div>

      {open && query.trim() && (
        <ul className={styles.results} id="security-results" role="listbox">
          {results.length === 0 && <li className={styles.empty}>No match in the panel.</li>}
          {results.map((r, i) => (
            <li key={r.id}>
              <button
                type="button"
                role="option"
                aria-selected={i === cursor}
                className={`${styles.result} ${i === cursor ? styles.resultActive : ""}`}
                onMouseEnter={() => setCursor(i)}
                onClick={() => commit(r.id)}
              >
                <span className={styles.resultName}>
                  {r.name ?? `PERMNO ${r.id}`}
                  {r.ticker && <span className={styles.resultTicker}>{r.ticker}</span>}
                </span>
                <span className={styles.resultRange}>
                  {formatMonth(r.start)} – {formatMonth(r.end)}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}

      {selected.length > 0 && (
        <ul className={styles.chips}>
          {selected.map((securityId) => (
            <li key={securityId} className={styles.chip}>
              <span className={styles.chipDot} style={{ background: colorFor(securityId) }} />
              <span className={styles.chipLabel}>{labelFor(securityId)}</span>
              <button
                type="button"
                className={styles.chipRemove}
                onClick={() => onRemove(securityId)}
                aria-label={`Remove ${labelFor(securityId)}`}
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
