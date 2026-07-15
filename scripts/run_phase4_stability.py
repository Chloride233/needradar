"""Plan or run bounded public-platform collection stability observations."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from needradar.services.phase4_stability import build_plan, execute_plan, write_observations


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("keyword")
    parser.add_argument("--platforms", default="github,stackoverflow,juejin")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--max-items", type=int, default=20)
    parser.add_argument("--output", type=Path, default=Path("evaluation/phase4/stability-observations.json"))
    parser.add_argument("--execute", action="store_true", help="Perform real public-platform requests")
    parser.add_argument("--external-approved", action="store_true", help="Confirm the approved external request scope")
    args = parser.parse_args()

    platforms = [platform.strip() for platform in args.platforms.split(",") if platform.strip()]
    plan = build_plan(args.keyword, platforms, args.runs, args.max_items)
    if not args.execute:
        print(json.dumps({"mode": "dry_run", "plan": plan}, ensure_ascii=False, indent=2))
        return
    if not args.external_approved:
        raise SystemExit("--execute requires --external-approved")

    observations = asyncio.run(execute_plan(plan))
    record = write_observations(plan, observations, args.output)
    print(
        json.dumps(
            {"mode": "executed", "summary": record["summary"], "output": str(args.output)}, ensure_ascii=False, indent=2
        )
    )


if __name__ == "__main__":
    main()
