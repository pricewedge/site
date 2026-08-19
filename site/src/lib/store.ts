/** Loading estimates.
 *
 * The index (one entry per security) is fetched once. Individual securities are
 * then read out of the binary shards with a single HTTP range request each —
 * about 8 KB for the average security — so adding a fifth line to a chart costs
 * one small round trip rather than a re-download of the panel.
 */

import type { FirmIndex, FirmRecord, Manifest, SecurityRef } from "./types";

const BASE = (import.meta.env.VITE_DATA_BASE ?? "/data").replace(/\/$/, "");

let manifestPromise: Promise<Manifest> | null = null;
let indexPromise: Promise<FirmIndex> | null = null;

export function loadManifest(): Promise<Manifest> {
  manifestPromise ??= fetch(`${BASE}/manifest.json`).then(failFast).then((r) => r.json());
  return manifestPromise;
}

export function loadFirmIndex(): Promise<FirmIndex> {
  indexPromise ??= fetch(`${BASE}/firms/index.json`).then(failFast).then((r) => r.json());
  return indexPromise;
}

function failFast(response: Response): Response {
  if (!response.ok) throw new Error(`${response.status} ${response.statusText} — ${response.url}`);
  return response;
}

export function securityList(index: FirmIndex): SecurityRef[] {
  return index.records.map(([permno, t0, t1]) => ({
    permno,
    ...index.names[String(permno)],
    start: index.months[t0],
    end: index.months[t1],
  }));
}

const recordCache = new Map<number, Promise<FirmRecord>>();

export function loadSecurity(index: FirmIndex, permno: number): Promise<FirmRecord> {
  const cached = recordCache.get(permno);
  if (cached) return cached;

  const entry = index.records.find((r) => r[0] === permno);
  if (!entry) return Promise.reject(new Error(`PERMNO ${permno} is not in the panel`));

  const [, t0, t1, shard, offset] = entry;
  const span = t1 - t0 + 1;
  const width = span * index.bytesPerValue;
  const bytes = index.series.length * width;

  const promise = fetch(`${BASE}/firms/shard-${String(shard).padStart(2, "0")}.bin`, {
    headers: { Range: `bytes=${offset}-${offset + bytes - 1}` },
  })
    .then(failFast)
    .then((r) => r.arrayBuffer())
    .then((buffer) => {
      if (buffer.byteLength < bytes) {
        throw new Error(
          `Short read for PERMNO ${permno}: the host must honour HTTP range requests.`,
        );
      }
      const series = new Map<string, Float32Array>();
      index.series.forEach((meta, i) => {
        series.set(meta.id, new Float32Array(buffer, i * width, span));
      });
      return {
        permno,
        ...index.names[String(permno)],
        months: index.months.slice(t0, t1 + 1),
        series,
      } satisfies FirmRecord;
    });

  recordCache.set(permno, promise);
  promise.catch(() => recordCache.delete(permno));
  return promise;
}

/** Rank securities for the search box. Exact PERMNO and ticker beat prefix beats substring. */
export function searchSecurities(all: SecurityRef[], query: string, limit = 40): SecurityRef[] {
  const q = query.trim().toUpperCase();
  if (!q) return [];

  const scored: { ref: SecurityRef; score: number }[] = [];
  for (const ref of all) {
    const permno = String(ref.permno);
    const ticker = ref.ticker ?? "";
    const name = (ref.name ?? "").toUpperCase();

    let score = Infinity;
    if (permno === q) score = 0;
    else if (ticker && ticker === q) score = 1;
    else if (ticker.startsWith(q)) score = 2;
    else if (name.startsWith(q)) score = 3;
    else if (permno.startsWith(q)) score = 4;
    else if (name.includes(q)) score = 5;

    if (score < Infinity) scored.push({ ref, score });
  }

  scored.sort((a, b) => a.score - b.score || b.ref.end - a.ref.end || a.ref.permno - b.ref.permno);
  return scored.slice(0, limit).map((s) => s.ref);
}
