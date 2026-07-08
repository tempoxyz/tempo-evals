"""Verifier scenario for tempo/mpp-server-discovery-endpoint.

THE SHARED MPP VERIFIER HARNESS LIVES IN client_lib.py (AUTO-GENERATED FROM
shared/mpp/ BY npm run sync); THIS FILE HOLDS ONLY THE TASK-SPECIFIC CHECKS.
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
