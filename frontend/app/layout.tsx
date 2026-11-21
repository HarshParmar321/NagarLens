import type { Metadata } from "next";

import Shell from "@/components/shell";

import "./globals.css";
import Providers from "./providers";

export const metadata: Metadata = {
  title: "NagarLens · Follow the Rupee",
  description: "Follow every rupee from a citizen's complaint to a fix that held. Synthetic organizer data.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="antialiased">
        <Providers>
          <Shell>{children}</Shell>
        </Providers>
      </body>
    </html>
  );
}
