const MAX_BODY_BYTES = 5 * 1024 * 1024;

export async function GET() {
  try {
    const upstream = await fetch(`${process.env.CY06_API_URL ?? "http://127.0.0.1:8000"}/api/v1/demo`, { cache: "no-store" });
    return new Response(await upstream.text(), {
      status: upstream.status,
      headers: { "Content-Type": "application/json" },
    });
  } catch {
    return Response.json({ detail: "Python analysis API is unavailable. Start it on port 8000." }, { status: 503 });
  }
}

export async function POST(request: Request) {
  const body = await request.text();
  if (new TextEncoder().encode(body).byteLength > MAX_BODY_BYTES) {
    return Response.json({ detail: "Input is too large. Maximum size is 5 MB." }, { status: 413 });
  }

  try {
    const upstream = await fetch(`${process.env.CY06_API_URL ?? "http://127.0.0.1:8000"}/api/v1/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
      cache: "no-store",
    });
    return new Response(await upstream.text(), {
      status: upstream.status,
      headers: { "Content-Type": "application/json" },
    });
  } catch {
    return Response.json({ detail: "Python analysis API is unavailable. Start it on port 8000." }, { status: 503 });
  }
}
