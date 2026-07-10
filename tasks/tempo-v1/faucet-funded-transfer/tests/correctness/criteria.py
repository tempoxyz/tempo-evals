import rewardkit as rk
from tempo_bench_rewardkit.common.checks import register_tempo_eval_contract

register_tempo_eval_contract()
rk.tempo_rejects_other_blockchains()
rk.tempo_uses_viem_tempo_actions(["faucet.fund", "token.transfer"])
