"use client";
import { useState, useRef, useEffect } from "react";

// ─── Glosarium Istilah ───────────────────────────────────────────
// Semua istilah teknis dijelasin pake bahasa sehari-hari + analogi
const GLOSARIUM = {
  simulasi: {
    label: "Simulasi",
    arti: "Tiruan atau percobaan. Kayak main game — kita cobain skenario 'bagaimana kalau...' tanpa bikin dampak beneran di dunia nyata.",
  },
  agen: {
    label: "Agen / Peserta",
    arti: "Perwakilan dari suatu kelompok masyarakat yang 'duduk' di simulasi. Bayangin kayak perwakilan OSIS — setiap agen mewakili suara kelompoknya masing-masing.",
  },
  sentimen: {
    label: "Sentimen / Sikap",
    arti: "Pendirian atau perasaan suatu kelompok terhadap topik yang dibahas. Tiap agen punya 3 sikap: Setuju (⬆), Netral (➡), atau Tidak Setuju (⬇).",
  },
  polarisasi: {
    label: "Polarisasi",
    arti: "Kondisi dimana masyarakat terbelah jadi dua kubu yang saling bertolak belakang. Kayak pertandingan sepak bola — pendukung tim A dan tim B saling ngotot beda pendapat.",
  },
  probabilitas: {
    label: "Probabilitas / Kemungkinan",
    arti: "Angka persentase yang ngasih tau seberapa besar kemungkinan suatu hasil akan terjadi. 0% = mustahil, 100% = pasti. Kayak ramalan cuaca: '90% kemungkinan hujan'.",
  },
  ronde: {
    label: "Putaran / Ronde",
    arti: "Satu babak diskusi di simulasi. Tiap ronde, semua agen ngeluarin pendapat dan bisa berubah sikap. Makin banyak ronde, makin keliatan pergerakannya.",
  },
  skenario: {
    label: "Skenario / Hasil Kemungkinan",
    arti: "Gambaran situasi yang mungkin terjadi berdasarkan hasil simulasi. Kayak skenario di film — ada beberapa kemungkinan akhir cerita, dan kita lihat mana yang paling mungkin.",
  },
  konsensus: {
    label: "Konsensus / Sepakat",
    arti: "Semua kelompok punya pendapat yang sama. Kayak rapat keluarga dimana semua setuju mau makan di tempat yang sama.",
  },
  rekomendasi: {
    label: "Rekomendasi / Saran",
    arti: "Saran langkah yang bisa diambil berdasarkan hasil simulasi. Kayak saran dari temen yang udah pernah ngalamin situasi yang sama.",
  },
  risiko: {
    label: "Risiko / Bahaya",
    arti: "Kemungkinan buruk yang bisa terjadi kalau suatu keputusan diambil tanpa persiapan. Seperti peringatan: 'Hati-hati, jalanan licin kalau ujan'.",
  },
  agresif: {
    label: "Kumpulan Sikap",
    arti: "Kumpulan sikap dari semua kelompok yang digabung jadi satu grafik, biar keliatan perubahan pendapat secara keseluruhan. Kayak nilai rata-rata di rapor.",
  },
  aktorKunci: {
    label: "Aktor Kunci / Kelompok Berpengaruh",
    arti: "Kelompok yang suaranya paling didengar dan bisa mempengaruhi kelompok lain. Kayak ketua kelas yang pendapatnya ditiru sama temen-temen lainnya.",
  },
  brief: {
    label: "Informasi Awal",
    arti: "Data atau info tambahan yang dikasih ke agen biar simulasi lebih akurat. Kayak contekan — makin lengkap briefingnya, makin mirip hasilnya sama dunia nyata.",
  },
  meteranSikap: {
    label: "Meteran / Peta Sikap",
    arti: "Grafik yang nunjukin pergerakan sikap tiap kelompok dari awal sampai akhir simulasi. Kayak nilai di termometer: merah = menolak, hijau = setuju, abu = netral.",
  },
};

// ─── Komponen InfoTip ─────────────────────────────────────────────
export default function InfoTip({ istilah, ukuran = "sm" }) {
  const [buka, setBuka] = useState(false);
  const ref = useRef(null);
  const data = GLOSARIUM[istilah];

  // Tutup popover kalau klik di luar
  useEffect(() => {
    if (!buka) return;
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setBuka(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [buka]);

  if (!data) return null;

  const sizeClass = ukuran === "xs"
    ? "text-[11px]" : ukuran === "lg"
    ? "text-[15px]" : "text-[13px]";

  return (
    <span className="inline-flex items-center gap-0.5 relative" ref={ref}>
      <span
        className={`${sizeClass} text-[#cc785c] font-medium border-b border-dotted border-[#cc785c]/40 cursor-help`}
        onClick={() => setBuka(!buka)}
        onKeyDown={(e) => e.key === "Enter" && setBuka(!buka)}
        tabIndex={0}
        role="button"
        aria-label={`Info: ${data.label}`}
      >
        {data.label}
      </span>
      {/* Ikon tanya */}
      <button
        onClick={() => setBuka(!buka)}
        className="inline-flex items-center justify-center w-3.5 h-3.5 rounded-full bg-[#cc785c]/10 border border-[#cc785c]/25 text-[#cc785c] text-[9px] font-bold leading-none cursor-help hover:bg-[#cc785c]/20 transition shrink-0"
        aria-label="Penjelasan"
        tabIndex={-1}
      >
        ?
      </button>
      {buka && (
        <div
          className="absolute z-50 top-full left-0 mt-1.5 w-64 sm:w-72 p-3 rounded-[10px] shadow-lg border border-[#cc785c]/20 bg-[#faf9f5] text-left"
          style={{ boxShadow: "0 8px 24px rgba(20,20,19,0.12)" }}
        >
          <p className="text-[11px] font-bold text-[#141413] mb-1 uppercase tracking-[0.5px]">{data.label}</p>
          <p className="text-[12px] leading-relaxed text-[#3d3d3a]">{data.arti}</p>
        </div>
      )}
    </span>
  );
}

// ─── Komponen GlossarySidebar — legend tetap di pojok ─────────────
export function GlossaryButton() {
  const [buka, setBuka] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (!buka) return;
    const handler = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setBuka(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [buka]);

  return (
    <div className="fixed bottom-4 right-4 z-50" ref={ref}>
      <button
        onClick={() => setBuka(!buka)}
        className="flex items-center gap-1.5 px-3 py-2 rounded-[9999px] bg-[#cc785c] text-white text-xs font-medium shadow-lg hover:bg-[#a9583e] transition"
        aria-label="Buka glosarium"
      >
        <span className="text-sm">📖</span>
        Daftar Istilah
      </button>
      {buka && (
        <div
          className="absolute bottom-12 right-0 w-72 sm:w-80 max-h-[70vh] overflow-y-auto p-4 rounded-[12px] border border-[#e6dfd8] bg-[#faf9f5] shadow-xl"
          style={{ boxShadow: "0 12px 36px rgba(20,20,19,0.15)" }}
        >
          <p className="text-[11px] font-bold uppercase tracking-[1px] text-[#141413] mb-3">📖 Daftar Istilah</p>
          <div className="space-y-3">
            {Object.entries(GLOSARIUM).map(([key, val]) => (
              <div key={key}>
                <p className="text-[11px] font-bold text-[#cc785c] mb-0.5">{val.label}</p>
                <p className="text-[11px] text-[#3d3d3a] leading-relaxed">{val.arti}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
