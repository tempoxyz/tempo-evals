"""Verifier scenario for tempo/mpp-server-x402-mpp-charges.

The shared MPP verifier harness lives in tempo_bench_rewardkit.mpp.client_lib
(baked into the base image); this file holds only the task-specific checks.
"""

import subprocess

from tempo_bench_rewardkit.mpp import client_lib as lib


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
