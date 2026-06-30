import { Plus_Jakarta_Sans, Inter, Space_Grotesk } from "next/font/google";
import "./globals.css";
import Navbar from "./components/Navbar";
import Footer from "./components/Footer";

const jakarta = Plus_Jakarta_Sans({
  subsets: ["latin"],
  weight: ["500", "600", "700"],
  variable: "--font-heading",
});

const inter = Inter({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-body",
});

const spaceGrotesk = Space_Grotesk({
  subsets: ["latin"],
  weight: ["600", "700"],
  variable: "--font-logo",
});

export const metadata = {
  title: "VoxSwarm — Social Simulation Engine",
  description:
    "VoxSwarm is a social simulation and prediction engine for decision-makers. Simulate public opinion, assess policy reception, and identify key actors before issues go public.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="id" className={`${jakarta.variable} ${inter.variable} ${spaceGrotesk.variable}`}>
      <body>
        <Navbar />

        {/* ─── Grain Texture ─── */}
        <div className="grain-overlay" aria-hidden="true" />

        {/* ─── Main Content ─── */}
        <main className="flex min-h-screen flex-col">{children}</main>

        <Footer />
      </body>
    </html>
  );
}
