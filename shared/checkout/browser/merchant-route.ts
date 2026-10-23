// Intercept at CDP level: Playwright context.route skips subsequent requests in
// a redirect chain. Cloud Chromium cannot resolve the trial-private merchant.
import { installWallet } from "./wallet.js";
import type { Page } from "playwright-core";

export default async ({ page }: { page: Page }) => {
  const context = page.context();
  await installWallet(context);
  const cdp = await context.newCDPSession(page);
  cdp.on("Fetch.requestPaused", async ({ requestId, networkId, request }) => {
    try {
      let data = request.postData;
      if (data === undefined && request.hasPostData && networkId) {
        data = (await cdp.send("Network.getRequestPostData", { requestId: networkId })).postData;
      }
      const response = await context.request.fetch(request.url, {
        method: request.method, headers: request.headers, data,
        maxRedirects: 0, timeout: 30_000,
      });
      // APIResponse.body is decompressed; preserve repeated Set-Cookie headers.
      const headers = response.headersArray().filter(({ name }) =>
        !["content-encoding", "content-length", "transfer-encoding", "connection"].includes(name.toLowerCase()));
      await cdp.send("Fetch.fulfillRequest", {
        requestId, responseCode: response.status(), responseHeaders: headers,
        body: (await response.body()).toString("base64"),
      });
      await response.dispose();
    } catch {
      await cdp.send("Fetch.failRequest", { requestId, errorReason: "Failed" }).catch(() => {});
    }
  });
  await cdp.send("Fetch.enable", { patterns: [{ urlPattern: "http://merchant:3000/*", requestStage: "Request" }] });
};
