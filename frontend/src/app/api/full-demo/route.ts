export async function GET() {
  try {
    const upstream = await fetch(`${process.env.CY06_API_URL ?? "http://127.0.0.1:8000"}/api/v1/full-demo`, { cache: "no-store" });
    return new Response(await upstream.text(), {
      status: upstream.status,
      headers: { "Content-Type": "application/json" },
    });
  } catch {
    return Response.json({ detail: "Python analysis API is unavailable. Start it on port 8000." }, { status: 503 });
  }
}
