# Identifier overlays

Drop `permno_names.csv` here to attach CRSP company names and tickers to the
search index:

```csv
permno,name,ticker
14593,APPLE INC,AAPL
10107,MICROSOFT CORP,MSFT
```

`permno` is required; `name` and `ticker` are each optional. Rows for PERMNOs
that are not in the panel are ignored.

The file is gitignored. CRSP identifiers are licensed, so decide deliberately
whether the generated `firms/index.json` may be published with names attached —
if not, run the build without this file and the site falls back to PERMNO
search, which is what it does today.
