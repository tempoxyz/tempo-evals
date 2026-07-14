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
    currency_options = lib.run_node_script(
        "currency-options-client",
        "currency_options_client.ts",
        env={
            "MPPX_RPC_URL": lib.RPC_URL,
            "TEMPO_MPP_PAID_URL": out["paidUrl"],
            "TEMPO_MPP_PAYER_PRIVATE_KEY": lib.PAYER_PRIVATE_KEY,
        },
    )
    payer = currency_options.get("payer")
    paid = currency_options.get("paid")
    if not isinstance(payer, str) or not isinstance(paid, dict):
        raise RuntimeError("currency options client did not report a payment")
    reference = paid.get("receiptReference")
    if not isinstance(reference, str):
        raise RuntimeError("currency options client did not report a receipt reference")

    return {
        "out": out,
        "free": lib.free_request(out["freeUrl"]),
        "currencyOptions": currency_options,
        "paid": lib.payment_transaction(reference, payer),
    }


if __name__ == "__main__":
    lib.run(run_task)
