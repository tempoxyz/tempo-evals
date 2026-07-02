from collections.abc import Mapping
from pathlib import Path
from textwrap import dedent
from types import MappingProxyType
from typing import Final

from obrist.collections import (
    BenchmarkJobSpec,
    EnvironmentDefaults,
    HarborTemplateOverrides,
    NodeTestPackageSpec,
    PackagedSuiteSpec,
    ProfileSpec,
    SharedAssetSpec,
    SolutionSpec,
    SourcePatternSpec,
    TaskCaseSpec,
)
from obrist.dsl import MCPServer, MCPTransport

PACKAGE_DIR = Path(__file__).resolve().parent
SOLUTION_DIR = PACKAGE_DIR / "solutions"


LOCALNET_RPC_URL: Final = "http://tempo-localnet:8545"
LOCALNET_ALPHA_USD_TOKEN: Final = "0x20c0000000000000000000000000000000000001"
LOCALNET_SWAP_TOKEN: Final = "0x20c0000000000000000000000000000000000000"
LOCALNET_RECIPIENT: Final = "0x1111111111111111111111111111111111111111"
LOCALNET_FEE_MANAGER: Final = "0xfeec000000000000000000000000000000000000"
LOCALNET_TIP20_FACTORY: Final = "0x20fc000000000000000000000000000000000000"
LOCALNET_TIP403_REGISTRY: Final = "0x403c000000000000000000000000000000000000"
LOCALNET_STABLECOIN_DEX: Final = "0xdec0000000000000000000000000000000000000"
LOCALNET_PAYER_PRIVATE_KEY: Final = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
LOCALNET_AUX_PRIVATE_KEY: Final = "0x59c6995e998f97a5a004497e5da46f94a879b621718eb9bde6e3db6c2b2b3b4d"
LOCALNET_PRIVATE_KEYS: Final = frozenset((LOCALNET_PAYER_PRIVATE_KEY, LOCALNET_AUX_PRIVATE_KEY))


def env_map(values: Mapping[str, str]) -> Mapping[str, str]:
    """Return an immutable environment fixture mapping."""

    return MappingProxyType(dict(values))


TEMPO_COMMON_ENV: Final = env_map(
    {
        "TEMPO_BENCH_SUBMISSION_TIMEOUT_MS": "180000",
        "TEMPO_BENCH_RPC_WAIT_MS": "60000",
        "TEMPO_BENCH_LOG_WAIT_MS": "30000",
        "TEMPO_RPC_URL": LOCALNET_RPC_URL,
        "TEMPO_TOKEN": LOCALNET_ALPHA_USD_TOKEN,
        "TEMPO_PAYER_PRIVATE_KEY": LOCALNET_PAYER_PRIVATE_KEY,
        "TEMPO_RECIPIENT": LOCALNET_RECIPIENT,
        "TEMPO_DECIMALS": "6",
        "TEMPO_BENCH_TURNS_SCORE_CUTOFFS": "20=1.0,40=0.8,60=0.5,80=0.2,*=0.0",
        "TEMPO_BENCH_TOKENS_SCORE_CUTOFFS": "250000=1.0,500000=0.8,1000000=0.5,1500000=0.2,*=0.0",
    }
)


TEMPO_EXECUTION_CONSTRAINTS = (
    "`TEMPO_RPC_URL` is already set to the Tempo localnet RPC endpoint (`http://tempo-localnet:8545`).",
    "Use that localnet RPC endpoint for all build, run, and self-check commands.",
    "Do not hard-code or call public Tempo RPC endpoints such as Moderato/testnet.",
    "Treat private-key environment variables as localnet-only runtime inputs; do not print, log, or write "
    "them into source files.",
    "Do not run live testnet smoke tests; local build/run checks must use the provided environment variables.",
)


