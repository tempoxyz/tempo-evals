"""Verifier scenario for tempo/mpp-server-charge-pathusd-usdc.

The shared MPP verifier harness lives in client_lib.py (synced from
shared/mpp/ by scripts/sync_shared.py); this file holds only the
task-specific checks.
"""

import subprocess

import client_lib as lib


async def run_task(process: subprocess.Popen[str]) -> dict:
    out = lib.read_out_json(process, ["freeUrl", "paidUrl"])
    return {
        "out": out,
        "free": lib.free_request(out["freeUrl"]),
        "offer": lib.challenge_request(
            out["paidUrl"],
            {
                "pathUsdAdvertised": lib.TOKEN,
                "usdcAdvertised": lib.USDC,
            },
        ),
        "paid": await lib.paid_request(out["paidUrl"]),
    }


if __name__ == "__main__":
    lib.run(run_task)
