"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, useEffect } from "react";

interface NavLink {
  href: string;
  label: string;
  /** Tooltip on hover — kept consistent with the existing layout. */
  title?: string;
  /** Pages that should also light up this link (e.g. /event/* under Transactions). */
  matches?: (pathname: string) => boolean;
}

const LINKS: NavLink[] = [
  {
    href: "/transactions",
    label: "Transactions",
    matches: (p) => p.startsWith("/transactions") || p.startsWith("/event/"),
  },
  {
    href: "/citizen-actions",
    label: "Citizen Actions",
    title: "Directory of citizen-led actions",
  },
  {
    href: "/sources",
    label: "Sources",
  },
  {
    href: "/about",
    label: "About",
  },
  {
    href: "/review",
    label: "Review",
    title: "Human review queue",
  },
];

const COLOR_DEFAULT = "#B8B9B6";
const COLOR_ACTIVE = "#B6FFCE"; // brand green

export function NavLinks() {
  const pathname = usePathname() ?? "/";
  const [mobileOpen, setMobileOpen] = useState(false);

  // Close the mobile drawer whenever the user navigates to a new page.
  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  // Lock background scroll while the drawer is open.
  useEffect(() => {
    if (!mobileOpen) return;
    const original = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = original; };
  }, [mobileOpen]);

  function isActive(link: NavLink) {
    return link.matches
      ? link.matches(pathname)
      : pathname === link.href || pathname.startsWith(link.href + "/");
  }

  return (
    <>
      {/* DESKTOP — inline horizontal links (≥ sm) */}
      <div
        className="hidden sm:flex items-center gap-3 sm:gap-6 text-xs sm:text-sm overflow-x-auto"
        style={{ minWidth: 0 }}
      >
        {LINKS.map((link) => {
          const active = isActive(link);
          return (
            <Link
              key={link.href}
              href={link.href}
              title={link.title}
              aria-current={active ? "page" : undefined}
              className="font-medium hover:opacity-80 whitespace-nowrap"
              style={{ color: active ? COLOR_ACTIVE : COLOR_DEFAULT }}
            >
              {link.label}
            </Link>
          );
        })}
      </div>

      {/* MOBILE — hamburger button (< sm) */}
      <button
        type="button"
        onClick={() => setMobileOpen((v) => !v)}
        aria-label={mobileOpen ? "Close menu" : "Open menu"}
        aria-expanded={mobileOpen}
        className="sm:hidden inline-flex items-center justify-center"
        style={{
          width: 36,
          height: 36,
          padding: 0,
          background: "transparent",
          border: "1px solid #2E2E2E",
          color: "#B8B9B6",
          cursor: "pointer",
        }}
      >
        {/* Three-bar icon (or X when open) */}
        <span style={{ display: "flex", flexDirection: "column", gap: 4 }} aria-hidden>
          <span style={{ width: 18, height: 2, background: "#B8B9B6", display: "block",
            transform: mobileOpen ? "rotate(45deg) translate(4px, 4px)" : "none",
            transition: "transform 150ms ease" }} />
          <span style={{ width: 18, height: 2, background: "#B8B9B6", display: "block",
            opacity: mobileOpen ? 0 : 1,
            transition: "opacity 100ms ease" }} />
          <span style={{ width: 18, height: 2, background: "#B8B9B6", display: "block",
            transform: mobileOpen ? "rotate(-45deg) translate(4px, -4px)" : "none",
            transition: "transform 150ms ease" }} />
        </span>
      </button>

      {/* MOBILE — fullscreen drawer (< sm only) */}
      {mobileOpen && (
        <div
          role="dialog"
          aria-modal="true"
          className="sm:hidden"
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            zIndex: 60,
            background: "rgba(17, 17, 17, 0.97)",
            backdropFilter: "blur(8px)",
            display: "flex",
            flexDirection: "column",
          }}
        >
          {/* Drawer header — match the navbar height + a close button */}
          <div
            style={{
              padding: "16px 16px 12px",
              borderBottom: "1px solid #2E2E2E",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <span
              className="font-mono text-xs uppercase tracking-wider"
              style={{ color: "#B8B9B6" }}
            >
              Menu
            </span>
            <button
              type="button"
              onClick={() => setMobileOpen(false)}
              aria-label="Close menu"
              style={{
                width: 36,
                height: 36,
                padding: 0,
                background: "transparent",
                border: "1px solid #2E2E2E",
                color: "#B8B9B6",
                cursor: "pointer",
                fontFamily: "ui-monospace, monospace",
                fontSize: 16,
                lineHeight: 1,
              }}
            >
              ×
            </button>
          </div>

          {/* Drawer links — vertical list */}
          <nav style={{ display: "flex", flexDirection: "column", padding: "8px 0" }}>
            {LINKS.map((link) => {
              const active = isActive(link);
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  title={link.title}
                  aria-current={active ? "page" : undefined}
                  className="font-medium"
                  style={{
                    display: "block",
                    padding: "16px 20px",
                    fontSize: 16,
                    color: active ? COLOR_ACTIVE : COLOR_DEFAULT,
                    borderBottom: "1px solid #1E1E1E",
                    textDecoration: "none",
                  }}
                >
                  {link.label}
                </Link>
              );
            })}
          </nav>
        </div>
      )}
    </>
  );
}