TEMPO_PROFILES = (
    ProfileSpec(
        name="docs",
        instruction="Tempo docs are available at https://docs.tempo.xyz/ and through the `TEMPO_DOCS_URL` environment variable. You may use WebSearch/WebFetch for Tempo docs; prefer docs from docs.tempo.xyz and do not use public RPC endpoints.",
        env=env_map({"TEMPO_DOCS_URL": "https://docs.tempo.xyz/"}),
        trajectory_pattern="docs\\.tempo\\.xyz|TEMPO_DOCS_URL|Tempo docs|documentation",
    ),
    ProfileSpec(
        name="mcp",
        instruction="The official Tempo MCP server is configured as `tempo`. Use it if your agent runtime exposes MCP tools; do not use WebSearch, WebFetch, or public RPC endpoints.",
        mcp_servers=(MCPServer(name="tempo", transport=MCPTransport.STREAMABLE_HTTP, url="https://mcp.tempo.xyz"),),
        trajectory_pattern="tempo|mcp|docs|documentation|search",
    ),
)


TEMPO_TEMPLATE_OVERRIDES = HarborTemplateOverrides(criteria=PACKAGE_DIR / "templates/criteria.py.j2")

TEMPO_TEST_PACKAGE = NodeTestPackageSpec(
    dependencies={
        "@tempo-bench/verifier": "file:./tempo-bench-verifier",
    }
)

TEMPO_SHARED_ASSETS = (
    SharedAssetSpec(source="docker/main-node/Dockerfile", destination="environment/Dockerfile"),
    SharedAssetSpec(source="docker/compose/tempo-localnet.yaml", destination="environment/docker-compose.yaml"),
    SharedAssetSpec(source="docker/tempo-localnet", destination="environment/tempo-localnet"),
    SharedAssetSpec(source="rewardkit-package", destination="environment/rewardkit-package"),
    SharedAssetSpec(source="rewardkit/verify-tempo.sh", destination="tests/correctness/verify-tempo.sh"),
    SharedAssetSpec(source="rewardkit/quality", destination="tests/quality"),
    SharedAssetSpec(source="rewardkit/test.sh", destination="tests/test.sh"),
    SharedAssetSpec(source="verifier", destination="tests/tempo-bench-verifier"),
)


