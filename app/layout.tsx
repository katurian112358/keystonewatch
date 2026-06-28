import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Keystone Watch — PA Legislative Accountability",
  description:
    "Track every Pennsylvania state legislator's voting record, sponsored bills, and press releases.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-gray-50 text-gray-900 font-sans">
        <header className="bg-white border-b border-gray-200 sticky top-0 z-10">
          <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
            <a href="/" className="font-bold text-lg tracking-tight">
              Keystone Watch
            </a>
            <nav className="flex gap-6 text-sm text-gray-600">
              <a href="/" className="hover:text-gray-900">
                Home
              </a>
              <a href="/legislators" className="hover:text-gray-900">
                All Legislators
              </a>
            </nav>
          </div>
        </header>
        <main className="max-w-6xl mx-auto px-4 py-8">{children}</main>
        <footer className="border-t border-gray-200 mt-16 py-8 text-center text-sm text-gray-500">
          <p>
            Data from{" "}
            <a
              href="https://openstates.org"
              className="underline"
              target="_blank"
              rel="noopener noreferrer"
            >
              OpenStates
            </a>
            . AI summaries by Claude. No ads, no tracking.
          </p>
          <p className="mt-1">Pennsylvania state legislators only.</p>
        </footer>
      </body>
    </html>
  );
}
