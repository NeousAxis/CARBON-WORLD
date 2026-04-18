import Link from "next/link";

const frameworks = [
  {
    name: "UN Sustainable Development Goals",
    description: "17 goals addressing global challenges from poverty to climate action",
  },
  {
    name: "Universal Declaration of Human Rights (1948)",
    description: "Fundamental rights and freedoms for all people",
  },
  {
    name: "ILO Core Labor Standards",
    description: "Freedom of association, forced labor, child labor, discrimination",
  },
  {
    name: "Universal Declaration of Animal Rights (1978)",
    description: "Rights of animals to life, liberty, and freedom from suffering",
  },
  {
    name: "UN Convention on the Rights of the Child",
    description: "Protection and well-being of children worldwide",
  },
  {
    name: "UN Declaration on the Rights of Indigenous Peoples",
    description: "Self-determination, cultural identity, and land rights",
  },
  {
    name: "Planetary Boundaries",
    description: "9 scientific limits for a safe operating space for humanity",
  },
];

export default function AboutPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 sm:px-6 py-8 sm:py-12" style={{ backgroundColor: "#111111" }}>
      <Link
        href="/"
        className="inline-flex items-center gap-1 text-sm hover:opacity-80 mb-6 sm:mb-8"
        style={{ color: "#B8B9B6" }}
      >
        &larr; Back to dashboard
      </Link>

      <h1 className="text-2xl sm:text-3xl font-bold mb-4 sm:mb-6" style={{ color: "#FFFFFF" }}>
        About CARBON WORLD
      </h1>

      {/* Introduction */}
      <section className="mb-10">
        <p className="leading-relaxed mb-4" style={{ color: "#B8B9B6" }}>
          CARBON WORLD is an experimental token on Solana (CBWD) whose supply is
          controlled by a local AI system. The AI monitors real-world government
          and institutional decisions that affect living beings and the
          environment, then adjusts the token supply accordingly.
        </p>
        <p className="leading-relaxed" style={{ color: "#B8B9B6" }}>
          Positive decisions for the planet trigger a <strong style={{ color: "#B6FFCE" }}>BURN</strong> (reducing
          supply), while harmful decisions trigger a <strong style={{ color: "#FF5C33" }}>MINT</strong> (increasing
          supply). The token becomes a living ledger of humanity&apos;s
          collective impact on the world.
        </p>
      </section>

      {/* How scoring works */}
      <section className="mb-10">
        <h2 className="text-xl font-semibold mb-4" style={{ color: "#FFFFFF" }}>
          How the AI scoring works
        </h2>
        <p className="leading-relaxed mb-4" style={{ color: "#B8B9B6" }}>
          Every event goes through a multi-step analysis pipeline. First, an AI
          classifier filters for concrete governmental or institutional actions.
          Then, a deeper AI model performs a dual ethical analysis &mdash;
          identifying both positive and negative aspects of each decision across
          7 international ethical frameworks.
        </p>
        <p className="leading-relaxed mb-4" style={{ color: "#B8B9B6" }}>
          The analysis uses a 4-dimensional temporal framework:
        </p>
        <div
          className="p-6 mb-4"
          style={{
            backgroundColor: "#1A1A1A",
            border: "1px solid #2E2E2E",
            boxShadow: "0 1px 1.75px rgba(0,0,0,0.05)",
          }}
        >
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
            <div>
              <div className="font-semibold" style={{ color: "#FFFFFF" }}>
                Snapshot (25%)
              </div>
              <div style={{ color: "#B8B9B6" }}>
                Net impact today: positives minus negatives
              </div>
            </div>
            <div>
              <div className="font-semibold" style={{ color: "#FFFFFF" }}>
                Trajectory (20%)
              </div>
              <div style={{ color: "#B8B9B6" }}>
                Direction of the underlying trend
              </div>
            </div>
            <div>
              <div className="font-semibold" style={{ color: "#FFFFFF" }}>
                Revaluation (15%)
              </div>
              <div style={{ color: "#B8B9B6" }}>
                Triggers that could flip the judgment
              </div>
            </div>
            <div>
              <div className="font-semibold" style={{ color: "#FFFFFF" }}>
                Prospective (40%)
              </div>
              <div style={{ color: "#B8B9B6" }}>
                3 future scenarios over 2-30 years
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Score scale */}
      <section className="mb-10">
        <h2 className="text-xl font-semibold mb-4" style={{ color: "#FFFFFF" }}>
          Decision scale
        </h2>
        <div
          className="p-6"
          style={{
            backgroundColor: "#1A1A1A",
            border: "1px solid #2E2E2E",
            boxShadow: "0 1px 1.75px rgba(0,0,0,0.05)",
          }}
        >
          <div className="space-y-3 text-sm">
            <div className="flex items-center gap-3">
              <span
                className="inline-block w-24 px-3 py-1 text-center font-semibold text-xs uppercase"
                style={{ backgroundColor: "#222924", color: "#B6FFCE" }}
              >
                BURN
              </span>
              <span style={{ color: "#B8B9B6" }}>
                Score &ge; 6 &mdash; Positive for the planet. Token supply
                decreases.
              </span>
            </div>
            <div className="flex items-center gap-3">
              <span
                className="inline-block w-24 px-3 py-1 text-center font-semibold text-xs uppercase"
                style={{ backgroundColor: "#2E2E2E", color: "#B8B9B6" }}
              >
                NEUTRAL
              </span>
              <span style={{ color: "#B8B9B6" }}>
                Score between 4 and 6 &mdash; Mixed or inconclusive impact.
              </span>
            </div>
            <div className="flex items-center gap-3">
              <span
                className="inline-block w-24 px-3 py-1 text-center font-semibold text-xs uppercase"
                style={{ backgroundColor: "#24100B", color: "#FF5C33" }}
              >
                MINT
              </span>
              <span style={{ color: "#B8B9B6" }}>
                Score &le; 4 &mdash; Harmful to the planet. Token supply
                increases.
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* 7 frameworks */}
      <section className="mb-10">
        <h2 className="text-xl font-semibold mb-4" style={{ color: "#FFFFFF" }}>
          7 ethical frameworks
        </h2>
        <div className="space-y-3">
          {frameworks.map((fw, i) => (
            <div
              key={i}
              className="p-4"
              style={{
                backgroundColor: "#1A1A1A",
                border: "1px solid #2E2E2E",
                boxShadow: "0 1px 1.75px rgba(0,0,0,0.05)",
              }}
            >
              <div className="font-semibold text-sm" style={{ color: "#FFFFFF" }}>
                {i + 1}. {fw.name}
              </div>
              <div className="text-sm" style={{ color: "#B8B9B6" }}>{fw.description}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Token info */}
      <section>
        <h2 className="text-xl font-semibold mb-4" style={{ color: "#FFFFFF" }}>
          Token details
        </h2>
        <div
          className="p-6 text-sm"
          style={{
            backgroundColor: "#1A1A1A",
            border: "1px solid #2E2E2E",
            boxShadow: "0 1px 1.75px rgba(0,0,0,0.05)",
          }}
        >
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <span style={{ color: "#B8B9B6" }}>Name:</span>{" "}
              <span className="font-medium" style={{ color: "#FFFFFF" }}>Carbon World</span>
            </div>
            <div>
              <span style={{ color: "#B8B9B6" }}>Symbol:</span>{" "}
              <span className="font-medium" style={{ color: "#FF8400" }}>CBWD</span>
            </div>
            <div>
              <span style={{ color: "#B8B9B6" }}>Network:</span>{" "}
              <span className="font-medium" style={{ color: "#FFFFFF" }}>Solana (mainnet)</span>
            </div>
            <div>
              <span style={{ color: "#B8B9B6" }}>Decimals:</span>{" "}
              <span className="font-medium" style={{ color: "#FFFFFF" }}>6</span>
            </div>
            <div className="sm:col-span-2">
              <span style={{ color: "#B8B9B6" }}>Mint address:</span>{" "}
              <span className="font-mono text-xs" style={{ color: "#FF8400" }}>
                HRqmMnbA18VgstcfjCueAuzVZEoHHbLbbu973AqmK3Fs
              </span>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
