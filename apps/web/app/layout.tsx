import type { Metadata } from "next";
import { IBM_Plex_Sans, Space_Grotesk } from "next/font/google";

import { AppShell } from "@/components/AppShell";
import { RunContextProvider } from "@/lib/run-context";
import { ThemeProvider } from "@/lib/theme-context";

import "./globals.css";

const headingFont = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-heading",
});

const bodyFont = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-body",
});

export const metadata: Metadata = {
  title: "Pharma Control Tower",
  description: "Planner console for dispatch generation, approval, and demo-state visibility.",
};

export const viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${headingFont.variable} ${bodyFont.variable}`} suppressHydrationWarning>
        <ThemeProvider>
          <RunContextProvider>
            <AppShell>{children}</AppShell>
          </RunContextProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
