"use strict";
(() => {
  const L = globalThis.AuditLogic;
  const data = JSON.parse(document.getElementById("report-data").textContent);
  const events = Array.isArray(data.events) ? data.events : [];
  const knownIds = new Set(events.map((e) => e.id));
  const annotations = Object.create(null);
  const $ = (id) => document.getElementById(id);
  const storagePrefix = "hermes-audit:annotation:";
  let displayed = 120;

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = String(text);
    return node;
  }
  function storageKey(id) {
    return storagePrefix + id;
  }
  function warn(text) {
    $("storage-warning").textContent = text;
    $("storage-warning").hidden = !text;
  }
  try {
    for (const event of events) {
      const stored = localStorage.getItem(storageKey(event.id));
      if (stored)
        annotations[event.id] = L.normalizeAnnotation(JSON.parse(stored));
    }
  } catch (_) {
    warn(
      "Browser storage unavailable. Export annotations before closing this file.",
    );
  }

  function choices(id, items, label) {
    const select = $(id),
      previous = select.value;
    select.replaceChildren(new Option(label, ""));
    for (const item of items) select.add(new Option(item, item));
    select.value = items.includes(previous) ? previous : "";
  }
  const sessions = [...new Set(events.map((e) => e.session_id))].sort();
  choices("session-filter", sessions, "All sessions");
  choices("severity-filter", [...L.levels].reverse(), "All severities");
  choices(
    "tool-filter",
    [...new Set(events.map((e) => e.tool))].sort(),
    "All tools",
  );
  function updateTags() {
    const tags = [
      ...new Set(events.flatMap((e) => L.tagsOf(e, annotations))),
    ].sort();
    choices("tag-filter", tags, "All tags");
  }
  function filters() {
    return {
      query: $("query").value,
      session: $("session-filter").value,
      severity: $("severity-filter").value,
      tag: $("tag-filter").value,
      tool: $("tool-filter").value,
      kind: $("kind-filter").value,
      onlyFailures: $("only-failures").checked,
    };
  }
  function iso(ts) {
    return ts ? new Date(Number(ts) * 1000).toLocaleString() : "Unknown time";
  }
  function preview(event) {
    const raw =
      event.kind === "message"
        ? event.result
        : JSON.stringify(event.arguments) || event.result;
    return String(raw || event.result || "No recorded detail")
      .replace(/\s+/g, " ")
      .slice(0, 190);
  }
  function section(parent, heading, value) {
    const wrap = el("div", "detail-section");
    wrap.append(el("h3", "detail-label", heading));
    const pre = el("pre", "raw", String(value || "(empty)").slice(0, 16000));
    wrap.append(pre);
    if (String(value || "").length > 16000) {
      const more = el("button", "expand-text", "Show full recorded text");
      more.type = "button";
      more.addEventListener("click", () => {
        pre.textContent = String(value);
        more.remove();
      });
      wrap.append(more);
    }
    parent.append(wrap);
  }
  function card(event) {
    const wrap = el(
      "details",
      "entry severity-" + L.severityOf(event, annotations),
    );
    wrap.dataset.id = event.id;
    const summary = el("summary", "entry-summary");
    const chip = el(
      "span",
      "severity-chip",
      L.severityOf(event, annotations).toUpperCase(),
    );
    const meta = el("div", "entry-meta");
    meta.append(
      el(
        "span",
        "tool-name",
        event.kind === "message" ? event.role + " message" : event.tool,
      ),
    );
    meta.append(el("span", "entry-time", iso(event.timestamp)));
    const title = el("div", "entry-title", preview(event));
    const footer = el("div", "entry-footer");
    footer.append(
      el("span", "session-label", event.session_title || event.session_id),
    );
    for (const tag of L.tagsOf(event, annotations).slice(0, 5))
      footer.append(el("span", "tag", tag));
    if (event.failed) footer.append(el("span", "failed-tag", "FAILED"));
    const summaryBody = el("div", "entry-main");
    summaryBody.append(meta, title, footer);
    summary.append(chip, summaryBody, el("span", "chevron", "⌄"));
    wrap.append(summary);
    const body = el("div", "entry-body");
    const evidence = el("div", "reasons");
    evidence.append(el("span", "detail-label", "WHY THIS LABEL"));
    for (const reason of event.reasons || [])
      evidence.append(el("p", "reason", reason));
    body.append(evidence);
    if (event.kind === "tool")
      section(body, "ARGUMENTS", JSON.stringify(event.arguments, null, 2));
    section(
      body,
      event.kind === "message" ? "MESSAGE" : "RESULT",
      event.result,
    );
    const annotation = L.normalizeAnnotation(annotations[event.id]);
    const form = el("div", "annotation");
    form.append(el("h3", "detail-label", "YOUR REVIEW · kept in this browser"));
    const grid = el("div", "annotation-grid");
    const tagsField = el("label", "field-label", "Tags (comma-separated)");
    const tagsInput = el("input", "annotation-tags");
    tagsInput.value = annotation.tags.join(", ");
    tagsInput.maxLength = 819;
    tagsField.append(tagsInput);
    const severityField = el("label", "field-label", "Override severity");
    const override = el("select", "annotation-severity");
    override.add(new Option("Use rule-based label", ""));
    for (const level of L.levels) override.add(new Option(level, level));
    override.value = annotation.severity;
    severityField.append(override);
    grid.append(tagsField, severityField);
    const noteField = el("label", "field-label", "Note");
    const note = el("textarea", "annotation-note");
    note.rows = 2;
    note.maxLength = 2000;
    note.value = annotation.note;
    noteField.append(note);
    const save = el("button", "save-annotation", "Save review");
    save.type = "button";
    save.addEventListener("click", () => {
      const item = L.normalizeAnnotation({
        severity: override.value,
        tags: tagsInput.value.split(","),
        note: note.value,
      });
      annotations[event.id] = item;
      try {
        localStorage.setItem(storageKey(event.id), JSON.stringify(item));
      } catch (_) {
        warn(
          "Browser storage unavailable. Export annotations before closing this file.",
        );
      }
      updateTags();
      render();
    });
    form.append(grid, noteField, save);
    body.append(form);
    wrap.append(body);
    return wrap;
  }
  function renderSummary() {
    const summary = $("summary");
    summary.replaceChildren();
    const toolEvents = events.filter((e) => e.kind === "tool");
    const counts = { critical: 0, high: 0, medium: 0, low: 0 };
    for (const e of toolEvents) {
      const level = L.severityOf(e, annotations);
      if (level in counts) counts[level]++;
    }
    for (const [level, count] of Object.entries(counts)) {
      const item = el("div", "summary-item summary-" + level);
      item.append(el("strong", "", count), el("span", "", level));
      summary.append(item);
    }
    $("report-meta").textContent =
      `${sessions.length} sessions · ${toolEvents.length} tool calls`;
  }
  function render() {
    renderSummary();
    const found = L.sortEvents(
      L.filterEvents(events, filters(), annotations),
      $("sort-order").value,
      annotations,
    );
    $("visible-count").textContent =
      `${found.length} of ${events.length} records`;
    const container = $("events");
    container.replaceChildren();
    const fragment = document.createDocumentFragment();
    for (const event of found.slice(0, displayed)) fragment.append(card(event));
    container.append(fragment);
    if (!found.length)
      container.append(
        el("p", "empty", "No matching records. Try fewer filters."),
      );
    $("load-more").hidden = found.length <= displayed;
    $("load-more").textContent =
      `Load more (${found.length - displayed} remaining)`;
  }
  updateTags();
  for (const id of [
    "query",
    "session-filter",
    "severity-filter",
    "tag-filter",
    "tool-filter",
    "kind-filter",
    "only-failures",
    "sort-order",
  ]) {
    $(id).addEventListener(id === "query" ? "input" : "change", () => {
      displayed = 120;
      render();
    });
  }
  $("load-more").addEventListener("click", () => {
    displayed += 120;
    render();
  });
  $("clear-filters").addEventListener("click", () => {
    for (const id of [
      "query",
      "session-filter",
      "severity-filter",
      "tag-filter",
      "tool-filter",
      "kind-filter",
    ])
      $(id).value = "";
    $("only-failures").checked = false;
    displayed = 120;
    render();
  });
  $("export-annotations").addEventListener("click", () => {
    const payload = JSON.stringify(
      { format: "hermes-audit-annotations-v1", items: annotations },
      null,
      2,
    );
    const url = URL.createObjectURL(
      new Blob([payload], { type: "application/json" }),
    );
    const link = el("a");
    link.href = url;
    link.download = "hermes-audit-annotations.json";
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 30000);
  });
  $("import-annotations").addEventListener("change", async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    if (file.size > 2_000_000) {
      warn("Annotation file exceeds 2 MB.");
      return;
    }
    try {
      const payload = JSON.parse(await file.text());
      if (
        payload.format !== "hermes-audit-annotations-v1" ||
        !payload.items ||
        typeof payload.items !== "object" ||
        Array.isArray(payload.items)
      )
        throw Error("Unsupported annotation format");
      for (const [id, value] of Object.entries(payload.items)) {
        if (!knownIds.has(id)) continue;
        const item = L.normalizeAnnotation(value);
        annotations[id] = item;
        try {
          localStorage.setItem(storageKey(id), JSON.stringify(item));
        } catch (_) {
          warn("Browser storage unavailable; export before closing.");
        }
      }
      updateTags();
      render();
    } catch (error) {
      warn("Could not import annotations: " + error.message);
    }
    event.target.value = "";
  });
  render();
})();
