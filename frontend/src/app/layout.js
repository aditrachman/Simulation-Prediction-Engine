import { DM_Sans, Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const dmSans = DM_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "700", "800"],
  variable: "--font-display",
});

const inter = Inter({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-body",
});

const jetbrains = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-mono",
});

export const metadata = {
  title: "VoxSwarm — Social Simulation Engine",
  description:
    "VoxSwarm is a social simulation and prediction engine for decision-makers. Simulate public opinion, assess policy reception, and identify key actors before issues go public.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="id" className={`${dmSans.variable} ${inter.variable} ${jetbrains.variable}`}>
      <body style={{ fontFamily: "var(--font-body), Inter, sans-serif" }}>
        {children}
      </body>
    </html>
  );
}
