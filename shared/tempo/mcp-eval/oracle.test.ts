import assert from "node:assert/strict";
import test from "node:test";

import { docsRequest } from "./oracle.ts";

test("builds profile-specific oracle documentation calls", () => {
  assert.deepEqual(docsRequest("docs_search", "Tempo fees"), {
    name: "call_read_tool",
    arguments: { name: "docs_search", arguments: { query: "Tempo fees", max_results: 1 } },
  });
  assert.deepEqual(docsRequest("docs_code", "Tempo fees"), {
    name: "call_write_tool",
    arguments: {
      name: "docs_code",
      arguments: {
        code: 'async () => codemode.search({ query: "Tempo fees", source: "tempo", max_results: 1 })',
      },
    },
  });
});

test("rejects an unknown oracle documentation tool", () => {
  assert.throws(() => docsRequest("other", "Tempo fees"), /Unknown MCP oracle docs tool/);
});
