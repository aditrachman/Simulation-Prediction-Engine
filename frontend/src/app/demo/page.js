"use client";
import { eksporPDF } from "../utils/eksporpdf";
import { eksporCSV, eksporWord } from "../utils/eksporlainnya";
import { useState, useRef } from "react";
import WordCloud from "../components/WordCloud";
import InfoTip from "../components/InfoTip";
import { GlossaryButton } from "../components/InfoTip";
import Link from "next/link";

// ─── Sentimen Helpers ──────────────────────────────────────────
const SENTIMEN = {
  positif: { warna: "#5db872", label: "Setuju",    bg: "bg-[#5db872]/10 text-[#5db872]" },
  netral:  { warna: "#6c6a64", label: "Netral",     bg: "bg-[#6c6a64]/10 text-[#6c6a64]" },
  negatif: { warna: "#c64545", label: "Tidak Setuju", bg: "bg-[#c64545]/10 text-[#c64545]" },
};

const LABEL_SKOR = [
  { max: 30, label: "Menolak Keras", warna: "#c64545", bg: "bg-[#c64545]/10 text-[#c64545]" },
  { max: 49, label: "Cenderung Menolak", warna: "#d4a017", bg: "bg-[#d4a017]/10 text-[#d4a017]" },
  { max: 50, label: "Netral", warna: "#6c6a64", bg: "bg-[#6c6a64]/10 text-[#6c6a64]" },
  { max: 70, label: "Cenderung Mendukung", warna: "#5db8a6", bg: "bg-[#5db8a6]/10 text-[#5db8a6]" },
  { max: 100, label: "Mendukung Kuat", warna: "#5db872", bg: "bg-[#5db872]/10 text-[#5db872]" },
];
const labelSkor = (s) => LABEL_SKOR.find(l => s <= l.max) ?? LABEL_SKOR[LABEL_SKOR.length - 1];

// ─── Mapping skenario — pake bahasa sederhana ───────────────────
const DESKRIPSI_SKENARIO = {
  "Semua Setuju": "Semua kelompok punya pendapat yang sama",
  "Konsensus": "Semua kelompok mencapai kata sepakat",
  "Masyarakat Terpecah": "Masyarakat terbagi jadi beberapa kubu — bisa timbul masalah",
  "Polarisasi": "Masyarakat terbelah jadi dua kubu besar yang saling berlawanan",
  "Tidak Ada Perubahan": "Tidak ada perubahan berarti — pendapat masyarakat tetap sama dari awal",
  "Status Quo": "Keadaan tetap sama — tidak ada yang berubah dari sekarang",
};

const INSIGHT_SKENARIO = {
  "Semua Setuju": "Semua pihak setuju —",
  "Konsensus": "Semua pihak mencapai kata sepakat —",
  "Masyarakat Terpecah": "Pendapat masyarakat terbelah —",
  "Polarisasi": "Masyarakat terbelah jadi dua kubu —",
  "Tidak Ada Perubahan": "Pendapat publik tetap —",
  "Status Quo": "Situasi tetap seperti sekarang —",
};
const WARNA_AGEN = ["#cc785c","#5db872","#e8a55a","#c64545","#5db8a6","#a09d96","#6c6a64","#252523"];

function bacaData(payload, pesan = "Data tidak ditemukan.") {
  if (!payload || typeof payload !== "object" || !payload.data)
    throw new Error(payload?.detail || payload?.message || pesan);
  const hasil = payload.data;
  if (payload.konteks_real?.data_transparency)
    hasil.data_transparency = payload.konteks_real.data_transparency;
  return hasil;
}

// ─── Badge Sentimen ──────────────────────────────────────────────
const BadgeSentimen = ({ label }) => {
  const s = SENTIMEN[label] ?? SENTIMEN.netral;
  return (
    <span className={`inline-flex items-center gap-1 rounded-[9999px] px-2.5 py-0.5 text-[11px] font-medium ${s.bg}`}>
      <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: s.warna }} />
      {s.label}
    </span>
  );
};

const getPendekatan = (nama) => {
  const n = nama.toLowerCase();
  if (n.includes("jurnalis") || n.includes("media") || n.includes("wartawan"))
    return "Adakan konferensi pers, sediakan data yang bisa dicek, berikan akses ke orang yang bisa dipercaya.";
  if (n.includes("oposisi") || n.includes("kritis") || n.includes("lawan"))
    return "Undang dialog empat mata, akui kekurangan kebijakan, tawarkan evaluasi rutin yang libatkan mereka.";
  if (n.includes("akademisi") || n.includes("dosen") || n.includes("peneliti") || n.includes("ilmuwan"))
    return "Libatkan dalam penelitian bareng, publikasikan data pendukung, minta masukan buat perbaikan.";
  if (n.includes("mahasiswa") || n.includes("pelajar") || n.includes("aktivis") || n.includes("ormas"))
    return "Gunakan medsos dan forum kampus, sampaikan dampak langsung kebijakan ke kehidupan sehari-hari.";
  if (n.includes("pengusaha") || n.includes("umkm") || n.includes("bisnis") || n.includes("wirausaha"))
    return "Fokus ke dampak duit yang nyata, tawarkan imbalan atau ganti rugi, libatkan perkumpulan bisnis.";
  if (n.includes("pemerintah") || n.includes("birokrat") || n.includes("menteri") || n.includes("pejabat"))
    return "Koordinasi antar bagian, pastikan pesan yang disampaikan sama semua.";
  if (n.includes("pekerja") || n.includes("kantoran") || n.includes("karyawan") || n.includes("buruh"))
    return "Sampaikan lewat perkumpulan pekerja, fokus ke dampak ke penghasilan dan kesejahteraan.";
  return "Libatkan lewat saluran yang biasa mereka pake, sampaikan manfaat nyata.";
};

