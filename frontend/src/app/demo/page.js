"use client";
import { eksporPDF } from "../utils/eksporpdf";
import { eksporCSV } from "../utils/eksporlainnya";
import { eksporWord } from "../utils/eksporlainnya";
import { useState, useEffect, useRef, useMemo } from "react";
import Link from "next/link";
import {
  BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Cell,
  LineChart, Line, Tooltip, CartesianGrid, ReferenceLine, Legend,
} from "recharts";

// ─── Warna & Label ─────────────────────────────────────────────────
const SENTIMEN = {
  positif: { warna: "#22c55e", label: "Setuju", bg: "bg-green-500/15 border-green-500/30 text-green-400" },
  netral:  { warna: "#64748b", label: "Netral",     bg: "bg-slate-500/15 border-slate-500/30 text-slate-300" },
  negatif: { warna: "#ef4444", label: "Tidak Setuju", bg: "bg-red-500/15 border-red-500/30 text-red-400" },
};
const WARNA_AGEN = ["#3B82F6","#22c55e","#f59e0b","#ef4444","#8b5cf6","#06b6d4","#ec4899","#14b8a6"];
const LABEL_SENTIMEN = { positif: "Mendukung", netral: "Netral", negatif: "Menolak" };
const WARNA_SENTIMEN = { positif: "#22c55e", netral: "#64748b", negatif: "#ef4444" };

// ─── Helper ────────────────────────────────────────────────────────
function bersihkanTeks(teks) {
  if (!teks) return "";
  return teks.replace(/[^\x00-\x7F]/g, "").replace(/  +/g, " ").trim();
}

function bacaData(payload, pesan = "Data tidak ditemukan.") {
  if (!payload || typeof payload !== "object" || !payload.data)
    throw new Error(payload?.detail || payload?.message || pesan);
  return payload.data;
}

