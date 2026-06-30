"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

const navLinks = [
  { label: "Beranda", href: "/" },
  { label: "Simulasi", href: "/demo" },
  { label: "Dokumentasi", href: "https://github.com/aditrachman/Simulation-Prediction-Engine", external: true },
];

export default function Navbar() {
  const pathname = usePathname();

  return (
    <header className="h-16 border-b border-[#e6dfd8] bg-[#faf9f5]">
      <div className="mx-auto flex h-full max-w-[1200px] items-center justify-between px-6">
        <Link href="/" className="flex items-center gap-2 no-underline">
          <span
            className="text-lg tracking-tight"
            className="tracking-tight" style={{ fontFamily: "var(--font-logo), sans-serif", fontWeight: 700, color: "#141413", letterSpacing: "-0.02em" }}
          >
            VoxSwarm
          </span>
        </Link>

        <nav className="hidden items-center gap-1 md:flex">
          {navLinks.map((link) => {
            const active = !link.external && pathname === link.href;
            return (
              <a
                key={link.label}
                href={link.href}
                target={link.external ? "_blank" : undefined}
                rel={link.external ? "noreferrer" : undefined}
                className={`rounded-[8px] px-4 py-2 text-[14px] font-medium leading-[1.4] no-underline transition-all ${
                  active
                    ? "bg-[#cc785c]/10 text-[#cc785c]"
                    : "text-[#3d3d3a] hover:bg-[#efe9de] hover:text-[#141413]"
                }`}
                style={{ fontFamily: "var(--font-body), sans-serif" }}
              >
                {link.label}
              </a>
            );
          })}
        </nav>

        <Link
          href="/demo"
          className="inline-flex h-10 items-center justify-center rounded-[8px] bg-[#cc785c] px-5 text-[14px] font-medium text-white no-underline transition-all hover:bg-[#a9583e]"
          style={{ fontFamily: "var(--font-body), sans-serif", lineHeight: 1 }}
        >
          Mulai Simulasi
        </Link>

        <button className="flex h-10 w-10 items-center justify-center md:hidden" aria-label="Menu">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#141413" strokeWidth="1.5" strokeLinecap="round">
            <line x1="3" y1="6" x2="21" y2="6" />
            <line x1="3" y1="12" x2="21" y2="12" />
            <line x1="3" y1="18" x2="21" y2="18" />
          </svg>
        </button>
      </div>
    </header>
  );
}
