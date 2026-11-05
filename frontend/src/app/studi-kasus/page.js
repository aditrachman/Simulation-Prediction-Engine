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

export default async function StudiKasusIndexPage() {
  const presets = await getPresets(process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000");

  return (
    <div className="cs">
      <div className="cs-wrap cs-section">
        <div className="cs-head">
          <div className="cs-eyebrow">Studi Kasus</div>
          <h1 className="cs-h2">Studi Kasus Simulasi</h1>
          <p className="cs-lead">
            Jelajahi hasil simulasi opini publik untuk berbagai isu kebijakan. Setiap studi kasus
            menampilkan hasil simulasi multi-agen multi-ronde dengan analisis mendalam.
          </p>
        </div>

        {presets.length === 0 ? (
          <div className="cs-card">
            <h2 className="cs-h2">Belum ada studi kasus</h2>
            <p className="cs-lead">
              Belum ada simulasi yang disimpan sebagai studi kasus. Jalankan simulasi di halaman{" "}
              <Link href="/demo">Coba Simulasi</Link> untuk membuat yang baru.
            </p>
          </div>
        ) : (
          <div className="cs-row cs-row-20">
            {presets.map((preset) => (
              <article key={preset.id} className="cs-card">
                <div className="cs-label">
                  {preset.kategori || "Kebijakan publik"} · {preset.tanggal}
                </div>
                <h2 className="cs-round-title">
                  <Link href={`/studi-kasus/${preset.id}`} style={{ color: "inherit", textDecoration: "none" }}>
                    {preset.judul}
                  </Link>
                </h2>
                {preset.peserta ? (
                  <div className="cs-small">{preset.peserta} peserta</div>
                ) : null}
                <div className="cs-btns">
                  <Link className="cs-btn" href={`/studi-kasus/${preset.id}`}>
                    Buka studi kasus
                  </Link>
                </div>
              </article>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
