"use client";

/**
 * A pinned scene. One idea per viewport.
 *
 * The next scene does not begin until this one has landed, which is the second
 * transferable thing about the reference standard: it refuses to put two claims
 * on screen at once.
 *
 * Content is present in the DOM and legible with animation removed. Motion
 * changes emphasis, never availability (AC-C10).
 */

import { useEffect, useRef, useState } from "react";

export default function Scene({
  kicker,
  heading,
  body,
  aside,
}: {
  kicker: string;
  heading: string;
  body: string;
  aside?: React.ReactNode;
}) {
  const ref = useRef<HTMLDivElement | null>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const element = ref.current;
    if (!element) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setVisible(true);
      return;
    }
    const observer = new IntersectionObserver(
      ([entry]) => {
        // Latching rather than toggling: a scene that fades out when scrolled
        // past reads as content disappearing, which is what AC-C10 forbids.
        if (entry?.isIntersecting) setVisible(true);
      },
      { threshold: 0.35 },
    );
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  return (
    <section style={{ borderTop: "1px solid var(--line)" }}>
      <div
        ref={ref}
        className="wrap"
        style={{
          paddingBlock: "var(--s9)",
          display: "grid",
          gap: "var(--s7)",
          // auto-fit with a min track rather than a 768px breakpoint: the
          // aside carries monospace tables that clip long before the viewport
          // reaches tablet width, and a breakpoint chosen from device sizes
          // rather than from the content is a breakpoint that will be wrong.
          gridTemplateColumns: aside
            ? "repeat(auto-fit, minmax(min(100%, 400px), 1fr))"
            : "1fr",
          alignItems: "start",
          opacity: visible ? 1 : 0,
          transform: visible ? "none" : "translateY(14px)",
          transition: "opacity var(--t-considered), transform var(--t-considered)",
        }}
      >
        <div>
          <p className="mono" style={{ color: "var(--text-3)", marginBottom: "var(--s4)" }}>
            {kicker.toUpperCase()}
          </p>
          <h2 style={{ marginBottom: "var(--s5)", maxWidth: "18ch" }}>{heading}</h2>
          <p style={{ color: "var(--text-2)", fontSize: "1.125rem" }}>{body}</p>
        </div>
        {aside}
      </div>
    </section>
  );
}