TEMPO_CASES = (
    TaskCaseSpec(
        slug="transfer-with-memo",
        title="Tempo Transfer With Memo",
        description="Build a minimal Tempo localnet integration that sends a TIP-20 transfer with a memo.",
        keywords=("tempo", "tip20", "memo", "localnet", "typescript"),
        prompt=dedent(
            """\
            Build a minimal TypeScript project in `/app` that sends a Tempo localnet
            stablecoin payment with a memo.

            Use the following values:

            - RPC URL: read from `TEMPO_RPC_URL`
            - Payer private key: read from `TEMPO_PAYER_PRIVATE_KEY`
            - Token address: read from `TEMPO_TOKEN`
            - Recipient address: read from `TEMPO_RECIPIENT`
            - Amount: read from `TEMPO_AMOUNT`
            - Decimals: read from `TEMPO_DECIMALS`
            - Memo: read from `TEMPO_MEMO`
            """
        ).strip(),
        requirements=(
            "Put the submission directly in `/app`.",
            "Include a `package.json`.",
            "Include `tsconfig.json`.",
            "Put the runtime source in `src/index.ts`.",
            "Include scripts named exactly `build` and `run`.",
            "`npm run build` must typecheck or compile the project.",
            "`npm run run` must execute the transfer on Tempo localnet.",
            "Attach the memo to the payment using `transferWithMemo`.",
            "Do not edit `/tests`, `/logs`, or `/solution`.",
        ),
        verifier_case="transfer-with-memo",
        env=env_map({"TEMPO_BENCH_CASE": "transfer-with-memo", "TEMPO_AMOUNT": "0.17", "TEMPO_MEMO": "TEMPO-EVAL-001"}),
        source_patterns=(
            SourcePatternSpec(name="source_uses_transfer_with_memo_semantics", pattern="transferWithMemo|transferSync"),
            SourcePatternSpec(name="source_reads_tempo_memo", pattern="TEMPO_MEMO"),
            SourcePatternSpec(name="source_parses_token_units", pattern="parseUnits"),
        ),
        solution=SolutionSpec(path=SOLUTION_DIR / "transfer-with-memo"),
    ),
    TaskCaseSpec(
        slug="transfer-with-memo-fee-payer",
        title="Tempo Transfer With Memo And Fee Payer",
        description="Build a Tempo localnet integration that sends a memo transfer sponsored by a fee payer.",
        keywords=("tempo", "tip20", "memo", "fee-payer", "localnet", "typescript"),
        prompt=dedent(
            """\
            Build a minimal TypeScript project in `/app` that sends a Tempo localnet
            stablecoin payment with a 32-byte memo and a separate fee payer.

            Use environment variables for all values:

            - `TEMPO_RPC_URL`
            - `TEMPO_PAYER_PRIVATE_KEY`
            - `TEMPO_FEE_PAYER_PRIVATE_KEY`
            - `TEMPO_FEE_TOKEN`
            - `TEMPO_TOKEN`
            - `TEMPO_RECIPIENT`
            - `TEMPO_AMOUNT`
            - `TEMPO_DECIMALS`
            - `TEMPO_MEMO`
            """
        ).strip(),
        requirements=(
            "Put the submission directly in `/app`.",
            "Include `package.json`.",
            "Include `tsconfig.json`.",
            "Put the runtime source in `src/index.ts`.",
            "Include scripts named exactly `build` and `run`.",
            "`npm run build` must typecheck or compile.",
            "`npm run run` must execute the transfer on Tempo localnet.",
            "Use `transferWithMemo` semantics and include the memo.",
            "Use the fee payer private key as the Tempo transaction fee payer.",
            "Do not edit `/tests`, `/logs`, or `/solution`.",
        ),
        verifier_case="transfer-with-memo",
        env=env_map(
            {
                "TEMPO_BENCH_CASE": "transfer-with-memo",
                "TEMPO_FEE_TOKEN": LOCALNET_ALPHA_USD_TOKEN,
                "TEMPO_FEE_PAYER_PRIVATE_KEY": LOCALNET_AUX_PRIVATE_KEY,
                "TEMPO_AMOUNT": "0.19",
                "TEMPO_MEMO": "TEMPO-FEEPAYER-001",
            }
        ),
        source_patterns=(
            SourcePatternSpec(name="source_uses_transfer_with_memo_semantics", pattern="transferWithMemo|transferSync"),
            SourcePatternSpec(name="source_reads_tempo_memo", pattern="TEMPO_MEMO"),
            SourcePatternSpec(name="source_parses_token_units", pattern="parseUnits"),
            SourcePatternSpec(name="source_reads_fee_payer_private_key", pattern="TEMPO_FEE_PAYER_PRIVATE_KEY"),
            SourcePatternSpec(name="source_passes_fee_payer", pattern="feePayer"),
            SourcePatternSpec(name="source_reads_fee_token", pattern="TEMPO_FEE_TOKEN"),
        ),
        solution=SolutionSpec(path=SOLUTION_DIR / "transfer-with-memo-fee-payer"),
    ),
    TaskCaseSpec(
        slug="set-fee-token",
        title="Tempo Set Fee Token",
        description="Build a Tempo localnet integration that sets AlphaUSD as the account's default fee token.",
        keywords=("tempo", "fee-token", "alpha-usd", "localnet", "typescript"),
        prompt=dedent(
            """\
            Build a minimal TypeScript project in `/app` that sets the account's default
            Tempo fee token to AlphaUSD.

            Use environment variables for all values:

            - `TEMPO_RPC_URL`
            - `TEMPO_PAYER_PRIVATE_KEY`
            - `TEMPO_FEE_TOKEN`
            - `TEMPO_FEE_MANAGER`
            """
        ).strip(),
        requirements=(
            "Put the submission directly in `/app`.",
            "Include `package.json`.",
            "Include `tsconfig.json`.",
            "Put the runtime source in `src/index.ts`.",
            "Include scripts named exactly `build` and `run`.",
            "`npm run build` must typecheck or compile.",
            "`npm run run` must call `setUserToken` on the Fee Manager.",
            "Use `TEMPO_FEE_TOKEN` as the token argument.",
            "Do not edit `/tests`, `/logs`, or `/solution`.",
        ),
        verifier_case="set-fee-token",
        env=env_map(
            {
                "TEMPO_BENCH_CASE": "set-fee-token",
                "TEMPO_FEE_TOKEN": LOCALNET_ALPHA_USD_TOKEN,
                "TEMPO_FEE_MANAGER": LOCALNET_FEE_MANAGER,
                "TEMPO_AMOUNT": "0.01",
                "TEMPO_MEMO": "TEMPO-FEE-TOKEN",
            }
        ),
        source_patterns=(
            SourcePatternSpec(name="source_calls_set_user_token", pattern="setUserToken"),
            SourcePatternSpec(name="source_reads_tempo_fee_token", pattern="TEMPO_FEE_TOKEN"),
        ),
        solution=SolutionSpec(path=SOLUTION_DIR / "set-fee-token"),
    ),
    TaskCaseSpec(
        slug="create-stablecoin-with-policy",
        title="Tempo Create Stablecoin With Transfer Policy",
        description="Build a Tempo localnet integration that creates a TIP-20 stablecoin, creates a transfer policy, and links it.",
        keywords=("tempo", "tip20", "stablecoin", "tip403", "policy", "localnet", "typescript"),
        prompt=dedent(
            """\
            Build a minimal TypeScript project in `/app` that creates a TIP-20 stablecoin,
            creates a TIP-403 transfer policy, and links that policy to the new token.

            Use environment variables for all values:

            - `TEMPO_RPC_URL`
            - `TEMPO_PAYER_PRIVATE_KEY`
            - `TEMPO_TOKEN`
            - `TEMPO_STABLECOIN_NAME`
            - `TEMPO_STABLECOIN_SYMBOL`
            - `TEMPO_STABLECOIN_CURRENCY`
            - `TEMPO_STABLECOIN_SALT`
            - `TEMPO_POLICY_TYPE`
            - `TEMPO_POLICY_ACCOUNT`
            """
        ).strip(),
        requirements=(
            "Put the submission directly in `/app`.",
            "Include `package.json`.",
            "Include `tsconfig.json`.",
            "Put the runtime source in `src/index.ts`.",
            "Include scripts named exactly `build` and `run`.",
            "`npm run build` must typecheck or compile.",
            "Create the stablecoin with currency `TEMPO_STABLECOIN_CURRENCY`.",
            "Create a TIP-403 policy of type `TEMPO_POLICY_TYPE` including `TEMPO_POLICY_ACCOUNT`.",
            "Link the created policy to the created stablecoin.",
            "Do not edit `/tests`, `/logs`, or `/solution`.",
        ),
        verifier_case="create-stablecoin-with-policy",
        env=env_map(
            {
                "TEMPO_BENCH_CASE": "create-stablecoin-with-policy",
                "TEMPO_TIP20_FACTORY": LOCALNET_TIP20_FACTORY,
                "TEMPO_TIP403_REGISTRY": LOCALNET_TIP403_REGISTRY,
                "TEMPO_AMOUNT": "0.01",
                "TEMPO_MEMO": "TEMPO-STABLECOIN",
                "TEMPO_STABLECOIN_NAME": "Tempo Bench Policy USD",
                "TEMPO_STABLECOIN_SYMBOL": "TBPUSD",
                "TEMPO_STABLECOIN_CURRENCY": "USD",
                "TEMPO_STABLECOIN_SALT": "0x0000000000000000000000000000000000000000000000000000000000000b01",
                "TEMPO_POLICY_TYPE": "blacklist",
                "TEMPO_POLICY_ACCOUNT": LOCALNET_RECIPIENT,
            }
        ),
        source_patterns=(
            SourcePatternSpec(
                name="source_creates_stablecoin",
                pattern="token\\.createSync|createSync\\(client,\\s*\\{[\\s\\S]*currency",
            ),
            SourcePatternSpec(name="source_creates_transfer_policy", pattern="policy\\.createSync"),
            SourcePatternSpec(name="source_links_transfer_policy", pattern="changeTransferPolicySync|transferPolicy"),
            SourcePatternSpec(name="source_reads_stablecoin_currency", pattern="TEMPO_STABLECOIN_CURRENCY"),
            SourcePatternSpec(name="source_reads_policy_account", pattern="TEMPO_POLICY_ACCOUNT"),
        ),
        solution=SolutionSpec(path=SOLUTION_DIR / "create-stablecoin-with-policy"),
    ),
    TaskCaseSpec(
        slug="faucet-funded-transfer",
        title="Tempo Faucet Funded Transfer",
        description="Build a Tempo localnet integration that funds a wallet from the faucet and transfers AlphaUSD.",
        keywords=("tempo", "faucet", "tip20", "transfer", "localnet", "typescript"),
        prompt=dedent(
            """\
            Build a minimal TypeScript project in `/app` that funds a wallet with Tempo's
            faucet, then sends an AlphaUSD transfer from that funded wallet.

            Use environment variables for all values:

            - `TEMPO_RPC_URL`
            - `TEMPO_FAUCET_PRIVATE_KEY`
            - `TEMPO_TOKEN`
            - `TEMPO_RECIPIENT`
            - `TEMPO_AMOUNT`
            - `TEMPO_DECIMALS`
            """
        ).strip(),
        requirements=(
            "Put the submission directly in `/app`.",
            "Include `package.json`.",
            "Include `tsconfig.json`.",
            "Put the runtime source in `src/index.ts`.",
            "Include scripts named exactly `build` and `run`.",
            "`npm run build` must typecheck or compile.",
            "`npm run run` must call the Tempo faucet for the faucet wallet before transfer.",
            "Transfer `TEMPO_AMOUNT` of `TEMPO_TOKEN` to `TEMPO_RECIPIENT`.",
            "Do not edit `/tests`, `/logs`, or `/solution`.",
        ),
        verifier_case="faucet-funded-transfer",
        env=env_map(
            {
                "TEMPO_BENCH_CASE": "faucet-funded-transfer",
                "TEMPO_FAUCET_PRIVATE_KEY": LOCALNET_AUX_PRIVATE_KEY,
                "TEMPO_AMOUNT": "0.23",
                "TEMPO_MEMO": "TEMPO-FAUCET",
            }
        ),
        source_patterns=(
            SourcePatternSpec(name="source_calls_faucet_fund", pattern="faucet\\.fundSync|fundSync"),
            SourcePatternSpec(name="source_reads_faucet_private_key", pattern="TEMPO_FAUCET_PRIVATE_KEY"),
            SourcePatternSpec(name="source_sends_transfer", pattern="transferSync|transferWithMemo"),
        ),
        solution=SolutionSpec(path=SOLUTION_DIR / "faucet-funded-transfer"),
    ),
    TaskCaseSpec(
        slug="stablecoin-dex-swap",
        title="Tempo Stablecoin DEX Swap",
        description="Build a Tempo localnet integration that approves the Stablecoin DEX, creates liquidity, and executes a swap.",
        keywords=("tempo", "stablecoin-dex", "swap", "tip20", "localnet", "typescript"),
        prompt=dedent(
            """\
            Build a minimal TypeScript project in `/app` that uses Tempo's Stablecoin DEX
            to execute a swap.

            Use environment variables for all values:

            - `TEMPO_RPC_URL`
            - `TEMPO_PAYER_PRIVATE_KEY`
            - `TEMPO_DEX_MAKER_PRIVATE_KEY`
            - `TEMPO_STABLECOIN_DEX`
            - `TEMPO_SWAP_TOKEN_IN`
            - `TEMPO_SWAP_TOKEN_OUT`
            - `TEMPO_SWAP_AMOUNT_IN`
            - `TEMPO_SWAP_MIN_AMOUNT_OUT`
            - `TEMPO_DECIMALS`
            """
        ).strip(),
        requirements=(
            "Put the submission directly in `/app`.",
            "Include `package.json`.",
            "Include `tsconfig.json`.",
            "Put the runtime source in `src/index.ts`.",
            "Include scripts named exactly `build` and `run`.",
            "`npm run build` must typecheck or compile.",
            "`npm run run` must fund wallets as needed, approve DEX token spending, provide liquidity, and execute a DEX swap.",
            "Use Tempo Stablecoin DEX swap APIs, not a plain token transfer.",
            "Do not edit `/tests`, `/logs`, or `/solution`.",
        ),
        verifier_case="stablecoin-dex-swap",
        env=env_map(
            {
                "TEMPO_BENCH_CASE": "stablecoin-dex-swap",
                "TEMPO_STABLECOIN_DEX": LOCALNET_STABLECOIN_DEX,
                "TEMPO_DEX_MAKER_PRIVATE_KEY": LOCALNET_AUX_PRIVATE_KEY,
                "TEMPO_AMOUNT": "100",
                "TEMPO_MEMO": "TEMPO-DEX",
                "TEMPO_SWAP_TOKEN_IN": LOCALNET_SWAP_TOKEN,
                "TEMPO_SWAP_TOKEN_OUT": LOCALNET_ALPHA_USD_TOKEN,
                "TEMPO_SWAP_AMOUNT_IN": "100",
                "TEMPO_SWAP_MIN_AMOUNT_OUT": "0",
            }
        ),
        source_patterns=(
            SourcePatternSpec(name="source_uses_dex_actions", pattern="Actions\\.dex|\\.dex\\."),
            SourcePatternSpec(name="source_approves_dex_spending", pattern="approveSync"),
            SourcePatternSpec(name="source_provides_dex_liquidity", pattern="placeSync|provideLiquidity|addLiquidity"),
            SourcePatternSpec(name="source_executes_dex_swap", pattern="sellSync|buySync|swapSync"),
            SourcePatternSpec(
                name="source_reads_swap_token_env",
                pattern="TEMPO_SWAP_TOKEN_IN[\\s\\S]*TEMPO_SWAP_TOKEN_OUT|TEMPO_SWAP_TOKEN_OUT[\\s\\S]*TEMPO_SWAP_TOKEN_IN",
            ),
        ),
        solution=SolutionSpec(path=SOLUTION_DIR / "stablecoin-dex-swap"),
    ),
)


TEMPO_BENCH = BenchmarkJobSpec(
    collection_name="tempobench",
    job_name="tempo-bench",
    dataset_name="tempo/tempo-bench",
    dataset_description="Tempo integration benchmark",
    dataset_keywords=("stablecoins", "docs", "tempo"),
    dataset_author_name="Tempo",
    package_dir=PACKAGE_DIR,
    repo_root=PACKAGE_DIR.parents[2],
    shared_dir=PACKAGE_DIR / "shared",
    default_suite="default",
    profiles=TEMPO_PROFILES,
    cases=TEMPO_CASES,
    suites=(PackagedSuiteSpec(name="default", job_name="tempo-bench-local"),),
    environment=EnvironmentDefaults(env=TEMPO_COMMON_ENV),
    test_package=TEMPO_TEST_PACKAGE,
    shared_assets=TEMPO_SHARED_ASSETS,
    quality_reward_source="rewardkit/quality/reward.toml",
    templates=TEMPO_TEMPLATE_OVERRIDES,
    execution_constraints=TEMPO_EXECUTION_CONSTRAINTS,
)
