"""Seeds the same baseline/candidate regression scenario as run_demo_comparison.py,
but into Postgres for the docker-compose stack rather than an in-process store.

Doesn't serve the API itself - the api service in docker-compose.yml already does
that. Run this once after bringing the stack up; re-running it just adds another
baseline/candidate run pair rather than erroring, so it's not wired in as an
automatic compose service.

Usage:
    docker compose up -d
    docker compose run --rm api python scripts/seed_demo_data.py
"""

from __future__ import annotations

import asyncio

from app.postgres_store import PostgresStore
from scripts._demo_scenario import seed


async def main() -> None:
    store = PostgresStore()
    baseline_run_id, candidate_run_id = await seed(store)

    print(f"Baseline run:   {baseline_run_id}")
    print(f"Candidate run:  {candidate_run_id}")
    print(f"Comparison API: http://localhost:8000/api/v1/comparisons/{baseline_run_id}/{candidate_run_id}")


if __name__ == "__main__":
    asyncio.run(main())
