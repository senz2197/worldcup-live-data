from __future__ import annotations

import argparse

from app import main as run_app
from data_provider import DataProvider


def smoke_test() -> None:
    provider = DataProvider()
    snapshot = provider.load_all(force=False)
    print(f"matches={len(snapshot.matches)} teams={len(snapshot.teams)} groups={len(snapshot.standings)} boards={len(snapshot.leaderboards)}")
    live = sum(1 for match in snapshot.matches if match.is_live)
    upcoming = sum(1 for match in snapshot.matches if match.is_upcoming)
    completed = sum(1 for match in snapshot.matches if match.completed)
    print(f"live={live} upcoming={upcoming} completed={completed}")
    if snapshot.errors:
        print("warnings:")
        for error in snapshot.errors:
            print(f"- {error}")


def main() -> None:
    parser = argparse.ArgumentParser(description="WorldCup Float desktop score widget")
    parser.add_argument("--smoke-test", action="store_true", help="Fetch and parse data without opening the UI")
    args = parser.parse_args()
    if args.smoke_test:
        smoke_test()
    else:
        run_app()


if __name__ == "__main__":
    main()
