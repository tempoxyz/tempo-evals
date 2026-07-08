"""Verifier scenario for tempo/mpp-server-mcp-pathusd.

The shared MPP verifier harness lives in client_lib.py (synced from
shared/mpp/ by scripts/sync_shared.py); this file holds only the
task-specific checks.
"""

import json
import subprocess

import client_lib as lib


async def run_task(process: subprocess.Popen[str]) -> dict:
    urls = lib.read_out_json(process, ["mcpUrl"])
    out = json.loads(lib.OUT_PATH.read_text(encoding="utf-8"))
    free_tool = out.get("freeTool")
    paid_tool = out.get("paidTool")
    if not isinstance(free_tool, str) or not isinstance(paid_tool, str):
        raise RuntimeError("out.json must include freeTool and paidTool strings")

    payer = lib.TempoAccount.from_key(lib.PAYER_PRIVATE_KEY)
    lib.fund_account(payer.address)
    mcp = lib.run_node_script(
        "mcp-client",
        "mcp_client.ts",
        env={
            "MPPX_RPC_URL": lib.RPC_URL,
            "TEMPO_MPP_CHAIN_ID": str(lib.CHAIN_ID),
            "TEMPO_MPP_FREE_TOOL": free_tool,
            "TEMPO_MPP_MCP_URL": urls["mcpUrl"],
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
