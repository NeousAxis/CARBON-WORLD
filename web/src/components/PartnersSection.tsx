import Link from "next/link";

interface Partner {
  slug: string;
  name: string;
  monogram: string;
  type: string;
  tagline: string;
  accent: "primary" | "success" | "foreground";
  website?: string;
}

const PARTNERS: Partner[] = [
  {
    slug: "helion-watch",
    name: "Helion Watch",
    monogram: "HW",
    type: "Independent Media · Mock",
    tagline: "Placeholder organisation — replace once a real partner signs in.",
    accent: "primary",
  },
  {
    slug: "boreal-institute",
    name: "Boreal Institute",
    monogram: "BI",
    type: "Climate Think Tank · Mock",
    tagline: "Placeholder organisation — replace once a real partner signs in.",
    accent: "success",
  },
  {
    slug: "mosaic-research-lab",
    name: "Mosaic Research Lab",
    monogram: "MR",
    type: "Sustainable Development · Mock",
    tagline: "Placeholder organisation — replace once a real partner signs in.",
    accent: "foreground",
  },
];

const ACCENT_CLASS: Record<Partner["accent"], string> = {
  primary: "text-[var(--primary)] border-[var(--primary)]",
  success: "text-[var(--success-fg)] border-[var(--success-fg)]",
  foreground: "text-[var(--foreground)] border-[var(--muted)]",
};

function PartnerLogo({ monogram, accent }: { monogram: string; accent: Partner["accent"] }) {
  return (
    <div
      className={`flex h-16 w-16 shrink-0 items-center justify-center border font-mono text-lg font-semibold tracking-tighter ${ACCENT_CLASS[accent]}`}
      style={{ backgroundColor: "var(--card-bg)" }}
      aria-hidden
    >
      {monogram}
    </div>
  );
}

export function PartnersSection({ partners = PARTNERS }: { partners?: Partner[] }) {
  return (
    <section
      className="border p-4"
      style={{
        backgroundColor: "var(--card-bg)",
        borderColor: "var(--border)",
      }}
    >
      <header className="flex flex-wrap items-baseline justify-between gap-2 pb-4">
        <div className="flex items-baseline gap-3">
          <h2
            className="font-mono text-sm uppercase tracking-wider"
            style={{ color: "var(--muted)" }}
          >
            Partners · Early Supporters
          </h2>
          <span
            className="font-mono text-[10px] uppercase tracking-wider"
            style={{
              color: "var(--warning-fg)",
              backgroundColor: "var(--warning-bg)",
              border: "1px solid var(--warning-fg)",
              padding: "2px 6px",
            }}
          >
            Mock · Preview only
          </span>
        </div>
        <p
          className="font-mono text-xs uppercase tracking-wider"
          style={{ color: "var(--muted)" }}
        >
          No real partners yet — outreach in progress
        </p>
      </header>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {partners.map((partner) => {
          const body = (
            <div
              className="flex items-start gap-4 border p-4 transition-colors"
              style={{
                backgroundColor: "var(--background)",
                borderColor: "var(--border)",
              }}
            >
              <PartnerLogo monogram={partner.monogram} accent={partner.accent} />
              <div className="flex min-w-0 flex-1 flex-col gap-1">
                <div
                  className="font-mono text-xs uppercase tracking-wider"
                  style={{ color: "var(--muted)" }}
                >
                  {partner.type}
                </div>
                <div
                  className="truncate font-mono text-base font-medium"
                  style={{ color: "var(--foreground)" }}
                >
                  {partner.name}
                </div>
                <div
                  className="text-xs leading-snug"
                  style={{ color: "var(--muted)" }}
                >
                  {partner.tagline}
                </div>
              </div>
            </div>
          );

          if (!partner.website) {
            return (
              <div key={partner.slug} aria-label={`${partner.name} — ${partner.type}`}>
                {body}
              </div>
            );
          }

          return (
            <Link
              key={partner.slug}
              href={partner.website}
              target="_blank"
              rel="noreferrer noopener"
              aria-label={`${partner.name} — ${partner.type}`}
              className="block hover:opacity-90"
            >
              {body}
            </Link>
          );
        })}
      </div>

      <footer className="mt-4 flex items-center justify-between">
        <p
          className="font-mono text-[11px] uppercase tracking-wider"
          style={{ color: "var(--muted)" }}
        >
          Media · Think tanks · NGOs — join via neousaxis@gmail.com
        </p>
        <Link
          href="mailto:neousaxis@gmail.com?subject=CARBON%20WORLD%20API%20partnership"
          className="font-mono text-[11px] uppercase tracking-wider"
          style={{ color: "var(--primary)" }}
        >
          REQUEST ACCESS →
        </Link>
      </footer>
    </section>
  );
}
