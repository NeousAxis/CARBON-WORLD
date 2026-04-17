import fs from "fs";
import path from "path";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const filePath = path.join(process.cwd(), "data", "export.json");
    const raw = fs.readFileSync(filePath, "utf-8");
    const data = JSON.parse(raw);

    return Response.json(data, {
      headers: {
        "Cache-Control": "no-store, must-revalidate",
      },
    });
  } catch (err) {
    console.error("[api/stats] Failed to read export.json:", err);
    return Response.json(
      { error: "Failed to load stats" },
      { status: 500, headers: { "Cache-Control": "no-store" } }
    );
  }
}
