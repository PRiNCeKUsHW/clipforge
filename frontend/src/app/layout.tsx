import type { Metadata } from "next";
import { Bangers, Geist, Geist_Mono, Inter, Montserrat } from "next/font/google";
import { Suspense } from "react";

import { AppHeader } from "@/components/app-header";
import { Providers } from "@/components/providers";
import { Toaster } from "@/components/ui/sonner";

import "./globals.css";

const geistSans = Geist({ variable: "--font-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });
// Caption preview fonts (the same faces the renderer bundles)
const montserrat = Montserrat({ variable: "--font-montserrat", weight: ["800", "900"], subsets: ["latin"] });
const inter = Inter({ variable: "--font-inter", weight: ["700"], subsets: ["latin"] });
const bangers = Bangers({ variable: "--font-bangers", weight: ["400"], subsets: ["latin"] });

export const metadata: Metadata = {
  title: "ClipForge",
  description: "Turn long videos into scored, captioned short clips.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} ${montserrat.variable} ${inter.variable} ${bangers.variable} h-full antialiased`} suppressHydrationWarning>
      <body className="flex min-h-full flex-col">
        <Providers>
          {/* The header reads the current path; on dynamic routes that needs a Suspense boundary */}
          <Suspense fallback={<div className="h-14 border-b border-border/60" />}>
            <AppHeader />
          </Suspense>
          <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col px-4 py-8">{children}</main>
          <Toaster richColors position="bottom-right" />
        </Providers>
      </body>
    </html>
  );
}
