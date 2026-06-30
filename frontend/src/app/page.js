"use client";
import Link from "next/link";

// ─── Feature Icons ────────────────────────────────────────────
const IconNetwork = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#cc785c" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="5" r="2.5" />
    <circle cx="5" cy="19" r="2.5" />
    <circle cx="19" cy="19" r="2.5" />
    <line x1="12" y1="7.5" x2="5" y2="16.5" />
    <line x1="12" y1="7.5" x2="19" y2="16.5" />
    <line x1="7.5" y1="19" x2="16.5" y2="19" />
  </svg>
);

const IconChart = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#cc785c" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="3" width="18" height="18" rx="2" />
    <line x1="7" y1="16" x2="7" y2="12" />
    <line x1="12" y1="16" x2="12" y2="8" />
    <line x1="17" y1="16" x2="17" y2="10" />
  </svg>
);

const IconTarget = () => (
  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#cc785c" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="9" />
    <circle cx="12" cy="12" r="5" />
    <circle cx="12" cy="12" r="1.5" fill="#cc785c" />
    <line x1="12" y1="3" x2="12" y2="7" />
    <line x1="12" y1="17" x2="12" y2="21" />
    <line x1="3" y1="12" x2="7" y2="12" />
    <line x1="17" y1="12" x2="21" y2="12" />
  </svg>
);

const IconArrow = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M5 12h14M12 5l7 7-7 7" />
  </svg>
);

const featureIcons = [IconNetwork, IconChart, IconTarget];

// ─── Data ─────────────────────────────────────────────────────
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

const metrics = [
  { value: "91%", label: "Akurasi Skenario" },
  { value: "24+", label: "Jumlah Agen" },
  { value: "5",   label: "Kategori Isu" },
  { value: "<30s", label: "Waktu Simulasi" },
];

