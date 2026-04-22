import { FrameworkBar } from "./FrameworkBar";

export interface FrameworkActivity {
  positive: number;
  negative: number;
}

export interface FrameworkActivityCardProps {
  data: {
    SDG: FrameworkActivity;
    UDHR: FrameworkActivity;
    ILO: FrameworkActivity;
    CRC: FrameworkActivity;
    UNDRIP: FrameworkActivity;
    Animal: FrameworkActivity;
    PB: FrameworkActivity;
  };
}

/** Canonical order and long names for all 7 frameworks */
const FRAMEWORKS: Array<{
  key: keyof FrameworkActivityCardProps["data"];
  code: string;
  name: string;
}> = [
  {
    key: "SDG",
    code: "SDG",
    name: "UN Sustainable Development Goals (17)",
  },
  {
    key: "UDHR",
    code: "UDHR",
    name: "Universal Declaration of Human Rights (1948)",
  },
  {
    key: "ILO",
    code: "ILO",
    name: "ILO Core Labor Standards",
  },
  {
    key: "CRC",
    code: "CRC",
    name: "UN Convention on the Rights of the Child",
  },
  {
    key: "UNDRIP",
    code: "UNDRIP",
    name: "UN Declaration on the Rights of Indigenous Peoples",
  },
  {
    key: "Animal",
    code: "Animal",
    name: "Universal Declaration of Animal Rights (1978)",
  },
  {
    key: "PB",
    code: "PB",
    name: "Planetary Boundaries (Rockstrom 2009)",
  },
];

/**
 * FrameworkActivityCard — Server Component
 *
 * Central "panoptic" indicator showing 7-day ethical activity across the 7
 * UN reference frameworks used by the CARBON WORLD pipeline.
 *
 * Each row is a FrameworkBar (grid 80px|1fr|80px):
 *   - code label  |  stacked burn/mint bar  |  +N / −N counts
 *
 * The header legend uses coloured inline spans so colours are explicit and
 * not reliant on Tailwind arbitrary-value classes that may not purge cleanly.
 *
 * Example:
 *   <FrameworkActivityCard data={{
 *     SDG:    { positive: 16, negative: 19 },
 *     UDHR:   { positive: 0,  negative: 12 },
 *     ILO:    { positive: 2,  negative: 5  },
 *     CRC:    { positive: 1,  negative: 4  },
 *     UNDRIP: { positive: 6,  negative: 2  },
 *     Animal: { positive: 4,  negative: 1  },
 *     PB:     { positive: 8,  negative: 15 },
 *   }} />
 */
export function FrameworkActivityCard({
  data,
}: FrameworkActivityCardProps) {
  return (
    <div
      style={{
        backgroundColor: "var(--card-bg)",
        border: "1px solid var(--border)",
      }}
      className="p-4"
    >
      {/* Header — title left, legend right */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "baseline",
          marginBottom: "4px",
        }}
      >
        {/* Title */}
        <span
          className="font-mono text-sm uppercase tracking-wider"
          style={{ color: "var(--muted)" }}
        >
          FRAMEWORK ACTIVITY · 7 DAYS
        </span>

        {/* Legend: "+ POSITIVE · − NEGATIVE" */}
        <span
          className="font-mono"
          style={{ fontSize: "11px", color: "var(--muted)" }}
        >
          <span style={{ color: "var(--cw-burn)" }}>+</span>
          <span style={{ color: "var(--muted)" }}> POSITIVE</span>
          <span style={{ color: "var(--muted)" }}> &middot; </span>
          <span style={{ color: "var(--cw-mint)" }}>&#x2212;</span>
          <span style={{ color: "var(--muted)" }}> NEGATIVE</span>
        </span>
      </div>

      {/* 7 framework rows */}
      <div>
        {FRAMEWORKS.map(({ key, code, name }) => (
          <FrameworkBar
            key={key}
            code={code}
            name={name}
            positive={data[key].positive}
            negative={data[key].negative}
          />
        ))}
      </div>
    </div>
  );
}
