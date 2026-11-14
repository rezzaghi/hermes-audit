"use strict";
(function (root) {
  const levels = ["info", "low", "medium", "high", "critical"];
  function normalizeAnnotation(value) {
    const v =
      value && typeof value === "object" && !Array.isArray(value) ? value : {};
    const severity =
      typeof v.severity === "string" && levels.includes(v.severity)
        ? v.severity
        : "";
    const raw = Array.isArray(v.tags) ? v.tags : [];
    const tags = [
      ...new Set(
        raw
          .filter((x) => typeof x === "string")
          .map((x) => x.trim().slice(0, 40))
          .filter(Boolean),
      ),
    ].slice(0, 20);
    return {
      severity,
      tags,
      note: typeof v.note === "string" ? v.note.slice(0, 2000) : "",
    };
  }
  function severityOf(event, annotations) {
    return annotations[event.id]?.severity || event.severity;
  }
  function tagsOf(event, annotations) {
    return [
      ...new Set([
        ...(event.tags || []),
        ...(annotations[event.id]?.tags || []),
      ]),
    ];
  }
  function filterEvents(events, filters = {}, annotations = {}) {
    const words = (filters.query || "")
      .toLocaleLowerCase()
      .trim()
      .split(/\s+/)
      .filter(Boolean);
    return events.filter((e) => {
      if (filters.session && e.session_id !== filters.session) return false;
      if (filters.severity && severityOf(e, annotations) !== filters.severity)
        return false;
      if (filters.tool && e.tool !== filters.tool) return false;
      if (filters.kind && e.kind !== filters.kind) return false;
      if (filters.tag && !tagsOf(e, annotations).includes(filters.tag))
        return false;
      if (filters.onlyFailures && !e.failed) return false;
      if (!words.length) return true;
      const a = annotations[e.id] || {};
      const text = [
        e.tool,
        e.session_title,
        e.session_id,
        e.result,
        JSON.stringify(e.arguments),
        ...(e.reasons || []),
        ...tagsOf(e, annotations),
        a.note || "",
      ]
        .join(" ")
        .toLocaleLowerCase();
      return words.every((word) => text.includes(word));
    });
  }
  function sortEvents(events, order = "newest", annotations = {}) {
    return [...events].sort((a, b) => {
      if (order === "severity") {
        const diff =
          levels.indexOf(severityOf(b, annotations)) -
          levels.indexOf(severityOf(a, annotations));
        if (diff) return diff;
      }
      return (
        (order === "oldest" ? 1 : -1) *
          ((a.timestamp || 0) - (b.timestamp || 0)) || a.id.localeCompare(b.id)
      );
    });
  }
  const api = {
    levels,
    normalizeAnnotation,
    severityOf,
    tagsOf,
    filterEvents,
    sortEvents,
  };
  root.AuditLogic = api;
  if (typeof module !== "undefined") module.exports = api;
})(globalThis);
