# pricewedge.com

Price wedge estimates from Binsbergen, Boons, Opp and Tamoni, "Dynamic Asset
(Mis)Pricing: Build-up versus Resolution Anomalies" (*Journal of Financial
Economics*), published as an interactive explorer and as bulk downloads.

The site computes nothing. A Python pipeline reads the MATLAB replication
package once, writes static artefacts, and the site reads those.

```
pipeline/   Python. Reads the replication package, writes data/.
data/       Generated artefacts. Not in version control; published as releases.
site/       Static site (Vite + React + TypeScript). No backend.
```

## Building the data

```bash
cd pipeline
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python build.py
```

The pipeline looks for the replication package at
`../../Project Folders/JFE/JFE_final/ReplicationPackage`. Point it elsewhere
with `PRICEWEDGE_SOURCE`, and change the output directory with
`PRICEWEDGE_OUT` or `--out`.

It refuses to write anything unless two sets of checks pass:

- **Portfolio.** All 114 published PW★ estimates in Table 1 are reproduced from
  `DataRepIss0` to within 0.05 percentage points. This is a full re-implementation
  of `MainPart2.m` in numpy, so a future re-run against updated CRSP data cannot
  silently move the published numbers.
- **Firm.** The eight cells of `PWshare.mat` are checked against claims in the
  paper: the full-sample and out-of-sample equity wedges must correlate at 0.98
  (Section 4.4), the out-of-sample cells must start in October 1998, and the
  firm-value cells must imply an equity share of firm value inside [0, 1]
  (Eq. 9).

Runtime is about a minute, most of it in the download bundles.

### Output

| Path | What |
|---|---|
| `manifest.json` | Vintage, specification metadata, download inventory. The site's only source of copy about the estimates. |
| `firms/index.json` | One record per security: `[permno, t0, t1, shard, byteOffset]`. |
| `firms/shard-NN.bin` | Float32 series, series-major per security. Read with HTTP range requests. |
| `portfolios.json` | Rebuilt portfolio wedges, all deciles, all horizons, both cash-flow treatments. |
| `downloads/` | Versioned CSV and Parquet bundles plus a README. |

The binary shards exist so the browser never downloads the panel. Selecting a
security costs one range request of about 8 KB. **The host must honour HTTP
range requests** — Cloudflare Pages, R2, S3 and nginx all do; the site raises a
visible error if it gets a 200 with a full body instead of a 206.

### Adding company names

CRSP names and tickers are licensed and ship with nothing in this repository, so
the site searches by PERMNO. To attach them, drop a CSV at
`pipeline/overlays/permno_names.csv` with columns `permno,name,ticker` and
re-run the build. The index picks them up, the search box switches to matching
on name and ticker, and chips and chart labels use the name.

## Running the site

```bash
cd site
npm install
npm run dev        # http://localhost:5173, reads ../data through a symlink
npm run build      # -> site/dist
```

`VITE_DATA_BASE` sets where the estimates are fetched from; it defaults to
`/data`.

## Deploying

The site is static and the data is static, so any CDN works. Cloudflare Pages is
the intended target: free, custom domain, no bandwidth cap, and it serves range
requests.

```bash
cd site && npm run build
cp -R ../data dist/data          # or point VITE_DATA_BASE at a separate host
npx wrangler pages deploy dist --project-name pricewedge
```

`site/public/_headers` sets immutable caching on the shards and downloads and a
short TTL on the manifest. `site/public/_redirects` sends unknown paths to
`index.html` so client-side routes survive a reload.

Two constraints worth knowing about Pages: 25 MiB per file and 20,000 files per
deployment. The pipeline caps shards at 18 MiB, and the current vintage is nine
shards, so both are comfortable. When the panel grows past that, move `data/`
to Cloudflare R2 behind `data.pricewedge.com` and set `VITE_DATA_BASE` — nothing
else changes.

## Updating the estimates

Vintages are additive. Bump `VINTAGE` and `DATA_VERSION` in
`pipeline/pwsite/config.py`, rebuild, and publish the new download files
alongside the old ones so existing citations keep resolving.
