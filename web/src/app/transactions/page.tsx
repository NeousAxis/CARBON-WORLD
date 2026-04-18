import Link from "next/link";
import { getEvents, formatAmount, formatDate } from "@/lib/data";

export default function TransactionsPage() {
  const events = getEvents();
  const withTx = events.filter((e) => e.tx_hash);
  const withoutTx = events.filter((e) => !e.tx_hash);

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <Link
        href="/"
        className="text-sm hover:opacity-80 mb-6 inline-block"
        style={{ color: "#FF8400" }}
      >
        &larr; Back to dashboard
      </Link>

      <h1
        className="text-3xl font-bold mb-2"
        style={{ fontFamily: "'JetBrains Mono', monospace", color: "#FFFFFF" }}
      >
        On-Chain Transactions
      </h1>
      <p className="mb-8" style={{ color: "#B8B9B6" }}>
        Every MINT and BURN decision is recorded on the Solana blockchain.
        Click any transaction hash to verify it on Solana Explorer.
      </p>

      {/* Stats strip */}
      <div
        className="flex flex-wrap items-center gap-3 sm:gap-6 mb-6 sm:mb-8 p-3 sm:p-4 text-xs"
        style={{ backgroundColor: "#1A1A1A", border: "1px solid #2E2E2E" }}
      >
        <div className="flex items-center gap-2">
          <span style={{ color: "#B8B9B6" }}>ON-CHAIN</span>
          <span className="font-mono font-bold" style={{ color: "#B6FFCE" }}>
            {withTx.length}
          </span>
        </div>
        <div style={{ width: 1, height: 16, backgroundColor: "#2E2E2E" }} />
        <div className="flex items-center gap-2">
          <span style={{ color: "#B8B9B6" }}>PENDING</span>
          <span className="font-mono font-bold" style={{ color: "#FF8400" }}>
            {withoutTx.length}
          </span>
        </div>
        <div style={{ width: 1, height: 16, backgroundColor: "#2E2E2E" }} />
        <div className="flex items-center gap-2">
          <span style={{ color: "#B8B9B6" }}>TOTAL</span>
          <span className="font-mono font-bold" style={{ color: "#FFFFFF" }}>
            {events.length}
          </span>
        </div>
        <div style={{ width: 1, height: 16, backgroundColor: "#2E2E2E" }} />
        <div className="flex items-center gap-2">
          <span style={{ color: "#B8B9B6" }}>NETWORK</span>
          <span className="font-mono font-bold" style={{ color: "#FF8400" }}>
            MAINNET
          </span>
        </div>
      </div>

      {/* On-chain transactions */}
      {withTx.length > 0 && (
        <div
          className="mb-8"
          style={{ backgroundColor: "#1A1A1A", border: "1px solid #2E2E2E" }}
        >
          <div
            className="flex items-center px-4 py-2 text-xs font-bold uppercase tracking-wider"
            style={{ backgroundColor: "#2E2E2E", color: "#B8B9B6" }}
          >
            <span className="w-20">Date</span>
            <span className="w-16">Type</span>
            <span className="flex-1">Event</span>
            <span className="w-28 text-right">Amount</span>
            <span className="w-[340px] text-right">Transaction Hash</span>
          </div>

          {withTx.map((event, i) => {
            const isBurn = event.decision === "BURN";
            return (
              <div
                key={event.id}
                className="flex items-center px-4 py-3 text-sm"
                style={{
                  backgroundColor: i % 2 === 0 ? "#1A1A1A" : "#111111",
                  borderBottom: "1px solid #2E2E2E",
                }}
              >
                <span className="w-20 font-mono text-xs" style={{ color: "#B8B9B6" }}>
                  {new Date(event.created_at).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
                </span>
                <span className="w-16">
                  <span
                    className="inline-block px-2 py-0.5 text-xs font-bold"
                    style={{
                      backgroundColor: isBurn ? "#222924" : "#24100B",
                      color: isBurn ? "#B6FFCE" : "#FF5C33",
                    }}
                  >
                    {event.decision}
                  </span>
                </span>
                <span className="flex-1 truncate pr-4" style={{ color: "#FFFFFF" }}>
                  <Link href={`/event/${event.id}`} className="hover:underline" style={{ color: "#FFFFFF" }}>
                    {event.event_title}
                  </Link>
                </span>
                <span
                  className="w-28 text-right font-mono font-semibold text-xs"
                  style={{ color: isBurn ? "#B6FFCE" : "#FF5C33" }}
                >
                  {isBurn ? "-" : "+"}{formatAmount(event.amount_crbn)}
                </span>
                <span className="w-[340px] text-right">
                  <a
                    href={`https://explorer.solana.com/tx/${event.tx_hash}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-mono text-xs hover:underline"
                    style={{ color: "#FF8400" }}
                  >
                    {event.tx_hash!.slice(0, 20)}...{event.tx_hash!.slice(-8)}
                  </a>
                </span>
              </div>
            );
          })}
        </div>
      )}

      {/* Pending transactions */}
      {withoutTx.length > 0 && (
        <div style={{ backgroundColor: "#1A1A1A", border: "1px solid #2E2E2E" }}>
          <div
            className="flex items-center px-4 py-2 text-xs font-bold uppercase tracking-wider"
            style={{ backgroundColor: "#2E2E2E", color: "#B8B9B6" }}
          >
            <span className="w-20">Date</span>
            <span className="w-16">Type</span>
            <span className="flex-1">Event</span>
            <span className="w-28 text-right">Amount</span>
            <span className="w-[340px] text-right">Status</span>
          </div>

          {withoutTx.map((event, i) => {
            const isBurn = event.decision === "BURN";
            return (
              <div
                key={event.id}
                className="flex items-center px-4 py-3 text-sm"
                style={{
                  backgroundColor: i % 2 === 0 ? "#1A1A1A" : "#111111",
                  borderBottom: "1px solid #2E2E2E",
                  opacity: 0.6,
                }}
              >
                <span className="w-20 font-mono text-xs" style={{ color: "#B8B9B6" }}>
                  {new Date(event.created_at).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
                </span>
                <span className="w-16">
                  <span
                    className="inline-block px-2 py-0.5 text-xs font-bold"
                    style={{
                      backgroundColor: isBurn ? "#222924" : "#24100B",
                      color: isBurn ? "#B6FFCE" : "#FF5C33",
                    }}
                  >
                    {event.decision}
                  </span>
                </span>
                <span className="flex-1 truncate pr-4" style={{ color: "#FFFFFF" }}>
                  <Link href={`/event/${event.id}`} className="hover:underline" style={{ color: "#FFFFFF" }}>
                    {event.event_title}
                  </Link>
                </span>
                <span
                  className="w-28 text-right font-mono font-semibold text-xs"
                  style={{ color: isBurn ? "#B6FFCE" : "#FF5C33" }}
                >
                  {isBurn ? "-" : "+"}{formatAmount(event.amount_crbn)}
                </span>
                <span className="w-[340px] text-right">
                  <span className="font-mono text-xs" style={{ color: "#666" }}>
                    Pending — pre-Phase 4
                  </span>
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
