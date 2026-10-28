import assert from "node:assert/strict";
import { test } from "node:test";

import { RECONNECT_DELAYS_MS, reconnectDelay } from "./reconnect.ts";

test("a restart or a dropped connection is retried, with growing waits", () => {
  for (const code of [1001, 1006, 1011, 1012]) {
    assert.equal(reconnectDelay(code, 0, false), 1000, `code ${code}`);
  }
  assert.deepEqual(
    RECONNECT_DELAYS_MS.map((_, attempt) => reconnectDelay(1012, attempt, false)),
    [1000, 2000, 4000, 8000, 15000],
  );
});

test("it gives up once the attempts are used up", () => {
  assert.equal(reconnectDelay(1006, RECONNECT_DELAYS_MS.length, false), undefined);
});

test("refusals are never retried", () => {
  for (const code of [4401, 4404, 4409, 1013, 1000]) {
    assert.equal(reconnectDelay(code, 0, false), undefined, `code ${code}`);
  }
});

test("after the candidate asked to end, a closed socket is not a reason to reconnect", () => {
  assert.equal(reconnectDelay(1006, 0, true), undefined);
});
