import type { Metadata } from "next";
import { Geist } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const geist = Geist({
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "CARBON WORLD",
  description:
    "AI-powered ethical scoring of human decisions. CBWD token on Solana.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={geist.className}>
      <head>
        <link
          href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="min-h-screen flex flex-col antialiased" style={{ backgroundColor: "#111111", color: "#FFFFFF" }}>
        {/* Navbar */}
        <header className="sticky top-0 z-50" style={{ backgroundColor: "#1A1A1A", borderBottom: "1px solid #2E2E2E" }}>
          <nav className="mx-auto max-w-5xl flex items-center justify-between px-6 py-4">
            <Link
              href="/"
              className="text-xl font-bold tracking-tight"
              style={{ color: "#FF8400" }}
            >
              CARBON WORLD
            </Link>
            <div className="flex items-center gap-6">
              <Link
                href="/sources"
                className="text-sm font-medium hover:opacity-80"
                style={{ color: "#B8B9B6" }}
              >
                Sources
              </Link>
              <Link
                href="/about"
                className="text-sm font-medium hover:opacity-80"
                style={{ color: "#B8B9B6" }}
              >
                About
              </Link>
            </div>
          </nav>
        </header>

        {/* Main content */}
        <main className="flex-1">{children}</main>

        {/* Footer */}
        <footer style={{ backgroundColor: "#1A1A1A", borderTop: "1px solid #2E2E2E" }}>
          <div className="mx-auto max-w-5xl px-6 py-6 flex items-center justify-between text-sm" style={{ color: "#B8B9B6" }}>
            <span>Powered by Carbon World</span>
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
