"""Verifier scenario for tempo/mpp-client-access-keys.

The shared MPP verifier harness lives in client_lib.py (synced from
shared/mpp/ by scripts/sync_shared.py); this file holds only the
task-specific checks.
"""

import json
import os
import subprocess

import client_lib as lib


def main() -> None:
    oracle_process = None
    try:
        payer = lib.TempoAccount.from_key(lib.PAYER_PRIVATE_KEY)
        lib.fund_account(payer.address)
        oracle_process, oracle = lib.start_oracle_paid_server()

        result = subprocess.run(
            ["npm", "run", "--silent", "run"],
            cwd=lib.WORKSPACE,
            env={
                **os.environ,
                "MPPX_RPC_URL": lib.RPC_URL,
                "PAID_URL": oracle["paidUrl"],
                "TEMPO_MPP_PAYER_PRIVATE_KEY": lib.PAYER_PRIVATE_KEY,
            },
            text=True,
            capture_output=True,
            timeout=180,
            check=False,
        )
        lib.write_json(
            lib.LOG_DIR / "client-run.json",
            {
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            },
        )
        if result.returncode != 0:
            raise RuntimeError(f"client run failed: {result.stderr.strip()}")
        if not lib.OUT_PATH.exists():
            raise RuntimeError("client did not write out.json")

        out = json.loads(lib.OUT_PATH.read_text(encoding="utf-8"))
        if out.get("paidUrl") != oracle["paidUrl"]:
            raise RuntimeError("out.json paidUrl did not match verifier endpoint")
        if out.get("status") != 200:
            raise RuntimeError("client did not receive HTTP 200 from paid endpoint")
        if out.get("json") is not True:
            raise RuntimeError("client did not parse paid JSON response")
        if out.get("hasReceipt") is not True:
            raise RuntimeError("client did not record a payment receipt")
        if out.get("receiptMethod") != "tempo":
            raise RuntimeError("client receipt method was not tempo")
        if out.get("receiptStatus") != "success":
            raise RuntimeError("client receipt was not successful")

        lib.write_scores(
            {
                "reward": 1,
                "oracle": oracle,
                "client": out,
            }
        )
        lib.write_json(lib.LOG_DIR / "details.json", {"ok": True, **out})
    except Exception as exc:
        lib.fail(str(exc))
    finally:
        if oracle_process is not None:
            lib.stop_process_group(oracle_process)


if __name__ == "__main__":
    main()
