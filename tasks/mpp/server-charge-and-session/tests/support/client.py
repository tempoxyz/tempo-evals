"""Verifier scenario for tempo/mpp-server-charge-and-session.

The shared MPP verifier harness lives in tempo_bench_rewardkit.mpp.client_lib
(installed in the verifier image); this file holds only the task-specific checks.
"""

import subprocess

from tempo_bench_rewardkit.mpp import client_lib as lib


async def run_task(process: subprocess.Popen[str]) -> dict:
    out = lib.read_out_json(
        process,
        {"chargeUrl": str, "sessionUrl": str},
        {"chargeUrl", "sessionUrl"},
    )
    return {
        "out": out,
        "chargeOffer": lib.challenge_request(
            out["chargeUrl"],
            {"method": "tempo", "intent": "charge", "currency": lib.TOKEN},
        ),
        "sessionOffer": lib.challenge_request(
            out["sessionUrl"],
            {"method": "tempo", "intent": "session", "currency": lib.TOKEN},
        ),
        "charge": await lib.paid_request(out["chargeUrl"]),
        "session": lib.session_request(out["sessionUrl"]),
    }


if __name__ == "__main__":
    lib.run(run_task)
