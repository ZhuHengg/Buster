import type { Metadata } from "next";

import Sidebar from "@/components/Sidebar";

import "./globals.css";

export const metadata: Metadata = {
  title: "Central Monitoring System",
  description: "Proactive CCTV alerting for township security",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="flex h-full min-h-full gap-3 bg-bg p-3 text-text">
        <Sidebar />
        <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden rounded-2xl border border-line bg-shell shadow-[0_8px_30px_rgba(0,0,0,0.35)]">
          {children}
        </div>
      </body>
    </html>
  );
}
