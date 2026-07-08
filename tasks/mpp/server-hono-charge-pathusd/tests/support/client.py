"""Verifier scenario for tempo/mpp-server-hono-charge-pathusd.

THE SHARED MPP VERIFIER HARNESS LIVES IN client_lib.py (AUTO-GENERATED FROM
shared/mpp/ BY npm run sync); THIS FILE HOLDS ONLY THE TASK-SPECIFIC CHECKS.
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
            {"pathUsdAdvertised": lib.TOKEN, "chargeAdvertised": "charge"},
        ),
        "paid": await lib.paid_request(out["paidUrl"]),
    }


if __name__ == "__main__":
    lib.run(run_task)
