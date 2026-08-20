import type { NextConfig } from "next";

const isDev = process.env.NODE_ENV !== "production";

const config: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "X-Frame-Options", value: "DENY" },
          {
            // No third-party origins at all. The page loads no fonts, no
            // analytics and no CDN, so the policy can be this tight.
            //
            // 'unsafe-eval' in DEVELOPMENT ONLY. Next's dev server compiles
            // modules through eval for hot reloading, so a policy without it
            // renders the page server-side and never hydrates - every button
            // becomes inert HTML with only a CSP violation in the console to
            // say why. Production builds do not use eval and must not allow it.
            key: "Content-Security-Policy",
            value: [
              "default-src 'self'",
              isDev
                ? "script-src 'self' 'unsafe-inline' 'unsafe-eval'"
                : "script-src 'self' 'unsafe-inline'",
              "style-src 'self' 'unsafe-inline'",
              "img-src 'self' data: blob:",
              "media-src 'self'",
              "connect-src 'self'",
              "frame-ancestors 'none'",
              "base-uri 'self'",
              "form-action 'self'",
            ].join("; "),
          },
        ],
      },
    ];
  },
};

export default config;
