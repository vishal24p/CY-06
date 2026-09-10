import type { AnalysisReport } from "@/lib/types";

export async function analyzeInventory(inventory: unknown): Promise<AnalysisReport> {
  const response = await fetch("/api/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ inventory, context: {} }),
  });

  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.detail ?? "Analysis failed.");
  }
  return payload as AnalysisReport;
}
