import type { Metadata } from "next";
import { Geist } from "next/font/google";
import Link from "next/link";
import { RawFeedTicker } from "@/components/RawFeedTicker";
import { NavLinks } from "@/components/NavLinks";
import "./globals.css";

const geist = Geist({
  subsets: ["latin"],
});

// `metadataBase` is required so Next 16 can resolve relative og:image URLs
// (the auto-generated /opengraph-image) against the canonical host.
export const metadata: Metadata = {
  metadataBase: new URL("https://carbon-world.xyz"),
  title: {
    default: "CARBON WORLD — AI-driven Solana ethical impact index",
    template: "%s · CARBON WORLD",
  },
  description:
    "An AI-driven Solana token (CBWD) whose supply reflects humanity's measurable impact on the living world. BURN when decisions help life, MINT when they harm it. Swiss-based, open-source, volunteer.",
  applicationName: "CARBON WORLD",
  keywords: [
    "CARBON WORLD",
    "CBWD",
    "Solana",
    "ethics",
    "SDG",
    "planetary boundaries",
    "open-source",
    "AI",
    "indicator",
  ],
  authors: [{ name: "Neous Axis", url: "https://carbon-world.xyz" }],
  creator: "Neous Axis",
  publisher: "Neous Axis",
  alternates: {
    canonical: "https://carbon-world.xyz",
  },
  openGraph: {
    type: "website",
    locale: "en_US",
    siteName: "CARBON WORLD",
    title: "CARBON WORLD — AI-driven Solana ethical impact index",
    description:
      "An AI-driven Solana token whose supply reflects humanity's measurable impact on the living world. BURN when decisions help life, MINT when they harm it.",
    url: "https://carbon-world.xyz",
    // og:image is auto-injected from src/app/opengraph-image.tsx
  },
  twitter: {
    card: "summary_large_image",
    title: "CARBON WORLD — AI-driven Solana ethical impact index",
    description:
      "An AI-driven Solana token whose supply reflects humanity's measurable impact on the living world.",
    // twitter:image is auto-injected from src/app/opengraph-image.tsx
  },
  robots: {
    index: true,
    follow: true,
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={geist.className}>
      <head>
        <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
        <link
          href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="min-h-screen flex flex-col antialiased" style={{ backgroundColor: "#111111", color: "#FFFFFF" }}>
        {/* Navbar */}
        <header className="sticky top-0 z-50" style={{ backgroundColor: "#1A1A1A", borderBottom: "1px solid #2E2E2E" }}>
          <nav className="mx-auto max-w-5xl flex items-center justify-between px-4 sm:px-6 py-3 sm:py-4 gap-3">
            <Link
              href="/"
              className="flex items-center gap-2 sm:gap-3 text-base sm:text-xl font-bold tracking-tight shrink-0"
              style={{ color: "#B6FFCE" }}
            >
              <img
                src="/carbon-world-xl.png"
                alt="Carbon World"
                className="w-[60px] h-[60px] sm:w-[108px] sm:h-[108px]"
              />
              <span className="hidden xs:inline sm:inline">
                CARBON <span style={{ color: "var(--brand-teal)" }}>WORLD</span>
              </span>
            </Link>
            <NavLinks />
          </nav>
        </header>

        {/* Raw RSS feed ticker — scrolling proof that the system is reading the world */}
        <RawFeedTicker />

        {/* Main content */}
        <main className="flex-1">{children}</main>

        {/* Footer */}
        <footer style={{ backgroundColor: "#1A1A1A", borderTop: "1px solid #2E2E2E" }}>
          <div className="mx-auto max-w-5xl px-4 sm:px-6 py-4 sm:py-6 flex items-center justify-between text-xs sm:text-sm" style={{ color: "#B8B9B6" }}>
            <span>Powered by Carbon World</span>
            <span
              className="font-mono uppercase tracking-wider"
              style={{ color: "#B8B9B6", fontSize: "0.75rem" }}
              aria-label="Swiss based project"
            >
              <span aria-hidden style={{ color: "#FF5C33", marginRight: 6 }}>
                🇨🇭
              </span>
              Swiss based project
            </span>
            <a
              href="https://github.com/NeousAxis/CARBON-WORLD"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:opacity-80"
              style={{ color: "#B8B9B6" }}
            >
              GitHub
            </a>
          </div>
        </footer>
      </body>
    </html>
  );
}
