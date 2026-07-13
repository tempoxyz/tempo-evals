"""Verifier scenario for tempo/mpp-server-charge-pathusd-usdc.

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
    return {
        "out": out,
        "free": lib.free_request(out["freeUrl"]),
        "currencyOptions": lib.run_node_script(
            "currency-options-client",
            "currency_options_client.ts",
            env={
                "MPPX_RPC_URL": lib.RPC_URL,
                "TEMPO_MPP_PAID_URL": out["paidUrl"],
                "TEMPO_MPP_PAYER_PRIVATE_KEY": lib.PAYER_PRIVATE_KEY,
            },
        ),
    }


if __name__ == "__main__":
    lib.run(run_task)
