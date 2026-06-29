import Link from "next/link";

const features = [
  {
    title: "Simulasi Opini Publik",
    desc: "Modelkan respons masyarakat dari beragam perspektif agen sebelum kebijakan atau isu diluncurkan ke publik.",
  },
  {
    title: "Analisis Sentimen Dinamis",
    desc: "Pantau pergeseran dukungan, penolakan, dan ketidakpastian melalui hasil simulasi yang terstruktur per putaran.",
  },
  {
    title: "Rekomendasi Strategis",
    desc: "Ubah narasi kompleks menjadi sinyal risiko dan rekomendasi yang dapat ditindaklanjuti oleh pengambil keputusan.",
  },
];

const docItems = [
  {
    title: "Panduan Cepat",
    desc: "Jalankan backend dan frontend secara lokal, hubungkan API, dan uji simulasi pertama dalam hitungan menit.",
    href: "https://github.com/aditrachman/Simulation-Prediction-Engine#installation",
  },
  {
    title: "Dokumentasi API",
    desc: "Pelajari endpoint dan format payload yang tersedia untuk mengotomatisasi alur kerja simulasi dan prediksi.",
    href: "https://github.com/aditrachman/Simulation-Prediction-Engine#api-endpoints",
  },
  {
    title: "Konfigurasi",
    desc: "Atur model, variabel lingkungan, dan pengaturan deployment sesuai kebutuhan spesifik Anda.",
    href: "https://github.com/aditrachman/Simulation-Prediction-Engine#configuration",
  },
];