const docs = [
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

// ═══════════════════════════════════════════════════════════════
export default function LandingPage() {
  return (
    <div style={{ background: "#faf9f5" }}>

      {/* ══════════════════════════════════════════════
          HERO
      ══════════════════════════════════════════════ */}
      <section
        style={{
          background: "#faf9f5",
          paddingTop: 96,
          paddingBottom: 96,
          borderBottom: "1px solid #e6dfd8",
        }}
      >
        <div className="mx-auto max-w-5xl px-6">
          {/* Two-col layout: text left, mockup card right */}
          <div className="flex flex-col gap-12 lg:flex-row lg:items-center lg:gap-16">

            {/* Left: copy */}
            <div className="max-w-xl lg:flex-1">
              <p
                style={{
                  fontFamily: "var(--font-body, sans-serif)",
                  fontSize: 11,
                  fontWeight: 500,
                  letterSpacing: "1.5px",
                  textTransform: "uppercase",
                  color: "#6c6a64",
                  marginBottom: 20,
                }}
              >
                Social Simulation Engine
              </p>

              <h1
                style={{
                  fontFamily: "var(--font-heading, sans-serif)",
                  fontSize: "clamp(38px, 5vw, 60px)",
                  fontWeight: 700,
                  lineHeight: 1.05,
                  letterSpacing: "-1.5px",
                  color: "#141413",
                  marginBottom: 24,
                }}
              >
                Simulasi opini publik<br />
                <span style={{ color: "#141413" }}>untuk keputusan</span>{" "}
                <span style={{ color: "#cc785c" }}>strategis</span>
              </h1>

              <p
                style={{
                  fontFamily: "var(--font-body, sans-serif)",
                  fontSize: 16,
                  lineHeight: 1.75,
                  color: "#3d3d3a",
                  marginBottom: 40,
                  maxWidth: 480,
                }}
              >
                VoxSwarm membantu tim kebijakan, perencana strategis, dan pengambil
                keputusan untuk menguji respons publik terhadap suatu isu — sebelum
                isu tersebut menjadi perhatian umum.
              </p>

              <div style={{ display: "flex", flexWrap: "wrap", gap: 12 }}>
                <Link
                  href="/demo"
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 8,
                    background: "#cc785c",
                    color: "#ffffff",
                    fontFamily: "var(--font-body, sans-serif)",
                    fontSize: 14,
                    fontWeight: 500,
                    padding: "12px 24px",
                    borderRadius: 8,
                    textDecoration: "none",
                    transition: "background 0.15s",
                  }}
                  onMouseEnter={e => e.currentTarget.style.background = "#a9583e"}
                  onMouseLeave={e => e.currentTarget.style.background = "#cc785c"}
                >
                  Coba Simulasi
                </Link>
                <a
                  href="https://github.com/aditrachman/Simulation-Prediction-Engine"
                  target="_blank"
                  rel="noreferrer"
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 8,
                    background: "#faf9f5",
                    color: "#141413",
                    fontFamily: "var(--font-body, sans-serif)",
                    fontSize: 14,
                    fontWeight: 500,
                    padding: "12px 24px",
                    borderRadius: 8,
                    border: "1px solid #e6dfd8",
                    textDecoration: "none",
                    transition: "border-color 0.15s",
                  }}
                  onMouseEnter={e => e.currentTarget.style.borderColor = "#cc785c"}
                  onMouseLeave={e => e.currentTarget.style.borderColor = "#e6dfd8"}
                >
                  Lihat di GitHub
                </a>
              </div>
            </div>

            {/* Right: dark mockup card */}
            <div
              style={{
                background: "#181715",
                borderRadius: 16,
                padding: 28,
                flexShrink: 0,
                width: "100%",
                maxWidth: 400,
              }}
            >
              {/* Window chrome */}
              <div style={{ display: "flex", gap: 6, marginBottom: 20 }}>
                <div style={{ width: 10, height: 10, borderRadius: "50%", background: "#c64545", opacity: 0.7 }} />
                <div style={{ width: 10, height: 10, borderRadius: "50%", background: "#d4a017", opacity: 0.7 }} />
                <div style={{ width: 10, height: 10, borderRadius: "50%", background: "#5db872", opacity: 0.7 }} />
              </div>

              {/* Simulated topic input */}
              <div style={{ background: "#252320", borderRadius: 8, padding: "10px 14px", marginBottom: 16, border: "1px solid #333" }}>
                <p style={{ fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)", fontSize: 12, color: "#a09d96", margin: 0 }}>
                  Topik
                </p>
                <p style={{ fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)", fontSize: 13, color: "#faf9f5", margin: "4px 0 0" }}>
                  Apakah kenaikan UMP 2025 menguntungkan buruh?
                </p>
              </div>

              {/* Simulated agents */}
              {[
                { init: "JU", name: "Jurnalis/Media", sentiment: "Netral", color: "#6c6a64" },
                { init: "BU", name: "Buruh/Pekerja", sentiment: "Setuju", color: "#5db872" },
                { init: "UM", name: "Pengusaha/UMKM", sentiment: "Tidak Setuju", color: "#c64545" },
              ].map((agent) => (
                <div
                  key={agent.name}
                  style={{
                    background: "#252320",
                    borderRadius: 8,
                    padding: "10px 12px",
                    marginBottom: 8,
                    display: "flex",
                    alignItems: "center",
                    gap: 10,
                  }}
                >
                  <div style={{
                    width: 30, height: 30, borderRadius: "50%",
                    background: agent.color + "22",
                    border: `1px solid ${agent.color}44`,
                    color: agent.color,
                    display: "flex", alignItems: "center", justifyContent: "center",
                    fontSize: 10, fontWeight: 700, flexShrink: 0,
                  }}>
                    {agent.init}
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <p style={{ fontSize: 12, color: "#faf9f5", margin: 0, fontWeight: 500 }}>{agent.name}</p>
                  </div>
                  <span style={{
                    fontSize: 10, fontWeight: 500,
                    color: agent.color,
                    background: agent.color + "18",
                    border: `1px solid ${agent.color}33`,
                    borderRadius: 9999, padding: "2px 8px", flexShrink: 0,
                  }}>
                    {agent.sentiment}
                  </span>
                </div>
              ))}

              {/* Status bar */}
              <div style={{
                marginTop: 16,
                background: "#cc785c18",
                border: "1px solid #cc785c33",
                borderRadius: 8,
                padding: "8px 12px",
                display: "flex", alignItems: "center", gap: 8,
              }}>
                <div style={{ width: 6, height: 6, borderRadius: "50%", background: "#cc785c", flexShrink: 0 }} />
                <p style={{ fontSize: 11, color: "#cc785c", margin: 0, fontWeight: 500 }}>Simulasi selesai · Polarisasi 65%</p>
              </div>
            </div>

          </div>
        </div>
      </section>

      {/* ══════════════════════════════════════════════
          METRICS
      ══════════════════════════════════════════════ */}
      <section style={{ background: "#efe9de", paddingTop: 56, paddingBottom: 56, borderBottom: "1px solid #e6dfd8" }}>
        <div className="mx-auto max-w-5xl px-6">
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            {metrics.map((m) => (
              <div
                key={m.label}
                style={{
                  background: "#faf9f5",
                  border: "1px solid #e6dfd8",
                  borderRadius: 12,
                  padding: "24px 16px",
                  textAlign: "center",
                }}
              >
                <p
                  style={{
                    fontFamily: "var(--font-heading, sans-serif)",
                    fontSize: 32,
                    fontWeight: 600,
                    letterSpacing: "-0.5px",
                    color: "#141413",
                    margin: "0 0 6px",
                  }}
                >
                  {m.value}
                </p>
                <p
                  style={{
                    fontFamily: "var(--font-body, sans-serif)",
                    fontSize: 12,
                    fontWeight: 500,
                    letterSpacing: "0.3px",
                    color: "#6c6a64",
                    margin: 0,
                  }}
                >
                  {m.label}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ══════════════════════════════════════════════
          FEATURES — 3-up
      ══════════════════════════════════════════════ */}
      <section style={{ background: "#faf9f5", paddingTop: 96, paddingBottom: 96 }}>
        <div className="mx-auto max-w-5xl px-6">

          {/* Section header */}
          <div style={{ textAlign: "center", marginBottom: 56 }}>
            <p style={{
              fontFamily: "var(--font-body, sans-serif)",
              fontSize: 11, fontWeight: 500,
              letterSpacing: "1.5px", textTransform: "uppercase",
              color: "#6c6a64", marginBottom: 16,
            }}>
              Kemampuan Inti
            </p>
            <h2
              style={{
                fontFamily: "var(--font-heading, sans-serif)",
                fontSize: 36, fontWeight: 600,
                letterSpacing: "-0.5px", lineHeight: 1.15,
                color: "#141413", margin: "0 auto 16px",
                maxWidth: 480,
              }}
            >
              Apa yang bisa dilakukan VoxSwarm
            </h2>
            <p style={{
              fontFamily: "var(--font-body, sans-serif)",
              fontSize: 15, lineHeight: 1.7,
              color: "#3d3d3a", maxWidth: 440, margin: "0 auto",
            }}>
              Tiga kemampuan inti yang mengubah simulasi AI menjadi inteligensi keputusan.
            </p>
          </div>

          {/* Cards */}
          <div className="grid gap-5 md:grid-cols-3">
            {features.map((feature, i) => {
              const Icon = featureIcons[i];
              return (
                <article
                  key={feature.title}
                  style={{
                    background: "#efe9de",
                    border: "1px solid #e6dfd8",
                    borderRadius: 12,
                    padding: 32,
                  }}
                >
                  {/* Icon circle */}
                  <div style={{
                    width: 44, height: 44, borderRadius: "50%",
                    background: "#cc785c18",
                    border: "1px solid #cc785c30",
                    display: "flex", alignItems: "center", justifyContent: "center",
                    marginBottom: 20,
                  }}>
                    <Icon />
                  </div>

                  <h3
                    style={{
                      fontFamily: "var(--font-heading, sans-serif)",
                      fontSize: 20, fontWeight: 600,
                      letterSpacing: "-0.3px", lineHeight: 1.3,
                      color: "#141413", marginBottom: 10,
                    }}
                  >
                    {feature.title}
                  </h3>
                  <p style={{
                    fontFamily: "var(--font-body, sans-serif)",
                    fontSize: 14, lineHeight: 1.7,
                    color: "#3d3d3a", margin: 0,
                  }}>
                    {feature.desc}
                  </p>
                </article>
              );
            })}
          </div>
        </div>
      </section>

      {/* ══════════════════════════════════════════════
          ABOUT — Dark card band
      ══════════════════════════════════════════════ */}
      <section style={{ background: "#efe9de", paddingTop: 96, paddingBottom: 96, borderTop: "1px solid #e6dfd8" }}>
        <div className="mx-auto max-w-5xl px-6">
          <div
            style={{
              background: "#181715",
              borderRadius: 16,
              padding: "48px 48px",
              display: "flex",
              flexDirection: "column",
              gap: 32,
            }}
          >
            <div>
              <p style={{
                fontFamily: "var(--font-body, sans-serif)",
                fontSize: 11, fontWeight: 500,
                letterSpacing: "1.5px", textTransform: "uppercase",
                color: "#a09d96", marginBottom: 16,
              }}>
                Tentang Proyek
              </p>
              <h2
                style={{
                  fontFamily: "var(--font-heading, sans-serif)",
                  fontSize: 32, fontWeight: 600,
                  letterSpacing: "-0.5px", lineHeight: 1.2,
                  color: "#faf9f5", marginBottom: 16, maxWidth: 480,
                }}
              >
                Dibuat oleh Adit Rachman
              </h2>
              <p style={{
                fontFamily: "var(--font-body, sans-serif)",
                fontSize: 15, lineHeight: 1.75,
                color: "#a09d96", maxWidth: 560,
              }}>
                VoxSwarm dikembangkan untuk mengubah simulasi AI menjadi inteligensi keputusan
                yang praktis. Fokus pada produk yang bersih secara visual, cepat dijalankan, dan
                berguna dalam skenario nyata.
              </p>
            </div>

            {/* Stats row */}
            <div style={{ display: "flex", flexWrap: "wrap", gap: 40, borderTop: "1px solid #333", paddingTop: 32 }}>
              {[
                { value: "3",   label: "Kategori simulasi" },
                { value: "∞",   label: "Skenario possible" },
                { value: "OSS", label: "Open source" },
              ].map((stat) => (
                <div key={stat.label}>
                  <p style={{
                    fontFamily: "var(--font-heading, sans-serif)",
                    fontSize: 28, fontWeight: 600,
                    color: "#faf9f5", margin: "0 0 4px",
                  }}>
                    {stat.value}
                  </p>
                  <p style={{
                    fontFamily: "var(--font-body, sans-serif)",
                    fontSize: 12, fontWeight: 500,
                    color: "#6c6a64", margin: 0, letterSpacing: "0.3px",
                  }}>
                    {stat.label}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ══════════════════════════════════════════════
          DOCS — 3-up
      ══════════════════════════════════════════════ */}
      <section style={{ background: "#faf9f5", paddingTop: 96, paddingBottom: 96 }}>
        <div className="mx-auto max-w-5xl px-6">

          <div style={{ textAlign: "center", marginBottom: 56 }}>
            <p style={{
              fontFamily: "var(--font-body, sans-serif)",
              fontSize: 11, fontWeight: 500,
              letterSpacing: "1.5px", textTransform: "uppercase",
              color: "#6c6a64", marginBottom: 16,
            }}>
              Dokumentasi
            </p>
            <h2
              style={{
                fontFamily: "var(--font-heading, sans-serif)",
                fontSize: 36, fontWeight: 600,
                  letterSpacing: "-0.5px", lineHeight: 1.15,
                  color: "#141413", margin: 0,
                }}
              >
                Semua yang Anda perlukan untuk memulai
            </h2>
          </div>

          <div className="grid gap-5 md:grid-cols-3">
            {docs.map((item) => (
              <a
                key={item.title}
                href={item.href}
                target="_blank"
                rel="noreferrer"
                style={{
                  display: "block",
                  background: "#faf9f5",
                  border: "1px solid #e6dfd8",
                  borderRadius: 12,
                  padding: 28,
                  textDecoration: "none",
                  transition: "border-color 0.15s",
                }}
                onMouseEnter={e => e.currentTarget.style.borderColor = "#cc785c"}
                onMouseLeave={e => e.currentTarget.style.borderColor = "#e6dfd8"}
              >
                <h3
                  style={{
                    fontFamily: "var(--font-heading, sans-serif)",
                    fontSize: 18, fontWeight: 600,
                    letterSpacing: "-0.2px",
                    color: "#141413", marginBottom: 10,
                  }}
                >
                  {item.title}
                </h3>
                <p style={{
                  fontFamily: "var(--font-body, sans-serif)",
                  fontSize: 14, lineHeight: 1.7,
                  color: "#3d3d3a", margin: "0 0 16px",
                }}>
                  {item.desc}
                </p>
                <span style={{
                  display: "inline-flex", alignItems: "center", gap: 6,
                  fontSize: 13, fontWeight: 500, color: "#cc785c",
                }}>
                  Baca dokumentasi
                  <IconArrow />
                </span>
              </a>
            ))}
          </div>
        </div>
      </section>

      {/* ══════════════════════════════════════════════
          CTA — Coral full-bleed band
      ══════════════════════════════════════════════ */}
      <section
        style={{
          background: "#cc785c",
          paddingTop: 72,
          paddingBottom: 72,
        }}
      >
        <div className="mx-auto max-w-5xl px-6">
          <div style={{ maxWidth: 520, margin: "0 auto", textAlign: "center" }}>
            <h2
              style={{
                fontFamily: "var(--font-heading, sans-serif)",
                fontSize: 36, fontWeight: 600,
                  letterSpacing: "-0.5px", lineHeight: 1.15,
                  color: "#ffffff", marginBottom: 16,
                }}
              >
                Siap mencoba simulasi?
            </h2>
            <p style={{
              fontFamily: "var(--font-body, sans-serif)",
              fontSize: 16, lineHeight: 1.75,
              color: "rgba(255,255,255,0.8)",
              marginBottom: 36,
            }}>
              Uji respons publik terhadap isu Anda sekarang — gratis, tanpa perlu registrasi.
            </p>
            <Link
              href="/demo"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 8,
                background: "#faf9f5",
                color: "#141413",
                fontFamily: "var(--font-body, sans-serif)",
                fontSize: 14,
                fontWeight: 500,
                padding: "12px 28px",
                borderRadius: 8,
                textDecoration: "none",
                transition: "opacity 0.15s",
              }}
              onMouseEnter={e => e.currentTarget.style.opacity = "0.9"}
              onMouseLeave={e => e.currentTarget.style.opacity = "1"}
            >
              Mulai Simulasi
            </Link>
          </div>
        </div>
      </section>

    </div>
  );
}