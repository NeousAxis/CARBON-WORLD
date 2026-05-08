import Link from "next/link";
import type { CitizenVsInstitutional } from "@/lib/types";
import { InfoTooltip } from "../InfoTooltip";

export interface CitizenVsInstitutionalCardProps {
  data: CitizenVsInstitutional;
}

/**
 * CitizenVsInstitutionalCard — server component.
 *
 * Tests Cyril's hypothesis (2026-05-05) that citizen actions outnumber
 * government decisions per day. Two big counters + a tiny daily bar
 * chart so the trend is visible at a glance.
 *
 * Classification logic lives in the worker (`_is_citizen_event` in
 * exporter.py) — see InfoTooltip text for the user-facing summary.
 */
export function CitizenVsInstitutionalCard({
  data,
}: CitizenVsInstitutionalCardProps) {
  const total = data.citizen + data.institutional;
  const pctCitizen = total > 0 ? Math.round((data.citizen / total) * 100) : 0;
  const pctInstitutional = total > 0 ? 100 - pctCitizen : 0;

  // Daily bars (max value across both series for normalization)
  const max = Math.max(
    1,
    ...data.daily.map((d) => Math.max(d.citizen, d.institutional)),
  );

  return (
    <div
      style={{
        backgroundColor: "var(--card-bg)",
        border: "1px solid var(--border)",
      }}
      className="p-4"
    >
      <p
        className="text-xs uppercase tracking-wider font-mono mb-1"
        style={{ color: "var(--muted)" }}
      >
        CITIZEN VS INSTITUTIONAL · 7D
        <InfoTooltip text="Tests the hypothesis that citizen-led actions outnumber government decisions per day. An event counts as CITIZEN when it is editorial-consciousness, comes from a citizen/NGO outlet (Mongabay, Reporterre, Yes Magazine, Greenpeace, La Via Campesina…), or its title/justification mentions volunteer, grassroots, indigenous, coalition, NGO, activist, protest, restoration, rescue, assembly, movement, petition, etc. Otherwise classified as INSTITUTIONAL (laws, treaties, court rulings, corporate or government decisions). On-chain only." />
      </p>
      <p
        className="text-[10px] uppercase tracking-wider font-mono mb-4"
        style={{ color: "var(--brand-teal)" }}
      >
        WHO ACTS MORE — PEOPLE OR POWER?
      </p>

      {total === 0 ? (
        <div className="flex items-center justify-center py-8">
          <span
            className="text-xs font-mono uppercase tracking-wider"
            style={{ color: "var(--muted)" }}
          >
            NO DATA YET
          </span>
        </div>
      ) : (
        <>
          {/* Two big counters — each clickable to drill down to /events */}
          <div className="grid grid-cols-2 gap-3 mb-4">
            <Link
              href="/events?bucket=citizen&since=7d"
              className="block p-3 hover:opacity-90"
              style={{
                backgroundColor: "#111111",
                border: "1px solid var(--border)",
                cursor: "pointer",
                textDecoration: "none",
              }}
              title={`See the ${data.citizen} citizen-led events`}
            >
              <p
                className="text-[10px] uppercase tracking-wider font-mono mb-1"
                style={{ color: "var(--success-fg, #B6FFCE)" }}
              >
                CITIZEN
              </p>
              <p
                className="text-3xl font-mono font-bold leading-none"
                style={{ color: "var(--success-fg, #B6FFCE)" }}
              >
                {data.citizen}
              </p>
              <p className="text-xs font-mono mt-1" style={{ color: "var(--muted)" }}>
                {pctCitizen}% · click to see events
              </p>
            </Link>
            <Link
              href="/events?bucket=institutional&since=7d"
              className="block p-3 hover:opacity-90"
              style={{
                backgroundColor: "#111111",
                border: "1px solid var(--border)",
                cursor: "pointer",
                textDecoration: "none",
              }}
              title={`See the ${data.institutional} institutional events`}
            >
              <p
                className="text-[10px] uppercase tracking-wider font-mono mb-1"
                style={{ color: "#FF8400" }}
              >
                INSTITUTIONAL
              </p>
              <p
                className="text-3xl font-mono font-bold leading-none"
                style={{ color: "#FF8400" }}
              >
                {data.institutional}
              </p>
              <p className="text-xs font-mono mt-1" style={{ color: "var(--muted)" }}>
                {pctInstitutional}% · click to see events
              </p>
            </Link>
          </div>

          {/* Verdict line — direct answer to the hypothesis */}
          <p
            className="text-[11px] font-mono mb-3"
            style={{ color: "var(--foreground)" }}
          >
            {data.citizen > data.institutional ? (
              <>
                <span style={{ color: "var(--success-fg, #B6FFCE)" }}>● Citizens</span>{" "}
                lead by{" "}
                <span style={{ color: "var(--foreground)" }}>
                  {data.citizen - data.institutional}
                </span>{" "}
                event{data.citizen - data.institutional === 1 ? "" : "s"}.
              </>
            ) : data.institutional > data.citizen ? (
              <>
                <span style={{ color: "#FF8400" }}>● Institutions</span> lead by{" "}
                <span style={{ color: "var(--foreground)" }}>
                  {data.institutional - data.citizen}
                </span>{" "}
                event{data.institutional - data.citizen === 1 ? "" : "s"}.
              </>
            ) : (
              <span>Tied at {data.citizen} each.</span>
            )}
          </p>

          {/* Daily breakdown — paired vertical mini-bars per day */}
          <div className="flex flex-col gap-2">
            <p
              className="text-[10px] uppercase tracking-wider font-mono"
              style={{ color: "var(--muted)" }}
            >
              DAILY BREAKDOWN
            </p>
            <div className="flex items-end justify-between gap-1" style={{ height: 60 }}>
              {data.daily.map((d) => {
                const ch = max > 0 ? (d.citizen / max) * 50 : 0;
                const ih = max > 0 ? (d.institutional / max) * 50 : 0;
                return (
                  <div
                    key={d.date}
                    className="flex flex-col items-center"
                    style={{ flex: 1, minWidth: 0 }}
                    title={`${d.date}: ${d.citizen} citizen / ${d.institutional} institutional`}
                  >
                    <div
                      style={{
                        display: "flex",
                        alignItems: "flex-end",
                        gap: 2,
                        height: 50,
                      }}
                    >
                      <div
                        style={{
                          width: 6,
                          height: ch,
                          backgroundColor: "var(--success-fg, #B6FFCE)",
                          opacity: 0.85,
                        }}
                      />
                      <div
                        style={{
                          width: 6,
                          height: ih,
                          backgroundColor: "#FF8400",
                          opacity: 0.85,
                        }}
                      />
                    </div>
                    <span
                      className="text-[9px] font-mono"
                      style={{ color: "var(--muted)", marginTop: 4 }}
                    >
                      {d.date.slice(5)}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
