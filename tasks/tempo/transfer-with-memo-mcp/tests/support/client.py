"""Verifier scenario for tempo/transfer-with-memo.

Shared Moderato helpers live in client_lib.py; this file keeps the
task-specific transaction fixture and proof flow small.
"""

import secrets

import client_lib as lib


def main() -> None:
    try:
        # Fixture setup: isolate each run with a fresh payer and memo.
        payer_key = lib.new_private_key()
        payer = lib.account_from_key(payer_key)
        memo = f"tb-{secrets.token_hex(8)}"
        lib.fund_account(payer.address)

        runtime_env = {
            "TEMPO_AMOUNT": str(lib.AMOUNT),
            "TEMPO_DECIMALS": str(lib.DECIMALS),
            "TEMPO_MEMO": memo,
            "TEMPO_PAYER_PRIVATE_KEY": payer_key,
            "TEMPO_RECIPIENT": lib.RECIPIENT,
            "TEMPO_RPC_URL": lib.RPC_URL,
            "TEMPO_TOKEN": lib.TOKEN,
        }

        # Submission run: execute the user's app with only runtime fixture env.
        submission = lib.run_submission(runtime_env)

        # Artifact read: use /app/out.json as the only transaction locator.
        out = lib.read_transfer_out_json()
        transaction_hash = out["transactionHash"]

        # Transaction fetch and semantic proof: re-read truth from Moderato RPC.
        proof = lib.verify_transfer_with_memo(
            transaction_hash=transaction_hash,
            payer=payer.address,
            recipient=lib.RECIPIENT,
            token=lib.TOKEN,
            amount=lib.AMOUNT,
            decimals=lib.DECIMALS,
            memo=memo,
        )

        # Score write: RewardKit checks this score instead of duplicating RPC logic.
        lib.write_scores(
            {
                "reward": 1,
                "out": out,
                "submission": submission,
                "transaction": proof,
            }
        )
        lib.write_json(lib.LOG_DIR / "details.json", {"ok": True, "transaction": proof})
    except Exception as exc:
        lib.fail(str(exc))


if __name__ == "__main__":
    main()
