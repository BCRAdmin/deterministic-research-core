#!/usr/bin/env node

import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

const [productRoot, bundleParent, ticker, runRoot] = process.argv.slice(2);
if (!productRoot || !bundleParent || !ticker || !runRoot) throw new Error("usage: productRoot bundleParent ticker runRoot");
const { createBa12NativeApp } = await import(pathToFileURL(path.join(productRoot, "room16-app", "ba12-native-server.mjs")));
const app = createBa12NativeApp({ bundleRoot: bundleParent, host: "127.0.0.1" });
const server = app.listen(0, "127.0.0.1");
try {
  await new Promise((resolve, reject) => { server.once("listening", resolve); server.once("error", reject); });
  const { port } = server.address();
  const base = `http://127.0.0.1:${port}`;
  const healthResponse = await fetch(`${base}/api/health`);
  const reportResponse = await fetch(`${base}/api/reports/latest/${encodeURIComponent(ticker)}`);
  const markdownResponse = await fetch(`${base}/api/reports/latest/${encodeURIComponent(ticker)}/markdown`);
  const health = await healthResponse.json();
  const envelope = await reportResponse.json();
  const markdown = await markdownResponse.text();
  const report = envelope.report || {};
  const pass = healthResponse.status === 200 && reportResponse.status === 200 && markdownResponse.status === 200
    && health.authority === "room16.compiler_artifact_bundle@2" && health.legacyTruthFallback === false
    && [health.releaseAuthorized, health.publicationAuthorized, health.deployAuthorized, health.commerceAuthorized].every((x) => x === false)
    && report.ticker === ticker && report.bindingStatus === "verified" && report.rendererCutover === true
    && report.legacyTruthFallback === false && markdown.startsWith(`# ${ticker} Alpha REIT research dossier`);
  const output = { status: pass ? "PASS" : "FAIL", canonicalRuntime: health.canonicalRuntime, authority: health.authority, trustEpoch: health.trustEpoch, rendererCutover: health.rendererCutover, legacyTruthFallback: health.legacyTruthFallback, releaseAuthorized: health.releaseAuthorized, publicationAuthorized: health.publicationAuthorized, deployAuthorized: health.deployAuthorized, commerceAuthorized: health.commerceAuthorized, http: { health: healthResponse.status, report: reportResponse.status, markdown: markdownResponse.status }, report };
  const evidenceRoot = path.join(runRoot, "evidence");
  fs.writeFileSync(path.join(evidenceRoot, "09_PRODUCT_RUNTIME_REPORT.json"), `${JSON.stringify(output, null, 2)}\n`);
  fs.writeFileSync(path.join(evidenceRoot, "10_HUMAN_REPORT.md"), markdown.endsWith("\n") ? markdown : `${markdown}\n`);
  console.log(JSON.stringify({ status: output.status, bundleSha256: report.bundleSha256, receiptSha256: report.receiptSha256, factCount: (report.facts || []).length, claimCount: (report.claims || []).length }));
  process.exitCode = pass ? 0 : 1;
} finally {
  await new Promise((resolve) => server.close(resolve));
}
