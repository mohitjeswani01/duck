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

const SITE_URL = "https://duck.dev";
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
