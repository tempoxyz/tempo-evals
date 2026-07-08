"""Verifier scenario for tempo/mpp-server-discovery-endpoint.

The shared MPP verifier harness lives in client_lib.py (synced from
shared/mpp/ by scripts/sync_shared.py); this file holds only the
task-specific checks.
"""

import subprocess
from urllib.parse import urlparse

import client_lib as lib


async def run_task(process: subprocess.Popen[str]) -> dict:
    out = lib.read_out_json(process, ["paidUrl", "openapiUrl"])
    paid_path = urlparse(out["paidUrl"]).path
    return {
        "out": out,
        "discovery": lib.discovery_request(out["openapiUrl"], paid_path),
        "offer": lib.challenge_request(
            out["paidUrl"],
            {"pathUsdAdvertised": lib.TOKEN, "chargeAdvertised": "charge"},
        ),
        "paid": await lib.paid_request(out["paidUrl"]),
    }


if __name__ == "__main__":
    lib.run(run_task)
