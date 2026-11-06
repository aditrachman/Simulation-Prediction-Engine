import Link from "next/link";
import "./landing.css";

// Contoh sesi nyata: run "Pajak barang mewah berlaku November 2026",
// 12 persona, 3 ronde. Skor sikap -1 (menolak) sampai +1 (mendukung).
const personas = [
  { nama: "Oposisi Kritis", skor: -0.9, baris: 0 },
  { nama: "Mahasiswa", skor: -0.8, baris: 1 },
  { nama: "Jurnalis/Media", skor: -0.8, baris: 2 },
  { nama: "Ibu Rumah Tangga", skor: -0.8, baris: 3 },
  { nama: "Buruh Pabrik", skor: -0.8, baris: 4 },
  { nama: "Penyedia Jasa Layanan Eksklusif", skor: -0.75, baris: 0 },
  { nama: "Pekerja Kantoran", skor: -0.6, baris: 2 },
  { nama: "Pengguna Mobil Mewah", skor: -0.6, baris: 4 },
  { nama: "Pengusaha/UMKM", skor: 0, baris: 0 },
  { nama: "Akademisi", skor: 0, baris: 2 },
  { nama: "Guru", skor: 0, baris: 4 },
  { nama: "Pemerintah", skor: 0.7, baris: 2 },
];

const stanceOf = (skor) =>
  skor <= -0.25 ? "menolak" : skor >= 0.25 ? "mendukung" : "netral";

const stanceColor = {
  menolak: "var(--lp-tolak)",
  netral: "var(--lp-netral)",
  mendukung: "var(--lp-dukung)",
};

const specs = [
  { value: "12", label: "persona tersedia, dari buruh sampai pemerintah" },
  { value: "1–5", label: "ronde debat, bisa diatur per sesi" },
  { value: "3", label: "format unduhan: PDF, CSV, Word" },
  { value: "0", label: "langkah pendaftaran" },
];

const steps = [
  {
    title: "Tulis topiknya",
    desc: "Satu kalimat cukup, misalnya “Pemerintah menaikkan tarif PPN menjadi 12 persen”. Pilih kategori dan jumlah ronde kalau perlu.",
  },
  {
    title: "Agen berdebat",
    desc: "Persona bicara bergiliran. Masing-masing punya peran, bobot pengaruh, dan skor sikap yang bergerak dari ronde ke ronde.",
  },
  {
    title: "Baca risalahnya",
    desc: "Transkrip tiap ronde, peta sikap akhir, prediksi arah opini, dan rekomendasi. Unduh sebagai PDF, CSV, atau Word.",
  },
];

const outputs = [
  {
    key: "Peta sikap",
    desc: "Skor tiap persona dan arah perubahannya di setiap ronde.",
  },
  {
    key: "Transkrip",
    desc: "Pendapat tiap persona, dikelompokkan per ronde.",
  },
  {
    key: "Prediksi",
    desc: "Peluang konsensus, polarisasi, atau status quo di akhir sesi.",
  },
  {
    key: "Rekomendasi",
    desc: "Aktor paling berpengaruh dan langkah yang disarankan.",
  },
];

const docs = [
  {
    title: "Panduan cepat",
    desc: "Menjalankan backend dan frontend di komputer sendiri.",
    href: "https://github.com/aditrachman/Simulation-Prediction-Engine#installation",
    external: true,
  },
  {
    title: "Dokumentasi API",
    desc: "Endpoint dan contoh payload untuk otomasi.",
    href: "https://github.com/aditrachman/Simulation-Prediction-Engine#api-endpoints",
    external: true,
  },
  {
    title: "Konfigurasi",
    desc: "Model, variabel lingkungan, dan batas pemakaian.",
    href: "https://github.com/aditrachman/Simulation-Prediction-Engine#configuration",
    external: true,
  },
  {
    title: "Studi kasus",
    desc: "Contoh risalah dari sesi yang sudah dijalankan.",
    href: "/studi-kasus",
    external: false,
  },
];

