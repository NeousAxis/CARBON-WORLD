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
    <div className="mx-auto max-w-3xl px-6 py-12">
      <Link
        href="/"
        className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-900 mb-8"
      >
        &larr; Back to dashboard
      </Link>

      <h1 className="text-3xl font-bold text-gray-900 mb-6">
        About CARBON WORLD
      </h1>

      {/* Introduction */}
      <section className="mb-10">
        <p className="text-gray-700 leading-relaxed mb-4">
          CARBON WORLD is an experimental token on Solana (CBWD) whose supply is
          controlled by a local AI system. The AI monitors real-world government
          and institutional decisions that affect living beings and the
          environment, then adjusts the token supply accordingly.
        </p>
        <p className="text-gray-700 leading-relaxed">
          Positive decisions for the planet trigger a <strong className="text-emerald-600">BURN</strong> (reducing
          supply), while harmful decisions trigger a <strong className="text-red-600">MINT</strong> (increasing
          supply). The token becomes a living ledger of humanity&apos;s
          collective impact on the world.
        </p>
      </section>

      {/* How scoring works */}
      <section className="mb-10">
        <h2 className="text-xl font-semibold text-gray-900 mb-4">
          How the AI scoring works
        </h2>
        <p className="text-gray-700 leading-relaxed mb-4">
          Every event goes through a multi-step analysis pipeline. First, an AI
          classifier filters for concrete governmental or institutional actions.
          Then, a deeper AI model performs a dual ethical analysis &mdash;
          identifying both positive and negative aspects of each decision across
          7 international ethical frameworks.
        </p>
        <p className="text-gray-700 leading-relaxed mb-4">
          The analysis uses a 4-dimensional temporal framework:
        </p>
        <div className="rounded-2xl bg-white border border-gray-200 p-6 mb-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
            <div>
              <div className="font-semibold text-gray-900">
                Snapshot (25%)
              </div>
              <div className="text-gray-600">
                Net impact today: positives minus negatives
              </div>
            </div>
            <div>
              <div className="font-semibold text-gray-900">
                Trajectory (20%)
              </div>
              <div className="text-gray-600">
                Direction of the underlying trend
              </div>
            </div>
            <div>
              <div className="font-semibold text-gray-900">
                Revaluation (15%)
              </div>
              <div className="text-gray-600">
                Triggers that could flip the judgment
              </div>
            </div>
            <div>
              <div className="font-semibold text-gray-900">
                Prospective (40%)
              </div>
              <div className="text-gray-600">
                3 future scenarios over 2-30 years
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Score scale */}
      <section className="mb-10">
        <h2 className="text-xl font-semibold text-gray-900 mb-4">
          Decision scale
        </h2>
        <div className="rounded-2xl bg-white border border-gray-200 p-6">
          <div className="space-y-3 text-sm">
            <div className="flex items-center gap-3">
              <span className="inline-block w-24 rounded-full bg-emerald-100 text-emerald-700 px-3 py-1 text-center font-semibold text-xs uppercase">
                BURN
              </span>
              <span className="text-gray-700">
                Score &ge; 6 &mdash; Positive for the planet. Token supply
                decreases.
              </span>
            </div>
            <div className="flex items-center gap-3">
              <span className="inline-block w-24 rounded-full bg-gray-100 text-gray-600 px-3 py-1 text-center font-semibold text-xs uppercase">
                NEUTRAL
              </span>
              <span className="text-gray-700">
                Score between 4 and 6 &mdash; Mixed or inconclusive impact.
              </span>
            </div>
            <div className="flex items-center gap-3">
              <span className="inline-block w-24 rounded-full bg-red-100 text-red-700 px-3 py-1 text-center font-semibold text-xs uppercase">
                MINT
              </span>
              <span className="text-gray-700">
                Score &le; 4 &mdash; Harmful to the planet. Token supply
                increases.
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* 7 frameworks */}
      <section className="mb-10">
        <h2 className="text-xl font-semibold text-gray-900 mb-4">
          7 ethical frameworks
        </h2>
        <div className="space-y-3">
          {frameworks.map((fw, i) => (
            <div
              key={i}
              className="rounded-2xl bg-white border border-gray-200 p-4"
            >
              <div className="font-semibold text-gray-900 text-sm">
                {i + 1}. {fw.name}
              </div>
              <div className="text-gray-600 text-sm">{fw.description}</div>
            </div>
          ))}
        </div>
      </section>

      {/* Token info */}
      <section>
        <h2 className="text-xl font-semibold text-gray-900 mb-4">
          Token details
        </h2>
        <div className="rounded-2xl bg-white border border-gray-200 p-6 text-sm">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <span className="text-gray-500">Name:</span>{" "}
              <span className="font-medium">Carbon World</span>
            </div>
            <div>
              <span className="text-gray-500">Symbol:</span>{" "}
              <span className="font-medium">CBWD</span>
            </div>
            <div>
              <span className="text-gray-500">Network:</span>{" "}
              <span className="font-medium">Solana (devnet)</span>
            </div>
            <div>
              <span className="text-gray-500">Decimals:</span>{" "}
              <span className="font-medium">6</span>
            </div>
            <div className="sm:col-span-2">
              <span className="text-gray-500">Mint address:</span>{" "}
              <span className="font-mono text-xs">
                HRqmMnbA18VgstcfjCueAuzVZEoHHbLbbu973AqmK3Fs
              </span>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
