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
      <body className="min-h-screen flex flex-col bg-gray-50 text-gray-900 antialiased">
        {/* Navbar */}
        <header className="sticky top-0 z-50 bg-white border-b border-gray-200">
          <nav className="mx-auto max-w-5xl flex items-center justify-between px-6 py-4">
            <Link
              href="/"
              className="text-xl font-bold tracking-tight text-gray-900"
            >
              CARBON WORLD
            </Link>
            <div className="flex items-center gap-6">
              <Link
                href="/about"
                className="text-sm font-medium text-gray-600 hover:text-gray-900"
              >
                About
              </Link>
            </div>
          </nav>
        </header>

        {/* Main content */}
        <main className="flex-1">{children}</main>

        {/* Footer */}
        <footer className="border-t border-gray-200 bg-white">
          <div className="mx-auto max-w-5xl px-6 py-6 flex items-center justify-between text-sm text-gray-500">
            <span>Powered by AI on Solana</span>
            <a
              href="https://github.com/NeousAxis/CARBON-WORLD"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-gray-900"
            >
              GitHub
            </a>
          </div>
        </footer>
      </body>
    </html>
  );
}
