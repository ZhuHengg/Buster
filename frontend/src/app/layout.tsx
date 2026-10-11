import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "Central Monitoring System",
  description: "Proactive CCTV alerting for township security",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="flex h-full min-h-full flex-col bg-bg text-text">{children}</body>
    </html>
  );
}
