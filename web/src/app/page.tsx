import fs from "fs";
import path from "path";
import { DashboardClient } from "@/components/DashboardClient";
import type { ExportData } from "@/lib/types";

// Force dynamic rendering — read export.json fresh on every request.
// Without this, Next.js would pre-render at build time and show stale data
// until the next deploy.
export const dynamic = "force-dynamic";

function loadInitialData(): ExportData {
  const filePath = path.join(process.cwd(), "data", "export.json");
  const raw = fs.readFileSync(filePath, "utf-8");
  return JSON.parse(raw) as ExportData;
}

export default function Home() {
  const initialData = loadInitialData();
  return <DashboardClient initialData={initialData} />;
}
