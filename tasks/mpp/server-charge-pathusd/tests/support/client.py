"""Verifier scenario for tempo/mpp-server-charge-pathusd.

The shared MPP verifier harness lives in stable_bench_rewardkit.mpp.client_lib
(installed in the verifier image); this file holds only the task-specific checks.
"""

import subprocess

from stable_bench_rewardkit.mpp import client_lib as lib


async def run_task(process: subprocess.Popen[str]) -> dict:
    out = lib.read_out_json(
        process,
        {"freeUrl": str, "paidUrl": str},
        {"freeUrl", "paidUrl"},
    )
    return {
        "out": out,
        "free": lib.free_request(out["freeUrl"]),
        "paid": await lib.paid_request(out["paidUrl"]),
    }


if __name__ == "__main__":
    lib.run(run_task)
