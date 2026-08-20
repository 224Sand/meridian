import type { Metadata, Viewport } from "next";
import config from "../../../../product.config.json";
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
      <body>{children}</body>
    </html>
  );
}
