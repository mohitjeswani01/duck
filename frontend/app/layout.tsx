import type { Metadata, Viewport } from "next";
import { Bricolage_Grotesque, Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const bricolage = Bricolage_Grotesque({
  variable: "--font-bricolage",
  subsets: ["latin"],
});

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-jetbrains-mono",
  subsets: ["latin"],
});

// Must come from an env var, not a hardcoded guess — metadataBase resolves
// every relative OG/Twitter image URL (including the generated
// /opengraph-image route below) against this value. A wrong domain here
// means link previews silently point at a 404 on the real deployed site.
// Defaults to localhost for dev; set NEXT_PUBLIC_SITE_URL to the real Vercel
// URL (or custom domain) in production.
const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";
const SITE_DESCRIPTION =
  "Describe your bug out loud. Duck reads your code, asks the right questions, and finds the fix — the rubber duck that talks back, built voice-first with Wispr Flow.";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: "Duck — explain the bug out loud",
    template: "%s · Duck",
  },
  description: SITE_DESCRIPTION,
  icons: {
    icon: "/icon.svg",
  },
  openGraph: {
    title: "Duck — explain the bug out loud",
    description: SITE_DESCRIPTION,
    url: SITE_URL,
    siteName: "Duck",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Duck — explain the bug out loud",
    description: SITE_DESCRIPTION,
  },
};

export const viewport: Viewport = {
  themeColor: "#fbf7ee",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${bricolage.variable} ${inter.variable} ${jetbrainsMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-cream text-ink">{children}</body>
    </html>
  );
}
