import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const CANONICAL_HOST = "carbon-token.xyz";

export function middleware(request: NextRequest) {
  const host = request.headers.get("host") || "";
  if (host.endsWith(".vercel.app")) {
    const url = new URL(request.url);
    url.host = CANONICAL_HOST;
    url.protocol = "https:";
    url.port = "";
    return NextResponse.redirect(url, 308);
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/|api/).*)"],
};
