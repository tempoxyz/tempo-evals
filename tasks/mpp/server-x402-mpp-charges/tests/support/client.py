"""Verifier scenario for tempo/mpp-server-x402-mpp-charges."""

import json
import os
import subprocess
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from tempo_bench_rewardkit.mpp import client_lib as lib


class FacilitatorHandler(BaseHTTPRequestHandler):
    calls: list[dict] = []

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("content-length", "0"))
        try:
            payload = json.loads(self.rfile.read(length))
            payment = payload["paymentPayload"]
            requirements = payload["paymentRequirements"]
            authorization = payment["payload"]["authorization"]
            if (
                payload["x402Version"] != 2
                or payment["x402Version"] != 2
                or payment["accepted"] != requirements
                or requirements["scheme"] != "exact"
                or requirements["network"] != "eip155:84532"
                or not str(payment["payload"]["signature"]).startswith("0x")
                or authorization["to"].lower() != requirements["payTo"].lower()
            ):
                raise ValueError("invalid x402 facilitator request")
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            self.send_error(400, str(exc))
            return

        self.calls.append({"path": self.path, "payment": payment})
        response = (
            {"isValid": True, "payer": authorization["from"]}
            if self.path == "/verify"
            else {
                "network": requirements["network"],
                "payer": authorization["from"],
                "success": True,
                "transaction": f"0x{'1' * 64}",
            }
        )
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(response).encode())

    def log_message(self, format: str, *args: object) -> None:
        return


@contextmanager
def facilitator():
    FacilitatorHandler.calls = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), FacilitatorHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


async def run_task(process: subprocess.Popen[str]) -> dict:
    out = lib.read_out_json(
        process,
        {"mppPaidUrl": str, "x402PaidUrl": str},
        {"mppPaidUrl", "x402PaidUrl"},
    )
    x402 = lib.run_node_script(
        "x402-client",
        "x402_client.ts",
        env={"TEMPO_MPP_X402_PAID_URL": out["x402PaidUrl"]},
    )
    paths = [call["path"] for call in FacilitatorHandler.calls]
    if paths != ["/verify", "/settle"]:
        raise RuntimeError(f"x402 facilitator calls did not verify and settle: {paths}")
    return {
        "out": out,
        "mppOffer": lib.challenge_request(
            out["mppPaidUrl"],
            {"method": "tempo", "intent": "charge", "currency": lib.TOKEN},
        ),
        "x402": x402,
        "x402Facilitator": {"paths": paths},
        "paid": await lib.paid_request(out["mppPaidUrl"]),
    }


if __name__ == "__main__":
    with facilitator() as url:
        os.environ["TEMPO_MPP_X402_FACILITATOR_URL"] = url
        lib.run(run_task)
