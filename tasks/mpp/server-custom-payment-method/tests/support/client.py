"""Verifier scenario for tempo/mpp-server-custom-payment-method.

The shared MPP verifier harness lives in tempo_bench_rewardkit.mpp.client_lib
(baked into the base image); this file holds only the task-specific checks.
"""

import subprocess

from tempo_bench_rewardkit.mpp import client_lib as lib


async def run_task(process: subprocess.Popen[str]) -> dict:
    out = lib.read_out_json(
        process,
        {"freeUrl": str, "paidUrl": str},
        {"freeUrl", "paidUrl"},
    )
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