function SwarmChart() {
  return (
    <>
      <div className="lp-swarm" role="img" aria-label="Sebaran sikap dua belas persona pada sesi contoh">
        <div className="lp-swarm-mid" aria-hidden="true" />
        {personas.map((p, i) => {
          const label = stanceOf(p.skor);
          return (
            <span
              key={p.nama}
              className="lp-swarm-dot"
              title={`${p.nama}: ${label}`}
              style={{
                left: `${((p.skor + 1) / 2) * 100}%`,
                top: `${8 + p.baris * 20}px`,
                background: stanceColor[label],
                animationDelay: `${i * 28}ms`,
              }}
            />
          );
        })}
      </div>
      <div className="lp-swarm-axis" aria-hidden="true">
        <span>Menolak</span>
        <span>Netral</span>
        <span>Mendukung</span>
      </div>
    </>
  );
}

export default function LandingPage() {
  return (
    <div className="lp">
      {/* ── Hero ───────────────────────────────────────── */}
      <section className="lp-hero">
        <div className="lp-wrap">
          <div className="lp-hero-grid">
            <div>
              <p className="lp-eyebrow">Risalah uji kebijakan</p>

              <h1 className="lp-h1">
                Sidangkan kebijakan <em>sebelum</em> ia diumumkan.
              </h1>

              <p className="lp-lead">
                Masukkan satu topik. Persona yang mewakili kelompok berbeda akan
                berdebat tiga ronde, lalu kamu baca transkrip, peta sikap, dan
                rekomendasinya.
              </p>

              <div className="lp-actions">
                <Link href="/demo" className="lp-btn lp-btn-primary">
                  Mulai simulasi
                </Link>
                <Link href="/studi-kasus" className="lp-btn lp-btn-quiet">
                  Lihat contoh risalah
                </Link>
              </div>

              <p className="lp-note" style={{ marginTop: 18 }}>
                Tanpa akun. Hasil bisa diunduh sebagai PDF, CSV, atau Word.
              </p>
            </div>

            {/* Contoh risalah */}
            <aside className="lp-risalah" aria-label="Contoh ringkasan risalah">
              <div className="lp-risalah-head">
                <span>Contoh risalah</span>
                <span>12 persona · 3 ronde</span>
              </div>

              <p className="lp-risalah-topik">
                Pajak barang mewah berlaku November 2026
              </p>

              <SwarmChart />

              <div className="lp-counts">
                <span>
                  <i style={{ background: "var(--lp-tolak)" }} />8 menolak
                </span>
                <span>
                  <i style={{ background: "var(--lp-netral)" }} />3 netral
                </span>
                <span>
                  <i style={{ background: "var(--lp-dukung)" }} />1 mendukung
                </span>
              </div>

              <div className="lp-verdict">
                <div className="lp-verdict-item">
                  <p className="lp-verdict-value">65</p>
                  <p className="lp-verdict-label">Polarisasi</p>
                </div>
                <div className="lp-verdict-item">
                  <p className="lp-verdict-value">15</p>
                  <p className="lp-verdict-label">Konsensus</p>
                </div>
                <div className="lp-verdict-item">
                  <p className="lp-verdict-value">20</p>
                  <p className="lp-verdict-label">Status quo</p>
                </div>
              </div>

              <blockquote className="lp-quote">
                <p>
                  “Pajak mewah cuma jadi beban, bro. Tanpa alokasi dana jelas,
                  korupsi nambah.”
                </p>
                <cite>Mahasiswa · ronde 3</cite>
              </blockquote>
            </aside>
          </div>
        </div>
      </section>

      {/* ── Spesifikasi ────────────────────────────────── */}
      <section className="lp-strip" aria-label="Ringkasan cara kerja">
        <div className="lp-wrap">
          <div className="lp-strip-grid">
            {specs.map((s) => (
              <div className="lp-strip-item" key={s.label}>
                <p className="lp-strip-value">{s.value}</p>
                <p className="lp-strip-label">{s.label}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Cara kerja ─────────────────────────────────── */}
      <section className="lp-section">
        <div className="lp-wrap">
          <div className="lp-split">
            <div className="lp-split-aside">
              <p className="lp-eyebrow">Cara kerja</p>
              <h2 className="lp-h2">Tiga langkah, satu risalah.</h2>
              <p className="lp-body" style={{ marginTop: 16, maxWidth: "30ch" }}>
                Tidak ada dasbor yang perlu dipelajari. Alurnya sama seperti
                menyiapkan bahan sidang.
              </p>
            </div>

            <div className="lp-steps">
              {steps.map((step, i) => (
                <div className="lp-step" key={step.title}>
                  <p className="lp-step-num">
                    {String(i + 1).padStart(2, "0")}
                  </p>
                  <div>
                    <h3 className="lp-h3">{step.title}</h3>
                    <p className="lp-body">{step.desc}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ── Isi risalah ────────────────────────────────── */}
      <section className="lp-section">
        <div className="lp-wrap">
          <div className="lp-split">
            <div className="lp-split-aside">
              <p className="lp-eyebrow">Isi risalah</p>
              <h2 className="lp-h2">Yang kamu baca setelah sesi selesai.</h2>
            </div>

            <div className="lp-outputs">
              {outputs.map((o) => (
                <div className="lp-output" key={o.key}>
                  <p className="lp-output-key">{o.key}</p>
                  <p className="lp-body">{o.desc}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ── Bahan bacaan ───────────────────────────────── */}
      <section className="lp-section">
        <div className="lp-wrap">
          <div className="lp-split">
            <div className="lp-split-aside">
              <p className="lp-eyebrow">Bahan bacaan</p>
              <h2 className="lp-h2">Kalau mau menjalankan sendiri.</h2>
            </div>

            <div className="lp-docs">
              {docs.map((doc) => (
                <Link
                  key={doc.title}
                  href={doc.href}
                  className="lp-doc"
                  {...(doc.external
                    ? { target: "_blank", rel: "noreferrer" }
                    : {})}
                >
                  <span>
                    <span className="lp-doc-title">{doc.title}</span>
                    <span className="lp-doc-desc" style={{ display: "block" }}>
                      {doc.desc}
                    </span>
                  </span>
                  <span className="lp-doc-arrow" aria-hidden="true">
                    →
                  </span>
                </Link>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ── Penutup ────────────────────────────────────── */}
      <section className="lp-close">
        <div className="lp-wrap">
          <div className="lp-close-grid">
            <div>
              <p className="lp-eyebrow">Mulai</p>
              <h2 className="lp-h2" style={{ maxWidth: "16ch" }}>
                Mulai dari satu topik.
              </h2>
              <p className="lp-lead" style={{ marginTop: 18 }}>
                Isi topik, pilih kategori dan jumlah ronde. Risalahnya bisa
                dibaca, diunduh, dan dibuka lagi kapan saja.
              </p>

              <div className="lp-actions">
                <Link href="/demo" className="lp-btn lp-btn-primary">
                  Jalankan simulasi
                </Link>
                <Link href="/studi-kasus" className="lp-btn lp-btn-quiet">
                  Baca contoh dulu
                </Link>
              </div>
            </div>

            <ol className="lp-close-list">
              <li>
                <span className="lp-close-num">1</span>Isi topik dan kategori
              </li>
              <li>
                <span className="lp-close-num">2</span>Tunggu tiga ronde selesai
              </li>
              <li>
                <span className="lp-close-num">3</span>Unduh atau bagikan risalah
              </li>
            </ol>
          </div>

          <p className="lp-disclaimer">
            VoxSwarm mensimulasikan reaksi kelompok berdasarkan persona dan
            data berita. Hasilnya bahan pertimbangan, bukan pengganti riset
            lapangan atau survei.
          </p>
        </div>
      </section>
    </div>
  );
}
