import type { RunContext } from "@/lib/types";

export function formatNumber(value: number | null | undefined) {
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: 1,
  }).format(value ?? 0);
}

export function formatInteger(value: number | null | undefined) {
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: 0,
  }).format(value ?? 0);
}

export function formatDateTime(value: string | null | undefined) {
  if (!value) {
    return "Not available";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export function formatRelativeHours(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "Unknown";
  }
  return `${value.toFixed(1)}h`;
}

export function toneFromSeverity(value: string) {
  switch (value) {
    case "critical":
      return "critical";
    case "high":
      return "warning";
    case "medium":
      return "info";
    case "low":
      return "neutral";
    case "warning":
      return "warning";
    case "success":
      return "success";
    default:
      return "info";
  }
}

export function getPlanLabel(versionNumber: number) {
  const preset = ["Plan A", "Plan B", "Plan C"];
  if (versionNumber >= 1 && versionNumber <= preset.length) {
    return preset[versionNumber - 1];
  }
  return `Override v${versionNumber}`;
}

export function buildQueryString(runContext: RunContext | null) {
  if (!runContext) {
    return "";
  }

  const params = new URLSearchParams();
  if (runContext.m1RunId) {
    params.set("m1RunId", String(runContext.m1RunId));
  }
  if (runContext.m2RunId) {
    params.set("m2RunId", String(runContext.m2RunId));
  }
  if (runContext.m3RunId) {
    params.set("m3RunId", String(runContext.m3RunId));
  }

  const value = params.toString();
  return value ? `?${value}` : "";
}

export function downloadText(
  filename: string,
  content: string,
  mimeType = "text/plain;charset=utf-8"
) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export function rowsToCsv(
  headers: string[],
  rows: Array<Array<string | number | null | undefined>>
) {
  const escapeValue = (value: string | number | null | undefined) => {
    const normalized = value === null || value === undefined ? "" : String(value);
    if (normalized.includes(",") || normalized.includes("\"") || normalized.includes("\n")) {
      return `"${normalized.replaceAll("\"", "\"\"")}"`;
    }
    return normalized;
  };

  return [headers, ...rows]
    .map((row) => row.map(escapeValue).join(","))
    .join("\n");
}
