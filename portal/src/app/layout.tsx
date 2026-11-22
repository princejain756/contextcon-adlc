import type { Metadata } from "next";
import { Geist_Mono, Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin", "latin-ext"],
  weight: "variable",
  style: "normal",
  axes: ["opsz"],
  variable: "--font-inter",
  display: "swap",
});

const geistMono = Geist_Mono({
  subsets: ["latin"],
  weight: "variable",
  style: "normal",
  variable: "--font-geist-mono",
  display: "swap",
  preload: false,
});

export const metadata: Metadata = {
  metadataBase: new URL("https://contextcon.prince.sh"),
  title: "contextcon-adlc | Meko Shared Engineering Memory & 2-Minute Audit Portal",
  description:
    "Live trace explorer, 10-task token benchmark, cross-machine Claude Code and Codex handoff, AMP Postgres 18 branch verification, and closed-loop self-learning built on Meko Cloud.",
  openGraph: {
    title: "contextcon-adlc | One Shared Meko Memory Across Every Coding Agent",
    description:
      "Inspect all 16 Meko traces, 26 collective memories, cross-agent SQL handoff, AMP Postgres 18 CoW branching, and paired 10-task benchmark metrics in under 2 minutes.",
    url: "https://contextcon.prince.sh",
    siteName: "contextcon-adlc Audit Portal",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "contextcon-adlc | Meko Shared Engineering Memory & 2-Minute Audit Portal",
    description:
      "Cross-agent handoff, AMP Postgres 18 CoW fork, closed-loop self-learning, and 10-task token benchmark.",
  },
};

const themeInitScript = `(function(){try{var t=localStorage.getItem('contextcon-theme');if(t==='dark'){document.documentElement.classList.add('dark');}}catch(e){}})();`;

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${inter.variable} ${geistMono.variable}`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body className="min-h-screen bg-canvas text-ink antialiased">{children}</body>
    </html>
  );
}
