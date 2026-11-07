"use client";

import { eksporPDF } from "../utils/eksporpdf";
import { eksporCSV, eksporWord } from "../utils/eksporlainnya";
import { useState, useRef } from "react";
import WordCloud from "../components/WordCloud";
import InfoTip from "../components/InfoTip";
import { GlossaryButton } from "../components/InfoTip";
import Link from "next/link";

// ── Sentiment helpers ──
const SENTIMENT = {
  positif: { color: "#1b8a4a", label: "Mendukung", bg: "bg-[#1b8a4a]/10 text-[#1b8a4a] border-[#1b8a4a]/30" },
  netral:  { color: "#6c6a64", label: "Netral",     bg: "bg-[#6c6a64]/10 text-[#6c6a64] border-[#6c6a64]/30" },
  negatif: { color: "#b83a3a", label: "Menolak",    bg: "bg-[#b83a3a]/10 text-[#b83a3a] border-[#b83a3a]/30" },
};

const BADGE_SKORE = [
  { max: 30, label: "Sangat Menolak", color: "#b83a3a" },
  { max: 49, label: "Cenderung Menolak", color: "#b8860b" },
  { max: 50, label: "Netral", color: "#6c6a64" },
  { max: 70, label: "Cenderung Mendukung", color: "#1b8a7a" },
  { max: 100, label: "Sangat Mendukung", color: "#1b8a4a" },
];
const labelSkor = (s) => BADGE_SKORE.find(l => s <= l.max) ?? BADGE_SKORE[BADGE_SKORE.length - 1];

const INSIGHT_LABEL = {
  "Semua Setuju": "Konsensus penuh",
  "Konsensus": "Konsensus",
  "Masyarakat Terpecah": "Terpecah",
  "Polarisasi": "Polarisasi",
  "Tidak Ada Perubahan": "Tetap",
  "Status Quo": "Status quo",
};

const DESKRIPSI_SKENARIO = {
  "Konsensus": "Kelompok cenderung sepakat, ruang debat menyempit.",
  "Polarisasi": "Dua kubu menguat dan saling menjauh, titik temu sulit.",
  "Status Quo": "Tidak ada perubahan arah berarti, posisi awal bertahan.",
  "Semua Setuju": "Hampir semua persona sepakat tanpa sisa perbedaan.",
  "Masyarakat Terpecah": "Suara terbelah tanpa kubu yang dominan.",
  "Tidak Ada Perubahan": "Sikap akhir mirip dengan sikap awal.",
};

const AGENT_COLORS = ["#cc785c", "#1b8a4a", "#e8a55a", "#b83a3a", "#1b8a7a", "#6c6a64", "#252523"];

function bacaData(payload, pesan = "Data tidak ditemukan.") {
  if (!payload || typeof payload !== "object" || !payload.data)
    throw new Error(payload?.detail || payload?.message || pesan);
  const hasil = payload.data;
  const konteks = payload.konteks_real ?? {};
  if (konteks.data_transparency) hasil.data_transparency = konteks.data_transparency;
  // Angka sumber hanya ada di konteks_real, bukan di dalam data hasil.
  hasil.ringkas_sumber = {
    total: konteks.total_sumber ?? hasil.data_transparency?.rss_articles_passed_threshold ?? 0,
    ditemukan: hasil.data_transparency?.rss_articles_found ?? null,
    lolos: hasil.data_transparency?.rss_articles_passed_threshold ?? null,
    polling: hasil.data_transparency?.polling_reference_matched ?? false,
    status: hasil.data_transparency?.briefing_status ?? "",
    catatan: hasil.data_transparency?.note ?? "",
    reddit: Array.isArray(konteks.reddit) ? konteks.reddit.length : 0,
    // Status jalur sumber; null berarti cache lama tanpa field ini.
    status_sumber: konteks.sumber_status ?? null,
    pesan_sumber: konteks.sumber_pesan ?? "",
    peringatan: Array.isArray(konteks.sumber_peringatan) ? konteks.sumber_peringatan : [],
    sumber_berita: (konteks.berita ?? []).map(b => ({
      judul: b?.judul ?? "",
      media: mediaSumber(b),
      tanggal: tanggalRingkas(b?.tanggal_iso),
      link: b?.link ?? "",
    })).filter(b => b.judul),
  };
  return hasil;
}

function mediaSumber(artikel) {
  if (artikel?.sumber && artikel.sumber !== "google_news_search") return artikel.sumber;
  if (!artikel?.source_url) return "Sumber tidak diketahui";
  try {
    return new URL(artikel.source_url).hostname.replace(/^www\./, "");
  } catch {
    return "Sumber tidak diketahui";
  }
}

// "2026-11-06T14:58:29+00:00" -> "6 Nov 2026"
function tanggalRingkas(iso) {
  const teks = String(iso ?? "");
  const cocok = teks.match(/^(\d{4})-(\d{2})-(\d{2})/);
  const bulan = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];
  if (cocok) return `${Number(cocok[3])} ${bulan[Number(cocok[2]) - 1]} ${cocok[1]}`;
  const t = new Date(teks);
  if (Number.isNaN(t.getTime())) return "";
  return `${t.getUTCDate()} ${bulan[t.getUTCMonth()]} ${t.getUTCFullYear()}`;
}

// "finance.detik.com: TimeoutError" -> "finance.detik.com (timeout)"
function ringkasPeringatan(teks) {
  const [host, ...sisa] = String(teks).split(":");
  const alasan = sisa.join(":").trim();
  const label = /timeout/i.test(alasan) ? "timeout" : (alasan || "gagal dibuka");
  return `${host.trim()} (${label})`;
}

