import { JetBrains_Mono } from "next/font/google";

import "./globals.css";

const jetbrains = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "700"], // bebas mau nambah
});

export const metadata = {
  title: "VoxSwarm",
  description:
    "VoxSwarm is a simulation intelligence platform for modeling social dynamics, testing scenarios, and predicting collective reactions to high-stakes events.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <head>
        <link
          href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:ital,wght@0,100..800;1,100..800&display=swap"
          rel="stylesheet"
        />
      </head>
      <body style={{ fontFamily: "JetBrains Mono, monospace" }}>
        {children}
      </body>
    </html>
  );
}
