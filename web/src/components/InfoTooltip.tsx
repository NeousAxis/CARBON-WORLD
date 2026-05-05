"use client";

import { useState } from "react";

interface InfoTooltipProps {
  /** Plain-language explanation, French. Shown in the tooltip bubble. */
  text: string;
}

/**
 * Small "?" badge displayed next to indicator titles. Hover (desktop) or
 * tap (touch) toggles the explanation bubble. Lunaris-dark styling matches
 * the dashboard cards.
 */
export function InfoTooltip({ text }: InfoTooltipProps) {
  const [open, setOpen] = useState(false);

  return (
    <span
      style={{
        position: "relative",
        display: "inline-flex",
        marginLeft: 6,
        verticalAlign: "middle",
      }}
    >
      <button
        type="button"
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          setOpen((v) => !v);
        }}
        onBlur={() => setOpen(false)}
        aria-label="Info"
        title="Info"
        style={{
          width: 14,
          height: 14,
          borderRadius: "50%",
          border: "1px solid #5A5A5A",
          background: "transparent",
          color: "#B8B9B6",
          fontSize: 9,
          lineHeight: 1,
          cursor: "help",
          padding: 0,
          fontFamily: "'JetBrains Mono', ui-monospace, monospace",
          fontWeight: 700,
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        ?
      </button>
      {open && (
        <span
          role="tooltip"
          style={{
            position: "absolute",
            bottom: "calc(100% + 8px)",
            left: 0,
            zIndex: 50,
            width: 280,
            padding: "10px 12px",
            backgroundColor: "#0F1413",
            border: "1px solid #2E2E2E",
            color: "#E5E5E5",
            fontSize: 11,
            lineHeight: 1.5,
            fontFamily: "'JetBrains Mono', ui-monospace, monospace",
            fontWeight: 400,
            letterSpacing: 0,
            textTransform: "none",
            boxShadow: "0 4px 16px rgba(0,0,0,0.4)",
            whiteSpace: "normal",
            pointerEvents: "none",
          }}
        >
          {text}
        </span>
      )}
    </span>
  );
}
