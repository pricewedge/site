#!/usr/bin/env python3
"""One-time WRDS setup: asks for your credentials, stores them, checks they work.

Run it once. Afterwards every refresh runs unattended.

Your password is written only to `~/.pgpass`, the file Postgres reads
credentials from, with permissions that make it readable by you alone. It is
not stored anywhere else, not printed, and not committed.
"""

from __future__ import annotations

import getpass
import os
import stat
import sys
from pathlib import Path

HOST = "wrds-pgdata.wharton.upenn.edu"
PORT = 9737
DB = "wrds"
PGPASS = Path.home() / ".pgpass"


def store(username: str, password: str) -> None:
    line = f"{HOST}:{PORT}:{DB}:{username}:{password}"
    existing = []
    if PGPASS.exists():
        existing = [
            l for l in PGPASS.read_text().splitlines()
            if l.strip() and not l.startswith(f"{HOST}:{PORT}:{DB}:")
        ]
    PGPASS.write_text("\n".join(existing + [line]) + "\n")
    PGPASS.chmod(stat.S_IRUSR | stat.S_IWUSR)   # 600; Postgres refuses anything looser


def main() -> int:
    print("WRDS setup for the price wedge pipeline")
    print("=" * 46)
    print("Your WRDS username is the one you log in to wrds-www.wharton.upenn.edu with.\n")

    username = input("WRDS username: ").strip()
    if not username:
        print("No username given; nothing changed.")
        return 1
    password = getpass.getpass("WRDS password (typing is hidden): ")
    if not password:
        print("No password given; nothing changed.")
        return 1

    store(username, password)
    print(f"\nSaved to {PGPASS} (readable only by you).")

    print("Connecting…")
    try:
        import wrds

        db = wrds.Connection(wrds_username=username)
    except Exception as exc:  # noqa: BLE001 - the message is what helps
        print(f"\nCould not connect: {exc}")
        print("\nMost likely causes:")
        print("  - username or password mistyped (re-run this script)")
        print("  - your WRDS account is not yet approved by Rochester's representative")
        return 1

    print("Connected.\n")

    # Remember the username for later runs so nothing has to be typed again.
    profile = Path.home() / ".zshrc"
    marker = "export WRDS_USERNAME="
    text = profile.read_text() if profile.exists() else ""
    if marker not in text:
        with profile.open("a") as fh:
            fh.write(f'\n# price wedge pipeline\n{marker}"{username}"\n')
        print(f"Recorded your username in {profile} for future sessions.")

    os.environ["WRDS_USERNAME"] = username
    print("\nNow reporting what your subscription exposes:\n")
    from pwsite.wrds_source import discover

    discover(db)
    print("\nDone — copy everything above this line back into the chat.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
