"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

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

  return (
    <div
      className="flex items-center gap-3 sm:gap-6 text-xs sm:text-sm overflow-x-auto"
      // min-w-0 unblocks `overflow-x-auto` inside a flex parent — without
      // it, the flex child refuses to shrink below content width and the
      // menu spills off the right edge of the navbar on narrow screens.
      style={{ minWidth: 0 }}
    >
      {LINKS.map((link) => {
        const isActive = link.matches
          ? link.matches(pathname)
          : pathname === link.href || pathname.startsWith(link.href + "/");
        return (
          <Link
            key={link.href}
            href={link.href}
            title={link.title}
            aria-current={isActive ? "page" : undefined}
            className="font-medium hover:opacity-80 whitespace-nowrap"
            style={{ color: isActive ? COLOR_ACTIVE : COLOR_DEFAULT }}
          >
            {link.label}
          </Link>
        );
      })}
    </div>
  );
}
