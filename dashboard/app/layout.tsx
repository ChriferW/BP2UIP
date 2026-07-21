import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "BP2UIP",
  description:
    "A migration compiler for RPA estates: Blue Prism in, modernized UiPath out, with the reasoning shown.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-neutral-950 text-neutral-100 antialiased">
        <nav className="border-b border-neutral-900">
          <div className="mx-auto flex max-w-5xl items-center gap-6 px-6 py-3 text-sm">
            <Link href="/" className="font-mono font-bold tracking-tight">
              BP2UIP
            </Link>
            <Link href="/estate" className="text-neutral-400 hover:text-neutral-100">
              Estate
            </Link>
            <Link href="/review" className="text-neutral-400 hover:text-neutral-100">
              Review
            </Link>
            <Link href="/uplift" className="text-neutral-400 hover:text-neutral-100">
              Uplift
            </Link>
          </div>
        </nav>
        {children}
      </body>
    </html>
  );
}
