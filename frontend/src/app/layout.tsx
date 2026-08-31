import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "AI Resume Screening",
  description: "Cloud-native AI-based resume screening and ranking system",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