// ── Badge ──
const Badge = ({ label, variant = "default" }) => {
  const variants = {
    default: "bg-[#efe9de] text-[#252523] border-[#e6dfd8]",
    positif: "bg-[#1b8a4a]/10 text-[#1b8a4a] border-[#1b8a4a]/30",
    netral: "bg-[#6c6a64]/10 text-[#6c6a64] border-[#6c6a64]/30",
    negatif: "bg-[#b83a3a]/10 text-[#b83a3a] border-[#b83a3a]/30",
    warning: "bg-[#b8860b]/10 text-[#b8860b] border-[#b8860b]/30",
    outline: "bg-transparent text-[#252523] border-[#e6dfd8]",
  };
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11px] font-medium border ${variants[variant] || variants.default}`}>
      {label}
    </span>
  );
};

const getPendekatan = (nama) => {
  const n = nama.toLowerCase();
  if (n.includes("jurnalis") || n.includes("media") || n.includes("wartawan"))
    return "Adakan konferensi pers, sediakan data yang dapat diverifikasi, berikan akses ke narasumber terpercaya.";
  if (n.includes("oposisi") || n.includes("kritis") || n.includes("lawan"))
    return "Undang dialog tertutup, akui kekurangan kebijakan, tawarkan evaluasi berkala yang melibatkan mereka.";
  if (n.includes("akademisi") || n.includes("dosen") || n.includes("peneliti") || n.includes("ilmuwan"))
    return "Libatkan dalam penelitian bersama, publikasikan data pendukung, minta masukan untuk perbaikan.";
  if (n.includes("mahasiswa") || n.includes("pelajar") || n.includes("aktivis") || n.includes("ormas"))
    return "Gunakan media sosial dan forum kampus, sampaikan dampak langsung kebijakan ke kehidupan sehari-hari.";
  if (n.includes("pengusaha") || n.includes("umkm") || n.includes("bisnis") || n.includes("wirausaha"))
    return "Fokus pada dampak finansial nyata, tawarkan insentif atau kompensasi, libatkan asosiasi bisnis.";
  if (n.includes("pemerintah") || n.includes("birokrat") || n.includes("menteri") || n.includes("pejabat"))
    return "Koordinasi antar instansi, pastikan narasi yang disampaikan konsisten.";
  if (n.includes("pekerja") || n.includes("kantoran") || n.includes("karyawan") || n.includes("buruh"))
    return "Sampaikan lewat serikat pekerja, fokus pada dampak terhadap penghasilan dan kesejahteraan.";
  return "Libatkan melalui saluran yang biasa mereka gunakan, sampaikan manfaat nyata.";
};

const getAlasanKritis = (nama, adalahPendukung = false) => {
  if (adalahPendukung) return "Dukungan kelompok ini perlu dijaga — bisa berubah jika tidak ada komunikasi aktif.";
  const n = nama.toLowerCase();
  if (n.includes("jurnalis") || n.includes("media") || n.includes("wartawan"))
    return "Menolak karena kurangnya data dan akses informasi yang terbatas dari pemerintah.";
  if (n.includes("oposisi") || n.includes("kritis") || n.includes("lawan"))
    return "Menolak karena keyakinan — menganggap kebijakan ini tidak berpihak pada rakyat.";
  if (n.includes("mahasiswa") || n.includes("pelajar") || n.includes("aktivis") || n.includes("ormas"))
    return "Menolak karena dampak langsung yang dirasakan tidak sesuai janji.";
  if (n.includes("pengusaha") || n.includes("umkm") || n.includes("bisnis") || n.includes("wirausaha"))
    return "Menolak karena biaya operasional naik tanpa kompensasi yang sepadan.";
  if (n.includes("akademisi") || n.includes("dosen") || n.includes("peneliti") || n.includes("ilmuwan"))
    return "Menolak berdasarkan data — penelitian menunjukkan kebijakan ini kurang efektif.";
  if (n.includes("pekerja") || n.includes("kantoran") || n.includes("karyawan") || n.includes("buruh"))
    return "Menolak karena kebijakan ini dianggap menambah beban tanpa meningkatkan kesejahteraan.";
  if (n.includes("pemerintah") || n.includes("birokrat") || n.includes("menteri") || n.includes("pejabat"))
    return "Bertahan — mengakui kekurangan namun menunjukkan capaian yang sudah ada.";
  if (n.includes("nelayan") || n.includes("petani") || n.includes("kelompok lapangan"))
    return "Menolak karena pelaksanaan di lapangan tidak sesuai kondisi nyata.";
  return "Menolak berdasarkan pengalaman langsung dan kekhawatiran yang belum terjawab.";
};

const truncateAtWord = (teks, maxChars) => {
  if (!teks || teks.length <= maxChars) return teks;
  const truncated = teks.slice(0, maxChars);
  const lastSpace = truncated.lastIndexOf(" ");
  return (lastSpace > maxChars * 0.5 ? truncated.slice(0, lastSpace) : truncated) + "…";
};

const beresinTeksAkhir = (teks) => {
  if (!teks) return teks;
  return teks
    .replace(/Skor\s*komposit\s*([\d.]+)/gi, (_, s) => {
      const n = parseFloat(s);
      if (n >= 0.8) return `Pengaruh Sangat Tinggi (${n})`;
      if (n >= 0.6) return `Pengaruh Tinggi (${n})`;
      if (n >= 0.4) return `Pengaruh Sedang (${n})`;
      return `Pengaruh Rendah (${n})`;
    })
    .replace(/Sentimen\s*akhir\s*negatif\s*\(([^)]+)\)/gi, "Kelompok ini menolak program tersebut")
    .replace(/Sentimen\s*akhir\s*positif\s*\(([^)]+)\)/gi, "Kelompok ini mendukung program tersebut")
    .replace(/Sentimen\s*akhir\s*netral\s*\(([^)]+)\)/gi, "Kelompok ini bersikap netral");
};

// Kalimat pertama cara_pendekatan cuma mengulang nama dan angka pengaruh.
const aksiPendekatan = (teks, nama) => {
  const isi = (teks ?? "").trim();
  if (!isi || !nama || !isi.startsWith(nama)) return isi;
  const titik = isi.indexOf(". ");
  return titik > 0 ? isi.slice(titik + 2) : isi;
};

const persen = (n) => (typeof n === "number" ? `${Math.round(n * 100)}%` : null);

const sikapDariAlasan = (teks) => {
  const cocok = String(teks ?? "").match(/-?\d+(?:[.,]\d+)?/);
  if (!cocok) return null;
  const n = parseFloat(cocok[0].replace(",", "."));
  if (Number.isNaN(n)) return null;
  return n >= 0.25 ? "positif" : n <= -0.25 ? "negatif" : "netral";
};

// ── Section labels ──
const SECTION_LABEL = {
  insight: "Kesimpulan",
  risiko: "Risiko Kunci",
  rekomendasi: "Rekomendasi",
  aktorKunci: "Aktor Kunci",
  kelompokKritis: "Kelompok Kritis",
  probabilitas: "Pelaksanaan",
  meteranSikap: "Perubahan Sikap",
  transkrip: "Catatan Diskusi",
  wordcloud: "Kata Kunci",
};

// ── Loading Overlay ──
const LoadingOverlay = ({ tahap, onCancel }) => {
  const steps = [
    "Menghubungkan ke server...",
    "Mengirim topik ke simulasi...",
    "Memproses respons server...",
    "Menganalisis hasil simulasi..."
  ];
  const getStepColor = (step, i) => {
    if (tahap === step) return "bg-[#cc785c] animate-pulse";
    if (tahap === "" || (i > 0 && tahap !== step && !tahap.startsWith(step.split(" ")[0]))) return "bg-[#e6dfd8]";
    return "bg-[#1b8a4a]";
  };
  const getStepTextColor = (step) => {
    if (tahap === step) return "font-medium text-[#cc785c]";
    return "text-[#6c6a64]";
  };
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-white/90 backdrop-blur-sm">
      <div className="rounded-xl border border-[#e6dfd8] bg-white p-8 max-w-md w-full mx-4 shadow-xl">
        <div className="flex items-center gap-3 mb-6">
          <div className="h-10 w-10 rounded-full border-3 border-[#e6dfd8] border-t-[#cc785c] animate-spin" />
          <div>
            <p className="text-lg font-semibold text-[#141413]">Sedang Memproses</p>
            <p className="text-sm text-[#6c6a64]">Mohon tunggu, simulasi berjalan...</p>
          </div>
        </div>
        <div className="space-y-3">
          {steps.map((step, i) => (
            <div key={step} className="flex items-center gap-3 text-sm">
              <div className={`h-2 w-2 rounded-full transition-colors ${
                tahap === step ? "bg-[#cc785c] animate-pulse" :
                tahap === "" || (i > 0 && tahap !== step && !tahap.startsWith(step.split(" ")[0])) ? "bg-[#e6dfd8]" : "bg-[#1b8a4a]"
              }`} />
              <span className={`text-[#3d3d3a] ${tahap === step ? "font-medium text-[#cc785c]" : "text-[#6c6a64]"}`}>
                {step}
              </span>
            </div>
          ))}
        </div>
        {onCancel && (
          <button onClick={onCancel} className="mt-6 w-full rounded-md border border-[#e6dfd8] bg-white px-4 py-2 text-sm font-medium text-[#6c6a64] hover:bg-[#efe9de] transition">
            Batalkan
          </button>
        )}
      </div>
    </div>
  );
};

