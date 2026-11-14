const test = require("node:test");
const assert = require("node:assert/strict");
const {
  filterEvents,
  sortEvents,
  normalizeAnnotation,
} = require("../hermes_audit/assets/logic.js");

const events = [
  {
    id: "s:1:0",
    kind: "tool",
    tool: "web_search",
    severity: "low",
    session_id: "s",
    tags: ["search"],
    reasons: ["Read-only"],
    arguments: { query: "Kimi pricing" },
    result: "Found official page",
    failed: false,
    timestamp: 2,
  },
  {
    id: "s:2:0",
    kind: "tool",
    tool: "terminal",
    severity: "critical",
    session_id: "s",
    tags: ["destructive"],
    reasons: ["Destructive command"],
    arguments: { command: "rm -rf /tmp/work" },
    result: "exit code 1",
    failed: true,
    timestamp: 3,
  },
  {
    id: "t:1:message",
    kind: "message",
    tool: "message",
    severity: "info",
    session_id: "t",
    tags: ["user"],
    reasons: [],
    arguments: {},
    result: "Find benchmark scores",
    failed: false,
    timestamp: 1,
  },
];

test("search matches tokens anywhere in a record and is case insensitive", () => {
  assert.deepEqual(
    filterEvents(events, { query: "kimi OFFICIAL" }, {}).map((e) => e.id),
    ["s:1:0"],
  );
});

test("filters severity, tag, failure, and session together", () => {
  const f = {
    severity: "critical",
    tag: "destructive",
    onlyFailures: true,
    session: "s",
  };
  assert.deepEqual(
    filterEvents(events, f, {}).map((e) => e.id),
    ["s:2:0"],
  );
});

test("personal severity override and tags affect filters", () => {
  const annotations = {
    "s:1:0": {
      severity: "high",
      tags: ["review-me"],
      note: "Check this source",
    },
  };
  assert.deepEqual(
    filterEvents(
      events,
      { severity: "high", tag: "review-me", query: "source" },
      annotations,
    ).map((e) => e.id),
    ["s:1:0"],
  );
});

test("sorts by severity or time without changing the input", () => {
  assert.deepEqual(
    sortEvents(events, "severity", {}).map((e) => e.id),
    ["s:2:0", "s:1:0", "t:1:message"],
  );
  assert.deepEqual(
    sortEvents(events, "oldest", {}).map((e) => e.id),
    ["t:1:message", "s:1:0", "s:2:0"],
  );
  assert.equal(events[0].id, "s:1:0");
});

test("imported annotations are restricted to known shapes and severities", () => {
  assert.deepEqual(
    normalizeAnnotation({
      severity: "critical",
      tags: ["foo", "foo", ""],
      note: "ok",
    }),
    { severity: "critical", tags: ["foo"], note: "ok" },
  );
  assert.equal(
    normalizeAnnotation({ severity: "supercritical", tags: [{}], note: 8 })
      .severity,
    "",
  );
});
