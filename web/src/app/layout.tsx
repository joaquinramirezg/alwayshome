import type { Metadata, Viewport } from "next";
import { Fraunces, Plus_Jakarta_Sans } from "next/font/google";
import "./globals.css";

const display = Fraunces({ variable: "--font-display", subsets: ["latin"], weight: ["500", "600", "700"] });
const sans = Plus_Jakarta_Sans({ variable: "--font-sans-brand", subsets: ["latin"], weight: ["400", "500", "600", "700"] });

const title = "AlwaysHome · From the FAIR Plan back to private insurance";
const description =
  "Enter your address, your home and your policy. See your wildfire exposure, what your insurance would really pay, and the fire-safety fixes that move you closest to affordable private coverage.";

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL ?? "https://msba-vibathon-2026.vercel.app"),
  title: { default: title, template: "%s · AlwaysHome" },
  description,
  applicationName: "AlwaysHome",
  keywords: ["FAIR Plan", "California wildfire insurance", "home hardening", "Safer from Wildfires", "insurance gap"],
  openGraph: { title, description, siteName: "AlwaysHome", type: "website", locale: "en_US" },
  twitter: { card: "summary_large_image", title, description },
};

export const viewport: Viewport = {
  themeColor: "#111111",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${display.variable} ${sans.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
