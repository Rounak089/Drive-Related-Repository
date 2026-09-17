"""
Server launcher for the Clinic Front Desk Web Application.
Run: py run_server.py [--port 8000]
"""

from __future__ import annotations

import argparse
import os
import sys

from clinic.policy import CancellationPolicy
from clinic.repository import ClinicRepository
from clinic.seed import seed_clinic_data
from clinic.service import ClinicService
from web.server import create_server


def main():
    parser = argparse.ArgumentParser(description="Launch the Clinic Front Desk Web Portal")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on (default: 8000)")
    parser.add_argument("--host", default="127.0.0.1", help="Host address (default: 127.0.0.1)")
    parser.add_argument("--db", default="clinic.db", help="Path to SQLite database")
    args = parser.parse_args()

    is_new = not os.path.exists(args.db) or os.path.getsize(args.db) == 0
    repo = ClinicRepository(args.db)
    service = ClinicService(repo, CancellationPolicy(cutoff_hours=24.0, late_fee=25.0))

    if is_new:
        print(f"[*] Initializing and seeding new database at '{args.db}'...")
        seed_clinic_data(service)
        print("[*] Database seeded with demo doctors and schedule.")

    server = create_server(service, host=args.host, port=args.port)
    url = f"http://{args.host}:{args.port}"
    print("=" * 65)
    print(" APEX CARE CLINIC — FRONT DESK PORTAL IS RUNNING")
    print("=" * 65)
    print(f" Access Web Dashboard:  {url}")
    print(f" Database File:         {os.path.abspath(args.db)}")
    print(f" Policy:                24h Cancellation Notice, $25.00 Late Fee")
    print(" Press Ctrl+C to stop the server.")
    print("=" * 65)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server gracefully...")
        server.server_close()
        sys.exit(0)


if __name__ == "__main__":
    main()

