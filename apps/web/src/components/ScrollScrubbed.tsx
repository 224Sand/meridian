"use client";

/**
 * Scroll-scrubbed video, pinned.
 *
 * The technique the reference standard actually uses, and the part that
 * transfers: the reader controls the pace, so nothing is missed by looking
 * away and nothing happens on a timer.
 *
 * Below 768px or under reduced motion the poster frame REPLACES the video
 * entirely. Scrubbing a video on a phone spends the visitor's data to produce a
 * worse experience than the still (DESIGN_SYSTEM.md section 5).
 */

import { useEffect, useRef, useState } from "react";

export default function ScrollScrubbed({
  src,
  poster,
  children,
}: {
  src: string;
  poster: string;
  children?: React.ReactNode;
}) {
  const section = useRef<HTMLElement | null>(null);
  const video = useRef<HTMLVideoElement | null>(null);
  const [scrub, setScrub] = useState(false);

  useEffect(() => {
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
    const wide = window.matchMedia("(min-width: 768px)");
    const decide = () => setScrub(wide.matches && !reduced.matches);
    decide();
    reduced.addEventListener("change", decide);
    wide.addEventListener("change", decide);
    return () => {
      reduced.removeEventListener("change", decide);
      wide.removeEventListener("change", decide);
    };
  }, []);

  useEffect(() => {
    if (!scrub) return;
    const element = section.current;
    const media = video.current;
    if (!element || !media) return;

    let frame = 0;
    let target = 0;

    const onScroll = () => {
      const rect = element.getBoundingClientRect();
      const travel = rect.height - window.innerHeight;
      if (travel <= 0) return;
      // Progress through the pinned region, clamped. Outside it the video holds
      // its first or last frame rather than snapping.
      const progress = Math.min(Math.max(-rect.top / travel, 0), 1);
      target = progress * (media.duration || 0);
      if (!frame) {
        frame = requestAnimationFrame(() => {
          frame = 0;
          // Seeking every scroll event overwhelms the decoder and produces the
          // stutter that makes a scrubbed video look broken. One seek per
          // animation frame is the most the browser can honour.
          if (Number.isFinite(target)) media.currentTime = target;
        });
      }
    };

    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
    return () => {
      window.removeEventListener("scroll", onScroll);
      if (frame) cancelAnimationFrame(frame);
    };
  }, [scrub]);

  return (
    <section ref={section} style={{ position: "relative", height: "240vh" }}>
      <div
        style={{
          position: "sticky",
          top: 0,
          height: "100vh",
          overflow: "hidden",
          display: "grid",
          placeItems: "center",
        }}
      >
        {scrub ? (
          <video
            ref={video}
            src={src}
            poster={poster}
            muted
            playsInline
            preload="auto"
            aria-hidden="true"
            style={{
              position: "absolute",
              inset: 0,
              width: "100%",
              height: "100%",
              objectFit: "cover",
              opacity: 0.34,
            }}
          />
        ) : (
          /* eslint-disable-next-line @next/next/no-img-element */
          <img
            src={poster}
            alt=""
            aria-hidden="true"
            style={{
              position: "absolute",
              inset: 0,
              width: "100%",
              height: "100%",
              objectFit: "cover",
              opacity: 0.28,
            }}
          />
        )}
        {/* Vignette: the only gradient in the system, and it exists so display
            type stays legible over moving footage rather than for effect. */}
        <div
          aria-hidden="true"
          style={{
            position: "absolute",
            inset: 0,
            background:
              "radial-gradient(120% 90% at 50% 40%, transparent 20%, rgba(0,0,0,0.72) 72%, #000 100%)",
          }}
        />
        <div className="wrap" style={{ position: "relative", width: "100%" }}>
          {children}
        </div>
      </div>
    </section>
  );
}