const getAlasanKritis = (nama, adalahPendukung = false) => {
  if (adalahPendukung) return "Dukungan kelompok ini perlu dijaga — bisa berubah kalau tidak ada komunikasi aktif.";
  const n = nama.toLowerCase();
  if (n.includes("jurnalis") || n.includes("media") || n.includes("wartawan"))
    return "Menolak karena kurangnya data dan akses informasi yang terbatas dari pemerintah.";
  if (n.includes("oposisi") || n.includes("kritis") || n.includes("lawan"))
    return "Menolak karena keyakinan — nganggap kebijakan ini tidak berpihak ke rakyat.";
  if (n.includes("mahasiswa") || n.includes("pelajar") || n.includes("aktivis") || n.includes("ormas"))
    return "Menolak karena dampak langsung yang dirasakan tidak sesuai janji.";
  if (n.includes("pengusaha") || n.includes("umkm") || n.includes("bisnis") || n.includes("wirausaha"))
    return "Menolak karena biaya jalan naik tanpa ganti rugi yang sepadan.";
  if (n.includes("akademisi") || n.includes("dosen") || n.includes("peneliti") || n.includes("ilmuwan"))
    return "Menolak berdasarkan data — hasil penelitian menunjukkan kebijakan ini kurang efektif.";
  if (n.includes("pekerja") || n.includes("kantoran") || n.includes("karyawan") || n.includes("buruh"))
    return "Menolak karena kebijakan ini dianggap nambah beban tanpa nambah kesejahteraan.";
  if (n.includes("pemerintah") || n.includes("birokrat") || n.includes("menteri") || n.includes("pejabat"))
    return "Bersikap bertahan — ngakuin kekurangan tapi nunjukin capaian yang udah ada.";
  if (n.includes("nelayan") || n.includes("petani") || n.includes("kelompok lapangan"))
    return "Menolak karena pelaksanaan di lapangan tidak sesuai kondisi nyata.";
  return "Menolak berdasarkan pengalaman langsung dan kekhawatiran yang belum terjawab.";
};

