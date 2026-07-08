"""Verifier scenario for tempo/mpp-server-x402-mpp-charges.

THE SHARED MPP VERIFIER HARNESS LIVES IN client_lib.py (AUTO-GENERATED FROM
shared/mpp/ BY npm run sync); THIS FILE HOLDS ONLY THE TASK-SPECIFIC CHECKS.
"""

import subprocess

import client_lib as lib


async def run_task(process: subprocess.Popen[str]) -> dict:
    out = lib.read_out_json(process, ["mppPaidUrl", "x402PaidUrl"])
    return {
        "out": out,
        "mppOffer": lib.challenge_request(
            out["mppPaidUrl"],
            {"pathUsdAdvertised": lib.TOKEN, "chargeAdvertised": "charge"},
        ),
        "x402Offer": lib.challenge_request(
            out["x402PaidUrl"],
            {"x402Advertised": "x402", "usdcAdvertised": lib.BASE_USDC},
        ),
        "paid": await lib.paid_request(out["mppPaidUrl"]),
    }


if __name__ == "__main__":
    lib.run(run_task)
