"""Verifier scenario for tempo/mpp-server-discovery-endpoint.

The shared MPP verifier harness lives in tempo_bench_rewardkit.mpp.client_lib
(installed in the verifier image); this file holds only the task-specific checks.
"""

import subprocess
from urllib.parse import urlparse

from tempo_bench_rewardkit.mpp import client_lib as lib


async def run_task(process: subprocess.Popen[str]) -> dict:
    out = lib.read_out_json(
        process,
        {"paidUrl": str, "openapiUrl": str},
        {"paidUrl", "openapiUrl"},
    )
    paid_path = urlparse(out["paidUrl"]).path
    return {
        "out": out,
        "discovery": lib.discovery_request(out["openapiUrl"], paid_path),
        "offer": lib.challenge_request(
            out["paidUrl"],
            {"method": "tempo", "intent": "charge", "currency": lib.TOKEN},
        ),
        "paid": await lib.paid_request(out["paidUrl"]),
    }


if __name__ == "__main__":
    lib.run(run_task)
