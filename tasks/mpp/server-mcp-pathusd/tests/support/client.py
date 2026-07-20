"""Verifier scenario for tempo/mpp-server-mcp-pathusd.

The shared MPP verifier harness lives in stable_bench_rewardkit.mpp.client_lib
(installed in the verifier image); this file holds only the task-specific checks.
"""

import subprocess

from stable_bench_rewardkit.mpp import client_lib as lib


async def run_task(process: subprocess.Popen[str]) -> dict:
    out = lib.read_out_json(
        process,
        {"mcpUrl": str, "freeTool": str, "paidTool": str},
        {"mcpUrl"},
    )
    free_tool = out["freeTool"]
    paid_tool = out["paidTool"]

    payer = lib.TempoAccount.from_key(lib.PAYER_PRIVATE_KEY)
    lib.fund_account(payer.address)
    mcp = lib.run_node_script(
        "mcp-client",
        "mcp_client.ts",
        env={
            "MPPX_RPC_URL": lib.RPC_URL,
            "TEMPO_MPP_CHAIN_ID": str(lib.CHAIN_ID),
            "TEMPO_MPP_FREE_TOOL": free_tool,
            "TEMPO_MPP_MCP_URL": out["mcpUrl"],
            "TEMPO_MPP_PAID_TOOL": paid_tool,
            "TEMPO_MPP_PAYER_PRIVATE_KEY": lib.PAYER_PRIVATE_KEY,
        },
        timeout=180,
    )
    return {
        "out": out,
        **mcp,
    }


if __name__ == "__main__":
    lib.run(run_task)
