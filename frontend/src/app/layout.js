import { Bricolage_Grotesque, Figtree } from "next/font/google";
import "./globals.css";
import "../kitch/styles/shell.css";
import "../kitch/styles/household.css";
import "../kitch/styles/chat.css";
import "../kitch/styles/recipes.css";
import "../kitch/styles/groceries.css";
import "../kitch/styles/nutrition.css";
import "../kitch/styles/entry.css";
import "../kitch/styles/snap.css";
import "../kitch/styles/legal.css";

const display = Bricolage_Grotesque({
  subsets: ["latin"],
  axes: ["opsz"],
  variable: "--font-display",
  display: "swap"
});

const ui = Figtree({
  subsets: ["latin"],
  variable: "--font-ui",
  display: "swap"
});

export const metadata = {
  title: "Kitch — Household meal planning",
  description: "Plan shared household meals, track pantry stock, prepare groceries, and log personal nutrition with an AI kitchen companion.",
  icons: {
    icon: [{ url: "/kitch-chef-hat.svg", type: "image/svg+xml" }],
    shortcut: "/kitch-chef-hat.svg",
    apple: "/kitch-chef-hat.svg"
  }
};

export const viewport = {
  themeColor: "#f5f1e8",
  colorScheme: "light"
};

export default function RootLayout({ children }) {
  return (
    <html lang="en" className={`${display.variable} ${ui.variable}`}>
      <body suppressHydrationWarning>
        {children}
      </body>
    </html>
  );
}
