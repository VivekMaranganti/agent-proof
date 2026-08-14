"""Seeds a baseline/candidate run pair with a real regression and serves the platform API.

Runs three seeded support tasks through the actual runner for both a "baseline" and
a "candidate" agent version. The candidate is scripted to skip the refund step on one
task, producing a genuine regression the /api/v1/comparisons endpoint can attribute.
Uses the in-memory PlatformStore, so no Postgres/Docker is required — this is for
exercising the comparison API and the frontend against it locally, not a persistence
demo (see scripts/run_demo_task.py for that, or scripts/seed_demo_data.py for the
Postgres-backed version of this same scenario against the docker-compose stack).

Usage:
    PYTHONPATH=".:backend" python scripts/run_demo_comparison.py
    # then, in frontend/: npm run dev
"""

from __future__ import annotations

import asyncio

import uvicorn

from app.main import create_app
from app.store import PlatformStore
from scripts._demo_scenario import seed


def main() -> None:
    store = PlatformStore()
    app = create_app(store=store)

    baseline_run_id, candidate_run_id = asyncio.run(seed(store))

    print(f"Baseline run:   {baseline_run_id}")
    print(f"Candidate run:  {candidate_run_id}")
    print(f"Comparison API: http://127.0.0.1:8000/api/v1/comparisons/{baseline_run_id}/{candidate_run_id}")
    print("Point the frontend dev server's inputs at the two run IDs above.")

    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")


if __name__ == "__main__":
    main()