export default function LandingPage() {
  return (
    <main className="min-h-screen bg-[#0B1120] text-[#F1F5F9]">
      {/* ─── NAV ─── */}
      <section className="mx-auto flex max-w-6xl flex-col px-6 pt-8 pb-16 md:px-10 md:pt-10 md:pb-20">
        <div className="mb-12 flex items-center justify-between">
          <h1 className="text-xl font-bold tracking-tight" style={{ fontFamily: "var(--font-display)" }}>
            VoxSwarm
          </h1>
          <Link
            href="/demo"
            className="rounded-lg border border-white/20 px-5 py-2 text-xs font-semibold transition hover:border-blue-400 hover:bg-blue-500/10"
          >
            Coba Simulasi
          </Link>
        </div>

        {/* ─── HERO ─── */}
        <div className="grid gap-12 lg:grid-cols-2 lg:items-center">
          <div>
            <p className="mb-3 text-xs font-medium tracking-wider text-blue-300 uppercase">
              Social Simulation Engine
            </p>
            <h2
              className="mb-5 text-4xl leading-tight font-extrabold tracking-tight md:text-5xl"
              style={{ fontFamily: "var(--font-display)" }}
            >
              Simulasi opini publik
              <span className="block text-blue-400">untuk keputusan strategis</span>
            </h2>
            <p className="mb-8 max-w-xl text-sm leading-7 text-slate-400 md:text-base">
              VoxSwarm membantu tim kebijakan, perencana strategis, dan pengambil keputusan untuk
              menguji respons publik terhadap suatu isu — sebelum isu tersebut menjadi perhatian umum.
            </p>

            <div className="flex flex-wrap gap-3">
              <Link
                href="/demo"
                className="rounded-lg bg-blue-600 px-6 py-3 text-sm font-semibold transition hover:bg-blue-500"
              >
                Coba Simulasi
              </Link>
              <a
                href="https://mirofish-demo.pages.dev/"
                target="_blank"
                rel="noreferrer"
                className="rounded-lg border border-white/20 px-6 py-3 text-sm font-medium text-slate-300 transition hover:border-white/40 hover:text-white"
              >
                Lihat Referensi
              </a>
            </div>
          </div>

          {/* ─── HERO STATS ─── */}
          <div className="rounded-2xl border border-white/10 bg-[#132237] p-8">
            <div className="mb-6 grid grid-cols-2 gap-4">
              <div className="rounded-xl border border-white/10 bg-[#1A2D4A] p-5">
                <p className="text-xs text-slate-400 uppercase tracking-wider">Akurasi Skenario</p>
                <p
                  className="mt-2 text-3xl font-bold text-blue-400"
                  style={{ fontFamily: "var(--font-display)" }}
                >
                  91%
                </p>
              </div>
              <div className="rounded-xl border border-white/10 bg-[#1A2D4A] p-5">
                <p className="text-xs text-slate-400 uppercase tracking-wider">Jumlah Agen</p>
                <p
                  className="mt-2 text-3xl font-bold text-blue-400"
                  style={{ fontFamily: "var(--font-display)" }}
                >
                  24+
                </p>
              </div>
            </div>
            <div className="rounded-xl border border-blue-500/20 bg-blue-500/5 p-5">
              <p className="text-xs font-medium tracking-wider text-blue-300 uppercase">
                Contoh Hasil Simulasi
              </p>
              <p className="mt-3 text-sm leading-7 text-slate-300">
                &ldquo;Kebijakan X berpotensi memicu penolakan moderat di komunitas perkotaan,
                sementara klaster pedesaan cenderung netral dengan risiko eskalasi rendah.&rdquo;
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ─── FEATURES ─── */}
      <section className="border-t border-white/10 bg-[#0E1929]">
        <div className="mx-auto max-w-6xl px-6 py-16 md:px-10">
          <p className="mb-2 text-xs font-medium tracking-wider text-blue-300 uppercase">
            Kemampuan Utama
          </p>
          <h2
            className="mb-8 text-2xl font-bold md:text-3xl"
            style={{ fontFamily: "var(--font-display)" }}
          >
            Apa yang bisa dilakukan VoxSwarm
          </h2>
          <div className="grid gap-4 md:grid-cols-3">
            {features.map((feature) => (
              <article
                key={feature.title}
                className="rounded-xl border border-white/10 bg-[#132237] p-6 transition hover:border-blue-500/30"
              >
                <h3 className="mb-2 text-sm font-bold text-white">{feature.title}</h3>
                <p className="text-sm leading-6 text-slate-400">{feature.desc}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      {/* ─── ABOUT + GITHUB ─── */}
      <section className="border-t border-white/10 bg-[#0B1120]">
        <div className="mx-auto max-w-6xl px-6 py-16 md:px-10">
          <div className="grid gap-6 md:grid-cols-2">
            <article className="rounded-xl border border-blue-500/20 bg-blue-500/5 p-7">
              <p className="mb-2 text-xs font-medium tracking-wider text-blue-300 uppercase">
                Dukung Pengembangan
              </p>
              <h3
                className="mb-3 text-xl font-bold"
                style={{ fontFamily: "var(--font-display)" }}
              >
                Bantu VoxSwarm Berkembang
              </h3>
              <p className="mb-5 text-sm leading-7 text-slate-400">
                Jika proyek ini bermanfaat, berikan bintang di GitHub untuk mendukung pengembangan
                dan pembaruan di masa mendatang.
              </p>
              <a
                href="https://github.com/aditrachman/Simulation-Prediction-Engine"
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center rounded-lg bg-blue-600 px-5 py-2.5 text-xs font-semibold transition hover:bg-blue-500"
              >
                Beri Bintang di GitHub
              </a>
            </article>

            <article className="rounded-xl border border-white/10 bg-[#132237] p-7">
              <p className="mb-2 text-xs font-medium tracking-wider text-blue-300 uppercase">
                Tentang
              </p>
              <h3
                className="mb-3 text-xl font-bold"
                style={{ fontFamily: "var(--font-display)" }}
              >
                Dibuat oleh Adit Rachman
              </h3>
              <p className="text-sm leading-7 text-slate-400">
                VoxSwarm dikembangkan untuk mengubah simulasi AI menjadi inteligensi keputusan
                yang praktis. Fokus pada produk yang bersih secara visual, cepat dijalankan, dan
                berguna dalam skenario nyata.
              </p>
            </article>
          </div>
        </div>
      </section>

      {/* ─── DOCS ─── */}
      <section className="border-t border-white/10 bg-[#0E1929]">
        <div className="mx-auto max-w-6xl px-6 py-16 md:px-10">
          <p className="mb-2 text-xs font-medium tracking-wider text-blue-300 uppercase">
            Dokumentasi
          </p>
          <h2
            className="mb-8 text-xl font-bold"
            style={{ fontFamily: "var(--font-display)" }}
          >
            Semua yang Anda perlukan untuk memulai
          </h2>
          <div className="grid gap-4 md:grid-cols-3">
            {docItems.map((item) => (
              <a
                key={item.title}
                href={item.href}
                target="_blank"
                rel="noreferrer"
                className="rounded-xl border border-white/10 bg-[#132237] p-6 transition hover:border-blue-500/30 hover:bg-blue-500/5"
              >
                <h4 className="mb-2 text-sm font-bold text-white">{item.title}</h4>
                <p className="text-sm leading-6 text-slate-400">{item.desc}</p>
              </a>
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}
