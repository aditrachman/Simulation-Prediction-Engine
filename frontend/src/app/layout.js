import { Plus_Jakarta_Sans, Inter, Space_Grotesk, Newsreader, Public_Sans } from "next/font/google";
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

const newsreader = Newsreader({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-newsreader",
});

const publicSans = Public_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-public-sans",
});

export const metadata = {
  title: "VoxSwarm — Simulasi Reaksi Kebijakan",
  description:
    "VoxSwarm: simulasi reaksi berbagai kelompok masyarakat terhadap kebijakan sebelum diluncurkan. Alat bantu pengambilan keputusan berbasis data.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="id" className={`${jakarta.variable} ${inter.variable} ${spaceGrotesk.variable} ${newsreader.variable} ${publicSans.variable}`}>
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
