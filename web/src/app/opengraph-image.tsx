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
          backgroundColor: "#111111",
          padding: "60px 72px",
          fontFamily: "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
          color: "#FFFFFF",
        }}
      >
        {/* Header row: logo + brand */}
        <div style={{ display: "flex", alignItems: "center", gap: 28 }}>
          {logo ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={logo} alt="" width={120} height={120} />
          ) : null}
          <div style={{ display: "flex", flexDirection: "column" }}>
            <div
              style={{
                display: "flex",
                fontSize: 72,
                fontWeight: 700,
                letterSpacing: "0.02em",
                lineHeight: 1,
              }}
            >
              <span style={{ color: "#B6FFCE" }}>CARBON</span>
              <span style={{ width: 18 }} />
              <span style={{ color: "#0190A0" }}>WORLD</span>
            </div>
            <div
              style={{
                display: "flex",
                marginTop: 12,
                fontSize: 22,
                letterSpacing: "0.18em",
                textTransform: "uppercase",
                color: "#B8B9B6",
              }}
            >
              Swiss-based · open-source · volunteer
            </div>
          </div>
        </div>

        {/* Spacer */}
        <div style={{ display: "flex", flex: 1 }} />

        {/* Tagline block */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            paddingTop: 32,
            borderTop: "1px solid #2E2E2E",
          }}
        >
          <div
            style={{
              display: "flex",
              fontSize: 36,
              lineHeight: 1.25,
              color: "#FFFFFF",
            }}
          >
            An AI-driven Solana token whose supply reflects humanity's
          </div>
          <div
            style={{
              display: "flex",
              fontSize: 36,
              lineHeight: 1.25,
              marginTop: 8,
              color: "#FFFFFF",
            }}
          >
            measurable impact on the <span style={{ color: "#B6FFCE", marginLeft: 12, marginRight: 12 }}>living world</span>.
          </div>

          <div style={{ display: "flex", marginTop: 32, gap: 24 }}>
            <div
              style={{
                display: "flex",
                padding: "10px 16px",
                border: "1px solid #2E2E2E",
                fontSize: 18,
                letterSpacing: "0.12em",
                textTransform: "uppercase",
                color: "#B6FFCE",
              }}
            >
              BURN  decisions help life
            </div>
            <div
              style={{
                display: "flex",
                padding: "10px 16px",
                border: "1px solid #2E2E2E",
                fontSize: 18,
                letterSpacing: "0.12em",
                textTransform: "uppercase",
                color: "#FF5C33",
              }}
            >
              MINT  decisions harm it
            </div>
          </div>

          <div
            style={{
              display: "flex",
              marginTop: 32,
              fontSize: 20,
              letterSpacing: "0.18em",
              textTransform: "uppercase",
              color: "#B8B9B6",
            }}
          >
            carbon-world.xyz
          </div>
        </div>
      </div>
    ),
    { ...size },
  );
}
