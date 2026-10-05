import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI-based Resume Screening",
  description: "Cloud-native AI-based resume screening and ranking system",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <header className="site-header">
          <div className="site-header__inner">
            <a className="brand" href="/"><span className="brand-mark">RS</span>Resume Screening</a>
            <nav className="site-nav" aria-label="Primary navigation">
              <a href="/auth/login">Sign in</a>
            </nav>
          </div>
        </header>
        {children}
      </body>
    </html>
  );
}