const truncateAtWord = (teks, maxChars) => {
  if (!teks || teks.length <= maxChars) return teks;
  const truncated = teks.slice(0, maxChars);
  const lastSpace = truncated.lastIndexOf(' ');
  return (lastSpace > maxChars * 0.5 ? truncated.slice(0, lastSpace) : truncated) + '…';
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

// ─── SECTION ANALOGIES — kalimat pembuka analogi ─────────────────
const ANALOGI = {
  insight: "💡 Bayangin kayak ramalan cuaca — kita lihat skenario mana yang paling mungkin terjadi.",
  risiko: "⚠️ Kayak peringatan di jalan tol — ini tanda bahaya yang perlu diwaspadai sebelum ambil keputusan.",
  rekomendasi: "🎯 Kayak saran dari teman yang udah pernah ngalamin — ini langkah yang bisa diambil biar hasilnya maksimal.",
  aktorKunci: "📢 Bayangin kayak ketua kelas — suara kelompok ini paling didengar dan bisa ngaruh ke yang lain.",
  kelompokKritis: "🔴 Kelompok yang paling keras nolak — mereka butuh perhatian khusus.",
  probabilitas: "📊 Kayak papan skor — ini peluang tiap kemungkinan hasil, makin besar angkanya makin mungkin terjadi.",
  meteranSikap: "📈 Kayak termometer — ini nunjukin perubahan sikap tiap kelompok dari awal sampai akhir diskusi.",
  transkrip: "💬 Ini catatan lengkap diskusinya — siapa bilang apa dan gimana reaksinya.",
  wordcloud: "☁️ Kata-kata yang paling sering muncul — makin besar tulisannya, makin sering kata itu dipake.",
};

// ─── InsightHero ─────────────────────────────────────────────────
const InsightHero = ({ prediksi, statusSimulasi, topik }) => {
  const sorted = Object.entries(prediksi ?? {}).sort((a, b) => b[1] - a[1]);
  if (!sorted.length) return null;
  const [skenario, prob] = sorted[0];
  const intro = INSIGHT_SKENARIO[skenario] ?? `Skenario "${skenario}" menjadi yang paling mungkin —`;
  const listOthers = sorted.slice(1).map(([s, p]) => `${s} (${p}%)`);
  const others = listOthers.length > 1
    ? listOthers.slice(0, -1).join(', ') + ' dan ' + listOthers[listOthers.length - 1]
    : listOthers[0] ?? '';
  const kalimat = others
    ? `${intro} ${prob}%, mengungguli ${others}.`
    : `${intro} ${prob}% kemungkinan.`;
  return (
    <div className="rounded-[12px] border border-[#cc785c]/20 bg-[#cc785c]/5 px-6 py-5">
      <p className="text-[11px] font-medium uppercase tracking-[1.5px] text-[#6c6a64] mb-2">Kesimpulan</p>
      <p className="text-lg leading-relaxed text-[#141413]" style={{ fontFamily: "var(--font-heading, sans-serif)" }}>
        &ldquo;{kalimat}&rdquo;
      </p>
    </div>
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

const TranskripRisalah = ({ daftarRonde, rondeAktif, setRondeAktif }) => {
  const [risalahTerbuka, setRisalahTerbuka] = useState(false);
  if (!daftarRonde?.length) return null;
  const agenPertama = daftarRonde[0]?.agen?.[0];
  const previewTeks = truncateAtWord(agenPertama?.pendapat, 200) ?? '';
  return (
    <section>
      {/* ANALOGI */}
      <p className="text-[12px] text-[#6c6a64] italic mb-6 leading-relaxed">{ANALOGI.transkrip}</p>
      <div className="flex items-center justify-between mb-6 flex-wrap gap-2">
        <h2 className="display-sm" style={{ fontWeight: 400 }}>💬 <InfoTip istilah="simulasi" ukuran="xs" /> — Catatan Diskusi</h2>
        {daftarRonde.length > 1 && (
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] text-[#6c6a64]"><InfoTip istilah="ronde" ukuran="xs" />:</span>
            {daftarRonde.map((_, i) => (
              <button key={`round-${i}`} onClick={() => setRondeAktif(i)}
                className={`h-7 min-w-[32px] rounded-[6px] px-2 text-[11px] font-medium transition ${
                  rondeAktif === i ? "bg-[#cc785c] text-white" : "bg-[#efe9de] text-[#6c6a64] hover:bg-[#e8e0d2]"
                }`}>
                {i + 1}
              </button>
            ))}
          </div>
        )}
      </div>
      {!risalahTerbuka ? (
        <div className="card">
          <p className="text-sm leading-[1.75] text-[#6c6a64] italic line-clamp-2">&ldquo;{previewTeks}&rdquo;</p>
          <button onClick={() => setRisalahTerbuka(true)}
            className="mt-3 text-sm font-medium text-[#cc785c] hover:text-[#a9583e] transition flex items-center gap-1">
            Buka Catatan Diskusi <span>▼</span>
          </button>
        </div>
      ) : (
        <div className="transition-all duration-300">
          {daftarRonde.map((ronde, rIdx) => {
            if (rIdx !== rondeAktif) return null;
            return (
              <div key={rIdx} className="card overflow-hidden">
                <HeaderRonde ronde={rIdx + 1} total={daftarRonde.length} />
                <div className="space-y-0">
                  {(ronde.agen ?? []).map((a, aIdx) => {
                    const warna = SENTIMEN[a.sentimen?.label]?.warna ?? "#6c6a64";
                    return (
                      <div key={aIdx} className="transcript-entry">
                        <div className="flex items-start gap-4">
                          <div className="flex items-center gap-2.5 min-w-0 shrink-0">
                            <div className="h-8 w-8 shrink-0 rounded-full flex items-center justify-center text-[10px] font-bold"
                              style={{ backgroundColor: warna + "18", border: `1px solid ${warna}44`, color: warna }}>
                              {a.nama.slice(0, 2).toUpperCase()}
                            </div>
                          </div>
                          <div className="min-w-0 flex-1">
                            <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                              <span className="text-sm font-semibold text-[#141413]">{a.nama}</span>
                              <BadgeSentimen label={a.sentimen?.label} />
                            </div>
                            <p className="text-sm leading-[1.75] text-[#3d3d3a]" style={{ letterSpacing: "0.01em" }}>
                              &ldquo;{a.pendapat}&rdquo;
                            </p>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
                <button onClick={() => setRisalahTerbuka(false)}
                  className="mt-4 text-sm font-medium text-[#cc785c] hover:text-[#a9583e] transition flex items-center gap-1">
                  Tutup Catatan <span>▲</span>
                </button>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
};

const StaticBarChart = ({ meterData }) => (
  <div className="space-y-4">
    {meterData.map((ag) => (
      <div key={ag.nama}>
        <div className="flex items-center gap-2 mb-1.5">
          <span className="text-sm font-medium text-[#141413] break-words">{ag.nama}</span>
          <span className={`inline-flex items-center gap-1 rounded-[9999px] px-2 py-0.5 text-[10px] font-medium whitespace-nowrap shrink-0 ${ag.skorLabel.bg}`}
            style={{ color: ag.skorLabel.warna, backgroundColor: ag.skorLabel.warna + "15", border: `1px solid ${ag.skorLabel.warna}30` }}>
            {ag.skorLabel.label}
          </span>
        </div>
        <div className="relative h-7 rounded-[9999px] bg-[#e6dfd8] overflow-hidden">
          <div className="h-full rounded-[9999px] transition-all flex items-center justify-end pr-2"
            style={{ width: `${ag.akhir}%`, backgroundColor: ag.skorLabel.warna, minWidth: ag.akhir > 0 ? '20px' : '0' }}>
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
    return { nama, skorLabel, skorRonde, warna: WARNA_AGEN[i % WARNA_AGEN.length], awal, akhir, selisih: akhir - awal };
  });
  const isSingleRound = totalRonde === 1;
  return (
    <section>
      {/* ANALOGI */}
      <p className="text-[12px] text-[#6c6a64] italic mb-6 leading-relaxed">{ANALOGI.meteranSikap}</p>
      <h2 className="display-sm mb-4" style={{ fontWeight: 400 }}>📊 <InfoTip istilah="meteranSikap" ukuran="xs" /></h2>
      
      {/* LEGEND WARNA — biar orang awam paham arti warna */}
      <div className="flex flex-wrap items-center gap-3 mb-5 text-[11px] text-[#6c6a64]">
        <span className="font-medium">Arti warna:</span>
        <span className="inline-flex items-center gap-1">
          <span className="w-3 h-3 rounded-full bg-[#c64545]" /> Menolak
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="w-3 h-3 rounded-full bg-[#d4a017]" /> Netral
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="w-3 h-3 rounded-full bg-[#5db872]" /> Mendukung
        </span>
      </div>

      <div className="card overflow-hidden">
        {isSingleRound ? (
          <>
            <p className="text-[12px] text-[#6c6a64] mb-1 leading-relaxed">
              Skor <InfoTip istilah="sentimen" ukuran="xs" /> terakhir tiap kelompok berdasarkan simulasi.
            </p>
            <p className="text-[11px] text-[#6c6a64] italic mb-5">
              💡 Coba jalankan lebih dari 1 <InfoTip istilah="ronde" ukuran="xs" /> untuk melihat pergerakan sikap antar babak.
            </p>
            <div className="flex items-center gap-3 mb-4 text-[10px] text-[#6c6a64]">
              <span>🔴 Menolak (0)</span>
              <span className="flex-1 h-px bg-[#e6dfd8]" />
              <span>🟢 Mendukung (100)</span>
            </div>
            <StaticBarChart meterData={meterData} />
          </>
        ) : (
          <>
            <p className="text-[12px] text-[#6c6a64] mb-5 leading-relaxed">
              Perubahan <InfoTip istilah="sentimen" ukuran="xs" /> tiap kelompok dari babak ke babak.
              Titik <strong className="text-[#141413]">bulat</strong> = posisi per babak · garis = arah perubahan.
            </p>
            {/* Legend meter */}
            <div className="flex items-center gap-3 mb-6 text-[10px] text-[#6c6a64]">
              <span>🔴 Menolak</span>
              <div className="relative flex-1 h-3 rounded-[9999px]" style={{
                background: "linear-gradient(to right, #c64545, #8e8b82 25%, #6c6a64 50%, #8e8b82 75%, #5db872)",
                opacity: 0.3,
              }} />
              <span>🟢 Mendukung</span>
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
                      <span className={`inline-flex items-center gap-1 rounded-[9999px] px-2 py-0.5 text-[10px] font-medium whitespace-nowrap shrink-0 ${ag.skorLabel.bg}`}
                        style={{ color: ag.skorLabel.warna, backgroundColor: ag.skorLabel.warna + "15", border: `1px solid ${ag.skorLabel.warna}30` }}>
                        {ag.skorLabel.label}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <span className="text-[10px] text-[#6c6a64] whitespace-nowrap">
                        {ag.awal}→{ag.akhir}{ag.selisih > 0 ? ` +${ag.selisih}` : ag.selisih < 0 ? ` ${ag.selisih}` : ""}
                      </span>
                      <span className="text-[10px] font-medium" style={{ color: ag.warna }}>
                        {ag.selisih > 0 ? "↗ Menguat" : ag.selisih < 0 ? "↘ Melemah" : "→ Stabil"}
                      </span>
                    </div>
                  </div>
                  <svg width="100%" height="28" viewBox="0 0 400 28" preserveAspectRatio="none" className="overflow-visible">
                    <rect x="0" y="11" width="400" height="6" rx="3" fill="url(#grad-bg)" opacity="0.3" />
                    {ag.skorRonde.length > 1 && (
                      <polyline fill="none" stroke={ag.warna} strokeWidth="2" strokeOpacity="0.5"
                        strokeDasharray={ag.skorRonde.length > 2 ? "3 2" : "none"}
                        points={ag.skorRonde.map((s, i) => {
                          const x = (400 / (totalRonde)) * i + (400 / (totalRonde + 1));
                          const y = 14 - (s - 50) * 0.1;
                          return `${x},${y}`;
                        }).join(" ")} />
                    )}
                    {ag.skorRonde.map((s, i) => {
                      const x = (400 / (totalRonde)) * i + (400 / (totalRonde + 1));
                      const y = 14 - (s - 50) * 0.1;
                      const isFirst = i === 0;
                      const isLast = i === ag.skorRonde.length - 1;
                      return (
                        <g key={i}>
                          <circle cx={x} cy={y} r={isFirst || isLast ? 5 : 3.5}
                            fill={isFirst || isLast ? ag.warna : "#faf9f5"}
                            stroke={ag.warna} strokeWidth="2" />
                        </g>
                      );
                    })}
                    <defs>
                      <linearGradient id="grad-bg" x1="0%" y1="0%" x2="100%" y2="0%">
                        <stop offset="0%" stopColor="#c64545" />
                        <stop offset="50%" stopColor="#6c6a64" />
                        <stop offset="100%" stopColor="#5db872" />
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

const SectionRisiko = ({ risikoUtama }) => {
  if (!risikoUtama) return null;
  return (
    <section>
      {/* ANALOGI */}
      <p className="text-[12px] text-[#6c6a64] italic mb-6 leading-relaxed">{ANALOGI.risiko}</p>
      <h2 className="display-sm mb-4" style={{ fontWeight: 400 }}>⚠️ Yang Perlu Diwaspadai</h2>
      <div className="rounded-[12px] border border-[#c64545]/30 bg-[#c64545]/5 px-5 py-4">
        <div className="flex items-start gap-3">
          <svg className="shrink-0 mt-0.5" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#c64545" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
            <line x1="12" y1="9" x2="12" y2="13" /><line x1="12" y1="17" x2="12.01" y2="17" />
          </svg>
          <p className="text-sm leading-relaxed text-[#3d3d3a]">{beresinTeksAkhir(risikoUtama)}</p>
        </div>
      </div>
    </section>
  );
};

const SectionRekomendasi = ({ rekomendasi, rekomendasiStrategis, aktorKunci, sentimenAgr, tier }) => {
  const ada = rekomendasi || rekomendasiStrategis?.length > 0 || aktorKunci?.length > 0;
  if (!ada) return null;
  const prioritas = aktorKunci?.[0] ?? null;
  const cariSwing = () => {
    if (!sentimenAgr || !Object.keys(sentimenAgr).length) return null;
    const entries = Object.entries(sentimenAgr).map(([nama, skorArr]) => {
      const akhir = Math.round(((skorArr[skorArr.length - 1] ?? 0) + 1) * 50);
      return { nama, skor: akhir, jarak: Math.abs(akhir - 50) };
    });
    entries.sort((a, b) => a.jarak - b.jarak);
    return entries[0] ?? null;
  };
  const swing = cariSwing();
  return (
    <section>
      {/* ANALOGI */}
      <p className="text-[12px] text-[#6c6a64] italic mb-6 leading-relaxed">{ANALOGI.rekomendasi}</p>
      <div className="flex items-center gap-3 mb-4 flex-wrap">
        <h2 className="display-sm" style={{ fontWeight: 400 }}>🎯 <InfoTip istilah="rekomendasi" ukuran="xs" /></h2>
        {tier === "free" && (
          <span className="inline-flex items-center gap-1 text-[11px] px-2.5 py-0.5 rounded-full bg-[#efe9de] text-[#6c6a64] font-medium">
            ⚡ Mode Cepat — saran umum berdasarkan data statistik
          </span>
        )}
      </div>
      <div className="card space-y-5">
        {prioritas && (
          <div>
            <p className="text-[13px] font-bold text-[#141413] uppercase tracking-[0.5px] mb-3">🎯 Prioritas Utama</p>
            <div className="rounded-[12px] border border-[#cc785c]/20 bg-[#cc785c]/5 p-4">
              <p className="text-sm leading-relaxed text-[#3d3d3a]">→ {prioritas.cara_pendekatan || getPendekatan(prioritas.nama)}</p>
            </div>
          </div>
        )}
        {swing && swing.nama !== prioritas?.nama && (
          <div>
            <p className="text-[13px] font-bold text-[#141413] uppercase tracking-[0.5px] mb-3">🔄 Kelompok yang Bisa Berubah Pikiran</p>
            <div className="rounded-[12px] border border-[#d4a017]/20 bg-[#d4a017]/5 p-4">
              <p className="text-sm font-semibold text-[#141413] mb-1">
                Kelompok yang masih bisa dipengaruhi: {swing.nama} (skor {swing.skor}, Netral)
              </p>
              <p className="text-sm leading-relaxed text-[#3d3d3a]">→ {getPendekatan(swing.nama)}</p>
            </div>
          </div>
        )}
        {rekomendasiStrategis?.length > 0 && (
          <div>
            <p className="text-[13px] font-medium text-[#6c6a64] uppercase tracking-[0.5px] mb-3">Langkah tambahan:</p>
            <div className="space-y-3">
              {rekomendasiStrategis.map((item, i) => (
                <div key={`rec-${i}`} className="flex items-start gap-3">
                  <div className="h-6 w-6 rounded-full bg-[#cc785c]/10 border border-[#cc785c]/25 flex items-center justify-center text-xs font-bold text-[#cc785c] shrink-0 mt-0.5">
                    {i + 1}
                  </div>
                  <p className="text-sm leading-relaxed text-[#3d3d3a]">{beresinTeksAkhir(item)}</p>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </section>
  );
};

const SectionKelompokKritis = ({ kelompokKritis }) => {
  if (!kelompokKritis?.length) return null;
  return (
    <section>
      {/* ANALOGI */}
      <p className="text-[12px] text-[#6c6a64] italic mb-6 leading-relaxed">{ANALOGI.kelompokKritis}</p>
      <div className="flex items-center gap-2 mb-4">
        <span className="text-sm">🔴</span>
        <p className="text-[11px] font-medium uppercase tracking-[1.5px] text-[#141413]">Perlu Perhatian Khusus</p>
      </div>
      <h2 className="display-sm mb-6" style={{ fontWeight: 400 }}>Kelompok yang Paling Keras Menolak</h2>
      <div className="space-y-3">
        {kelompokKritis.map((k) => (
          <div key={k.nama} className="rounded-[12px] border border-[#c64545]/25 bg-[#c64545]/5 p-4">
            <div className="flex items-center gap-2 mb-2">
              <div className="h-7 w-7 rounded-full bg-[#c64545]/10 border border-[#c64545]/20 flex items-center justify-center text-xs font-bold text-[#c64545] shrink-0">
                {k.nama.slice(0, 2).toUpperCase()}
              </div>
              <span className="text-sm font-semibold text-[#141413]">{k.nama}</span>
            </div>
            <p className="text-xs text-[#6c6a64] mb-1"><span className="text-[#c64545] font-medium">Kenapa nolak:</span> {k.alasan || getAlasanKritis(k.nama)}</p>
            <p className="text-xs text-[#3d3d3a]"><span className="text-[#d4a017] font-medium">Cara mendekati:</span> {k.cara_pendekatan || getPendekatan(k.nama)}</p>
          </div>
        ))}
      </div>
    </section>
  );
};

const SectionAktorKunci = ({ aktorKunci, penggerak }) => {
  if (!aktorKunci?.length) return null;
  return (
    <section>
      {/* ANALOGI */}
      <p className="text-[12px] text-[#6c6a64] italic mb-6 leading-relaxed">{ANALOGI.aktorKunci}</p>
      <h2 className="display-sm mb-6" style={{ fontWeight: 400 }}>📢 <InfoTip istilah="aktorKunci" ukuran="xs" /></h2>
      <div className="card">
        <div className="grid gap-3 sm:grid-cols-2">
          {aktorKunci.map((a, i) => {
            const w = WARNA_AGEN[i % WARNA_AGEN.length];
            const lb = a.sikap_label ?? "Netral";
            const lbWarna = lb === "Mendukung" ? "#5db872" : lb === "Menolak" ? "#c64545" : "#6c6a64";
            return (
              <div key={a.nama} className="rounded-[12px] border border-[#e6dfd8] bg-[#faf9f5] p-4">
                <div className="flex items-center gap-2 mb-1.5">
                  <div className="h-8 w-8 rounded-full flex items-center justify-center text-xs font-black shrink-0"
                    style={{ backgroundColor: w + "20", border: `1.5px solid ${w}`, color: w }}>
                    {a.nama.slice(0, 2).toUpperCase()}
                  </div>
                  <span className="text-sm font-semibold text-[#141413] flex-1 truncate">{a.nama}</span>
                  <span className="rounded-[9999px] px-2.5 py-0.5 text-[11px] font-medium"
                    style={{ color: lbWarna, borderColor: lbWarna + "40", backgroundColor: lbWarna + "15" }}>
                    {lb}
                  </span>
                </div>
                <p className="text-sm leading-relaxed text-[#3d3d3a]">{beresinTeksAkhir(a.alasan)}</p>
              </div>
            );
          })}
        </div>
        {penggerak && (
          <div className="mt-4 rounded-[12px] bg-[#faf9f5] border border-[#e6dfd8] px-4 py-3 flex items-center gap-3">
            <span className="text-lg" style={{ lineHeight: 1 }}>⚡</span>
            <div>
              <p className="text-[11px] font-medium uppercase tracking-[1px] text-[#6c6a64]">Kelompok Paling Berpengaruh</p>
              <p className="text-sm font-semibold text-[#141413]">{penggerak}</p>
            </div>
          </div>
        )}
      </div>
    </section>
  );
};

// ═══════════════════════════════════════════════════════════════════
//  MAIN PAGE
// ═══════════════════════════════════════════════════════════════════
export default function HalamanSimulasi() {
  const [terpasang]       = useState(true);
  const [topik,           setTopik]           = useState("");
  const [kategori,        setKategori]        = useState("Umum");
  const [jumlahRonde,     setJumlahRonde]     = useState(3);
  const [hasil,           setHasil]           = useState(null);
  const [memuat,          setMemuat]          = useState(false);
  const [tier,            setTier]            = useState("free");
  const [warningTopik,    setWarningTopik]    = useState(null);
  const [rondeAktif,      setRondeAktif]      = useState(0);
  const [ringkasanPenuh,  setRingkasanPenuh]  = useState(false);

  const inputRef = useRef(null);
  const hasilRef = useRef(null);
  const apiBase  = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

  const mulaiAnalisis = async () => {
    if (!topik.trim()) { inputRef.current?.focus(); return; }
    setMemuat(true);
    setHasil(null);
    setRondeAktif(0);
    setRingkasanPenuh(false);
    try {
      const body = { topik: topik.trim(), kategori, jumlah_ronde: jumlahRonde, tier };
      const res = await fetch(`${apiBase}/start-simulation`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        alert("❌ " + (err.detail || "Permintaan gagal."));
        setMemuat(false);
        return;
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

  const daftarRonde           = hasil?.ronde_detail ?? [];
  const rondeTerakhir         = daftarRonde[daftarRonde.length - 1] ?? null;
  const agenAkhir             = rondeTerakhir?.agen ?? [];
  const analisis              = hasil?.analisis ?? "";
  const prediksi              = hasil?.prediksi ?? {};
  const sentimenAgr           = hasil?.sentimen_agregat ?? {};
  const aktorAnalisis         = hasil?.aktor_analisis ?? null;
  const aktorKunci            = aktorAnalisis?.aktor_kunci ?? [];
  const rekomendasi           = aktorAnalisis?.rekomendasi ?? "";
  const rekomendasiStrategis  = hasil?.rekomendasi_strategis ?? [];
  const risikoUtama           = hasil?.risiko_utama ?? "";
  const kelompokKritis        = aktorAnalisis?.kelompok_kritis ?? [];
  const penggerak             = aktorAnalisis?.aktor_penggerak ?? "";

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
  const jmlMenolak   = agenAkhir.filter(a => a.sentimen?.label === "negatif").length;
  const jmlNetral    = agenAkhir.filter(a => a.sentimen?.label === "netral").length;

  let statusSimulasi = { label: "Belum Ada", warna: "#6c6a64", desk: "" };
  if (Object.keys(prediksi).length > 0) {
    const sorted = Object.entries(prediksi).sort((a, b) => b[1] - a[1]);
    const p = sorted[0];
    if (p[0] === "Semua Setuju" || p[0] === "Konsensus") {
      statusSimulasi = { label: "Sepakat", warna: "#5db872", desk: "Semua kelompok sepakat — opini publik cenderung positif." };
    } else if (p[0] === "Masyarakat Terpecah" || p[0] === "Polarisasi") {
      statusSimulasi = { label: "Terbelah", warna: "#c64545", desk: "Pendapat peserta terbelah — perlu perhatian serius." };
    } else {
      statusSimulasi = { label: "Stabil", warna: "#d4a017", desk: "Pendapat peserta cenderung stabil sepanjang simulasi." };
    }
  } else if (agenAkhir.length > 0) {
    if (jmlMendukung > jmlMenolak && jmlMendukung > jmlNetral)
      statusSimulasi = { label: "Cenderung Setuju", warna: "#5db872", desk: "Mayoritas peserta setuju dengan isu ini." };
    else if (jmlMenolak > jmlMendukung && jmlMenolak > jmlNetral)
      statusSimulasi = { label: "Cenderung Menolak", warna: "#c64545", desk: "Mayoritas peserta tidak setuju dengan isu ini." };
    else
      statusSimulasi = { label: "Pendapat Terbagi", warna: "#d4a017", desk: "Pendapat peserta terbagi rata." };
  }

  const handleSimpanPDF  = () => eksporPDF(hasil, topik, analisis, aktorAnalisis, null);
  const handleSimpanCSV  = () => eksporCSV(hasil, topik);
  const handleSimpanWord = () => eksporWord(hasil, topik, analisis).catch(e => alert(e.message));

  if (!terpasang) return null;

  return (
    <div className="flex flex-col bg-[#faf9f5] min-h-screen">

      {/* ════════ HERO + FORM — satu wrapper biar lebar selalu sama ════════ */}
      <div className="mx-auto w-full max-w-4xl px-4 md:px-6">

        {/* Hero */}
        <section className="pt-10 pb-6">
          <p className="caption-uppercase mb-4">
            <InfoTip istilah="simulasi" ukuran="xs" /> Opini Publik
          </p>
          <h1 className="display-xl mb-3">
            Simulasi Opini Publik
          </h1>
          <p className="text-base leading-[1.75] text-[#3d3d3a]" style={{ letterSpacing: "0.01em" }}>
            Masukkan topik — alat ini bakal mensimulasikan gimana berbagai kelompok masyarakat nanggapapi dan berdebat.
            <br />Hasilnya <strong>bukan</strong> survei beneran, tapi gambaran awal buat referensi.
          </p>
        </section>

        {/* Form Input — label pake bahasa sederhana + tooltip jelas */}
        <section className="pb-6">
          <div className="card">
            <div className="mb-5 flex flex-col gap-3 sm:flex-row">
              <input
                ref={inputRef}
                className="input-text flex-1"
                value={topik}
                onChange={e => setTopik(e.target.value.slice(0, 300))}
                onKeyDown={e => e.key === "Enter" && mulaiAnalisis()}
                placeholder='Contoh: "Apakah kenaikan UMP 2025 menguntungkan buruh atau merugikan UMKM?"'
              />
              <button onClick={mulaiAnalisis} disabled={memuat} className="btn-primary shrink-0">
                {memuat ? "Memproses…" : "Jalankan Simulasi"}
              </button>
            </div>

            <div className="flex flex-wrap items-center gap-5 text-sm text-[#3d3d3a]">
              {/* Kategori */}
              <div className="flex items-center gap-2">
                <span className="text-[13px] text-[#6c6a64]">Jenis topik:</span>
                <select value={kategori} onChange={e => setKategori(e.target.value)} className="select-input">
                  {["Umum","Ekonomi","Politik","Sosial","Hukum","Teknologi"].map(k =>
                    <option key={k} value={k}>{k}</option>
                  )}
                </select>
              </div>
              {/* Putaran */}
              <div className="flex items-center gap-2">
                <span className="text-[13px] text-[#6c6a64]" title="Makin banyak putaran, makin detail hasilnya tapi makin lama nunggu">
                  <InfoTip istilah="ronde" ukuran="xs" />:
                </span>
                <div className="flex gap-1">
                  {[1,2,3,4,5].map(n => (
                    <button key={n} onClick={() => setJumlahRonde(n)}
                      className={`h-7 w-7 rounded-[6px] text-xs font-medium transition ${
                        jumlahRonde === n
                          ? "bg-[#cc785c] text-white"
                          : "bg-[#efe9de] text-[#6c6a64] hover:bg-[#e8e0d2]"
                      }`}
                      title={`${n} putaran diskusi`}>
                      {n}
                    </button>
                  ))}
                </div>
              </div>
              {/* Mode — tooltip pake bahasa rakyat */}
              <div className="flex items-center gap-2">
                <span className="text-[13px] text-[#6c6a64]">Ketelitian:</span>
                <button onClick={() => setTier("free")}
                  className={`rounded-[9999px] px-3 py-1.5 text-xs font-medium transition ${
                    tier === "free" ? "bg-[#cc785c] text-white" : "bg-[#efe9de] text-[#6c6a64] hover:bg-[#e8e0d2]"
                  }`}
                  title="Saran disusun otomatis dari data statistik. Cepet, cocok buat coba-coba.">
                  ⚡ Cepat
                </button>
                <button onClick={() => setTier("normal")}
                  className={`rounded-[9999px] px-3 py-1.5 text-xs font-medium transition ${
                    tier === "normal" ? "bg-[#cc785c] text-white" : "bg-[#efe9de] text-[#6c6a64] hover:bg-[#e8e0d2]"
                  }`}
                  title="Saran dianalisis AI berdasarkan hasil diskusi. Lebih dalam, cocok buat analisis serius.">
                  🐢 Lengkap
                </button>
              </div>
            </div>
          </div>
        </section>

      </div>{/* end shared wrapper */}

      {/* ════════ LOADING — pake bahasa sederhana ════════ */}
      {memuat && (
        <section className="mx-auto mt-2 w-full max-w-4xl px-4 md:px-6 pb-16">
          <div className="card text-center py-16">
            <div className="mx-auto mb-8 flex w-fit gap-2">
              {[0,1,2,3].map(i => (
                <div key={i} className="loading-dot h-2 w-2 rounded-full bg-[#cc785c]"
                  style={{ animationDelay: `${i * 0.15}s` }} />
              ))}
            </div>
            <p className="display-sm mb-2">⏳ Lagi simulasi diskusi…</p>
            <p className="mb-8 text-sm text-[#6c6a64]">
              {jumlahRonde} putaran · estimasi {jumlahRonde * 10}–{jumlahRonde * 20} detik
            </p>
            <div className="mx-auto max-w-xs space-y-3 text-left">
              {[
                "1️⃣ Nyiapin peserta dari berbagai latar belakang",
                "2️⃣ Nyimulasiin diskusi antar kelompok",
                "3️⃣ Ngecek sikap dan perubahan pendapat",
                "4️⃣ Nyusun saran langkah ke depan",
              ].map((step, i) => (
                <div key={i} className="flex items-center gap-3">
                  <div className="h-5 w-5 rounded-full border border-[#cc785c]/30 bg-[#cc785c]/8 flex items-center justify-center shrink-0">
                    <div className="h-1.5 w-1.5 rounded-full bg-[#cc785c]/50" />
                  </div>
                  <p className="text-xs text-[#6c6a64]">{step}</p>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* ════════ EMPTY STATE ════════ */}
      {!hasil && !memuat && (
        <section className="mx-auto w-full max-w-4xl px-4 md:px-6 pb-16">
          <div className="card" style={{ textAlign: "center", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", minHeight: "220px", gap: "24px" }}>
            <div className="relative">
              <svg width="64" height="56" viewBox="0 0 64 56" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect x="2" y="2" width="40" height="28" rx="10" fill="#cc785c" fillOpacity="0.12" stroke="#cc785c" strokeOpacity="0.3" strokeWidth="1.5"/>
                <rect x="22" y="18" width="40" height="28" rx="10" fill="#6c6a64" fillOpacity="0.08" stroke="#6c6a64" strokeOpacity="0.2" strokeWidth="1.5"/>
                <circle cx="13" cy="16" r="2.5" fill="#cc785c" fillOpacity="0.5"/>
                <circle cx="22" cy="16" r="2.5" fill="#cc785c" fillOpacity="0.5"/>
                <circle cx="31" cy="16" r="2.5" fill="#cc785c" fillOpacity="0.5"/>
              </svg>
            </div>
            <p className="text-sm text-[#6c6a64] max-w-sm leading-relaxed">
              Ketik topik di atas atau pilih salah satu contoh di bawah buat mulai simulasi.
            </p>
            <div className="flex flex-col items-center gap-3 w-full">
              <p className="text-[11px] font-medium uppercase tracking-[1.2px] text-[#6c6a64]">Coba topik ini</p>
              <div className="flex flex-wrap justify-center gap-2">
                {[
                  "Apakah kenaikan UMP 2025 menguntungkan buruh?",
                  "Apakah kebijakan ganjil genap efektif di kota besar?",
                  "Apakah program MBG sudah tepat sasaran?",
                ].map((teks) => (
                  <button key={teks} onClick={() => { setTopik(teks); inputRef.current?.focus(); }}
                    className="px-4 py-2 text-[13px] border border-[#e6dfd8] rounded-full text-[#3d3d3a] hover:border-[#cc785c]/50 hover:bg-[#cc785c]/5 hover:text-[#cc785c] transition-all cursor-pointer">
                    {teks}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </section>
      )}

      {/* ════════ HASIL SIMULASI ════════ */}
      {hasil && (
        <div ref={hasilRef} className="mx-auto mt-8 w-full max-w-4xl px-4 pb-8 md:px-6 space-y-10">

          {/* Status bar */}
          <div className="flex flex-wrap items-center gap-3 pb-2 border-b border-[#e6dfd8]">
            <span className="inline-flex items-center gap-2 rounded-[9999px] px-3 py-1.5 text-[12px] font-semibold"
              style={{ backgroundColor: statusSimulasi.warna + "15", color: statusSimulasi.warna, border: `1px solid ${statusSimulasi.warna}30` }}>
              <span className="h-2 w-2 rounded-full" style={{ backgroundColor: statusSimulasi.warna }} />
              {statusSimulasi.label}
            </span>
            <span className="text-[12px] text-[#6c6a64]">{daftarRonde.length} putaran · {agenAkhir.length} peserta</span>
            {warningTopik && (
              <span className="inline-flex items-center gap-1.5 text-[11px] text-[#d4a017] bg-[#d4a017]/8 border border-[#d4a017]/20 rounded-full px-3 py-1">
                ⚠ {warningTopik}
              </span>
            )}
            {(() => {
              const dt = hasil?.data_transparency;
              if (!dt || dt.briefing_status === "full") return null;
              const isEmpty = dt.briefing_status === "empty";
              const label = isEmpty
                ? "Info Awal Kosong"
                : dt.polling_reference_matched
                  ? "Info Awal dari Jajak Pendapat"
                  : "Info Awal Terbatas";
              const bg = isEmpty ? "bg-red-100 text-red-700 border-red-200" : "bg-amber-100 text-amber-700 border-amber-200";
              return (
                <span className={`inline-flex items-center gap-1.5 text-[11px] font-medium rounded-full px-3 py-1 border ${bg}`}
                      title={dt.note}>
                  {isEmpty ? "⚠" : "📋"} {label} <InfoTip istilah="brief" ukuran="xs" />
                </span>
              );
            })()}
          </div>

          {/* Ringkasan */}
          {ringkasan && (
            <div className="rounded-[12px] border-l-2 border-[#cc785c] bg-[#cc785c]/3 pl-5 pr-4 py-4">
              <p className="text-sm leading-[1.85] text-[#3d3d3a] italic">{ringkasan}</p>
              {ringkasanTerpotong && (
                <button onClick={() => setRingkasanPenuh(!ringkasanPenuh)}
                  className="mt-2 text-[11px] font-medium text-[#cc785c] hover:text-[#a9583e] transition inline-flex items-center gap-1">
                  {ringkasanPenuh ? "Tutup ▲" : "Lihat selengkapnya…"}
                </button>
              )}
            </div>
          )}

          {/* INSIGHT */}
          <section>
            <p className="text-[12px] text-[#6c6a64] italic mb-6 leading-relaxed">{ANALOGI.insight}</p>
            <InsightHero prediksi={prediksi} statusSimulasi={statusSimulasi} topik={topik} />
          </section>

          {/* RISIKO */}
          <SectionRisiko risikoUtama={risikoUtama} />

          {/* REKOMENDASI */}
          <SectionRekomendasi rekomendasi={rekomendasi} rekomendasiStrategis={rekomendasiStrategis} aktorKunci={aktorKunci} sentimenAgr={sentimenAgr} tier={tier} />

          {/* AKTOR KUNCI */}
          <SectionAktorKunci aktorKunci={aktorKunci} penggerak={penggerak} />

          {/* KELOMPOK KRITIS */}
          <SectionKelompokKritis kelompokKritis={kelompokKritis} />

          {/* PROBABILITAS — pake label sederhana */}
          {Object.keys(prediksi).length > 0 && (
            <section>
              <p className="text-[12px] text-[#6c6a64] italic mb-6 leading-relaxed">{ANALOGI.probabilitas}</p>
              <h2 className="display-sm mb-6" style={{ fontWeight: 400 }}>📊 Kemungkinan Hasil <InfoTip istilah="probabilitas" ukuran="xs" /></h2>
              <div className="card">
                <div className="space-y-4">
                  {Object.entries(prediksi).sort((a, b) => b[1] - a[1]).map(([k, v], i) => {
                    const w = {
                      "Semua Setuju": "#5db872", "Konsensus": "#5db872",
                      "Masyarakat Terpecah": "#c64545", "Polarisasi": "#c64545",
                      "Tidak Ada Perubahan": "#6c6a64", "Status Quo": "#6c6a64",
                    }[k] ?? "#252523";
                    const desk = DESKRIPSI_SKENARIO[k] ?? "";
                    const tertinggi = i === 0;
                    return (
                      <div key={k} className={`rounded-[10px] p-3 transition ${tertinggi ? "border border-[#cc785c]/30 bg-[#cc785c]/5" : ""}`}>
                        <div className="flex items-center gap-3">
                          <span className="w-36 shrink-0 text-sm text-[#141413] font-medium">{k}</span>
                          <div className="flex-1 h-4 rounded-[9999px] bg-[#e6dfd8] overflow-hidden">
                            <div className="h-full rounded-[9999px] transition-all" style={{ width: `${v}%`, backgroundColor: w }} />
                          </div>
                          <span className="w-9 shrink-0 text-right text-sm font-bold" style={{ color: w }}>{v}%</span>
                          {tertinggi && (
                            <span className="rounded-[9999px] bg-[#cc785c]/10 border border-[#cc785c]/25 px-2.5 py-0.5 text-[10px] font-bold text-[#cc785c] whitespace-nowrap">
                              Paling Mungkin
                            </span>
                          )}
                        </div>
                        {desk && <p className="mt-1.5 text-[11px] text-[#6c6a64] leading-relaxed pl-0 sm:pl-[152px]">{desk}</p>}
                      </div>
                    );
                  })}
                </div>
                <p className="mt-4 text-xs text-[#6c6a64] italic">* Hasil ini cuma gambaran awal berdasarkan pengaturan yang dipake, bukan prediksi pasti.</p>
              </div>
            </section>
          )}

          {/* METERAN SIKAP */}
          {Object.keys(sentimenAgr).length > 0 && (
            <MeteranSikap sentimenAgr={sentimenAgr} daftarRonde={daftarRonde} />
          )}

          {/* WORDCLOUD */}
          {hasil?.wordcloud && (
            <section>
              <p className="text-[12px] text-[#6c6a64] italic mb-6 leading-relaxed">{ANALOGI.wordcloud}</p>
              <WordCloud data={hasil.wordcloud} />
            </section>
          )}

          {/* TRANSCRIPT */}
          <TranskripRisalah daftarRonde={daftarRonde} rondeAktif={rondeAktif} setRondeAktif={setRondeAktif} />

          {/* DISCLAIMER — pake bahasa santai */}
          <div className="rounded-[12px] border border-[#e6dfd8] bg-[#f5f0e8]/60 px-4 py-4">
            <div className="flex items-start gap-2.5">
              <span className="text-sm shrink-0 mt-0.5">💡</span>
              <div>
                <p className="text-[11px] font-bold text-[#141413] mb-1 uppercase tracking-[0.5px]">Yang Perlu Kamu Tahu</p>
                <p className="text-xs text-[#6c6a64] leading-relaxed">
                  Alat ini cuma buat simulasi dan referensi awal aja — <strong>bukan</strong> pengganti survei sungguhan atau riset resmi.
                  Hasilnya tergantung topik yang kamu kasih dan konfigurasi yang dipake. Jadi jangan jadikan ini satu-satunya acuan buat ambil keputusan, ya!
                </p>
              </div>
            </div>
          </div>

          {/* Tombol export */}
          <div className="flex flex-wrap items-center justify-between gap-3 print-hidden pt-2 border-t border-[#e6dfd8]">
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-[9999px] border border-[#e6dfd8] px-3 py-1 text-[11px] text-[#6c6a64]">
                {daftarRonde.length} putaran · {agenAkhir.length} peserta
              </span>
              <span className="rounded-[9999px] border border-[#e6dfd8] px-3 py-1 text-[11px] text-[#6c6a64]">
                {statusSimulasi.label}
              </span>
            </div>
            <div className="flex flex-wrap gap-2">
              {[
                { label: "PDF", handler: handleSimpanPDF },
                { label: "CSV", handler: handleSimpanCSV },
                { label: "Word", handler: handleSimpanWord },
              ].map(({ label, handler }) => (
                <button key={label} onClick={handler}
                  className="inline-flex items-center gap-1.5 rounded-[8px] border border-[#e6dfd8] bg-white px-3 py-1.5 text-xs font-medium text-[#3d3d3a] hover:border-[#cc785c]/40 hover:bg-[#cc785c]/5 hover:text-[#cc785c] transition-all">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                    <polyline points="7 10 12 15 17 10"/>
                    <line x1="12" y1="15" x2="12" y2="3"/>
                  </svg>
                  {label}
                </button>
              ))}
            </div>
          </div>

          {/* Reset */}
          <div className="pb-6 text-center print-hidden">
            <button
              onClick={() => { setHasil(null); setTopik(""); setRondeAktif(0); setTimeout(() => { inputRef.current?.focus(); window.scrollTo({ top: 0, behavior: "smooth" }); }, 100); }}
              className="text-xs text-[#6c6a64] underline underline-offset-4 hover:text-[#141413] transition">
            Mulai analisis baru
            </button>
          </div>

        </div>
      )}

      {/* TOMBOL GLOSARIUM — floating di pojok kanan bawah */}
      <GlossaryButton />

    </div>
  );
}
