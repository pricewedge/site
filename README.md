# pricewedge.com

**Live at [pricewedge.com](https://pricewedge.com).** Data releases at
[github.com/pricewedge/data](https://github.com/pricewedge/data/releases).

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

The replication package is licensed CRSP-derived data and is not in this
repository. Tell the pipeline where it is, once per machine:

```bash
echo "/path/to/JFE_final/ReplicationPackage" > pipeline/.source-path
```

`PRICEWEDGE_SOURCE` in the environment overrides that file. Change the output
directory with `PRICEWEDGE_OUT` or `--out`.

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

The binary shards exist so the browser never downloads the whole panel.

On a host that honours HTTP range requests, selecting a security costs one
request of about 8 KB. **Cloudflare Pages does not honour them** — it advertises
`accept-ranges: bytes` and then returns 200 with the entire file — so the client
checks the response status and, on a 200, indexes from the record's offset into
the full body. Reading it as though the body started at the offset silently
plots a *different* security's numbers, which is why the status is checked
rather than assumed.

Shards are therefore capped near 1 MiB rather than as large as the platform
allows: that is the per-security cost on a host without range support, and
immutable caching makes repeat securities in the same shard free. R2, S3 and
nginx do support ranges and fall back to the 8 KB path automatically.

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

# The download bundles live in a GitHub release, not on Pages: two of them
# exceed the 25 MiB per-file cap. Ship only what the explorer reads.
rm -rf dist/data && mkdir -p dist/data
cp ../data/manifest.json ../data/portfolios.json dist/data/
cp -R ../data/firms dist/data/firms

npx wrangler pages project create pricewedge --production-branch=main   # first time only
npx wrangler pages deploy dist --project-name pricewedge --branch main
```

Rebuild the data with `PRICEWEDGE_DOWNLOAD_BASE` set to the release URL first,
or the data page will link at files that are not deployed:

```bash
PRICEWEDGE_DOWNLOAD_BASE=https://github.com/pricewedge/data/releases/download/v1.0.0 \
  python build.py
```

**Verify a redeploy by reading numbers off the page, not by trusting the deploy
message.** A wrong-offset read renders plausible but incorrect estimates with no
error. Apple (PERMNO 14593) should show a latest wedge of +10.9% for Dec 2017
and a largest of +40.5% for Jan 2010 under the default specification.

`site/public/_headers` sets immutable caching on the shards and downloads and a
short TTL on the manifest. `site/public/_redirects` sends unknown paths to
`index.html` so client-side routes survive a reload.

Constraints worth knowing about Pages: 25 MiB per file, 20,000 files per
deployment, and no HTTP range support. The current vintage is 151 shards of
1 MiB plus about 50 site assets, so the file limits are comfortable.

Moving `data/` to Cloudflare R2 behind `data.pricewedge.com` and setting
`VITE_DATA_BASE` restores real range requests and drops the per-security cost
from ~1 MB to ~8 KB. Nothing else changes.

## Operational notes

Things that were not obvious the first time and cost real time:

- **Cloudflare Pages ignores HTTP range requests** (see above). This is the one
  that silently corrupts output rather than failing loudly.
- **`wrangler pages deploy` does not create the project.** Run
  `wrangler pages project create` once first.
- **Adding a custom domain through the API does not create the DNS record.**
  The dashboard does both; the API only registers the domain with the project.
  Add `CNAME @ -> pricewedge.pages.dev` and `CNAME www -> pricewedge.pages.dev`,
  both proxied, by hand.
- **Delete the registrar's old records** when importing a zone. An `A` record
  left at the apex silently wins over the CNAME you meant to use, and the site
  keeps serving the old host.
- **Your own resolver will lie to you** for up to an hour after a DNS change.
  Verify with `curl --resolve pricewedge.com:443:<cloudflare-ip>` rather than
  trusting a plain request.

## Still to do

- `www` -> apex redirect rule (Cloudflare dashboard; both hostnames currently
  serve the site, with `rel=canonical` pointing search engines at the apex)
- SPF / DMARC / null-MX records, so the domain cannot be used to spoof mail
- Re-enable DNSSEC on Cloudflare's keys
- Optionally move `data/` to R2 for true range requests

## Updating the estimates

Vintages are additive. Bump `VINTAGE` and `DATA_VERSION` in
`pipeline/pwsite/config.py`, rebuild, and publish the new download files
alongside the old ones so existing citations keep resolving.
