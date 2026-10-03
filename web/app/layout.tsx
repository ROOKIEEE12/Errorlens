import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "ErrorLens — Paste a failure. Get the real fix.",
  description: "Privacy-first debugging assistant for build logs, tracebacks and screenshots.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header className="nav">
          <Link href="/" className="brand">🔍 ErrorLens</Link>
          <nav><Link href="/">Analyze</Link><Link href="/history">History</Link></nav>
        </header>
        {children}
      </body>
    </html>
  );
}
