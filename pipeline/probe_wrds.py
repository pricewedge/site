#!/usr/bin/env python3
"""Report what this WRDS subscription exposes, so the pulls can be written
against the real schema rather than an assumed one.

    export WRDS_USERNAME=yourusername
    ./.venv/bin/python probe_wrds.py

Reads nothing but table metadata and a handful of rows. Downloads no data and
writes no files.
"""

from __future__ import annotations

import sys

from pwsite.wrds_source import MissingCredentials, connect, discover


def main() -> int:
    try:
        db = connect()
    except MissingCredentials as exc:
        print(exc)
        return 1
    except Exception as exc:  # noqa: BLE001 - the message is the useful part
        print(f"Could not connect: {exc}")
        print("\nIf this is an authentication failure, check ~/.pgpass has a line:")
        print("  wrds-pgdata.wharton.upenn.edu:9737:wrds:USERNAME:PASSWORD")
        print("and that the file is chmod 600.")
        return 1

    print("connected\n")
    print("tables this subscription exposes:")
    found = discover(db)

    print("\nsanity checks:")
    monthly = found["crsp_monthly"].name
    if monthly:
        span = db.raw_sql(f"select min(date) as first, max(date) as last from {monthly}")
        print(f"  {monthly}: {span.iloc[0]['first']} -> {span.iloc[0]['last']}")
    annual = found["compustat_annual"].name
    if annual:
        span = db.raw_sql(f"select min(datadate) as first, max(datadate) as last from {annual}")
        print(f"  {annual}: {span.iloc[0]['first']} -> {span.iloc[0]['last']}")

    daily = found["crsp_daily"].name
    if daily:
        print(f"\n  daily file present ({daily}); checking which spread inputs it carries")
        cols = set(found["crsp_daily"].columns)
        for group, needed in [
            ("high/low", {"askhi", "bidlo"}),
            ("quoted bid/ask", {"bid", "ask"}),
            ("turnover inputs", {"vol", "shrout"}),
        ]:
            have = needed & cols
            print(f"    {group:18} {'yes' if have == needed else 'partial/no'}  ({sorted(have)})")

    print("\nDone. Paste this output back and the pulls get written against it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
