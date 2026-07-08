"""Verifier scenario for tempo/mpp-server-custom-payment-method.

The shared MPP verifier harness lives in client_lib.py (synced from
shared/mpp/ by scripts/sync_shared.py); this file holds only the
task-specific checks.
"""

import subprocess

import client_lib as lib


async def run_task(process: subprocess.Popen[str]) -> dict:
    out = lib.read_out_json(process, ["freeUrl", "paidUrl"])
    custom = lib.run_node_script(
        "custom-method-client",
        "custom_method_client.ts",
        env={
            "MPP_CUSTOM_ACCESS_KEY": "tempo-bench-access-key",
            "TEMPO_MPP_PAID_URL": out["paidUrl"],
        },
    )
    return {
        "out": out,
        "free": lib.free_request(out["freeUrl"]),
        **custom,
    }


if __name__ == "__main__":
    lib.run(run_task)
