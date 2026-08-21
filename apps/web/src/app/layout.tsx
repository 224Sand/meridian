import type { Metadata, Viewport } from "next";
import config from "@/generated/product.config.json";
import "./globals.css";

export const metadata: Metadata = {
  title: `${config.name} — ${config.tagline}`,
  description: config.description,
  applicationName: config.name,
  openGraph: {
    title: `${config.name} — ${config.tagline}`,
    description: config.description,
    type: "website",
  },
  robots: { index: true, follow: true },
};

export const viewport: Viewport = {
  themeColor: "#000000",
  colorScheme: "dark",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <nav
          style={{
            position: "sticky", top: 0, zIndex: 10,
            backdropFilter: "blur(14px)",
            background: "rgba(0,0,0,0.72)",
            borderBottom: "1px solid var(--line)",
          }}
        >
          <div
            className="wrap nav-links"
            style={{ height: 52 }}
          >
            <a href="/" className="mono" style={{ color: "var(--text)", fontSize: "0.8125rem", letterSpacing: "0.04em" }}>
              {config.wordmark}
            </a>
            <span style={{ flex: 1 }} />
            {[
              ["/console", "Console"],
              ["/architecture", "Architecture"],
              ["/reliability", "Reliability"],
              ["/delivery", "Delivery"],
              [`https://github.com/${config.repo}`, "Source"],
            ].map(([href, label]) => (
              <a key={href} href={href} style={{ color: "var(--text-2)", fontSize: "0.875rem" }}>
                {label}
              </a>
            ))}
          </div>
        </nav>
        {children}
      </body>
    </html>
  );
}
