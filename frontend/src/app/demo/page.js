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

const AGENT_COLORS = ["#cc785c", "#1b8a4a", "#e8a55a", "#b83a3a", "#1b8a7a", "#6c6a64", "#252523"];

function bacaData(payload, pesan = "Data tidak ditemukan.") {
  if (!payload || typeof payload !== "object" || !payload.data)
    throw new Error(payload?.detail || payload?.message || pesan);
  const hasil = payload.data;
  if (payload.konteks_real?.data_transparency)
    hasil.data_transparency = payload.konteks_real.data_transparency;
  return hasil;
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

// ── Loading Overlay ──
const LoadingOverlay = ({ tahap, onCancel }) => (
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
        {[
          "Menghubungkan ke server...",
          "Mengirim topik ke simulasi...",
          "Memproses respons server...",
          "Menganalisis hasil simulasi..."
        ].map((step, i) => (
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

// ── Static Bar Chart ──
const StaticBarChart = ({ meterData }) => (
  <div className="space-y-4">
    {meterData.map((ag) => (
      <div key={ag.nama}>
        <div className="flex items-center gap-2 mb-1.5">
          <span className="text-sm font-medium text-[#141413] break-words">{ag.nama}</span>
          <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium whitespace-nowrap shrink-0 ${ag.skorLabel.bg}`}
            style={{ color: ag.skorLabel.color, backgroundColor: ag.skorLabel.color + "15", border: `1px solid ${ag.skorLabel.color}30` }}>
            {ag.skorLabel.label}
          </span>
        </div>
        <div className="relative h-7 rounded-full bg-[#e6dfd8] overflow-hidden">
          <div className="h-full rounded-full transition-all flex items-center justify-end pr-2"
            style={{ width: `${ag.akhir}%`, backgroundColor: ag.skorLabel.color, minWidth: ag.akhir > 0 ? "20px" : "0" }}>
            <span className="text-[11px] font-bold text-white drop-shadow-[0_1px_1px_rgba(0,0,0,0.3)]">{ag.akhir}</span>
          </div>
        </div>
      </div>
    ))}
  </div>
);

const MeteranSikap = ({ sentimenAgr, daftarRonde }) => {
  const namaAgen = Object.keys(sentimenAgr ?? {});
  if (!namaAgen.length) return null;
  const totalRonde = daftarRonde?.length ?? 0;
  if (totalRonde < 1) return null;
  const meterData = namaAgen.map((nama, i) => {
    const skorRonde = sentimenAgr[nama].map(s => Math.round(((s ?? 0) + 1) * 50));
    const awal = skorRonde[0];
    const akhir = skorRonde[skorRonde.length - 1];
    const skorLabel = labelSkor(akhir);
    return { nama, skorLabel, skorRonde, color: AGENT_COLORS[i % AGENT_COLORS.length], awal, akhir, selisih: akhir - awal };
  });
  const isSingleRound = totalRonde === 1;

  const rondeTerakhir = daftarRonde?.[daftarRonde.length - 1];
  const ringkasan = { positif: 0, netral: 0, negatif: 0 };
  (rondeTerakhir?.agen ?? []).forEach((a) => {
    const label = a.sentimen?.label;
    if (ringkasan[label] !== undefined) ringkasan[label] += 1;
  });
  const totalPeserta = ringkasan.positif + ringkasan.netral + ringkasan.negatif;

  return (
    <section className="py-6">
      <h2 className="display-sm mb-4" style={{ fontWeight: 400 }}>Perubahan Sikap</h2>

      {totalPeserta > 0 && (
        <div className="flex flex-wrap items-center gap-2 mb-5">
          <span className="text-[11px] font-medium text-[#6c6a64]">
            Posisi akhir {totalPeserta} peserta:
          </span>
          <Badge label={`${ringkasan.positif} Mendukung`} variant="positif" />
          <Badge label={`${ringkasan.netral} Netral`} variant="netral" />
          <Badge label={`${ringkasan.negatif} Menolak`} variant="negatif" />
        </div>
      )}

      <div className="flex flex-wrap items-center gap-3 mb-5 text-[11px] text-[#6c6a64]">
        <span className="font-medium">Legenda:</span>
        <span className="inline-flex items-center gap-1">
          <span className="w-3 h-3 rounded-full bg-[#b83a3a]" /> Menolak
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="w-3 h-3 rounded-full bg-[#6c6a64]" /> Netral
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="w-3 h-3 rounded-full bg-[#1b8a4a]" /> Mendukung
        </span>
      </div>

      <div className="rounded-lg border border-[#e6dfd8] bg-white overflow-hidden p-5">
        {isSingleRound ? (
          <>
            <p className="text-[12px] text-[#6c6a64] mb-1 leading-relaxed">
              Skor sentimen terakhir tiap kelompok berdasarkan simulasi.
            </p>
            <p className="text-[11px] text-[#6c6a64] italic mb-5">
              Jalankan lebih dari 1 babak untuk melihat pergerakan sikap.
            </p>
            <div className="flex items-center gap-3 mb-4 text-[10px] text-[#6c6a64]">
              <span>Menolak (0)</span>
              <span className="flex-1 h-px bg-[#e6dfd8]" />
              <span>Mendukung (100)</span>
            </div>
            <StaticBarChart meterData={meterData} />
          </>
        ) : (
          <>
            <p className="text-[12px] text-[#6c6a64] mb-5 leading-relaxed">
              Perubahan sentimen tiap kelompok dari babak ke babak.
              Titik <strong className="text-[#141413]">bulat</strong> = posisi per babak · garis = arah perubahan.
            </p>
            <div className="flex items-center gap-3 mb-6 text-[10px] text-[#6c6a64]">
              <span>Menolak</span>
              <div className="relative flex-1 h-3 rounded-full" style={{
                background: "linear-gradient(to right, #b83a3a, #8e8b82 25%, #6c6a64 50%, #8e8b82 75%, #1b8a4a)",
                opacity: 0.3,
              }} />
              <span>Mendukung</span>
            </div>
            <div className="flex justify-between text-[10px] text-[#6c6a64] -mt-2 mb-6">
              <span>0 (Tolak)</span><span>50 (Netral)</span><span>100 (Dukung)</span>
            </div>
            <div className="space-y-5">
              {meterData.map((ag) => (
                <div key={ag.nama}>
                  <div className="flex items-start justify-between mb-2 gap-2">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="text-sm font-medium text-[#141413] break-words">{ag.nama}</span>
                      <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium whitespace-nowrap shrink-0 ${ag.skorLabel.bg}`}
                        style={{ color: ag.skorLabel.color, backgroundColor: ag.skorLabel.color + "15", border: `1px solid ${ag.skorLabel.color}30` }}>
                        {ag.skorLabel.label}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <span className="text-[10px] text-[#6c6a64] whitespace-nowrap">
                        {ag.awal}→{ag.akhir}{ag.selisih > 0 ? ` +${ag.selisih}` : ag.selisih < 0 ? ` ${ag.selisih}` : ""}
                      </span>
                      <span className="text-[10px] font-medium" style={{ color: ag.color }}>
                        {ag.selisih > 0 ? "↗ Menguat" : ag.selisih < 0 ? "↘ Melemah" : "→ Stabil"}
                      </span>
                    </div>
                  </div>
                  <svg width="100%" height="28" viewBox="0 0 400 28" preserveAspectRatio="none" className="overflow-visible">
                    <rect x="0" y="11" width="400" height="6" rx="3" fill="url(#grad-bg)" opacity="0.3" />
                    {ag.skorRonde.length > 1 && (() => {
                        const points = ag.skorRonde.map((s, i) => {
                          const x = (400 / (totalRonde)) * i + (400 / (totalRonde + 1));
                          const y = 14 - (s - 50) * 0.1;
                          return `${x},${y}`;
                        }).join(" ");
                        return (
                          <polyline fill="none" stroke={ag.color} strokeWidth="2" strokeOpacity="0.5"
                            strokeDasharray={ag.skorRonde.length > 2 ? "3 2" : "none"}
                            points={points}
                          />
                        );
                      })()}
                    {ag.skorRonde.map((s, i) => {
                      const x = (400 / (totalRonde)) * i + (400 / (totalRonde + 1));
                      const y = 14 - (s - 50) * 0.1;
                      return (
                        <circle key={i} cx={x} cy={y} r="3.5" fill={ag.color} stroke="white" strokeWidth="1.5" />
                      );
                    })}
                    <defs>
                      <linearGradient id="grad-bg" x1="0" y1="0" x2="400" y2="0">
                        <stop offset="0%" stopColor="#b83a3a" />
                        <stop offset="25%" stopColor="#8e8b82" />
                        <stop offset="50%" stopColor="#6c6a64" />
                        <stop offset="75%" stopColor="#8e8b82" />
                        <stop offset="100%" stopColor="#1b8a4a" />
                      </linearGradient>
                    </defs>
                  </svg>
                </div>
              ))}
            </div>
          </>
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

            {/* Trustworthiness / Kualitas Data */}
            {(kualitas || meta.sumber !== undefined) && (
              <section className="py-6">
                <h2 className="display-sm mb-4" style={{ fontWeight: 400 }}>Kualitas Data</h2>
                <div className="rounded-lg border border-[#e6dfd8] bg-white p-5">
                  <div className="grid gap-4 sm:grid-cols-3">
                    <div className="rounded-lg border border-[#e6dfd8] bg-[#faf9f5] p-4">
                      <p className="text-[11px] font-medium uppercase tracking-[1.2px] text-[#6c6a64] mb-1">Sumber Data</p>
                      <p className="text-2xl font-bold text-[#141413]">{meta.sumber ?? 0} artikel</p>
                    </div>
                    <div className="rounded-lg border border-[#e6dfd8] bg-[#faf9f5] p-4">
                      <p className="text-[11px] font-medium uppercase tracking-[1.2px] text-[#6c6a64] mb-1">Peserta</p>
                      <p className="text-2xl font-bold text-[#141413]">{meta.peserta ?? totalPeserta} orang</p>
                    </div>
                    <div className="rounded-lg border border-[#e6dfd8] bg-[#faf9f5] p-4">
                      <p className="text-[11px] font-medium uppercase tracking-[1.2px] text-[#6c6a64] mb-1">Babak Diskusi</p>
                      <p className="text-2xl font-bold text-[#141413]">{meta.ronde ?? jumlahRonde}</p>
                    </div>
                  </div>
                  {kualitas && (
                    <div className="mt-4 rounded-lg border border-[#e6dfd8] bg-[#faf9f5] p-4">
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="text-[11px] font-medium uppercase tracking-[1.2px] text-[#6c6a64] mb-1">Tingkat Kepercayaan</p>
                          <p className="text-lg font-semibold text-[#141413]">{kualitas.status === "ok" ? "Standar" : kualitas.status === "warning" ? "Perlu Perhatian" : "Tidak Layak"}</p>
                        </div>
                        <Badge
                          label={kualitas.status === "ok" ? "Standar" : kualitas.status === "warning" ? "Perhatian" : "Tidak Layak"}
                          variant={kualitas.status === "ok" ? "positif" : kualitas.status === "warning" ? "warning" : "negatif"}
                        />
                      </div>
                      <p className="mt-2 text-sm text-[#6c6a64]">
                        {kualitas.fallback_count} dari {kualitas.total_giliran} giliran menggunakan nilai cadangan
                        ({(kualitas.fallback_rate * 100).toFixed(1)}%).
                      </p>
                    </div>
                  )}
                  {meta.tanggal && (
                    <p className="mt-4 text-sm text-[#6c6a64]">
                      Dijalankan pada {meta.tanggal}
                    </p>
                  )}
                  {data_transparency && (
                    <details className="mt-4 group">
                      <summary className="flex items-center gap-2 cursor-pointer text-sm font-medium text-[#6c6a64] hover:text-[#141413]">
                        <span>Transparansi Data</span>
                        <span className="text-[10px] text-[#6c6a64] transition-transform group-open:rotate-180">▼</span>
                      </summary>
                      <div className="mt-3 grid gap-2 sm:grid-cols-2 text-sm text-[#6c6a64]">
                        <div><strong>Total Sumber:</strong> {data_transparency.total_sources ?? 0}</div>
                        <div><strong>RSS:</strong> {data_transparency.rss_count ?? 0}</div>
                        <div><strong>Reddit:</strong> {data_transparency.reddit_count ?? 0}</div>
                        <div><strong>Polling:</strong> {data_transparency.polling_count ?? 0}</div>
                        <div><strong>Skor Keberagaman:</strong> {(data_transparency.diversity_score ?? 0).toFixed(2)}</div>
                        <div><strong>Skor Ketercapan:</strong> {(data_transparency.coverage_score ?? 0).toFixed(2)}</div>
                      </div>
                    </details>
                  )}
                </div>
              </section>
            )}

            {/* Key Findings - Actor Analysis */}
            {aktorAnalisis && (
              <section className="py-6">
                <h2 className="display-sm mb-4" style={{ fontWeight: 400 }}>Analisis Aktor</h2>
                <div className="space-y-4">
                  {(aktorKunci ?? []).map((aktor, idx) => (
                    <div key={idx} className="rounded-lg border border-[#e6dfd8] bg-white p-5">
                      <div className="flex items-start justify-between gap-4">
                        <div className="min-w-0">
                          <p className="text-sm font-semibold text-[#141413]">{aktor.nama}</p>
                          <p className="text-sm text-[#6c6a64] mt-0.5">{aktor.peran ?? "Aktor kunci"}</p>
                        </div>
                        <div className="flex items-center gap-2 shrink-0">
                          <Badge label={aktor.pengaruh >= 0.7 ? "Pengaruh Tinggi" : aktor.pengaruh >= 0.4 ? "Pengaruh Sedang" : "Pengaruh Rendah"}
                            variant={aktor.pengaruh >= 0.7 ? "negatif" : aktor.pengaruh >= 0.4 ? "warning" : "default"} />
                          <Badge label={aktor.konsisten ? "Konsisten" : "Volatil"} variant="outline" />
                        </div>
                      </div>
                      {aktor.alasan && (
                        <p className="mt-3 text-sm text-[#3d3d3a] leading-relaxed">{beresinTeksAkhir(aktor.alasan)}</p>
                      )}
                    </div>
                  ))}
                  {(rekomendasiStrategis ?? []).map((r, idx) => (
                    <div key={idx} className="rounded-lg border border-[#e6dfd8] bg-white p-5">
                      <p className="text-sm font-medium text-[#141413]">{r.aksi ?? r}</p>
                      {r.alasan && <p className="mt-1 text-sm text-[#6c6a64]">{r.alasan}</p>}
                      {r.prioritas && (
                        <Badge label={`Prioritas: ${r.prioritas}`} variant="warning" className="mt-2" />
                      )}
                    </div>
                  ))}
                  {rekomendasi && (
                    <div className="rounded-lg border border-[#e6dfd8] bg-[#cc785c]/5 p-5">
                      <p className="text-sm font-medium text-[#141413] mb-2">Rekomendasi Utama</p>
                      <p className="text-sm text-[#3d3d3a] leading-relaxed">{beresinTeksAkhir(rekomendasi)}</p>
                    </div>
                  )}
                  {risikoUtama && (
                    <div className="rounded-lg border border-[#b83a3a]/30 bg-[#b83a3a]/5 p-5">
                      <p className="text-sm font-medium text-[#b83a3a] mb-2">Risiko Utama</p>
                      <p className="text-sm text-[#3d3d3a] leading-relaxed">{beresinTeksAkhir(risikoUtama)}</p>
                    </div>
                  )}
                </div>
              </section>
            )}

            {/* Critical Groups */}
            {(kelompokKritis ?? []).length > 0 && (
              <section className="py-6">
                <h2 className="display-sm mb-4" style={{ fontWeight: 400 }}>Kelompok Kritis</h2>
                <div className="space-y-3">
                  {(kelompokKritis ?? []).map((k, idx) => (
                    <div key={idx} className="rounded-lg border border-[#e6dfd8] bg-white p-4">
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="text-sm font-semibold text-[#141413]">{k.nama}</p>
                          <p className="text-sm text-[#6c6a64]">{getAlasanKritis(k.nama)}</p>
                        </div>
                        <div className="flex items-center gap-2">
                          <Badge label={k.pengaruh >= 0.7 ? "Pengaruh Tinggi" : "Pengaruh Sedang"}
                            variant="negatif" />
                          <Badge label="Butuh Dialog" variant="warning" />
                        </div>
                      </div>
                      {k.pendekatan && (
                        <p className="mt-3 text-sm text-[#3d3d3a]">{k.pendekatan}</p>
                      )}
                    </div>
                  ))}
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
