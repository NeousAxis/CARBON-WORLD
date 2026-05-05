import { ImageResponse } from "next/og";
import fs from "node:fs";
import path from "node:path";

// Route segment config — Next 16 picks up `size` and `contentType` for the
// generated <meta property="og:image"> tag and the asset's response headers.
export const alt = "CARBON WORLD — AI-driven Solana token reflecting humanity's impact on the living world";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

// Read the logo from /public at build/runtime; ImageResponse needs an
// inline data URI for guaranteed embedding in the social preview.
function getLogoDataUri(): string {
  try {
    const logoPath = path.join(process.cwd(), "public", "carbon-world-xl.png");
    const buf = fs.readFileSync(logoPath);
    return `data:image/png;base64,${buf.toString("base64")}`;
  } catch {
    return "";
  }
}

/**
 * Hero-style OG card.
 *
 * Design priority: visual identity must survive when the image is downscaled
 * to a small thumbnail (iMessage / WhatsApp / Slack inline previews scale
 * the 1200×630 to ~150 px wide, where small details vanish).
 *
 * → Big logo, big brand wordmark, minimal text, lots of breathing room.
 */
export default async function OpenGraphImage() {
  const logo = getLogoDataUri();

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          backgroundColor: "#111111",
          padding: "60px",
          fontFamily: "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
        }}
      >
        {/* Hero row: logo + wordmark, centered */}
        <div style={{ display: "flex", alignItems: "center", gap: 40 }}>
          {logo ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={logo} alt="" width={260} height={260} />
          ) : null}
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "flex-start",
            }}
          >
            <div
              style={{
                display: "flex",
                fontSize: 110,
                fontWeight: 700,
                lineHeight: 1,
                letterSpacing: "0.01em",
              }}
            >
              <span style={{ color: "#B6FFCE" }}>CARBON</span>
            </div>
            <div
              style={{
                display: "flex",
                fontSize: 110,
                fontWeight: 700,
                lineHeight: 1,
                letterSpacing: "0.01em",
                marginTop: 12,
              }}
            >
              <span style={{ color: "#0190A0" }}>WORLD</span>
            </div>
          </div>
        </div>

        {/* Tagline */}
        <div
          style={{
            display: "flex",
            marginTop: 48,
            fontSize: 26,
            letterSpacing: "0.18em",
            textTransform: "uppercase",
            color: "#B8B9B6",
          }}
        >
          AI-driven · Solana · ethical impact index
        </div>
      </div>
    ),
    { ...size },
  );
}
