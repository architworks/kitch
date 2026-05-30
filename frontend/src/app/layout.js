import "./globals.css";

export const metadata = {
  title: "Kitch — AI Household Meal Planning Assistant",
  description: "Plan shared household meals, track pantry stock, prepare groceries, and log personal nutrition with an AI kitchen companion.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        {children}
      </body>
    </html>
  );
}
