import type { Manifest, SpecMeta } from "../lib/types";
import styles from "./SpecPicker.module.css";

/** Plain-language description of a specification, assembled from the manifest so
 *  the site and the download README always say the same thing. */
export function specNote(manifest: Manifest, spec: SpecMeta): string {
  return [
    manifest.firm.mappingNotes[spec.mapping],
    manifest.firm.levelNotes[spec.level],
    spec.sample === "oos" ? manifest.firm.sampleNotes.oos : null,
  ]
    .filter(Boolean)
    .join(" ");
}

/** The eight published specifications are the cross of three binary choices, so
 *  they are offered as three toggles rather than one eight-item dropdown. */
export function SpecPicker({
  manifest,
  specId,
  onChange,
}: {
  manifest: Manifest;
  specId: string;
  onChange: (id: string) => void;
}) {
  const specs = manifest.firm.specs;
  const current = specs.find((s) => s.id === specId) ?? specs[0];

  const pick = (patch: Partial<Pick<typeof current, "mapping" | "level" | "sample">>) => {
    const want = { ...current, ...patch };
    const match = specs.find(
      (s) => s.mapping === want.mapping && s.level === want.level && s.sample === want.sample,
    );
    if (match) onChange(match.id);
  };

  return (
    <div className={styles.wrap}>
      <span className={styles.label} id="spec-label">
        Specification
      </span>
      <div className={styles.groups} role="group" aria-labelledby="spec-label">
        <Toggle
          options={[
            { value: "equity", label: "Equity" },
            { value: "firm", label: "Firm value" },
          ]}
          value={current.level}
          onChange={(v) => pick({ level: v as "equity" | "firm" })}
        />
        <Toggle
          options={[
            { value: "pc3", label: "3 PCs" },
            { value: "ff5", label: "FF5 + mom" },
          ]}
          value={current.mapping}
          onChange={(v) => pick({ mapping: v as "pc3" | "ff5" })}
        />
        <Toggle
          options={[
            { value: "full", label: "Full sample" },
            { value: "oos", label: "Out of sample" },
          ]}
          value={current.sample}
          onChange={(v) => pick({ sample: v as "full" | "oos" })}
        />
      </div>
    </div>
  );
}

function Toggle({
  options,
  value,
  onChange,
}: {
  options: { value: string; label: string }[];
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div className={styles.toggle}>
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          className={styles.toggleButton}
          aria-pressed={value === option.value}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