// ─── Badge Sikap ────────────────────────────────────────────────────
const BadgeSikap = ({ label }) => {
  const s = SENTIMEN[label] ?? SENTIMEN.netral;
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-bold ${s.bg}`}>
      <span className="h-2 w-2 rounded-full" style={{ backgroundColor: s.warna }} />
      {s.label}
    </span>
  );
};

// ─── A1: Kartu & JudulSeksi ───────────────────────────────────────────
const Kartu = ({ children, className = "" }) => (
  <div className={`rounded-2xl border border-white/8 bg-[#0D1017] p-6 page-break-avoid print-card hover:border-white/[0.14] transition-all duration-200 ${className}`}>
    {children}
  </div>
);

const JudulSeksi = ({ children }) => (
  <p className="mb-3 text-[11px] font-semibold tracking-[0.12em] text-slate-400 uppercase">{children}</p>
);

// ─── A2: BadgeSentimen ───────────────────────────────────────────────
const BadgeSentimen = ({ label }) => {
  const style = {
    positif: "bg-emerald-950 text-emerald-300 border-emerald-800 print-badge-mendukung",
    netral:  "bg-slate-800 text-slate-300 border-slate-700 print-badge-netral",
    negatif: "bg-red-950 text-red-300 border-red-800 print-badge-menolak",
  }[label] ?? "bg-slate-800/60 text-slate-400 border-slate-700";
  return (
    <span className={`rounded-md border px-2 py-0.5 text-[11px] font-medium ${style}`}>
      {LABEL_SENTIMEN[label] ?? label ?? "–"}
    </span>
  );
};

// ─── B1: KartuKesimpulan ─────────────────────────────────────────────
const KartuKesimpulan = ({ topik, status, narasi, daftarRonde, rondeIni }) => {
  const INFO = {
    stabil:    { label: "Situasi Stabil",   border: "border-l-emerald-500", dot: "bg-emerald-400", teks: "text-emerald-300" },
    berbahaya: { label: "Potensi Konflik",  border: "border-l-red-500",     dot: "bg-red-400",     teks: "text-red-300" },
    terbagi:   { label: "Pendapat Terbagi", border: "border-l-amber-500",   dot: "bg-amber-400",   teks: "text-amber-300" },
  };
  const info = INFO[status] ?? INFO.terbagi;

  const ringkasan = (() => {
    if (!narasi) return "—";
    const idx = narasi.indexOf(".", 60);
    return idx > 0 ? narasi.slice(0, idx + 1) : narasi.slice(0, 180);
  })();

  const pesertaCount = rondeIni?.agen?.length ?? 0;
  const putaranCount = daftarRonde?.length ?? 0;

  return (
    <div className={`rounded-2xl border border-white/8 bg-[#0D1017] p-6 border-l-4 ${info.border}`}>
      {/* Status badge */}
      <div className="flex items-center gap-2 mb-4">
        <span className={`inline-block h-2 w-2 rounded-full ${info.dot}`} />
        <span className={`text-xs font-semibold ${info.teks}`}>{info.label}</span>
        <span className="text-slate-700 text-xs">·</span>
        <span className="text-xs text-slate-600">
          {putaranCount} putaran · {pesertaCount} peserta
        </span>
      </div>

      {/* Topik */}
      <p className="text-[11px] text-slate-600 mb-1 uppercase tracking-widest font-medium">Topik simulasi</p>
      <p className="text-base font-semibold text-white mb-4 leading-snug">"{topik}"</p>

      {/* Ringkasan */}
      <p className="text-sm text-slate-300 leading-7">{ringkasan}</p>
    </div>
  );
};

// ─── B2: KartuDistribusiSingkat ──────────────────────────────────────
const KartuDistribusiSingkat = ({ dataBar }) => {
  const menolak   = dataBar.filter(a => a.skor < 40).length;
  const mendukung = dataBar.filter(a => a.skor >= 60).length;
  const netral    = dataBar.length - menolak - mendukung;
  const total     = dataBar.length || 1;

  const items = [
    { label: "Menolak",    count: menolak,   bg: "bg-red-950",     text: "text-red-300",     bar: "bg-red-500" },
    { label: "Netral",     count: netral,    bg: "bg-slate-800/60",text: "text-slate-300",   bar: "bg-slate-600" },
    { label: "Mendukung",  count: mendukung, bg: "bg-emerald-950", text: "text-emerald-300", bar: "bg-emerald-500" },
  ];

  return (
    <Kartu>
      <JudulSeksi>Distribusi Pendapat</JudulSeksi>
      <div className="grid grid-cols-3 gap-3 mb-4">
        {items.map(({ label, count, bg, text }) => (
          <div key={label} className={`text-center py-4 px-3 rounded-xl ${bg} border border-white/5`}>
            <p className={`text-3xl font-bold ${text} mb-1`}>{count}</p>
            <p className={`text-xs ${text} opacity-70`}>{label}</p>
          </div>
        ))}
      </div>
      {/* Progress bar */}
      <div className="h-1.5 rounded-full overflow-hidden flex bg-white/5">
        {items.map(({ label, count, bar }) => (
          count > 0 && (
            <div key={label} className={`h-full ${bar} transition-all`}
              style={{ width: `${(count / total) * 100}%` }} />
          )
        ))}
      </div>
      <div className="flex justify-between mt-2">
        {items.map(({ label, count, text }) => (
          <span key={label} className={`text-[11px] ${text} opacity-60`}>
            {Math.round((count / total) * 100)}%
          </span>
        ))}
      </div>
    </Kartu>
  );
};

// ─── B3: KartuAgenRingkas ────────────────────────────────────────────
const KartuAgenRingkas = ({ rondeIni }) => {
  const [bukaIndex, setBukaIndex] = useState(null);
  const agen = rondeIni?.agen ?? [];

  return (
    <Kartu>
      <JudulSeksi>Suara Tiap Kelompok</JudulSeksi>
      <div className="space-y-2">
        {agen.map((a, i) => {
          const warnaMap = { positif: "#22c55e", netral: "#64748b", negatif: "#ef4444" };
          const warna = warnaMap[a.sentimen?.label] ?? "#6366f1";
          const buka  = bukaIndex === i;
          const quoteSingkat = a.pendapat
            ? a.pendapat.slice(0, 85) + (a.pendapat.length > 85 ? "..." : "")
            : "";

          return (
            <div key={i} className="agen-card overflow-hidden">
              <button
                onClick={() => setBukaIndex(buka ? null : i)}
                className="w-full flex items-center gap-3 px-4 py-3 text-left"
              >
                {/* Avatar */}
                <div
                  className="h-8 w-8 shrink-0 rounded-full flex items-center justify-center text-[10px] font-bold"
                  style={{ backgroundColor: warna + "1A", border: `1px solid ${warna}55`, color: warna }}
                >
                  {a.nama.slice(0, 2).toUpperCase()}
                </div>

                {/* Konten */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className="text-sm font-semibold text-slate-200">{a.nama}</span>
                    <BadgeSentimen label={a.sentimen?.label} />
                  </div>
                  {!buka && (
                    <p className="text-xs text-slate-500 truncate">"{quoteSingkat}"</p>
                  )}
                </div>

                <span className="text-slate-700 text-[10px] shrink-0 ml-2">{buka ? "▲" : "▼"}</span>
              </button>

              {buka && (
                <div className="px-4 pb-4 pt-1 border-t border-white/5">
                  <p className="text-sm leading-7 text-slate-300">"{a.pendapat}"</p>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </Kartu>
  );
};

// ─── B4: LaciDetail ──────────────────────────────────────────────────
const LaciDetail = ({ children }) => {
  const [buka, setBuka] = useState(false);

  return (
    <div className="rounded-2xl border border-white/8 overflow-hidden">
      <button
        onClick={() => setBuka(v => !v)}
        className="w-full flex items-center justify-between px-5 py-4 bg-[#0D1017] hover:bg-white/5 transition text-left"
      >
        <div className="flex items-center gap-3">
          <span className="text-sm font-semibold text-slate-300">Detail Lengkap</span>
          <span className="rounded-md bg-indigo-500/15 px-2 py-0.5 text-[10px] font-medium text-indigo-400 border border-indigo-500/20">
            Teknis & grafik
          </span>
        </div>
        <span className="text-xs text-slate-500 font-medium">
          {buka ? "Sembunyikan ▲" : "Lihat detail ▼"}
        </span>
      </button>

      {buka && (
        <div className="border-t border-white/8 space-y-5 p-5 bg-[#08090F]">
          {children}
        </div>
      )}
    </div>
  );
};

// ═══════════════════════════════════════════════════════════════════
//                         HALAMAN UTAMA
// ═══════════════════════════════════════════════════════════════════
export default function HalamanSimulasi() {
  const [terpasang,   setTerpasang]   = useState(false);
  const [topik,       setTopik]       = useState("");
  const [kategori,    setKategori]    = useState("Umum");
  const [jumlahRonde, setJumlahRonde] = useState(3);
  const [hasil,       setHasil]       = useState(null);
  const [memuat,      setMemuat]      = useState(false);
  const [tier,        setTier]        = useState("free");
  const [lihatDetail, setLihatDetail] = useState(false);
  const [warningTopik, setWarningTopik] = useState(null);
  const [bukaEkspor, setBukaEkspor] = useState(false);
  const [rondeAktif, setRondeAktif] = useState(0);

  const inputRef = useRef(null);
  const hasilRef = useRef(null);
  const apiBase  = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

  useEffect(() => {
    setTerpasang(true);
  }, []);

  // ── Mulai Simulasi ──────────────────────────────────────────────
  const mulaiAnalisis = async () => {
    if (!topik.trim()) { inputRef.current?.focus(); return; }
    setMemuat(true);
    setHasil(null);
    try {
      const body = { topik: topik.trim(), kategori, jumlah_ronde: jumlahRonde, tier };
      const res = await fetch(`${apiBase}/start-simulation`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Permintaan gagal.");
      }
      const data = await res.json();
      setHasil(bacaData(data, "Respons tidak berisi data."));
      if (data.warning) setWarningTopik(data.warning);
      else setWarningTopik(null);
      setTimeout(() => hasilRef.current?.scrollIntoView({ behavior: "smooth" }), 200);
    } catch (err) {
      alert("❌ " + (err.message || "Server tidak dapat dihubungi."));
    }
    setMemuat(false);
  };

  // ── Data turunan ────────────────────────────────────────────────
  const daftarRonde   = hasil?.ronde_detail ?? [];
  const rondePertama  = daftarRonde[0] ?? null;
  const rondeTerakhir = daftarRonde[daftarRonde.length - 1] ?? null;
  const agenAkhir     = rondeTerakhir?.agen ?? [];
  const analisis      = hasil?.analisis ?? "";
  const prediksi      = hasil?.prediksi ?? {};
  const sentimenAgr   = hasil?.sentimen_agregat ?? {};
  const aktorAnalisis = hasil?.aktor_analisis ?? null;
  const aktorKunci    = aktorAnalisis?.aktor_kunci ?? [];
  const rekomendasi   = aktorAnalisis?.rekomendasi ?? "";
  const rekomendasiStrategis = hasil?.rekomendasi_strategis ?? [];
  const risikoUtama   = hasil?.risiko_utama ?? "";
  const kelompokKritis = aktorAnalisis?.kelompok_kritis ?? [];
  const penggerak     = aktorAnalisis?.aktor_penggerak ?? "";

  // Ringkasan — bersihin teks dari markdown noise & jargon
  const ringkasan = analisis
    .split("\n")
    .filter(l => {
      const t = l.trim();
      if (!t) return false;
      if (t.includes("|")) return false;
      if (/^#{1,4}\s/.test(t)) return false;
      if (/^\d+\.\s+(Buat|Tugas|Narasi|Tabel|Prediksi)/i.test(t)) return false;
      if (/Pengaruh|Konsistensi|Skor\s*komposit|komposit/i.test(t)) return false;
      return true;
    })
    .join(" ")
    .replace(/\*{1,2}/g, "")
    .slice(0, 800);

  // Hitung sentimen akhir
  const jumlahMendukung = agenAkhir.filter(a => a.sentimen?.label === "positif").length;
  const jumlahMenolak   = agenAkhir.filter(a => a.sentimen?.label === "negatif").length;
  const jumlahNetral    = agenAkhir.filter(a => a.sentimen?.label === "netral").length;

  // Tentukan hasil akhir
  let hasilAkhir = { label: "Belum Ada", warna: "#64748b", ikon: "", desc: "" };
  if (Object.keys(prediksi).length > 0) {
    const sorted = Object.entries(prediksi).sort((a, b) => b[1] - a[1]);
    const p = sorted[0];
    if (p[0] === "Semua Setuju") {
      hasilAkhir = { label: "Semua Setuju", warna: "#22c55e", ikon: "🤝", desc: "Mayoritas peserta sepakat dengan isu ini — opini publik cenderung positif." };
    } else if (p[0] === "Masyarakat Terpecah") {
      hasilAkhir = { label: "Masyarakat Terpecah", warna: "#ef4444", ikon: "⚡", desc: "Pendapat peserta terbelah dan berpotensi memicu konflik." };
    } else {
      hasilAkhir = { label: "Opini Stabil", warna: "#f59e0b", ikon: "🔹", desc: "Pendapat peserta cenderung stabil sepanjang simulasi — tidak ada perdebatan yang berarti." };
    }
  } else if (agenAkhir.length > 0) {
    if (jumlahMendukung > jumlahMenolak && jumlahMendukung > jumlahNetral) {
      hasilAkhir = { label: "Cenderung Setuju", warna: "#22c55e", ikon: "📈", desc: "Mayoritas peserta setuju dengan isu ini — opini publik cenderung positif." };
    } else if (jumlahMenolak > jumlahMendukung && jumlahMenolak > jumlahNetral) {
      hasilAkhir = { label: "Cenderung Tidak Setuju", warna: "#ef4444", ikon: "📉", desc: "Mayoritas peserta tidak setuju dengan isu ini — opini publik cenderung negatif." };
    } else {
      hasilAkhir = { label: "Pendapat Terbagi", warna: "#f59e0b", ikon: "⚖️", desc: "Pendapat peserta terbagi rata — belum ada dominasi sikap yang jelas." };
    }
  }

  // Data untuk chart distribusi akhir
  const dataBar = useMemo(() => agenAkhir.map(a => ({
    nama:      a.nama,
    namaLabel: a.nama.length > 10 ? a.nama.slice(0, 9) + "…" : a.nama,
    skor:      Math.round(((a.sentimen?.skor ?? 0) + 1) * 50),
    warna:     SENTIMEN[a.sentimen?.label]?.warna ?? "#64748b",
    label:     a.sentimen?.label ?? "netral",
  })), [agenAkhir]);

  // Data untuk chart tren
  const dataTren = useMemo(() => {
    const namaAgen = Object.keys(sentimenAgr);
    if (!namaAgen.length) return [];
    return Array.from({ length: sentimenAgr[namaAgen[0]]?.length ?? 0 }, (_, i) => {
      const obj = { label: i + 1 };
      namaAgen.forEach(n => { obj[n] = +(sentimenAgr[n]?.[i] ?? 0).toFixed(2); });
      return obj;
    });
  }, [sentimenAgr]);

  // Warna per agen
  const warnaAgen = Object.keys(sentimenAgr).reduce((acc, nama, i) => {
    acc[nama] = WARNA_AGEN[i % WARNA_AGEN.length];
    return acc;
  }, {});

  // ── Simpan hasil ───────────────────────────────────────────────
  const handleSimpanPDF = () => eksporPDF(hasil, topik, analisis, aktorAnalisis, null);
  const handleSimpanCSV = () => eksporCSV(hasil, topik);
  const handleSimpanWord = () => eksporWord(hasil, topik, analisis).catch(e => alert(e.message));

  if (!terpasang) return null;

  return (
    <main className="bg-[#0B1120] text-[#F1F5F9]">

      {/* ════════════════ HEADER ════════════════ */}
      <div className="mx-auto max-w-4xl px-4 py-5 md:px-6">
        <div className="flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2 text-sm text-slate-500 hover:text-white transition">
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M10.5 19.5L3 12m0 0l7.5-7.5M3 12h18" />
            </svg>
            Beranda
          </Link>
          <div className="flex items-center gap-2">
            <span className="text-lg font-bold tracking-tight" style={{ fontFamily: "var(--font-display)" }}>VoxSwarm</span>
            <span className="rounded-full bg-blue-500/15 px-2 py-0.5 text-[10px] font-semibold text-blue-400">Simulasi</span>
          </div>
        </div>
      </div>

      {/* ════════════════ ONBOARDING CONTEXT ════════════════ */}
      <section className="mx-auto max-w-4xl px-4 pt-6 pb-2 md:px-6">
        <p className="mb-1 text-xs font-medium tracking-wider text-blue-300 uppercase">
          Social Simulation Engine
        </p>
        <h2 className="mb-2 text-2xl font-bold tracking-tight text-white" style={{ fontFamily: "var(--font-display)" }}>
          Simulasi Opini Publik
        </h2>
        <p className="text-sm leading-7 text-slate-400 max-w-2xl">
          Masukkan topik atau isu kebijakan — VoxSwarm akan mensimulasikan bagaimana berbagai kelompok masyarakat merespons dan berdebat. Hasilnya berupa analisis sentimen, prediksi skenario, dan rekomendasi strategis.
        </p>
      </section>

      {/* ════════════════ FORM INPUT ════════════════ */}
      <section className="mx-auto max-w-4xl px-4 md:px-6">
        <div className="rounded-2xl border border-white/10 bg-[#132237] p-6 md:p-8 shadow-[0_0_40px_-12px_rgba(59,130,246,0.12)]">
          <h2 className="mb-4 text-xl font-bold text-white" style={{ fontFamily: "var(--font-display)" }}>
            Coba Simulasi Opini Publik
          </h2>

          <div className="mb-4 flex flex-col gap-3 sm:flex-row">
            <input
              ref={inputRef}
              className="flex-1 rounded-xl border border-white/10 bg-[#1A2D4A] px-4 py-3 text-sm text-slate-100 placeholder:text-slate-500 outline-none transition focus:border-blue-400 focus:shadow-[0_0_0_3px_rgba(59,130,246,0.08)]"
              value={topik}
              onChange={e => setTopik(e.target.value.slice(0, 300))}
              onKeyDown={e => e.key === "Enter" && mulaiAnalisis()}
              placeholder='Contoh: "Apakah kenaikan UMP 2025 menguntungkan buruh atau merugikan UMKM?"'
            />
            <button
              onClick={mulaiAnalisis}
              disabled={memuat}
              className="rounded-xl bg-blue-600 px-8 py-3 text-sm font-bold text-white transition hover:bg-blue-500 hover:shadow-[0_0_20px_-5px_rgba(59,130,246,0.4)] disabled:opacity-50 disabled:cursor-not-allowed shrink-0"
            >
              {memuat ? "Memproses…" : "Analisis"}
            </button>
          </div>

          <div className="flex flex-wrap items-center gap-4 text-sm text-slate-400">
            <div className="flex items-center gap-2">
              <span>Kategori:</span>
              <select value={kategori} onChange={e => setKategori(e.target.value)}
                className="rounded-lg border border-white/10 bg-[#1A2D4A] px-3 py-1.5 text-slate-300 outline-none focus:border-blue-400">
                {["Umum","Ekonomi","Politik","Sosial","Hukum","Teknologi"].map(k =>
                  <option key={k} value={k}>{k}</option>
                )}
              </select>
            </div>
            <div className="flex items-center gap-2">
              <span>Putaran:</span>
              <div className="flex gap-1">
                {[1,2,3,4,5].map(n => (
                  <button key={n} onClick={() => setJumlahRonde(n)}
                    className={`h-7 w-7 rounded-lg text-xs font-bold transition ${jumlahRonde === n ? "bg-blue-600 text-white" : "border border-white/10 text-slate-600 hover:border-blue-500 hover:text-white"}`}>
                    {n}
                  </button>
                ))}
              </div>
            </div>
            <div className="flex items-center gap-2">
              <span>Mode:</span>
              <button onClick={() => setTier("free")} title="Lebih cepat, model ringan. Cocok untuk eksplorasi awal."
                className={`rounded-lg px-3 py-1.5 text-xs font-bold transition ${tier === "free" ? "bg-emerald-600 text-white shadow-[0_0_12px_-4px_rgba(16,185,129,0.3)]" : "border border-white/10 text-slate-600 hover:border-emerald-500 hover:text-white"}`}>
                Cepat
              </button>
              <button onClick={() => setTier("normal")} title="Lebih dalam, analisis lebih akurat dan detail."
                className={`rounded-lg px-3 py-1.5 text-xs font-bold transition ${tier === "normal" ? "bg-amber-600 text-white shadow-[0_0_12px_-4px_rgba(245,158,11,0.3)]" : "border border-white/10 text-slate-600 hover:border-amber-500 hover:text-white"}`}>
                Lengkap
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* ════════════════ LOADING ════════════════ */}
      {memuat && (
        <section className="mx-auto mt-4 max-w-4xl px-4 md:px-6">
          <div className="rounded-2xl border border-white/10 bg-[#132237] p-10 text-center animate-pulse-border">
            <div className="mx-auto mb-6 flex w-fit gap-2.5">
              {[0,1,2,3].map(i => (
                <div key={i} className="h-2.5 w-2.5 rounded-full bg-blue-500"
                  style={{ animation: `lompat 1s ease-in-out ${i*0.15}s infinite` }} />
              ))}
            </div>
            <p className="mb-2 text-lg font-bold text-slate-100" style={{ fontFamily: "var(--font-display)" }}>
              Mensimulasikan diskusi…
            </p>
            <p className="mb-6 text-sm text-slate-400">
              {jumlahRonde} putaran · estimasi {jumlahRonde * 10}–{jumlahRonde * 20} detik
            </p>
            <div className="mx-auto max-w-xs space-y-2.5 text-left">
              {[
                "Menyiapkan agen dari berbagai latar belakang",
                "Mensimulasikan diskusi antar kelompok",
                "Menganalisis sentimen dan dinamika opini",
                "Menyusun rekomendasi strategis",
              ].map((step, i) => (
                <div key={i} className="flex items-center gap-3">
                  <div className="h-1.5 w-1.5 rounded-full bg-blue-500/40 shrink-0" />
                  <p className="text-xs text-slate-500">{step}</p>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* ════════════════ KOSONG ════════════════ */}
      {!hasil && !memuat && (
        <section className="mx-auto mt-6 max-w-4xl px-4 md:px-6">
          <div className="rounded-2xl border border-dashed border-white/10 p-16 text-center group hover:border-blue-500/30 transition-all duration-300">
            <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-blue-500/10 border border-blue-500/20 group-hover:bg-blue-500/20 group-hover:border-blue-500/40 transition-all duration-300">
              <svg className="h-7 w-7 text-blue-400 group-hover:scale-110 transition-transform duration-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 20.25c4.97 0 9-3.694 9-8.25s-4.03-8.25-9-8.25S3 7.444 3 12c0 2.104.859 4.023 2.273 5.48.432.447.74 1.04.586 1.641a4.483 4.483 0 01-.923 1.785A5.969 5.969 0 006 21c1.282 0 2.47-.402 3.445-1.087.81.22 1.668.337 2.555.337z" />
              </svg>
            </div>
            <h3 className="mb-2 text-2xl font-bold" style={{ fontFamily: "var(--font-display)" }}>
              Belum Ada Simulasi
            </h3>
            <p className="text-base text-slate-400">
              Ketik topik di atas lalu klik <strong className="text-white">Analisis</strong> untuk memulai.
            </p>
          </div>
        </section>
      )}

      {/* ════════════════ HASIL SIMULASI ════════════════ */}
      {hasil && (
        <div ref={hasilRef} className="mx-auto mt-6 max-w-4xl px-4 pb-8 md:px-6 space-y-4">

          {/* ── C2: ZONA 1 — Kesimpulan utama ── */}
          <KartuKesimpulan
            topik={topik}
            status={hasilAkhir.label === "Cenderung Tidak Setuju" || hasilAkhir.label === "Masyarakat Terpecah" ? "berbahaya" : hasilAkhir.label === "Pendapat Terbagi" ? "terbagi" : "stabil"}
            narasi={ringkasan}
            daftarRonde={daftarRonde}
            rondeIni={rondeTerakhir}
          />

          {/* ── C3: ZONA 2 — Distribusi singkat ── */}
          <KartuDistribusiSingkat dataBar={dataBar} />

          {/* ── C4: ZONA 3 — Suara tiap kelompok ── */}
          <KartuAgenRingkas rondeIni={rondeTerakhir} />

          {/* ── C5: ZONA 4 — Aktor kunci & penggerak ── */}
          {penggerak && (
            <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-5 flex items-start gap-3">
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-amber-500/20 text-base">🎯</span>
              <div>
                <p className="text-xs font-semibold text-amber-400/70 uppercase tracking-wider mb-0.5">Aktor Paling Berpengaruh</p>
                <p className="text-sm font-bold text-amber-200">{penggerak}</p>
              </div>
            </div>
          )}

          {/* ── C6: ZONA 5 — Disclaimer ── */}
          <div className="rounded-xl border border-white/5 bg-[#0D1017] px-4 py-3">
            <p className="text-xs text-slate-600 leading-relaxed">
              ⚠️ VoxSwarm adalah alat eksplorasi dan referensi awal, bukan pengganti survei atau riset empiris.
              Hasil simulasi bergantung pada konfigurasi agen dan topik yang diberikan.
              Gunakan sebagai bahan pertimbangan, bukan keputusan final.
            </p>
          </div>

          {/* ── C7: ZONA 6 — Laci detail collapsed ── */}
          <LaciDetail>

            {/* Warning topik */}
            {warningTopik && (
              <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 flex items-start gap-2">
                <span className="text-sm shrink-0 mt-0.5">⚠️</span>
                <p className="text-xs text-amber-200/80 leading-relaxed">{warningTopik}</p>
              </div>
            )}

            {/* Rekomendasi Strategis */}
            {(rekomendasi || rekomendasiStrategis.length > 0) && (
              <Kartu>
                <JudulSeksi>Rekomendasi Strategis</JudulSeksi>
                {rekomendasiStrategis.length > 0 ? (
                  <div className="space-y-3">
                    {rekomendasiStrategis.map((item, i) => (
                      <div key={i} className="flex items-start gap-3">
                        <div className="h-6 w-6 rounded-full bg-amber-500/20 border border-amber-500/30 flex items-center justify-center text-xs font-bold text-amber-300 shrink-0 mt-0.5">
                          {i + 1}
                        </div>
                        <p className="text-sm leading-relaxed text-slate-200">{item}</p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm leading-relaxed text-slate-200">{rekomendasi}</p>
                )}
              </Kartu>
            )}

            {/* Risiko Utama */}
            {risikoUtama && (
              <Kartu>
                <JudulSeksi>Risiko Utama</JudulSeksi>
                <div className="flex items-start gap-2">
                  <span className="text-lg shrink-0">⚠️</span>
                  <p className="text-sm leading-relaxed text-slate-300">{risikoUtama}</p>
                </div>
              </Kartu>
            )}

            {/* Navigasi putaran */}
            {daftarRonde.length > 1 && (
              <div className="flex flex-wrap items-center gap-2 print:hidden">
                <span className="text-xs text-slate-500">Lihat putaran:</span>
                {daftarRonde.map((_, i) => (
                  <button key={i} onClick={() => setRondeAktif(i)}
                    className={`rounded-lg px-4 py-1.5 text-xs font-medium transition ${
                      rondeAktif === i
                        ? "bg-indigo-600 text-white"
                        : "border border-white/10 text-slate-500 hover:border-indigo-400 hover:text-white"
                    }`}
                  >
                    Babak {i + 1}
                  </button>
                ))}
              </div>
            )}

            {/* Chart grid */}
            <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
              {/* BarChart */}
              {dataBar.length > 0 && (
                <Kartu>
                  <JudulSeksi>Peta Dukungan — Babak {rondeAktif + 1}</JudulSeksi>
                  <p className="mb-4 text-xs text-slate-600">Skor 0 = sangat menolak · 100 = sangat mendukung</p>
                  <div style={{ height: 220, width: "100%" }}>
                    <ResponsiveContainer width="100%" height={220} minWidth={0}>
                      <BarChart data={dataBar} margin={{ bottom: 0 }}>
                        <XAxis dataKey="namaLabel" interval={0} tick={{ fontSize: 9, fill: "#64748b" }} axisLine={false} tickLine={false} />
                        <YAxis domain={[0,100]} hide />
                        <Tooltip
                          cursor={{ fill: "rgba(99,102,241,0.06)" }}
                          contentStyle={{ background: "#0D1017", border: "0.5px solid rgba(255,255,255,0.1)", borderRadius: 10, fontSize: 11, color: "#e2e8f0" }}
                          formatter={(v, _, p) => [`${v}/100 — ${LABEL_SENTIMEN[p.payload.label] ?? "-"}`, "Skor dukungan"]}
                        />
                        <Bar dataKey="skor" radius={[5,5,0,0]} barSize={32}>
                          {dataBar.map((e, i) => <Cell key={i} fill={e.warna} />)}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                  <div className="mt-3 flex gap-4">
                    {Object.entries(WARNA_SENTIMEN).map(([k, w]) => (
                      <span key={k} className="flex items-center gap-1.5 text-[11px] text-slate-600">
                        <span className="inline-block h-2 w-2 rounded-full" style={{ backgroundColor: w }} />
                        {LABEL_SENTIMEN[k]}
                      </span>
                    ))}
                  </div>
                </Kartu>
              )}

              {/* LineChart atau peserta */}
              {dataTren.length > 1 ? (
                <Kartu>
                  <JudulSeksi>Perubahan Sikap Tiap Babak</JudulSeksi>
                  <div className="mb-2 flex items-center justify-between text-[10px] text-slate-700">
                    <span>← Menolak</span><span>Netral</span><span>Mendukung →</span>
                  </div>
                  <div style={{ height: 210, width: "100%" }}>
                    <ResponsiveContainer width="100%" height={210} minWidth={0}>
                      <LineChart data={dataTren} margin={{ left: 8, right: 8, top: 4, bottom: 4 }}>
                        <CartesianGrid vertical={false} stroke="rgba(255,255,255,0.04)" />
                        <XAxis dataKey="label" tick={{ fontSize: 10, fill: "#475569" }} axisLine={false} tickLine={false} />
                        <YAxis domain={[-1,1]} ticks={[-1,-0.5,0,0.5,1]} tick={{ fontSize: 9, fill: "#334155" }} axisLine={false} tickLine={false}
                          tickFormatter={v => v === 0 ? "0" : v > 0 ? `+${v}` : `${v}`} width={28} />
                        <ReferenceLine y={0} stroke="rgba(255,255,255,0.08)" strokeDasharray="4 3" />
                        <Tooltip
                          contentStyle={{ background: "#0D1017", border: "0.5px solid rgba(255,255,255,0.12)", borderRadius: 10, fontSize: 11, color: "#e2e8f0" }}
                          formatter={(v, nama) => [
                            `${v > 0 ? `+${v}` : v}  ${v > 0.2 ? "Mendukung" : v < -0.2 ? "Menolak" : "Netral"}`,
                            nama
                          ]}
                        />
                        <Legend wrapperStyle={{ fontSize: 10, paddingTop: 8 }}
                          formatter={nama => <span style={{ color: warnaAgen[nama] ?? "#94a3b8" }}>{nama}</span>} />
                        {Object.keys(sentimenAgr).map(nama => (
                          <Line key={nama} type="monotone" dataKey={nama} stroke={warnaAgen[nama]}
                            strokeWidth={2} dot={{ r: 3.5, strokeWidth: 0, fill: warnaAgen[nama] }}
                            activeDot={{ r: 5, strokeWidth: 2, stroke: "#0D1017" }} />
                        ))}
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </Kartu>
              ) : (
                <Kartu>
                  <JudulSeksi>Peserta Simulasi</JudulSeksi>
                  <div className="space-y-2">
                    {(rondeTerakhir?.agen ?? []).map((a, i) => (
                      <div key={i} className="agen-card flex items-start gap-3 px-3 py-2.5">
                        <div className="mt-1 h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: WARNA_SENTIMEN[a.sentimen?.label] ?? "#64748b" }} />
                        <div>
                          <div className="mb-1 flex items-center gap-2">
                            <span className="text-xs font-semibold text-slate-200">{a.nama}</span>
                            <BadgeSentimen label={a.sentimen?.label} />
                          </div>
                          <p className="text-xs leading-relaxed text-slate-400">"{a.pendapat}"</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </Kartu>
              )}
            </div>

            {/* Prediksi */}
            {Object.keys(prediksi).length > 0 && (
              <Kartu>
                <JudulSeksi>Kemungkinan Hasil</JudulSeksi>
                <div className="space-y-3">
                  {Object.entries(prediksi).map(([k, v]) => {
                    const w = {
                      "Semua Setuju": "#22c55e",
                      "Konsensus": "#22c55e",
                      "Masyarakat Terpecah": "#ef4444",
                      "Polarisasi": "#ef4444",
                      "Tidak Ada Perubahan": "#64748b",
                      "Status Quo": "#64748b",
                    }[k] ?? "#3B82F6";
                    return (
                      <div key={k} className="flex items-center gap-3">
                        <span className="w-36 shrink-0 text-sm text-slate-300">{k}</span>
                        <div className="flex-1 h-3 rounded-full bg-white/5 overflow-hidden">
                          <div className="h-full rounded-full transition-all" style={{ width: `${v}%`, backgroundColor: w }} />
                        </div>
                        <span className="w-9 shrink-0 text-right text-sm font-bold" style={{ color: w }}>{v}%</span>
                      </div>
                    );
                  })}
                </div>
                <p className="mt-4 text-xs text-slate-500 italic">* Hasil ini bersifat eksploratif, bukan prediksi faktual.</p>
              </Kartu>
            )}

            {/* Ringkasan Analisis */}
            {ringkasan && (
              <Kartu>
                <JudulSeksi>Ringkasan Analisis</JudulSeksi>
                <p className="text-sm leading-7 text-slate-300">{ringkasan || "—"}</p>
              </Kartu>
            )}

            {/* Log diskusi lengkap — ronde aktif */}
            {daftarRonde.length > 0 && daftarRonde[rondeAktif] && (
              <Kartu>
                <JudulSeksi>Jalannya Diskusi — Babak {rondeAktif + 1}</JudulSeksi>
                <div className="max-h-96 space-y-5 overflow-y-auto pr-2">
                  {(daftarRonde[rondeAktif]?.agen ?? []).map((a, i) => {
                    const w = WARNA_SENTIMEN[a.sentimen?.label] ?? "#6366f1";
                    return (
                      <div key={i} className="flex gap-4">
                        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-[10px] font-bold"
                          style={{ backgroundColor: w + "1A", border: `1px solid ${w}55`, color: w }}>
                          {a.nama.slice(0, 2).toUpperCase()}
                        </div>
                        <div className="flex-1">
                          <div className="mb-1.5 flex flex-wrap items-center gap-2">
                            <span className="text-sm font-semibold text-slate-200">{a.nama}</span>
                            <BadgeSentimen label={a.sentimen?.label} />
                          </div>
                          <p className="text-sm leading-7 text-slate-300">{a.pendapat}</p>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </Kartu>
            )}

            {/* Aktor Kunci */}
            {aktorKunci.length > 0 && (
              <Kartu>
                <JudulSeksi>Aktor Paling Berpengaruh</JudulSeksi>
                <div className="grid gap-3 sm:grid-cols-2">
                  {aktorKunci.map((a, i) => {
                    const w = WARNA_AGEN[i % WARNA_AGEN.length];
                    const lb = a.sikap_label ?? "Netral";
                    const lbWarna = lb === "Mendukung" ? "#22c55e" : lb === "Menolak" ? "#ef4444" : "#64748b";
                    return (
                      <div key={i} className="rounded-xl border border-white/10 bg-white/[0.03] p-4 hover:border-white/20 transition-all duration-200">
                        <div className="flex items-center gap-2 mb-1.5">
                          <div className="h-8 w-8 rounded-full flex items-center justify-center text-xs font-black shrink-0"
                            style={{ backgroundColor: w + "20", border: `1.5px solid ${w}`, color: w }}>
                            {a.nama.slice(0,2).toUpperCase()}
                          </div>
                          <span className="text-sm font-bold text-white flex-1 truncate">{a.nama}</span>
                          <span className="rounded-full px-3 py-0.5 text-xs font-bold border"
                            style={{ color: lbWarna, borderColor: lbWarna + "40", backgroundColor: lbWarna + "15" }}>
                            {lb}
                          </span>
                        </div>
                        <p className="text-sm text-slate-300 leading-relaxed">{a.alasan}</p>
                      </div>
                    );
                  })}
                </div>
              </Kartu>
            )}

            {/* Kelompok Kritis */}
            {kelompokKritis.length > 0 && (
              <Kartu>
                <JudulSeksi>Kelompok yang Perlu Dinetralisir</JudulSeksi>
                <div className="space-y-3">
                  {kelompokKritis.map((k, i) => (
                    <div key={i} className="rounded-xl border border-red-500/15 bg-red-500/5 p-4">
                      <div className="flex items-center gap-2 mb-2">
                        <div className="h-7 w-7 rounded-full bg-red-500/20 border border-red-500/30 flex items-center justify-center text-xs font-black text-red-300 shrink-0">
                          {k.nama.slice(0,2).toUpperCase()}
                        </div>
                        <span className="text-sm font-bold text-white">{k.nama}</span>
                      </div>
                      <p className="text-xs text-slate-400 mb-1"><span className="text-red-300 font-semibold">Kenapa kritis:</span> {k.alasan}</p>
                      <p className="text-xs text-slate-300"><span className="text-amber-300 font-semibold">Cara pendekatan:</span> {k.cara_pendekatan}</p>
                    </div>
                  ))}
                </div>
              </Kartu>
            )}

            {/* Ekspor */}
            <div className="flex flex-wrap gap-3 pt-2">
              <button onClick={handleSimpanPDF}
                className="rounded-xl bg-blue-600/20 border border-blue-500/30 px-5 py-2.5 text-sm font-bold text-blue-300 hover:bg-blue-600/40 hover:text-white transition">
                🖨️ Simpan PDF
              </button>
              <button onClick={handleSimpanCSV}
                className="rounded-xl border border-white/10 px-5 py-2.5 text-sm font-semibold text-slate-300 hover:border-blue-500 hover:text-white transition">
                📊 Unduh CSV
              </button>
              <button onClick={handleSimpanWord}
                className="rounded-xl border border-white/10 px-5 py-2.5 text-sm font-semibold text-slate-300 hover:border-blue-500 hover:text-white transition">
                📄 Unduh Word
              </button>
            </div>

          </LaciDetail>

          {/* ── C8: Bar metadata + ekspor ── */}
          <div className="flex flex-wrap items-center justify-between gap-3 print:hidden">
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-md border border-white/10 px-3 py-1 text-[11px] text-slate-500">{daftarRonde.length} putaran · {agenAkhir.length} peserta</span>
              <span className="rounded-md border border-white/10 px-3 py-1 text-[11px] text-slate-500">{hasilAkhir.label}</span>
            </div>
            <div className="relative">
              <button
                onClick={() => setBukaEkspor(v => !v)}
                className="flex items-center gap-2 rounded-xl border border-white/10 bg-[#0D1017] px-4 py-2 text-xs font-medium text-slate-400 hover:border-white/20 hover:text-white transition"
              >
                📥 Unduh Laporan ▾
              </button>
              {bukaEkspor && (
                <div className="absolute right-0 top-11 z-50 w-52 rounded-2xl border border-white/10 bg-[#0D1017] p-2 shadow-2xl">
                  {[
                    { ikon: "🖨️", label: "Cetak / Simpan PDF",  aksi: () => { handleSimpanPDF(); setBukaEkspor(false); } },
                    { ikon: "📊", label: "Unduh Excel / CSV",    aksi: () => { handleSimpanCSV(); setBukaEkspor(false); } },
                    { ikon: "📄", label: "Unduh Word (.docx)",   aksi: () => { handleSimpanWord(); setBukaEkspor(false); } },
                  ].map(({ ikon, label, aksi }) => (
                    <button key={label} onClick={aksi}
                      className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-xs text-slate-400 hover:bg-white/8 hover:text-slate-200 transition">
                      <span>{ikon}</span> {label}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* ── C9: Reset ── */}
          <div className="pb-6 text-center print:hidden">
            <button
              onClick={() => { setHasil(null); setTopik(""); setTimeout(() => { inputRef.current?.focus(); window.scrollTo({ top: 0, behavior: "smooth" }); }, 100); }}
              className="text-xs text-slate-700 underline underline-offset-4 hover:text-slate-400 transition"
            >
              Mulai analisis baru
            </button>
          </div>

        </div>
      )}

      {/* ════════════════ ANIMASI ════════════════ */}
      <style jsx global>{`
        @keyframes lompat {
          0%, 80%, 100% { transform: translateY(0); opacity: 0.3; }
          40%            { transform: translateY(-9px); opacity: 1; }
        }
        .line-clamp-3 {
          display: -webkit-box;
          -webkit-line-clamp: 3;
          -webkit-box-orient: vertical;
          overflow: hidden;
        }
        /* Teks utama konten lebih mudah dibaca */
        .text-readable {
          font-size: 14px;
          line-height: 1.75;
          color: #cbd5e1;
        }
        /* Teks sekunder yang tidak bersaing dengan konten utama */
        .text-hint {
          font-size: 12px;
          color: #475569;
          line-height: 1.5;
        }
        /* Kartu agen — hover state konsisten */
        .agen-card {
          border-radius: 12px;
          border: 0.5px solid rgba(255,255,255,0.07);
          background: rgba(255,255,255,0.025);
          transition: border-color 0.15s, background 0.15s;
        }
        .agen-card:hover {
          border-color: rgba(255,255,255,0.12);
          background: rgba(255,255,255,0.04);
        }
        /* Pulse border buat loading state */
        .animate-pulse-border { animation: pulseBorder 2s ease-in-out infinite; }
        @keyframes pulseBorder {
          0%, 100% { border-color: rgba(255,255,255,0.08); }
          50%      { border-color: rgba(59,130,246,0.25); }
        }
        /* Scrollbar kustom — minimalis, gelap, ga ganggu */
        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.08); border-radius: 3px; }
        ::-webkit-scrollbar-thumb:hover { background: rgba(255,255,255,0.15); }
        @media print {
          @page { size: A4 portrait; margin: 15mm 18mm; }
          * { -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }
          body, main { background: #fff !important; color: #1e293b !important; }
          .print\\:hidden { display: none !important; }
          * { color: #1e293b !important; }
        }
      `}</style>
    </main>
  );
}
