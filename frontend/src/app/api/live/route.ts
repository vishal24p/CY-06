export async function GET() {
  try {
    const baseUrl = process.env.CY06_API_URL ?? "http://127.0.0.1:8000";
    const inventoryResponse = await fetch(`${baseUrl}/api/v1/live`, { cache: "no-store" });
    const inventory = await inventoryResponse.json();
    if (!inventoryResponse.ok) return Response.json(inventory, { status: inventoryResponse.status });

    const analysisResponse = await fetch(`${baseUrl}/api/v1/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ inventory, context: {} }),
    });
    const report = await analysisResponse.json();
    return Response.json(analysisResponse.ok ? { inventory, report } : report, { status: analysisResponse.status });
  } catch {
    return Response.json({ detail: "Python analysis API is unavailable. Start it on port 8000." }, { status: 503 });
  }
}
