"""Verifier scenario for tempo/mpp-server-charge-pathusd.

The shared MPP verifier harness lives in tempo_bench_rewardkit.mpp.client_lib
(baked into the base image); this file holds only the task-specific checks.
"""

import subprocess

from tempo_bench_rewardkit.mpp import client_lib as lib


async def run_task(process: subprocess.Popen[str]) -> dict:
    out = lib.read_out_json(process, ["freeUrl", "paidUrl"])
    return {
        "out": out,
        "free": lib.free_request(out["freeUrl"]),
        "paid": await lib.paid_request(out["paidUrl"]),
    }


if __name__ == "__main__":
    lib.run(run_task)
