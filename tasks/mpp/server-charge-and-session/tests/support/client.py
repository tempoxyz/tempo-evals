"""Verifier scenario for tempo/mpp-server-charge-and-session.

The shared MPP verifier harness lives in client_lib.py (synced from
shared/mpp/ by scripts/sync_shared.py); this file holds only the
task-specific checks.
"""

import subprocess

import client_lib as lib


async def run_task(process: subprocess.Popen[str]) -> dict:
    out = lib.read_out_json(process, ["chargeUrl", "sessionUrl"])
    return {
        "out": out,
        "chargeOffer": lib.challenge_request(
            out["chargeUrl"],
            {"pathUsdAdvertised": lib.TOKEN, "chargeAdvertised": "charge"},
        ),
        "sessionOffer": lib.challenge_request(
            out["sessionUrl"],
            {"pathUsdAdvertised": lib.TOKEN, "sessionAdvertised": "session"},
        ),
        "charge": await lib.paid_request(out["chargeUrl"]),
        "session": lib.session_request(out["sessionUrl"]),
    }


if __name__ == "__main__":
    lib.run(run_task)
