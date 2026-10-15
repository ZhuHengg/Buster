import type { Metadata } from "next";

import AppHeader from "@/components/AppHeader";
import Sidebar from "@/components/Sidebar";
import { CmsProvider } from "@/lib/cms";

import "./globals.css";

export const metadata: Metadata = {
  title: "Buster · Security Operations Centre",
  description: "Proactive CCTV monitoring and incident response for township security",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="flex h-full min-h-full flex-col bg-bg text-text">
        <CmsProvider>
          <a
            href="#main"
            className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-[100] focus:rounded-[var(--r-md)] focus:bg-brand focus:px-3 focus:py-2 focus:text-white"
          >
            Skip to main content
          </a>
          <AppHeader />
          <div className="flex min-h-0 flex-1">
            <Sidebar />
            <main id="main" className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
              {children}
            </main>
          </div>
        </CmsProvider>
      </body>
    </html>
  );
}
