import fs from "fs";
import path from "path";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const filePath = path.join(process.cwd(), "data", "raw_feed.json");
    const raw = fs.readFileSync(filePath, "utf-8");
    return new Response(raw, {
      headers: {
        "content-type": "application/json",
        "cache-control": "no-store, must-revalidate",
      },
    });
  } catch {
    return Response.json(
      { generated_at: new Date().toISOString(), count: 0, articles: [] },
      {
        headers: { "cache-control": "no-store" },
      }
    );
  }
}
