"use client";

import { useEffect, useRef, useState } from "react";

interface InfoTooltipProps {
  /** Plain-language explanation. Shown in the tooltip bubble. */
  text: string;
}

/**
 * Small "?" badge displayed next to indicator titles. Hover (desktop) or
 * tap (touch) toggles the explanation bubble. Lunaris-dark styling.
 *
 * Positioning strategy: the bubble uses `position: fixed` and is placed
 * dynamically via getBoundingClientRect, so it cannot be clipped by a
 * parent's overflow:hidden / max-w-7xl, and is always clamped inside
 * the viewport (never cut off on phones).
 */
export function InfoTooltip({ text }: InfoTooltipProps) {
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<{ top: number; left: number; width: number } | null>(null);
  const buttonRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    if (!open) return;
    const btn = buttonRef.current;
    if (!btn) return;

    function compute() {
      const rect = btn!.getBoundingClientRect();
      const viewportW = window.innerWidth;
      const viewportH = window.innerHeight;
      const margin = 8; // distance to viewport edges
      const desiredW = Math.min(280, viewportW - 2 * margin);

      // Anchor right edge of bubble to right edge of badge by default
      let left = rect.right - desiredW;
      // Clamp inside viewport horizontally
      if (left < margin) left = margin;
      if (left + desiredW > viewportW - margin) left = viewportW - margin - desiredW;

      // Default: above the badge, but if not enough room, place below
      const estimatedH = 120; // generous; bubble auto-grows
      let top: number;
      if (rect.top - margin - estimatedH > 0) {
        top = rect.top - margin - estimatedH; // above
      } else {
        top = rect.bottom + margin; // below
      }
      // Clamp top within viewport
      if (top < margin) top = margin;
      if (top + estimatedH > viewportH - margin) top = viewportH - margin - estimatedH;

      setPos({ top, left, width: desiredW });
    }

    compute();
    window.addEventListener("scroll", compute, { passive: true, capture: true });
    window.addEventListener("resize", compute);
    return () => {
      window.removeEventListener("scroll", compute, true);
      window.removeEventListener("resize", compute);
    };
  }, [open]);

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
        ref={buttonRef}
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
      {open && pos && (
        <span
          role="tooltip"
          style={{
            position: "fixed",
            top: pos.top,
            left: pos.left,
            width: pos.width,
            zIndex: 1000,
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
            boxShadow: "0 4px 16px rgba(0,0,0,0.5)",
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
