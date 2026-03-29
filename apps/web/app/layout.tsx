import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Nabaztag Control Surface",
  description: "Primitive-first control panel for Nabaztag devices",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="fr">
      <body>{children}</body>
    </html>
  );
}