// ── Helpers ──
const BadgeSentimen = ({ label }) => {
  const s = SENTIMENT[label] ?? SENTIMENT.netral;
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11px] font-medium ${s.bg}`}>
      <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: s.color }} />
      {s.label}
    </span>
  );
};

const HeaderRonde = ({ ronde, total }) => (
  <div className="flex items-center gap-3 py-3">
    <div className="h-px flex-1 bg-[#e6dfd8]" />
    <span className="text-[11px] font-medium uppercase tracking-[1.2px] text-[#6c6a64]">
      Babak {ronde} dari {total}
    </span>
    <div className="h-px flex-1 bg-[#e6dfd8]" />
  </div>
);

// ── Insight Hero ──
const InsightHero = ({ prediksi, statusSimulasi, topik }) => {
  const sorted = Object.entries(prediksi ?? {}).sort((a, b) => b[1] - a[1]);
  if (!sorted.length) return null;
  const [skenario, prob] = sorted[0];
  const label = INSIGHT_LABEL[skenario] ?? skenario;
  const listOthers = sorted.slice(1).map(([s, p]) => `${s} (${p}%)`);
  const others = listOthers.length > 1
    ? listOthers.slice(0, -1).join(", ") + " dan " + listOthers[listOthers.length - 1]
    : listOthers[0] ?? "";
  const kalimat = others
    ? `Skenario "${label}" paling mungkin (${prob}%), mengungguli ${others}.`
    : `Skenario "${label}" menjadi satu-satunya kemungkinan (${prob}%).`;
  return (
    <div className="rounded-lg border border-[#cc785c]/20 bg-[#cc785c]/5 px-6 py-5">
      <p className="text-[11px] font-medium uppercase tracking-[1.5px] text-[#6c6a64] mb-2">Kesimpulan</p>
      <p className="text-lg leading-relaxed text-[#141413]" style={{ fontFamily: "var(--font-heading, sans-serif)" }}>
        &ldquo;{kalimat}&rdquo;
      </p>
    </div>
  );
};

const TranskripRisalah = ({ daftarRonde, rondeAktif, setRondeAktif }) => {
  const [risalahTerbuka, setRisalahTerbuka] = useState(false);
  if (!daftarRonde?.length) return null;
  const agenPertama = daftarRonde[0]?.agen?.[0];
  const previewTeks = truncateAtWord(agenPertama?.pendapat, 200) ?? "";
  return (
    <section>
      <div className="flex items-center justify-between mb-6 flex-wrap gap-2">
        <h2 className="display-sm" style={{ fontWeight: 400 }}>Catatan Diskusi</h2>
        {daftarRonde.length > 1 && (
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] text-[#6c6a64]">Babak:</span>
            {daftarRonde.map((_, i) => (
              <button key={`round-${i}`} onClick={() => setRondeAktif(i)}
                className={`h-7 min-w-[32px] rounded-md px-2 text-[11px] font-medium transition ${
                  rondeAktif === i ? "bg-[#cc785c] text-white" : "bg-[#efe9de] text-[#6c6a64] hover:bg-[#e8e0d2]"
                }`}>
                {i + 1}
              </button>
            ))}
          </div>
        )}
      </div>
      {!risalahTerbuka ? (
        <div className="rounded-lg border border-[#e6dfd8] bg-white p-5">
          <p className="text-sm leading-relaxed text-[#6c6a64] italic line-clamp-2">&ldquo;{previewTeks}&rdquo;</p>
          <button onClick={() => setRisalahTerbuka(true)}
            className="mt-3 text-sm font-medium text-[#cc785c] hover:text-[#a9583e] transition flex items-center gap-1">
            Buka Catatan Diskusi
          </button>
        </div>
      ) : (
        <div className="transition-all duration-300">
          {daftarRonde.map((ronde, rIdx) => {
            if (rIdx !== rondeAktif) return null;
            return (
              <div key={rIdx} className="rounded-lg border border-[#e6dfd8] bg-white overflow-hidden">
                <HeaderRonde ronde={rIdx + 1} total={daftarRonde.length} />
                <div className="space-y-0 p-4">
                  {(ronde.agen ?? []).map((a, aIdx) => {
                    const s = SENTIMENT[a.sentimen?.label] ?? SENTIMENT.netral;
                    return (
                      <div key={aIdx} className="py-3 border-t border-[#f0ebe3] first:border-0">
                        <div className="flex items-start gap-4">
                          <div className="flex items-center gap-2.5 min-w-0 shrink-0">
                            <div className="h-8 w-8 shrink-0 rounded-full flex items-center justify-center text-[10px] font-bold"
                              style={{ backgroundColor: s.color + "18", border: `1px solid ${s.color}44`, color: s.color }}>
                              {a.nama.slice(0, 2).toUpperCase()}
                            </div>
                          </div>
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                              <span className="text-sm font-semibold text-[#141413]">{a.nama}</span>
                              <BadgeSentimen label={a.sentimen?.label} />
                            </div>
                            <p className="text-sm leading-relaxed text-[#3d3d3a]" style={{ letterSpacing: "0.01em" }}>
                              &ldquo;{a.pendapat}&rdquo;
                            </p>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
                <button onClick={() => setRisalahTerbuka(false)}
                  className="mx-4 mb-4 text-sm font-medium text-[#cc785c] hover:text-[#a9583e] transition flex items-center gap-1">
                  Tutup Catatan
                </button>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
};

// ── Perubahan Sikap ──
const namaSikap = { positif: "mendukung", netral: "netral", negatif: "menolak" };

const sikapDariSkor = (s) => (s >= 0.25 ? "positif" : s <= -0.25 ? "negatif" : "netral");

// Skor -1 (menolak) sampai +1 (mendukung) dipetakan ke posisi 0-100%.
const posisiSkor = (s) => ((Math.max(-1, Math.min(1, s ?? 0)) + 1) / 2) * 100;

const MeteranSikap = ({ sentimenAgr, daftarRonde }) => {
  const daftar = Object.entries(sentimenAgr ?? {});
  const totalRonde = daftarRonde?.length ?? 0;
  if (!daftar.length || totalRonde < 1) return null;

  const baris = daftar.map(([nama, deret]) => {
    const nilai = (deret ?? []).map((s) => Number(s) || 0);
    const awal = nilai[0] ?? 0;
    const akhir = nilai.length ? nilai[nilai.length - 1] : 0;
    const labelAwal = sikapDariSkor(awal);
    const labelAkhir = sikapDariSkor(akhir);
    const gerak = totalRonde === 1
      ? namaSikap[labelAkhir]
      : labelAwal === labelAkhir
        ? `tetap ${namaSikap[labelAkhir]}`
        : `${namaSikap[labelAwal]} → ${namaSikap[labelAkhir]}`;
    return { nama, awal, akhir, labelAkhir, gerak };
  });

  const jumlah = { positif: 0, netral: 0, negatif: 0 };
  baris.forEach((b) => { jumlah[b.labelAkhir] += 1; });

  return (
    <section className="py-6">
      <div className="flex items-end justify-between gap-4 flex-wrap mb-4">
        <h2 className="display-sm" style={{ fontWeight: 400 }}>Perubahan Sikap</h2>
        <p className="text-[11px] text-[#6c6a64]">
          {totalRonde === 1 ? "Posisi akhir" : `Awal dan akhir dari ${totalRonde} babak`}
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2 mb-4">
        <Badge label={`${jumlah.positif} mendukung`} variant="positif" />
        <Badge label={`${jumlah.netral} netral`} variant="netral" />
        <Badge label={`${jumlah.negatif} menolak`} variant="negatif" />
      </div>

      <div className="rounded-lg border border-[#e6dfd8] bg-white p-5">
        <div className="flex justify-between text-[10px] uppercase tracking-[1px] text-[#6c6a64] mb-4">
          <span>Menolak</span><span>Netral</span><span>Mendukung</span>
        </div>

        <div className="space-y-4">
          {baris.map((b) => {
            const warna = SENTIMENT[b.labelAkhir].color;
            const kiri = Math.min(posisiSkor(b.awal), posisiSkor(b.akhir));
            const lebar = Math.abs(posisiSkor(b.akhir) - posisiSkor(b.awal));
            return (
              <div key={b.nama}>
                <div className="flex items-baseline justify-between gap-3">
                  <span className="text-sm text-[#141413] break-words">{b.nama}</span>
                  <span className="text-[11px] text-[#6c6a64] shrink-0 text-right">{b.gerak}</span>
                </div>
                <div className="relative mt-2 h-1.5 rounded-full bg-[#e6dfd8]">
                  <span className="absolute left-1/2 top-0 h-full w-px bg-[#d3ccbf]" aria-hidden="true" />
                  {totalRonde > 1 && (
                    <>
                      <span
                        className="absolute top-1/2 h-[2px] -translate-y-1/2 rounded-full"
                        style={{ left: `${kiri}%`, width: `${lebar}%`, background: warna, opacity: 0.5 }}
                        aria-hidden="true"
                      />
                      <span
                        className="absolute top-1/2 h-2 w-2 -translate-x-1/2 -translate-y-1/2 rounded-full border border-[#a9a094] bg-white"
                        style={{ left: `${posisiSkor(b.awal)}%` }}
                        aria-hidden="true"
                      />
                    </>
                  )}
                  <span
                    className="absolute top-1/2 h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full"
                    style={{ left: `${posisiSkor(b.akhir)}%`, background: warna }}
                    aria-hidden="true"
                  />
                </div>
              </div>
            );
          })}
        </div>

        {totalRonde > 1 && (
          <p className="mt-5 text-[11px] text-[#6c6a64]">
            Titik kosong menandai posisi awal, titik berwarna posisi akhir.
          </p>
        )}
      </div>
    </section>
  );
};

// ── Main Demo Page ──
export default function DemoPage() {
  const [terpasang] = useState(true);
  const [topik, setTopik] = useState("");
  const [kategori, setKategori] = useState("Umum");
  const [jumlahRonde, setJumlahRonde] = useState(3);
  const [hasil, setHasil] = useState(null);
  const [memuat, setMemuat] = useState(false);
  const [tahapMemuat, setTahapMemuat] = useState("");
  const [tier, setTier] = useState("free");
  const [warningTopik, setWarningTopik] = useState(null);
  const [rondeAktif, setRondeAktif] = useState(0);
  const [ringkasanPenuh, setRingkasanPenuh] = useState(false);
  const [errorSimulasi, setErrorSimulasi] = useState("");
  const [caseStudyId, setCaseStudyId] = useState(null);
  const inputRef = useRef(null);
  const hasilRef = useRef(null);
  const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

  const mulaiAnalisis = async () => {
    if (!topik.trim()) { inputRef.current?.focus(); return; }
    setMemuat(true);
    setTahapMemuat("Menghubungkan ke server...");
    setHasil(null);
    setRondeAktif(0);
    setRingkasanPenuh(false);
    setErrorSimulasi("");
    setCaseStudyId(null);
    try {
      const body = { topik: topik.trim(), kategori, jumlah_ronde: jumlahRonde, tier };
      setTahapMemuat("Mengirim topik ke simulasi...");
      const res = await fetch(`${apiBase}/start-simulation`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      setTahapMemuat("Memproses respons server...");
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        setErrorSimulasi(err.detail || "Permintaan gagal.");
        setMemuat(false);
        setTahapMemuat("");
        return;
      }
      setTahapMemuat("Menganalisis hasil simulasi...");
      const data = await res.json();
      setHasil(bacaData(data, "Respons tidak berisi data."));
      if (data.case_study_id) setCaseStudyId(data.case_study_id);
      if (data.warning) setWarningTopik(data.warning);
      else setWarningTopik(null);
      setTimeout(() => hasilRef.current?.scrollIntoView({ behavior: "smooth" }), 200);
    } catch (err) {
      setErrorSimulasi(err.message || "Server tidak dapat dihubungi.");
    }
    setMemuat(false);
    setTahapMemuat("");
  };

  const daftarRonde = hasil?.ronde_detail ?? [];
  const rondeTerakhir = daftarRonde[daftarRonde.length - 1] ?? null;
  const agenAkhir = rondeTerakhir?.agen ?? [];
  const analisis = hasil?.analisis ?? "";
  const prediksi = hasil?.prediksi ?? {};
  const sentimenAgr = hasil?.sentimen_agregat ?? {};
  const aktorAnalisis = hasil?.aktor_analisis ?? null;
  const aktorKunci = aktorAnalisis?.aktor_kunci ?? [];
  const rekomendasi = aktorAnalisis?.rekomendasi ?? "";
  const rekomendasiStrategis = hasil?.rekomendasi_strategis ?? [];
  const risikoUtama = hasil?.risiko_utama ?? "";
  const kelompokKritis = aktorAnalisis?.kelompok_kritis ?? [];
  const penggerak = aktorAnalisis?.aktor_penggerak ?? "";
  const data_transparency = hasil?.data_transparency ?? null;
  const kualitas = hasil?.kualitas ?? null;
  const meta = hasil?.meta ?? {};
  const ringkasSumber = hasil?.ringkas_sumber ?? null;
  const jumlahSumber = ringkasSumber?.total ?? meta.sumber ?? 0;
  // Field tidak ada / kosong (cache lama) dianggap "kosong" hanya kalau memang 0 sumber.
  const statusMentah = ringkasSumber?.status_sumber;
  const statusSumber = ["ok", "kosong", "gagal"].includes(statusMentah)
    ? statusMentah
    : (jumlahSumber > 0 ? "ok" : "kosong");
  const peringatanSumber = ringkasSumber?.peringatan ?? [];
  // Konteks hanya berisi judul berita, jadi kepercayaan tidak pernah "Tinggi".
  const tingkatKepercayaan = statusSumber === "ok" ? "Sedang" : "Rendah";
  const jumlahBabak = meta.ronde ?? (daftarRonde.length || jumlahRonde);

  const ringkasanFull = analisis
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
    .replace(/\*{1,2}/g, "");
  const ringkasan = ringkasanPenuh ? ringkasanFull : truncateAtWord(ringkasanFull, 400);
  const ringkasanTerpotong = ringkasanFull.length > 400;

  const jmlMendukung = agenAkhir.filter(a => a.sentimen?.label === "positif").length;
  const jmlMenolak = agenAkhir.filter(a => a.sentimen?.label === "negatif").length;
  const jmlNetral = agenAkhir.filter(a => a.sentimen?.label === "netral").length;
  const totalPeserta = agenAkhir.length;
  const jumlahPeserta = meta.peserta ?? totalPeserta;

  let statusSimulasi = { label: "Belum Ada", color: "#6c6a64" };
  if (Object.keys(prediksi).length > 0) {
    const sorted = Object.entries(prediksi).sort((a, b) => b[1] - a[1]);
    const p = sorted[0];
    if (p[0] === "Semua Setuju" || p[0] === "Konsensus") {
      statusSimulasi = { label: "Konsensus", color: "#1b8a4a" };
    } else if (p[0] === "Masyarakat Terpecah" || p[0] === "Polarisasi") {
      statusSimulasi = { label: "Terbelah", color: "#b83a3a" };
    } else {
      statusSimulasi = { label: "Stabil", color: "#b8860b" };
    }
  } else if (totalPeserta > 0) {
    if (jmlMendukung > jmlMenolak && jmlMendukung > jmlNetral)
      statusSimulasi = { label: "Cenderung Mendukung", color: "#1b8a4a" };
    else if (jmlMenolak > jmlMendukung && jmlMenolak > jmlNetral)
      statusSimulasi = { label: "Cenderung Menolak", color: "#b83a3a" };
    else
      statusSimulasi = { label: "Pendapat Terbagi", color: "#b8860b" };
  }

  const handleSimpanPDF = () => eksporPDF(hasil, topik, analisis, aktorAnalisis, null);
  const handleSimpanCSV = () => eksporCSV(hasil, topik);
  const handleSimpanWord = () => eksporWord(hasil, topik, analisis).catch(e => alert(e.message));

  if (!terpasang) return null;

  return (
    <div className="flex flex-col bg-[#faf9f5] min-h-screen">
      {memuat && <LoadingOverlay tahap={tahapMemuat} onCancel={() => { setMemuat(false); setTahapMemuat(""); }} />}
      <div className="mx-auto w-full max-w-4xl px-4 md:px-6">

        {/* Hero + Form */}
        <section className="pt-10 pb-6">
          <p className="text-[11px] font-medium uppercase tracking-[1.5px] text-[#6c6a64] mb-4">
            VoxSwarm
          </p>
          <h1 className="display-xl mb-3" style={{ fontWeight: 400 }}>
            Simulasi Reaksi Kebijakan
          </h1>
          <p className="text-base leading-relaxed text-[#3d3d3a]" style={{ letterSpacing: "0.01em" }}>
            Masukkan topik kebijakan — sistem akan mensimulasikan reaksi berbagai kelompok masyarakat
            sebelum kebijakan diluncurkan. Hasilnya adalah gambaran awal untuk referensi pengambilan keputusan,
            bukan pengganti survei nyata.
          </p>
        </section>

        {/* Input Form */}
        <section className="pb-6">
          <div className="rounded-xl border border-[#e6dfd8] bg-white p-5 md:p-6">
            <div className="mb-5 flex flex-col gap-3 sm:flex-row">
              <input
                ref={inputRef}
                className="flex-1 rounded-md border border-[#e6dfd8] bg-white px-4 py-3 text-base text-[#141413] placeholder:text-[#8e8b82] focus:border-[#cc785c] focus:outline-none focus:ring-2 focus:ring-[#cc785c]/20 transition"
                value={topik}
                onChange={e => setTopik(e.target.value.slice(0, 300))}
                onKeyDown={e => e.key === "Enter" && mulaiAnalisis()}
                placeholder='Contoh: "Apakah kenaikan PPN 12% menguntungkan atau merugikan UMKM?"'
                disabled={memuat}
              />
              <button onClick={mulaiAnalisis} disabled={memuat || !topik.trim()}
                className="shrink-0 rounded-md bg-[#cc785c] px-6 py-3 text-base font-medium text-white hover:bg-[#a9583e] focus:outline-none focus:ring-2 focus:ring-[#cc785c]/30 disabled:opacity-50 disabled:cursor-not-allowed transition">
                {memuat ? "Memproses…" : "Jalankan Simulasi"}
              </button>
            </div>

            <div className="flex flex-wrap items-center gap-4 text-sm text-[#3d3d3a]">
              <div className="flex items-center gap-2">
                <span className="text-[#6c6a64]">Kategori:</span>
                <select value={kategori} onChange={e => setKategori(e.target.value)}
                  className="rounded-md border border-[#e6dfd8] bg-white px-3 py-2 text-sm text-[#141413] focus:border-[#cc785c] focus:outline-none focus:ring-2 focus:ring-[#cc785c]/20">
                  {["Umum", "Ekonomi", "Politik", "Sosial", "Hukum", "Teknologi"].map(k =>
                    <option key={k} value={k}>{k}</option>
                  )}
                </select>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[#6c6a64]">Babak:</span>
                <div className="flex gap-1">
                  {[1, 2, 3, 4, 5].map(n => (
                    <button key={n} onClick={() => setJumlahRonde(n)}
                      className={`h-8 min-w-[36px] rounded-md px-2 text-[11px] font-medium transition ${
                        jumlahRonde === n
                          ? "bg-[#cc785c] text-white"
                          : "bg-[#efe9de] text-[#6c6a64] hover:bg-[#e8e0d2]"
                      }`}>
                      {n}
                    </button>
                  ))}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-[#6c6a64]">Detail:</span>
                <div className="flex gap-1">
                  {["free", "normal"].map(t => (
                    <button key={t} onClick={() => setTier(t)}
                      className={`rounded-full px-3 py-1.5 text-[11px] font-medium transition ${
                        tier === t ? "bg-[#cc785c] text-white" : "bg-[#efe9de] text-[#6c6a64] hover:bg-[#e8e0d2]"
                      }`}
                      title={t === "free" ? "Cepat, ringkasan statistik" : "Lengkap, analisis AI"}>
                      {t === "free" ? "Cepat" : "Lengkap"}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {errorSimulasi && (
            <div className="mt-3 rounded-lg border border-[#b83a3a]/30 bg-[#b83a3a]/5 px-4 py-3 text-sm text-[#b83a3a]">
              <strong className="font-semibold">Simulasi gagal.</strong> {errorSimulasi}
            </div>
          )}
          {warningTopik && (
            <div className="mt-3 rounded-lg border border-[#b8860b]/30 bg-[#b8860b]/5 px-4 py-3 text-sm text-[#b8860b]">
              <strong className="font-semibold">Perhatian.</strong> {warningTopik}
            </div>
          )}
        </section>

        {/* Results */}
        {hasil && (
          <section ref={hasilRef} className="pb-10" id="hasil">
            {/* Insight Hero */}
            <InsightHero prediksi={prediksi} statusSimulasi={statusSimulasi} topik={topik} />

            {/* Executive Summary */}
            <section className="py-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="display-sm" style={{ fontWeight: 400 }}>Ringkasan Eksekutif</h2>
                {ringkasanTerpotong && (
                  <button onClick={() => setRingkasanPenuh(!ringkasanPenuh)}
                    className="text-sm font-medium text-[#cc785c] hover:text-[#a9583e] transition">
                    {ringkasanPenuh ? "Tutup" : "Baca selengkapnya"}
                  </button>
                )}
              </div>
              <p className="text-base leading-relaxed text-[#3d3d3a]" style={{ letterSpacing: "0.01em" }}>
                {ringkasan}
              </p>
            </section>

            {/* Kualitas data */}
            {(kualitas || ringkasSumber || meta.sumber !== undefined) && (
              <section className="py-6">
                <div className="flex items-center justify-between gap-2 flex-wrap mb-4">
                  <h2 className="display-sm" style={{ fontWeight: 400 }}>Kualitas Data</h2>
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] text-[#6c6a64]">Kepercayaan</span>
                    <Badge
                      label={tingkatKepercayaan}
                      variant={tingkatKepercayaan === "Sedang" ? "netral" : "negatif"}
                    />
                  </div>
                </div>
                <div className="rounded-lg border border-[#e6dfd8] bg-white">
                  <dl className="grid divide-y divide-[#f0ebe3] sm:grid-cols-3 sm:divide-x sm:divide-y-0">
                    <div className="p-4">
                      <dt className="text-[11px] font-medium uppercase tracking-[1.2px] text-[#6c6a64]">Sumber Data</dt>
                      <dd className="mt-1 text-2xl font-semibold text-[#141413]">
                        {statusSumber === "ok" && jumlahSumber > 0 ? `${jumlahSumber} artikel` : "Tidak ada"}
                      </dd>
                      {statusSumber === "ok" ? (
                        <p className="mt-1 text-[11px] leading-relaxed text-[#6c6a64]">
                          {ringkasSumber?.ditemukan
                            ? `${ringkasSumber.lolos ?? jumlahSumber} lolos filter dari ${ringkasSumber.ditemukan} artikel terkumpul`
                            : "Dipakai sebagai briefing agen"}
                        </p>
                      ) : statusSumber === "gagal" ? (
                        <>
                          <p className="mt-1 text-[11px] leading-relaxed text-[#6c6a64]">
                            Pengambilan berita gagal, jadi simulasi berjalan tanpa sumber.
                          </p>
                          <p className="mt-1.5 text-[11px] text-[#b8860b]">Coba jalankan ulang.</p>
                        </>
                      ) : (
                        <>
                          <p className="mt-1 text-[11px] leading-relaxed text-[#6c6a64]">
                            Pencarian berhasil, tetapi tidak ada berita yang cocok dengan topik ini.
                          </p>
                          {/* TODO: fitur tempel sumber belum ada */}
                          <button
                            type="button"
                            onClick={() => inputRef.current?.focus()}
                            className="mt-2 text-[11px] font-medium text-[#cc785c] hover:text-[#a9583e] transition"
                          >
                            Ubah topik
                          </button>
                        </>
                      )}
                    </div>
                    <div className="p-4">
                      <dt className="text-[11px] font-medium uppercase tracking-[1.2px] text-[#6c6a64]">Peserta</dt>
                      <dd className="mt-1 text-2xl font-semibold text-[#141413]">{jumlahPeserta} orang</dd>
                      <p className="mt-1 text-[11px] leading-relaxed text-[#6c6a64]">Persona yang berpendapat</p>
                    </div>
                    <div className="p-4">
                      <dt className="text-[11px] font-medium uppercase tracking-[1.2px] text-[#6c6a64]">Babak Diskusi</dt>
                      <dd className="mt-1 text-2xl font-semibold text-[#141413]">{jumlahBabak}</dd>
                      <p className="mt-1 text-[11px] leading-relaxed text-[#6c6a64]">Putaran debat yang dijalankan</p>
                    </div>
                  </dl>

                  {statusSumber === "ok" && (ringkasSumber?.sumber_berita ?? []).length > 0 && (
                    <div className="border-t border-[#f0ebe3] px-4 py-3">
                      <p className="text-[11px] leading-relaxed text-[#6c6a64]">
                        Yang dibaca simulasi hanya judul berita, bukan isi artikel.
                      </p>
                      <details className="group mt-1">
                        <summary className="flex items-center gap-2 cursor-pointer list-none text-[11px] font-medium text-[#6c6a64] hover:text-[#141413]">
                          <span>Daftar sumber ({Math.min(ringkasSumber.sumber_berita.length, 12)})</span>
                          <span className="text-[10px] transition-transform group-open:rotate-180">▼</span>
                        </summary>
                        <ul className="mt-2 space-y-2">
                          {ringkasSumber.sumber_berita.slice(0, 12).map((s, i) => (
                            <li key={`${s.judul}-${i}`} className="text-[11px] leading-relaxed">
                              {s.link ? (
                                <a
                                  href={s.link}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="text-[#141413] underline decoration-[#e6dfd8] underline-offset-2 hover:text-[#cc785c] transition"
                                >
                                  {s.judul}
                                </a>
                              ) : (
                                <span className="text-[#141413]">{s.judul}</span>
                              )}
                              <span className="block text-[#6c6a64]">
                                {s.media}{s.tanggal ? ` · ${s.tanggal}` : ""}
                              </span>
                            </li>
                          ))}
                        </ul>
                      </details>
                    </div>
                  )}

                  <details className="group border-t border-[#f0ebe3] px-4 py-3">
                    <summary className="flex items-center gap-2 cursor-pointer list-none text-sm font-medium text-[#6c6a64] hover:text-[#141413]">
                      <span>Lihat detail</span>
                      <span className="text-[10px] transition-transform group-open:rotate-180">▼</span>
                    </summary>
                    <div className="mt-2 space-y-1.5">
                      {kualitas && (
                        <p className="text-[11px] text-[#6c6a64]">
                          Seberapa sering jawaban peserta memakai nilai cadangan, bukan keluaran model.
                        </p>
                      )}
                      {kualitas && (
                        <p className="text-sm text-[#3d3d3a]">
                          {kualitas.fallback_count > 0 ? (
                            <>
                              <Badge
                                label={kualitas.status === "ok" ? "Lancar" : kualitas.status === "warning" ? "Sebagian cadangan" : "Banyak cadangan"}
                                variant={kualitas.status === "ok" ? "positif" : kualitas.status === "warning" ? "warning" : "negatif"}
                              />
                              <span className="ml-2 text-[#6c6a64]">
                                {kualitas.fallback_count} dari {kualitas.total_giliran} giliran memakai nilai cadangan
                                ({(kualitas.fallback_rate * 100).toFixed(1)}%).
                              </span>
                            </>
                          ) : (
                            <>
                              <Badge label="Lancar" variant="positif" />
                              <span className="ml-2 text-[#6c6a64]">
                                Semua {kualitas.total_giliran} giliran memakai keluaran model, tanpa nilai cadangan.
                              </span>
                            </>
                          )}
                        </p>
                      )}
                      {meta.tanggal && (
                        <p className="text-[11px] text-[#6c6a64]">Dijalankan pada {meta.tanggal}</p>
                      )}
                      {ringkasSumber?.catatan && (
                        <p className="text-[11px] text-[#6c6a64]">{ringkasSumber.catatan}</p>
                      )}
                      {statusSumber === "ok" && peringatanSumber.length > 0 && (
                        <p className="text-[11px] text-[#6c6a64]">
                          Sebagian sumber tidak bisa dibuka: {peringatanSumber.map(ringkasPeringatan).join(", ")}.
                        </p>
                      )}
                      {statusSumber === "gagal" && (
                        <p className="text-[11px] text-[#6c6a64]">
                          {ringkasSumber?.pesan_sumber || "Tidak ada detail kegagalan dari server."}
                        </p>
                      )}
                    </div>
                  </details>
                </div>
              </section>
            )}

            {/* Analisis Aktor */}
            {aktorAnalisis && (
              <section className="py-6">
                <h2 className="display-sm mb-2" style={{ fontWeight: 400 }}>Analisis Aktor</h2>
                <p className="text-sm text-[#6c6a64] leading-relaxed mb-5">
                  {aktorKunci.length > 0
                    ? "Diurutkan dari skor pengaruh, yang menggabungkan besarnya pengaruh dan konsistensi sikap sepanjang diskusi."
                    : "Tidak ada aktor yang menonjol pada sesi ini."}
                  {penggerak ? ` Penggerak utama: ${penggerak}.` : ""}
                </p>

                {aktorKunci.length > 0 && (
                  <div className="rounded-lg border border-[#e6dfd8] bg-white divide-y divide-[#f0ebe3]">
                    {aktorKunci.map((aktor, idx) => {
                      const pengaruh = aktor.pengaruh_skor ?? aktor.pengaruh ?? null;
                      const konsistensi = aktor.konsistensi_skor
                        ?? (typeof aktor.konsisten === "boolean" ? (aktor.konsisten ? 1 : 0) : null);
                      const labelSikap = aktor.sikap_label ?? null;
                      const aksi = aksiPendekatan(aktor.cara_pendekatan, aktor.nama) || beresinTeksAkhir(aktor.alasan);
                      return (
                        <div key={aktor.nama ?? idx} className="grid gap-3 p-4 sm:grid-cols-[minmax(0,1fr)_150px] sm:items-start">
                          <div className="min-w-0">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="text-sm font-semibold text-[#141413]">{aktor.nama}</span>
                              {labelSikap && <BadgeSentimen label={labelSikap} />}
                            </div>
                            {aksi && (
                              <p className="mt-1.5 text-sm leading-relaxed text-[#3d3d3a]">{aksi}</p>
                            )}
                            {aktor.dampak_jika_berubah && (
                              <p className="mt-1 text-[11px] text-[#6c6a64]">{aktor.dampak_jika_berubah}</p>
                            )}
                          </div>
                          <div className="text-[11px] text-[#6c6a64] sm:text-right sm:pt-0.5">
                            <p>
                              <span className="text-sm font-medium tabular-nums text-[#141413]">{persen(pengaruh) ?? "—"}</span> pengaruh
                            </p>
                            <p className="mt-0.5">
                              {konsistensi !== null ? `Konsistensi ${persen(konsistensi)}` : "Konsistensi tidak tersedia"}
                            </p>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}

                {(aktorAnalisis.swing_voter ?? []).length > 0 && (
                  <div className="mt-5">
                    <p className="text-[11px] font-medium uppercase tracking-[1.2px] text-[#6c6a64] mb-2">Paling mudah berubah</p>
                    <ul className="grid gap-2 sm:grid-cols-3">
                      {(aktorAnalisis.swing_voter ?? []).slice(0, 3).map((v, idx) => (
                        <li key={v.nama ?? idx} className="rounded-md border border-[#e6dfd8] bg-[#faf9f5] px-3 py-2.5">
                          <p className="text-sm text-[#141413] break-words">{v.nama}</p>
                          <p className="mt-0.5 text-[11px] text-[#6c6a64]">
                            {sikapDariAlasan(String(v.sikap_awal)) ?? "netral"} → {sikapDariAlasan(String(v.sikap_akhir)) ?? "netral"}
                          </p>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {(rekomendasiStrategis ?? []).length > 0 && (
                  <div className="mt-6">
                    <p className="text-[11px] font-medium uppercase tracking-[1.2px] text-[#6c6a64] mb-3">Langkah yang disarankan</p>
                    <ol className="space-y-3">
                      {(rekomendasiStrategis ?? []).map((r, idx) => {
                        const teks = typeof r === "string" ? r : r?.aksi;
                        if (!teks) return null;
                        return (
                          <li key={idx} className="grid grid-cols-[22px_minmax(0,1fr)] gap-3">
                            <span className="text-sm tabular-nums text-[#8f3a1f]">{idx + 1}</span>
                            <p className="text-sm leading-relaxed text-[#3d3d3a]">{teks}</p>
                          </li>
                        );
                      })}
                    </ol>
                  </div>
                )}

                {rekomendasi && (rekomendasiStrategis ?? []).length === 0 && (
                  <div className="mt-6 border-l-2 border-[#cc785c] pl-4">
                    <p className="text-[11px] font-medium uppercase tracking-[1.2px] text-[#6c6a64] mb-1">Rekomendasi</p>
                    <p className="text-sm leading-relaxed text-[#3d3d3a]">{beresinTeksAkhir(rekomendasi)}</p>
                  </div>
                )}

                {risikoUtama && (
                  <div className="mt-6 border-l-2 border-[#b83a3a] pl-4">
                    <p className="text-[11px] font-medium uppercase tracking-[1.2px] text-[#b83a3a] mb-1">Risiko Utama</p>
                    <p className="text-sm leading-relaxed text-[#3d3d3a]">{beresinTeksAkhir(risikoUtama)}</p>
                  </div>
                )}
              </section>
            )}

            {/* Kelompok Kritis */}
            {(kelompokKritis ?? []).length > 0 && (
              <section className="py-6">
                <h2 className="display-sm mb-4" style={{ fontWeight: 400 }}>Kelompok Kritis</h2>
                <div className="rounded-lg border border-[#e6dfd8] bg-white divide-y divide-[#f0ebe3]">
                  {(kelompokKritis ?? []).map((k, idx) => {
                    const label = sikapDariAlasan(k.alasan);
                    const alasan = k.alasan ? beresinTeksAkhir(k.alasan) : getAlasanKritis(k.nama);
                    return (
                      <div key={k.nama ?? idx} className="p-4">
                        <div className="flex items-start justify-between gap-3">
                          <p className="text-sm font-semibold text-[#141413] break-words">{k.nama}</p>
                          {label && <BadgeSentimen label={label} />}
                        </div>
                        {alasan && <p className="mt-1 text-sm text-[#6c6a64] leading-relaxed">{alasan}</p>}
                        {k.cara_pendekatan && (
                          <p className="mt-2 text-sm leading-relaxed text-[#3d3d3a]">{k.cara_pendekatan}</p>
                        )}
                      </div>
                    );
                  })}
                </div>
              </section>
            )}

            {/* Prediction / Scenarios */}
            {Object.keys(prediksi).length > 0 && (
              <section className="py-6">
                <h2 className="display-sm mb-4" style={{ fontWeight: 400 }}>Skenario Pelaksanaan</h2>
                <div className="rounded-lg border border-[#e6dfd8] bg-white overflow-hidden">
                  {Object.entries(prediksi)
                    .sort((a, b) => b[1] - a[1])
                    .map(([skenario, prob], idx) => (
                      <div key={idx} className={`border-t ${idx === 0 ? "" : "border-[#e6dfd8]"} p-5 ${idx === 0 ? "bg-[#cc785c]/3" : ""}`}>
                        <div className="flex items-center justify-between gap-4">
                          <div>
                            <p className="text-sm font-semibold text-[#141413]">{skenario}</p>
                            <p className="text-sm text-[#6c6a64] mt-0.5">{DESKRIPSI_SKENARIO[skenario] ?? ""}</p>
                          </div>
                          <div className="text-right shrink-0">
                            <p className="text-2xl font-bold text-[#141413]" style={{ fontFamily: "var(--font-heading, sans-serif)" }}>{prob}%</p>
                            <p className="text-[11px] text-[#6c6a64]">Kemungkinan</p>
                          </div>
                        </div>
                      </div>
                    ))}
                </div>
              </section>
            )}

            {/* Meteran Sikap */}
            {sentimenAgr && Object.keys(sentimenAgr).length > 0 && (
              <MeteranSikap sentimenAgr={sentimenAgr} daftarRonde={daftarRonde} />
            )}

            {/* Transkrip */}
            {daftarRonde.length > 0 && (
              <TranskripRisalah daftarRonde={daftarRonde} rondeAktif={rondeAktif} setRondeAktif={setRondeAktif} />
            )}

            {/* Word Cloud */}
            {hasil.wordcloud && (
              <section className="py-6">
                <h2 className="display-sm mb-4" style={{ fontWeight: 400 }}>Kata Kunci</h2>
                <WordCloud data={hasil.wordcloud} />
              </section>
            )}

            {/* Actions */}
            <section className="py-6 border-t border-[#e6dfd8]">
              <div className="flex flex-wrap gap-3">
                <button onClick={handleSimpanPDF}
                  className="inline-flex items-center gap-2 rounded-md border border-[#e6dfd8] bg-white px-4 py-2.5 text-sm font-medium text-[#3d3d3a] hover:border-[#cc785c]/40 hover:bg-[#cc785c]/5 hover:text-[#cc785c] transition">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                    <polyline points="7 10 12 15 17 10"/>
                    <line x1="12" y1="15" x2="12" y2="3"/>
                  </svg>
                  Unduh PDF
                </button>
                <button onClick={handleSimpanCSV}
                  className="inline-flex items-center gap-2 rounded-md border border-[#e6dfd8] bg-white px-4 py-2.5 text-sm font-medium text-[#3d3d3a] hover:border-[#cc785c]/40 hover:bg-[#cc785c]/5 hover:text-[#cc785c] transition">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                    <polyline points="14 2 14 8 20 8"/>
                    <line x1="16" y1="13" x2="8" y2="13"/>
                    <line x1="16" y1="17" x2="8" y2="17"/>
                  </svg>
                  Unduh CSV
                </button>
                <button onClick={handleSimpanWord}
                  className="inline-flex items-center gap-2 rounded-md border border-[#e6dfd8] bg-white px-4 py-2.5 text-sm font-medium text-[#3d3d3a] hover:border-[#cc785c]/40 hover:bg-[#cc785c]/5 hover:text-[#cc785c] transition">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                    <polyline points="14 2 14 8 20 8"/>
                    <line x1="16" y1="13" x2="8" y2="13"/>
                    <line x1="16" y1="17" x2="8" y2="17"/>
                  </svg>
                  Unduh Word
                </button>
                {caseStudyId && (
                  <Link href={`/studi-kasus/${caseStudyId}`}
                    className="inline-flex items-center gap-2 rounded-md border border-[#e6dfd8] bg-white px-4 py-2.5 text-sm font-medium text-[#3d3d3a] hover:border-[#cc785c]/40 hover:bg-[#cc785c]/5 hover:text-[#cc785c] transition">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                      <circle cx="12" cy="12" r="3"/>
                    </svg>
                    Lihat Studi Kasus Lengkap
                  </Link>
                )}
              </div>
            </section>

            {/* Reset */}
            <section className="py-6 text-center">
              <button
                onClick={() => { setHasil(null); setTopik(""); setRondeAktif(0); setCaseStudyId(null); setTimeout(() => { inputRef.current?.focus(); window.scrollTo({ top: 0, behavior: "smooth" }); }, 100); }}
                className="text-sm text-[#6c6a64] underline underline-offset-2 hover:text-[#141413] transition">
              Mulai analisis baru
              </button>
            </section>
          </section>
        )}

      </div>
    </div>
  );
}
