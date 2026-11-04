import Link from "next/link";

export const dynamic = "force-dynamic";

async function getPresets(apiBase) {
  try {
    const res = await fetch(`${apiBase}/case-study`, {
      cache: "no-store",
      headers: { "Content-Type": "application/json" },
    });

    if (!res.ok) return [];

    const data = await res.json();
    return data.items || [];
  } catch {
    return [];
  }
}

async function StudiKasusIndex() {
  const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
  const presets = await getPresets(process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000");

  return (
    <section className="mx-auto max-w-4xl px-4 py-16">
      <header className="mb-12">
        <p className="caption-uppercase mb-3 text-[#cc785c]">Studi Kasus</p>
        <h1 className="display-xl">Studi Kasus Simulasi</h1>
        <p className="mt-4 text-base leading-relaxed text-[#3d3d3a] max-w-2xl">
          Jelajahi hasil simulasi opini publik untuk berbagai isu kebijakan. Setiap studi kasus
          menampilkan hasil simulasi multi-agen multi-ronde dengan analisis mendalam.
        </p>
      </header>

      <div className="grid gap-6 sm:grid-cols-2">
        {presets.map((preset) => (
          <article key={preset.id} className="cs-card cs-card-lg group">
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex flex-wrap items-center gap-2 mb-3">
                  <span className="rounded-full bg-[#cc785c]/10 border border-[#cc785c]/20 px-2.5 py-0.5 text-xs font-medium text-[#cc785c]">
                    {preset.kategori || "Kebijakan publik"}
                  </span>
                  <span className="text-xs text-[#6c6a64]">{preset.tanggal}</span>
                </div>
                <Link href={`/studi-kasus/${preset.id}`} className="no-underline">
                  <h3 className="display-md text-[#141413] group-hover:text-[#cc785c] transition-colors">
                    {preset.judul}
                  </h3>
                </Link>
                <div className="mt-4 flex items-center gap-4 text-sm text-[#6c6a64]">
                  <span>👥 {preset.peserta} peserta</span>
                </div>
              </div>
              <div className="shrink-0">
                <span className="inline-flex items-center gap-1.5 rounded-[8px] border border-[#e6dfd8] bg-white px-3 py-1.5 text-xs font-medium text-[#3d3d3a] hover:border-[#cc785c]/40 hover:bg-[#cc785c]/5 hover:text-[#cc785c] transition-all">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                    <polyline points="7 10 12 15 17 10"/>
                    <line x1="12" y1="15" x2="12" y2="3"/>
                  </svg>
                  Buka
                </span>
              </div>
            </div>
          </article>
        ))}

        {/* Empty state fallback */}
        {presets.length === 0 && (
          <div className="card" style={{ textAlign: "center", padding: "64px 32px" }}>
            <p className="display-sm mb-4 text-[#141413]">Belum ada studi kasus</p>
            <p className="text-[#6c6a64] max-w-sm mx-auto leading-relaxed">
              Belum ada simulasi yang disimpan sebagai studi kasus. Jalankan simulasi di halaman
              <a href="/demo" className="text-link">Coba Simulasi</a> untuk membuat yang baru.
            </p>
          </div>
        )}
      </div>
    </section>
  );
}

export default async function StudiKasusIndexPage() {
  const presets = await getPresets(process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000");

  return (
    <section className="mx-auto max-w-4xl px-4 py-16">
      <header className="mb-12">
        <p className="caption-uppercase mb-3 text-[#cc785c]">Studi Kasus</p>
        <h1 className="display-xl">Studi Kasus Simulasi</h1>
        <p className="mt-4 text-base leading-relaxed text-[#3d3d3a] max-w-2xl">
          Jelajahi hasil simulasi opini publik untuk berbagai isu kebijakan. Setiap studi kasus
          menampilkan hasil simulasi multi-agen multi-ronde dengan analisis mendalam.
        </p>
      </header>

      <div className="grid gap-6 sm:grid-cols-2">
        {presets.map((preset) => (
          <article key={preset.id} className="cs-card cs-card-lg group">
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex flex-wrap items-center gap-2 mb-3">
                  <span className="rounded-full bg-[#cc785c]/10 border border-[#cc785c]/20 px-2.5 py-0.5 text-xs font-medium text-[#cc785c]">
                    {preset.kategori || "Kebijakan publik"}
                  </span>
                  <span className="text-xs text-[#6c6a64]">{preset.tanggal}</span>
                </div>
                <Link href={`/studi-kasus/${preset.id}`} className="no-underline">
                  <h3 className="display-md text-[#141413] group-hover:text-[#cc785c] transition-colors">
                    {preset.judul}
                  </h3>
                </Link>
                <div className="mt-4 flex items-center gap-4 text-sm text-[#6c6a64]">
                  <span>👥 {preset.peserta} peserta</span>
                </div>
              </div>
              <div className="shrink-0">
                <span className="inline-flex items-center gap-1.5 rounded-[8px] border border-[#e6dfd8] bg-white px-3 py-1.5 text-xs font-medium text-[#3d3d3a] hover:border-[#cc785c]/40 hover:bg-[#cc785c]/5 hover:text-[#cc785c] transition-all">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                    <polyline points="7 10 12 15 17 10"/>
                    <line x1="12" y1="15" x2="12" y2="3"/>
                  </svg>
                  Buka
                </span>
              </div>
            </div>
          </article>
        ))}

        {/* Empty state fallback */}
        {presets.length === 0 && (
          <div className="card" style={{ textAlign: "center", padding: "64px 32px" }}>
            <p className="display-sm mb-4 text-[#141413]">Belum ada studi kasus</p>
            <p className="text-[#6c6a64] max-w-sm mx-auto leading-relaxed">
              Belum ada simulasi yang disimpan sebagai studi kasus. Jalankan simulasi di halaman
              <a href="/demo" className="text-link">Coba Simulasi</a> untuk membuat yang baru.
            </p>
          </div>
        )}
      </div>
    </section>
  );
}