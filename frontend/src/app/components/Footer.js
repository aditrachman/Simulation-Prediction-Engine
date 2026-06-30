import Link from "next/link";

export default function Footer() {
  return (
    <footer className="bg-[#181715] border-t border-[#252320]">
      <div className="mx-auto max-w-[1200px] px-6 py-16">
        <div className="grid gap-10 sm:grid-cols-2 md:grid-cols-4">
          {/* Brand */}
          <div className="sm:col-span-2 md:col-span-1">
            <Link href="/" className="no-underline">
              <span
                className="text-lg tracking-tight text-[#faf9f5]"
                className="tracking-tight" style={{ fontFamily: "var(--font-logo), sans-serif", fontWeight: 700, letterSpacing: "-0.02em" }}
              >
                VoxSwarm
              </span>
            </Link>
            <p className="mt-3 text-[14px] leading-[1.55] text-[#a09d96]" style={{ letterSpacing: "0.15px" }}>
              Multi-agent opinion simulation untuk skenario kebijakan publik Indonesia.
            </p>
          </div>

          {/* Halaman */}
          <div>
            <p className="mb-4 text-[12px] font-medium uppercase tracking-[1.5px] text-[#a09d96]">Halaman</p>
            <ul className="space-y-3">
              <li><Link href="/" className="text-[14px] leading-[1.55] text-[#a09d96] no-underline transition-opacity hover:text-[#faf9f5]" style={{ letterSpacing: "0.15px" }}>Beranda</Link></li>
              <li><Link href="/demo" className="text-[14px] leading-[1.55] text-[#a09d96] no-underline transition-opacity hover:text-[#faf9f5]" style={{ letterSpacing: "0.15px" }}>Simulasi</Link></li>
            </ul>
          </div>

          {/* Dokumentasi */}
          <div>
            <p className="mb-4 text-[12px] font-medium uppercase tracking-[1.5px] text-[#a09d96]">Dokumentasi</p>
            <ul className="space-y-3">
              <li><a href="https://github.com/aditrachman/Simulation-Prediction-Engine" target="_blank" rel="noreferrer" className="text-[14px] leading-[1.55] text-[#a09d96] no-underline transition-opacity hover:text-[#faf9f5]" style={{ letterSpacing: "0.15px" }}>GitHub</a></li>
              <li><a href="https://github.com/aditrachman/Simulation-Prediction-Engine/blob/main/README.md" target="_blank" rel="noreferrer" className="text-[14px] leading-[1.55] text-[#a09d96] no-underline transition-opacity hover:text-[#faf9f5]" style={{ letterSpacing: "0.15px" }}>README</a></li>
            </ul>
          </div>

          {/* Tech Stack */}
          <div>
            <p className="mb-4 text-[12px] font-medium uppercase tracking-[1.5px] text-[#a09d96]">Tech Stack</p>
            <ul className="space-y-3">
              <li className="text-[14px] leading-[1.55] text-[#a09d96]" style={{ letterSpacing: "0.15px" }}>Next.js 15 + FastAPI</li>
              <li className="text-[14px] leading-[1.55] text-[#a09d96]" style={{ letterSpacing: "0.15px" }}>Groq LLM (llama-3.3)</li>
              <li className="text-[14px] leading-[1.55] text-[#a09d96]" style={{ letterSpacing: "0.15px" }}>scikit-learn + RSS</li>
            </ul>
          </div>
        </div>

        <div className="mt-16 border-t border-[#252320] pt-8 text-[14px] leading-[1.55] text-[#a09d96]" style={{ letterSpacing: "0.15px" }}>
          <p>© 2026 VoxSwarm — Tugas Akhir.</p>
        </div>
      </div>
    </footer>
  );
}
