export type SeriesKind = "wedge" | "percentile" | "level";

export interface SeriesMeta {
  id: string;
  kind: SeriesKind;
  label: string;
  decimals: number;
}

export interface FirmIndex {
  months: number[]; // yyyymm, ascending
  series: SeriesMeta[];
  bytesPerValue: number;
  dtype: "float32-le";
  recordFields: ["permno", "t0", "t1", "shard", "offset"];
  records: [number, number, number, number, number][];
  hasNames: boolean;
  names: Record<string, { name?: string; ticker?: string }>;
}

export interface SpecMeta {
  id: string;
  label: string;
  short: string;
  mapping: "pc3" | "ff5";
  level: "equity" | "firm";
  sample: "full" | "oos";
  default: boolean;
}

export interface CharacteristicMeta {
  id: string;
  source: string;
  label: string;
  group: string;
}

export interface Manifest {
  dataVersion: string;
  vintage: string;
  citation: {
    title: string;
    authors: string[];
    journal: string;
    url: string;
  };
  firm: {
    specs: SpecMeta[];
    mappingNotes: Record<string, string>;
    levelNotes: Record<string, string>;
    sampleNotes: Record<string, string>;
    characteristics: CharacteristicMeta[];
    levels: { id: string; label: string; decimals: number }[];
    timing: string;
    securities: number;
    shards: number;
    bytes: number;
    series: string[];
    namesAttached: boolean;
  };
  portfolio: {
    horizonMonths: number;
    eventYears: number[];
    characteristics: string[];
    treatments: Record<string, string>;
    cohorts: Record<string, number>;
  };
  downloads: {
    dataset: string;
    file: string;
    bytes: number;
    rows: number;
    /** Absolute when the bundle is hosted off-site, relative otherwise. */
    url: string;
    oversize: boolean;
    external: boolean;
  }[];
}

/** One security's estimates, already trimmed to its observed window. */
export interface FirmRecord {
  permno: number;
  name?: string;
  ticker?: string;
  /** yyyymm for each column of every series. */
  months: number[];
  /** series id -> values aligned with `months`, NaN where unobserved. */
  series: Map<string, Float32Array>;
}

export interface SecurityRef {
  permno: number;
  name?: string;
  ticker?: string;
  start: number;
  end: number;
}
