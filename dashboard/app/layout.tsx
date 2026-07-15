import type { Metadata } from "next";
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
        {children}
      </body>
    </html>
  );
}
