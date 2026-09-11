import assert from "node:assert/strict";
import { test } from "node:test";
import { simulateRemediation } from "../src/lib/api.ts";

const locator = { policy_name: "AssumeAdmin", statement_index: 1, action: "sts:AssumeRole", resource: "admin-role" };
const target = { remediation: locator };
const policy = () => ({ PolicyName: "AssumeAdmin", PolicyDocument: { Statement: [null, { Effect: "Allow", Action: ["sts:AssumeRole", "iam:GetRole"], Resource: ["admin-role"] }, { Effect: "Allow", Action: "sts:AssumeRole", Resource: "other-role" }] } });

test("preview edits raw statement index, ignores managed attachments, and preserves input", async (context) => {
  const inventory = { Policies: [policy()], RoleDetailList: [{ AttachedManagedPolicies: [{ PolicyName: "AssumeAdmin", PolicyArn: "policy-arn" }] }] };
  const before = structuredClone(inventory);
  let submitted;
  context.mock.method(globalThis, "fetch", async (_url, options) => {
    submitted = JSON.parse(options.body).inventory;
    return { ok: true, json: async () => ({ paths: [] }) };
  });
  await simulateRemediation(inventory, target);
  assert.deepEqual(inventory, before);
  assert.deepEqual(submitted.Policies[0].PolicyDocument.Statement[1].Action, ["iam:GetRole"]);
  assert.equal(submitted.Policies[0].PolicyDocument.Statement[2].Action, "sts:AssumeRole");
});

test("preview rejects mismatched resource before sending analysis", async (context) => {
  const fetch = context.mock.method(globalThis, "fetch", async () => assert.fail("Must not analyze a mismatched statement"));
  await assert.rejects(simulateRemediation({ Policies: [policy()] }, { remediation: { ...locator, resource: "wrong-role" } }), /preview was not applied/);
  assert.equal(fetch.mock.callCount(), 0);
});

test("preview rejects duplicate editable policy definitions", async () => {
  await assert.rejects(simulateRemediation({ Policies: [policy(), policy()] }, target), /ambiguous/);
});
