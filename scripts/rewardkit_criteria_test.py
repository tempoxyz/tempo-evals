import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "shared" / "global" / "rewardkit-lib"))

from tempo_bench_rewardkit import criteria  # noqa: E402


class ViemTempoCriterionTests(unittest.TestCase):
    def workspace(self, source: str) -> Path:
        workspace = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, workspace)
        (workspace / "src").mkdir()
        (workspace / "package.json").write_text('{"dependencies":{"viem":"^2.53.1"}}')
        (workspace / "src" / "index.ts").write_text(source)
        criteria.LOG_DIR = workspace / "logs"
        return workspace

    def test_accepts_dynamic_import_and_destructured_actions(self) -> None:
        workspace = self.workspace(
            'const tempo = await import("viem/tempo");\n'
            "const { transferSync } = tempo.Actions.token;\n"
        )

        self.assertTrue(criteria._uses_viem_tempo(workspace))

    def test_accepts_supported_tempo_modules_in_all_import_forms(self) -> None:
        for module in (
            "viem/tempo",
            "viem/tempo/actions",
            "viem/tempo/chains",
            "viem/tempo/zones",
        ):
            for source in (
                f'import {{ value }} from "{module}";\n',
                f'const tempo = await import("{module}");\n',
                f'const tempo = require("{module}");\n',
            ):
                with self.subTest(module=module, source=source):
                    workspace = self.workspace(source)

                    self.assertTrue(criteria._uses_viem_tempo(workspace))

    def test_rejects_unsupported_tempo_module_prefixes(self) -> None:
        for module in ("viem/tempography", "viem/tempo/not-real"):
            for source in (
                f'import {{ value }} from "{module}";\n',
                f'const tempo = await import("{module}");\n',
                f'const tempo = require("{module}");\n',
            ):
                with self.subTest(module=module, source=source):
                    workspace = self.workspace(source)

                    self.assertFalse(criteria._uses_viem_tempo(workspace))

    def test_rejects_missing_tempo_import(self) -> None:
        workspace = self.workspace('import { createPublicClient } from "viem";\n')

        self.assertFalse(criteria._uses_viem_tempo(workspace))


if __name__ == "__main__":
    unittest.main()
