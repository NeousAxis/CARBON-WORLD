export interface PartnerEntry {
  organization: string;
  submissions: number;
}

export interface PartnerActivityCardProps {
  /**
   * Organizations that submitted events via the Tier 2 API this week.
   * Empty array = no submissions yet.
   */
  partners: PartnerEntry[];
}

const MAX_VISIBLE = 5;

/**
 * PartnerActivityCard — Server Component
 *
 * Lists organizations that submitted events via the Tier 2 Bearer API
 * over the last 7 days. Shows empty state with contact info when no
 * submissions exist yet.
 *
 * Example props for smoke-test (non-empty):
 * <PartnerActivityCard partners={[
 *   { organization: "Amazon Watch", submissions: 3 },
 *   { organization: "Global Witness", submissions: 2 },
 * ]} />
 *
 * Example props for smoke-test (empty):
 * <PartnerActivityCard partners={[]} />
 */
export function PartnerActivityCard({ partners }: PartnerActivityCardProps) {
  const visible = partners.slice(0, MAX_VISIBLE);
  const overflow = partners.length - MAX_VISIBLE;

  return (
    <div
      style={{
        backgroundColor: "var(--card-bg)",
        border: "1px solid var(--border)",
      }}
      className="p-4"
    >
      {/* Title */}
      <p
        className="text-xs uppercase tracking-wider font-mono mb-3"
        style={{ color: "var(--muted)" }}
      >
        ACTIVE PARTNERS · 7D
      </p>

      {partners.length === 0 ? (
        /* Empty state */
        <div className="flex flex-col items-center gap-2 py-4">
          <span
            className="text-xs font-mono uppercase tracking-wider"
            style={{ color: "var(--muted)" }}
          >
            NO PARTNER SUBMISSIONS YET
          </span>
          <span
            className="text-[10px] font-mono text-center"
            style={{ color: "var(--brand-teal)" }}
          >
            Contact hello@carbon-token.xyz for API access
          </span>
        </div>
      ) : (
        /* Partner list */
        <div className="flex flex-col">
          {visible.map((partner, i) => (
            <div
              key={partner.organization}
              className="flex items-center justify-between py-2"
              style={{
                borderBottom:
                  i < visible.length - 1 || overflow > 0
                    ? "1px solid var(--border)"
                    : "none",
              }}
            >
              <span
                className="text-xs font-mono uppercase tracking-wider truncate mr-4"
                style={{ color: "var(--foreground)" }}
              >
                {partner.organization}
              </span>
              <span
                className="text-xs font-mono tabular-nums whitespace-nowrap shrink-0"
                style={{ color: "var(--muted)" }}
              >
                {partner.submissions}{" "}
                {partner.submissions === 1 ? "submission" : "submissions"}
              </span>
            </div>
          ))}

          {overflow > 0 && (
            <div className="pt-2">
              <span
                className="text-xs font-mono"
                style={{ color: "var(--muted)" }}
              >
                +{overflow} more
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
