"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import {
  BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Cell,
  LineChart, Line, Tooltip, Legend,
} from "recharts";

// ─── Konstanta ────────────────────────────────────────────────────────
const WARNA_SENTIMEN  = { positif: "#22c55e", netral: "#6366f1", negatif: "#ef4444" };
const LABEL_SENTIMEN  = { positif: "Mendukung", netral: "Netral", negatif: "Menolak" };
const WARNA_SKENARIO  = { Konsensus: "#22c55e", Polarisasi: "#ef4444", "Status Quo": "#6366f1" };
const WARNA_AGEN_LIST = ["#6366f1","#22c55e","#f59e0b","#ef4444","#8b5cf6","#06b6d4","#ec4899","#14b8a6"];

// ─── Export utils ─────────────────────────────────────────────────────
function eksporPDF() { window.print(); }

function eksporCSV(hasil, topik) {
  if (!hasil) return;
  const baris = [["Putaran","Nama Agen","Pendapat","Sentimen","Skor (-1 s/d 1)"]];
  (hasil.ronde_detail ?? []).forEach(ronde => {
    (ronde.agen ?? []).forEach(a => {
      baris.push([
        ronde.ronde, a.nama,
        `"${(a.pendapat ?? "").replace(/"/g, "'")}"`,
        LABEL_SENTIMEN[a.sentimen?.label] ?? a.sentimen?.label ?? "-",
        a.sentimen?.skor ?? 0,
      ]);
    });
  });
  const isi  = baris.map(r => r.join(",")).join("\n");
  const blob = new Blob(["\uFEFF" + isi], { type: "text/csv;charset=utf-8;" });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement("a");
  a.href = url; a.download = `VoxSwarm_${topik.slice(0, 30).replace(/\s+/g, "_")}.csv`;
  a.click(); URL.revokeObjectURL(url);
}

async function eksporWord(hasil, topik, analisis) {
  if (!window.docx) {
    await new Promise((resolve, reject) => {
      const s = document.createElement("script");
      s.src = "https://unpkg.com/docx@8.5.0/build/index.js";
      s.onload = resolve; s.onerror = () => reject(new Error("Gagal memuat library docx."));
      document.head.appendChild(s);
    });
  }
  const { Document, Paragraph, TextRun, Table, TableRow, TableCell, HeadingLevel, AlignmentType, WidthType, Packer } = window.docx;
  const tanggal   = new Date().toLocaleDateString("id-ID", { day: "numeric", month: "long", year: "numeric" });
  const narasi    = analisis.split("\n").filter(l => !l.includes("|") && l.trim()).join(" ").slice(0, 800);
  const rondeAkhir = (hasil.ronde_detail ?? []).at(-1);
  const barisAgen  = (rondeAkhir?.agen ?? []).map(a =>
    new TableRow({ children: [
      new TableCell({ children: [new Paragraph({ text: a.nama })] }),
      new TableCell({ children: [new Paragraph({ text: LABEL_SENTIMEN[a.sentimen?.label] ?? "-", alignment: AlignmentType.CENTER })] }),
      new TableCell({ children: [new Paragraph({ text: a.pendapat ?? "-" })] }),
    ]})
  );
  const doc = new Document({ sections: [{ children: [
    new Paragraph({ text: "LAPORAN SIMULASI VOXSWARM", heading: HeadingLevel.TITLE, alignment: AlignmentType.CENTER }),
    new Paragraph({ text: "" }),
    new Paragraph({ children: [new TextRun({ text: "Topik: ", bold: true }), new TextRun(topik)] }),
    new Paragraph({ children: [new TextRun({ text: "Tanggal: ", bold: true }), new TextRun(tanggal)] }),
    new Paragraph({ children: [new TextRun({ text: "Jumlah Putaran: ", bold: true }), new TextRun(String(hasil.jumlah_ronde ?? "-"))] }),
    ...(hasil.intervensi ? [new Paragraph({ children: [new TextRun({ text: "Intervensi: ", bold: true }), new TextRun(hasil.intervensi)] })] : []),
    new Paragraph({ text: "" }),
    new Paragraph({ text: "RINGKASAN ANALISIS", heading: HeadingLevel.HEADING_1 }),
    new Paragraph({ text: narasi }),
    new Paragraph({ text: "" }),
    new Paragraph({ text: "PREDIKSI SKENARIO", heading: HeadingLevel.HEADING_1 }),
    ...Object.entries(hasil.prediksi ?? {}).map(([k, v]) =>
      new Paragraph({ children: [new TextRun({ text: `${k}: `, bold: true }), new TextRun(`${v}%`)] })
    ),
    new Paragraph({ text: "" }),
    new Paragraph({ text: "PENDAPAT AGEN (PUTARAN TERAKHIR)", heading: HeadingLevel.HEADING_1 }),
    new Table({
      width: { size: 100, type: WidthType.PERCENTAGE },
      rows: [
        new TableRow({ tableHeader: true, children: ["Nama Agen","Sikap","Pendapat"].map(h =>
          new TableCell({ shading: { fill: "4338CA" }, children: [new Paragraph({ children: [new TextRun({ text: h, bold: true, color: "FFFFFF" })], alignment: AlignmentType.CENTER })] })
        )}),
        ...barisAgen,
      ],
    }),
    new Paragraph({ text: "" }),
    new Paragraph({ text: "Laporan ini dibuat otomatis oleh VoxSwarm — Sistem Simulasi Opini Multi-Agen.", alignment: AlignmentType.CENTER }),
  ]}]});
  const buffer = await Packer.toBlob(doc);
  const url    = URL.createObjectURL(buffer);
  const a      = document.createElement("a");
  a.href = url; a.download = `VoxSwarm_${topik.slice(0, 30).replace(/\s+/g, "_")}.docx`;
  a.click(); URL.revokeObjectURL(url);
}

// ─── Sub-komponen ─────────────────────────────────────────────────────
const BadgeSentimen = ({ label }) => {
  const style = { positif: "bg-green-900/50 text-green-300 border-green-700", netral: "bg-indigo-900/50 text-indigo-300 border-indigo-700", negatif: "bg-red-900/50 text-red-300 border-red-700" }[label] ?? "bg-slate-800 text-slate-400 border-slate-600";
  return <span className={`rounded-full border px-2.5 py-0.5 text-[11px] font-semibold ${style}`}>{LABEL_SENTIMEN[label] ?? label ?? "–"}</span>;
};

const Kartu = ({ children, className = "" }) => (
  <div className={`rounded-2xl border border-white/10 bg-[#0C0F1D] p-6 ${className}`}>{children}</div>
);

const JudulSeksi = ({ children }) => (
  <p className="mb-4 text-xs font-bold tracking-widest text-indigo-400 uppercase">{children}</p>
);

// ─── Komponen: Memori Agen ────────────────────────────────────────────
// Menampilkan akordion riwayat pendapat agen di setiap ronde
const KartuMemoriAgen = ({ rondeDetail, warnaAgen }) => {
  const [bukaIndex, setBukaIndex] = useState(null);

  // Susun data: { namaAgen → [{ ronde, pendapat, sentimen }] }
  const memoriPerAgen = {};
  (rondeDetail ?? []).forEach(ronde => {
    (ronde.agen ?? []).forEach(a => {
      if (!memoriPerAgen[a.nama]) memoriPerAgen[a.nama] = [];
      memoriPerAgen[a.nama].push({ ronde: ronde.ronde, pendapat: a.pendapat, sentimen: a.sentimen });
    });
  });

  const namaAgenList = Object.keys(memoriPerAgen);
  if (!namaAgenList.length) return null;

  return (
    <Kartu>
      <JudulSeksi>🧠 Memori & Evolusi Pendapat Agen</JudulSeksi>
      <p className="mb-4 text-xs text-slate-500">Klik nama agen untuk melihat bagaimana pendapatnya berubah dari putaran ke putaran.</p>
      <div className="space-y-2">
        {namaAgenList.map((nama, i) => {
          const warna   = warnaAgen[nama] ?? WARNA_AGEN_LIST[i % WARNA_AGEN_LIST.length];
          const riwayat = memoriPerAgen[nama];
          const buka    = bukaIndex === i;
          const sentimenAkhir = riwayat.at(-1)?.sentimen?.label ?? "netral";
          // Hitung apakah ada perubahan sentimen
          const perubahanSentimen = new Set(riwayat.map(r => r.sentimen?.label)).size > 1;

          return (
            <div key={nama} className="rounded-xl border border-white/10 overflow-hidden">
              {/* Header agen */}
              <button
                onClick={() => setBukaIndex(buka ? null : i)}
                className="w-full flex items-center gap-3 px-4 py-3 hover:bg-white/5 transition text-left"
              >
                {/* Avatar */}
                <div
                  className="h-8 w-8 shrink-0 rounded-full flex items-center justify-center text-[10px] font-black"
                  style={{ backgroundColor: warna + "22", border: `1.5px solid ${warna}`, color: warna }}
                >
                  {nama.slice(0, 2).toUpperCase()}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-bold text-slate-200">{nama}</span>
                    <BadgeSentimen label={sentimenAkhir} />
                    {perubahanSentimen && (
                      <span className="rounded-full bg-amber-900/40 border border-amber-700 px-2 py-0.5 text-[10px] font-semibold text-amber-300">
                        🔄 Pendapat berubah
                      </span>
                    )}
                  </div>
                  <p className="text-[11px] text-slate-500 mt-0.5">{riwayat.length} putaran terekam</p>
                </div>
                <span className="text-slate-600 text-xs ml-2">{buka ? "▲" : "▼"}</span>
              </button>

              {/* Konten akordion: timeline per ronde */}
              {buka && (
                <div className="px-4 pb-4 pt-1 space-y-3 border-t border-white/5">
                  {riwayat.map((item, j) => {
                    const w = WARNA_SENTIMEN[item.sentimen?.label] ?? "#6366f1";
                    return (
                      <div key={j} className="flex gap-3">
                        {/* Indikator ronde */}
                        <div className="flex flex-col items-center gap-1">
                          <div
                            className="h-6 w-6 rounded-full flex items-center justify-center text-[10px] font-black shrink-0"
                            style={{ backgroundColor: w + "22", border: `1px solid ${w}`, color: w }}
                          >
                            {item.ronde}
                          </div>
                          {j < riwayat.length - 1 && <div className="w-px flex-1 bg-white/10" />}
                        </div>
                        {/* Konten */}
                        <div className="pb-2">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="text-[11px] font-bold text-slate-400">Putaran {item.ronde}</span>
                            <BadgeSentimen label={item.sentimen?.label} />
                            <span className="text-[10px] text-slate-600">
                              skor: {item.sentimen?.skor > 0 ? "+" : ""}{item.sentimen?.skor ?? 0}
                            </span>
                          </div>
                          <p className="text-xs leading-relaxed text-slate-300 italic">"{item.pendapat}"</p>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </Kartu>
  );
};

// ─── Komponen: Panel Intervensi Post-Simulasi ─────────────────────────
const PanelIntervensi = ({ topik, kategori, jumlahRonde, agenCustom, onHasilBaru, memuat, setMemuat, apiBase }) => {
  const [intervensi,  setIntervensi]  = useState("");
  const [tampil,      setTampil]      = useState(false);
  const [pesanError,  setPesanError]  = useState("");

  const kirimIntervensi = async () => {
    if (!intervensi.trim()) return;
    setPesanError("");
    setMemuat(true);
    try {
      const body = {
        topik:         topik.trim(),
        kategori,
        jumlah_ronde:  jumlahRonde,
        intervensi:    intervensi.trim(),
        agen_custom:   agenCustom.length ? agenCustom : undefined,
      };
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
      onHasilBaru(data.data);
      setIntervensi("");
      setTampil(false);
    } catch (err) {
      setPesanError(err.message || "Server tidak dapat dihubungi.");
    }
    setMemuat(false);
  };

  return (
    <div className="rounded-2xl border border-amber-500/30 bg-amber-950/20 p-5 print:hidden">
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-2">
          <span className="text-base">👁️</span>
          <span className="text-sm font-bold text-amber-300">God's Eye — Injeksi Intervensi</span>
          <span className="rounded-full bg-amber-500/20 px-2 py-0.5 text-[10px] font-bold text-amber-400">LIVE</span>
        </div>
        <button
          onClick={() => { setTampil(v => !v); setPesanError(""); }}
          className="text-xs text-amber-500 hover:text-amber-300 transition underline underline-offset-2"
        >
          {tampil ? "Tutup ▲" : "Buka ▼"}
        </button>
      </div>
      <p className="text-[11px] text-amber-700 mb-3">
        Suntikkan skenario baru ke dalam simulasi yang sudah berjalan. Agen akan bereaksi ulang terhadap variabel baru ini.
      </p>

      {tampil && (
        <div className="space-y-3">
          <textarea
            rows={2}
            className="w-full rounded-xl border border-amber-500/30 bg-[#0E1220] px-4 py-3 text-sm text-slate-100 placeholder:text-slate-600 outline-none focus:border-amber-500 transition resize-none"
            value={intervensi}
            onChange={e => setIntervensi(e.target.value)}
            placeholder='Contoh: "Pemerintah tiba-tiba umumkan subsidi baru senilai Rp 50 triliun"'
          />
          {pesanError && <p className="text-xs text-red-400">❌ {pesanError}</p>}
          <div className="flex gap-2">
            <button
              onClick={kirimIntervensi}
              disabled={memuat || !intervensi.trim()}
              className="rounded-xl bg-amber-500 px-5 py-2.5 text-xs font-bold text-black transition hover:bg-amber-400 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {memuat ? "⏳ Memproses..." : "🚀 Injeksi & Simulasi Ulang"}
            </button>
            <button
              onClick={() => { setIntervensi(""); setPesanError(""); }}
              className="rounded-xl border border-white/10 px-4 py-2.5 text-xs text-slate-400 hover:text-white transition"
            >
              Reset
            </button>
          </div>
          <p className="text-[10px] text-amber-800">
            ⚠️ Simulasi akan dijalankan ulang penuh dengan intervensi ini diinjeksikan di putaran tengah.
          </p>
        </div>
      )}
    </div>
  );
};

// ─── Komponen: Tambah Agen Custom ─────────────────────────────────────
const PanelAgenCustom = ({ agenCustom, setAgenCustom }) => {
  const [tampil,   setTampil]   = useState(false);
  const [nama,     setNama]     = useState("");
  const [role,     setRole]     = useState("");
  const [pengaruh, setPengaruh] = useState(0.7);

  const tambahAgen = () => {
    if (!nama.trim() || !role.trim()) return;
    setAgenCustom(prev => [...prev, {
      nama:      nama.trim(),
      role:      role.trim(),
      pengaruh:  parseFloat(pengaruh),
      kepribadian: { openness: 0.6, agreeableness: 0.6, neuroticism: 0.4 },
    }]);
    setNama(""); setRole(""); setPengaruh(0.7);
  };

  const hapusAgen = (i) => setAgenCustom(prev => prev.filter((_, idx) => idx !== i));

  return (
    <div className="rounded-2xl border border-indigo-500/20 bg-indigo-950/10 p-4 print:hidden">
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-2">
          <span className="text-base">👤</span>
          <span className="text-sm font-bold text-indigo-300">Tambah Agen Custom</span>
          {agenCustom.length > 0 && (
            <span className="rounded-full bg-indigo-500/20 px-2 py-0.5 text-[10px] font-bold text-indigo-400">
              {agenCustom.length} agen ditambahkan
            </span>
          )}
        </div>
        <button
          onClick={() => setTampil(v => !v)}
          className="text-xs text-indigo-500 hover:text-indigo-300 transition underline underline-offset-2"
        >
          {tampil ? "Tutup ▲" : "Tambah ▼"}
        </button>
      </div>
      <p className="text-[11px] text-indigo-700 mb-2">
        Tambahkan karakter agen baru dengan perspektif khusus yang tidak ada di daftar bawaan.
      </p>

      {/* Daftar agen custom yang sudah ditambahkan */}
      {agenCustom.length > 0 && (
        <div className="mb-3 space-y-1.5">
          {agenCustom.map((a, i) => (
            <div key={i} className="flex items-center gap-2 rounded-xl bg-white/5 px-3 py-2">
              <div className="h-6 w-6 rounded-full bg-indigo-500/20 border border-indigo-500 flex items-center justify-center text-[9px] font-black text-indigo-300 shrink-0">
                {a.nama.slice(0, 2).toUpperCase()}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-bold text-slate-200 truncate">{a.nama}</p>
                <p className="text-[10px] text-slate-500 truncate">{a.role.slice(0, 60)}...</p>
              </div>
              <span className="text-[10px] text-slate-600">pengaruh: {a.pengaruh}</span>
              <button onClick={() => hapusAgen(i)} className="text-red-500 hover:text-red-300 text-xs ml-1 transition">✕</button>
            </div>
          ))}
        </div>
      )}

      {tampil && (
        <div className="space-y-2.5 border-t border-white/5 pt-3">
          <div>
            <label className="text-[11px] text-slate-500 block mb-1">Nama / Peran Agen</label>
            <input
              type="text"
              className="w-full rounded-lg border border-white/10 bg-[#0E1220] px-3 py-2 text-sm text-slate-100 placeholder:text-slate-600 outline-none focus:border-indigo-400 transition"
              value={nama}
              onChange={e => setNama(e.target.value)}
              placeholder='Contoh: "Aktivis Lingkungan"'
            />
          </div>
          <div>
            <label className="text-[11px] text-slate-500 block mb-1">Deskripsi karakter & sudut pandang</label>
            <textarea
              rows={2}
              className="w-full rounded-lg border border-white/10 bg-[#0E1220] px-3 py-2 text-sm text-slate-100 placeholder:text-slate-600 outline-none focus:border-indigo-400 transition resize-none"
              value={role}
              onChange={e => setRole(e.target.value)}
              placeholder='Contoh: "Kamu aktivis lingkungan yang kritis terhadap dampak industri. Kamu selalu menempatkan kelestarian alam di atas keuntungan ekonomi."'
            />
          </div>
          <div className="flex items-center gap-3">
            <label className="text-[11px] text-slate-500 whitespace-nowrap">Bobot pengaruh:</label>
            <input
              type="range" min="0.1" max="1.0" step="0.1"
              value={pengaruh}
              onChange={e => setPengaruh(e.target.value)}
              className="flex-1"
            />
            <span className="text-xs font-bold text-indigo-300 w-6 text-right">{pengaruh}</span>
          </div>
          <button
            onClick={tambahAgen}
            disabled={!nama.trim() || !role.trim()}
            className="rounded-xl bg-indigo-600 px-5 py-2 text-xs font-bold text-white transition hover:bg-indigo-500 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            + Tambahkan Agen
          </button>
        </div>
      )}
    </div>
  );
};

// ─── Komponen Utama ───────────────────────────────────────────────────
export default function VoxSwarmDashboard() {
  const [terpasang,    setTerpasang]    = useState(false);
  const [topik,        setTopik]        = useState("");
  const [kategori,     setKategori]     = useState("Umum");
  const [jumlahRonde,  setJumlahRonde]  = useState(3);
  const [agenCustom,   setAgenCustom]   = useState([]);     // ← baru
  const [hasil,        setHasil]        = useState(null);
  const [memuat,       setMemuat]       = useState(false);
  const [rondeAktif,   setRondeAktif]   = useState(0);
  const [bukaEkspor,   setBukaEkspor]   = useState(false);
  const [riwayatSim,   setRiwayatSim]   = useState([]);     // ← riwayat tiap run intervensi
  const [kategoriList, setKategoriList] = useState(["Umum","Ekonomi","Politik","Sosial","Hukum","Teknologi"]);

  const inputRef = useRef(null);
  const hasilRef = useRef(null);
  const apiBase  = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

  useEffect(() => {
    setTerpasang(true);
    fetch(`${apiBase}/categories`)
      .then(r => r.json())
      .then(d => { if (d.kategori?.length) setKategoriList(d.kategori); })
      .catch(() => {});
  }, []);

  // ── Mulai simulasi baru (dari form) ─────────────────────────────
  const mulaiAnalisis = async () => {
    if (!topik.trim()) { inputRef.current?.focus(); return; }
    setMemuat(true);
    setHasil(null);
    setRondeAktif(0);
    setBukaEkspor(false);
    setRiwayatSim([]);
    try {
      const body = {
        topik: topik.trim(),
        kategori,
        jumlah_ronde: jumlahRonde,
        agen_custom:  agenCustom.length ? agenCustom : undefined,
      };
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
      setHasil(data.data);
      setTimeout(() => hasilRef.current?.scrollIntoView({ behavior: "smooth" }), 200);
    } catch (err) {
      alert("❌ " + (err.message || "Server tidak dapat dihubungi."));
    }
    setMemuat(false);
  };

  // ── Terima hasil simulasi baru dari intervensi ───────────────────
  const handleHasilIntervensi = (hasilBaru) => {
    // Simpan run sebelumnya ke riwayat
    setRiwayatSim(prev => [...prev, hasil]);
    setHasil(hasilBaru);
    setRondeAktif(0);
    setTimeout(() => hasilRef.current?.scrollIntoView({ behavior: "smooth" }), 200);
  };

  // ── Data turunan ─────────────────────────────────────────────────
  const daftarRonde = hasil?.ronde_detail ?? [];
  const rondeIni    = daftarRonde[rondeAktif] ?? null;
  const analisis    = hasil?.analisis ?? "";
  const prediksi    = hasil?.prediksi ?? {};
  const sentimenAgr = hasil?.sentimen_agregat ?? {};
  const grafData    = hasil?.graf_data ?? { entitas: [], relasi: [] };

  const narasi = analisis.split("\n").filter(l => !l.includes("|") && l.trim()).join(" ").slice(0, 600);

  const dataBar = (rondeIni?.agen ?? []).map(a => ({
    nama:  a.nama,
    skor:  Math.round((a.sentimen?.skor + 1) * 50),
    warna: WARNA_SENTIMEN[a.sentimen?.label] ?? "#6366f1",
    label: a.sentimen?.label ?? "netral",
  }));

  const warnaAgen = Object.keys(sentimenAgr).reduce((acc, nama, i) => {
    acc[nama] = WARNA_AGEN_LIST[i % WARNA_AGEN_LIST.length];
    return acc;
  }, {});

  const dataTren = (() => {
    const agen = Object.keys(sentimenAgr);
    if (!agen.length) return [];
    return Array.from({ length: sentimenAgr[agen[0]]?.length ?? 0 }, (_, i) => {
      const obj = { label: `Putaran ${i + 1}` };
      agen.forEach(n => { obj[n] = +(sentimenAgr[n]?.[i] ?? 0).toFixed(2); });
      return obj;
    });
  })();

  const jmlNegatif = dataBar.filter(a => a.skor < 40).length;
  const jmlPositif = dataBar.filter(a => a.skor >= 60).length;
  const status = jmlNegatif > jmlPositif && jmlNegatif >= 2 ? "berbahaya" : jmlPositif >= jmlNegatif ? "stabil" : "terbagi";
  const INFO_STATUS = {
    stabil:    { label: "✅ Situasi Stabil",   kelas: "bg-green-600" },
    berbahaya: { label: "⚠️ Potensi Konflik",  kelas: "bg-red-600" },
    terbagi:   { label: "⚡ Pendapat Terbagi", kelas: "bg-amber-600" },
  };

  if (!terpasang) return null;

  return (
    <main className="min-h-screen bg-[#06080F] p-4 text-white md:p-8 print:bg-white print:p-8 print:text-slate-900">
      <div className="mx-auto max-w-5xl">

        {/* ══ HEADER ══ */}
        <header className="mb-6 flex items-center justify-between print:hidden">
          <Link href="/" className="text-sm text-slate-500 hover:text-white transition">← Kembali</Link>
          <div className="flex items-center gap-2">
            <div className="h-2 w-2 animate-pulse rounded-full bg-indigo-500" />
            <span className="text-sm font-black tracking-widest uppercase">VoxSwarm</span>
            <span className="rounded-full bg-indigo-500/20 px-2 py-0.5 text-[10px] font-bold text-indigo-300">v2</span>
          </div>
        </header>

        {/* ══ FORM INPUT ══ */}
        <section className="mb-4 rounded-2xl border border-white/10 bg-[#0C0F1D] p-5 print:hidden">
          <p className="mb-1 text-base font-bold text-white">Simulasikan isu apa hari ini?</p>
          <p className="mb-4 text-xs text-slate-500">Masukkan topik, pilih kategori dan jumlah putaran diskusi, lalu klik Analisis.</p>

          <div className="mb-3 flex gap-2">
            <input
              ref={inputRef}
              className="flex-1 rounded-xl border border-white/10 bg-[#0E1220] px-4 py-3 text-sm text-slate-100 placeholder:text-slate-600 outline-none focus:border-indigo-500 transition"
              value={topik}
              onChange={e => setTopik(e.target.value)}
              onKeyDown={e => e.key === "Enter" && mulaiAnalisis()}
              placeholder="Contoh: Kenaikan harga BBM, RUU Ketenagakerjaan baru, dll..."
            />
            <button
              onClick={mulaiAnalisis}
              disabled={memuat}
              className="rounded-xl bg-indigo-600 px-7 py-3 text-sm font-bold text-white transition hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {memuat ? "⏳ Memproses..." : "Analisis →"}
            </button>
          </div>

          <div className="flex flex-wrap items-center gap-4 border-t border-white/5 pt-3 mb-4">
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-500">Kategori isu:</span>
              <select
                value={kategori}
                onChange={e => setKategori(e.target.value)}
                className="rounded-lg border border-white/10 bg-[#0E1220] px-3 py-1.5 text-xs text-slate-300 outline-none focus:border-indigo-400"
              >
                {kategoriList.map(k => <option key={k} value={k}>{k}</option>)}
              </select>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-500">Jumlah putaran:</span>
              <div className="flex gap-1">
                {[1,2,3,4,5].map(n => (
                  <button key={n} onClick={() => setJumlahRonde(n)}
                    className={`h-7 w-7 rounded-lg text-xs font-bold transition ${jumlahRonde === n ? "bg-indigo-600 text-white" : "border border-white/10 text-slate-500 hover:border-indigo-500 hover:text-white"}`}
                  >{n}</button>
                ))}
              </div>
            </div>
          </div>

          {/* ── Tambah Agen Custom ── */}
          <PanelAgenCustom agenCustom={agenCustom} setAgenCustom={setAgenCustom} />
        </section>

        {/* ══ KOSONG ══ */}
        {!hasil && !memuat && (
          <div className="rounded-2xl border border-dashed border-white/10 p-16 text-center">
            <div className="mb-3 text-5xl">🧠</div>
            <h2 className="mb-2 text-xl font-bold">Belum ada simulasi</h2>
            <p className="text-sm text-slate-500">Masukkan topik di atas dan klik <strong className="text-white">Analisis</strong> untuk memulai.</p>
          </div>
        )}

        {/* ══ LOADING ══ */}
        {memuat && (
          <div className="rounded-2xl border border-white/10 bg-[#0C0F1D] p-16 text-center">
            <div className="mx-auto mb-6 flex w-fit gap-2">
              {[0,1,2,3].map(i => (
                <div key={i} className="h-2.5 w-2.5 rounded-full bg-indigo-500"
                  style={{ animation: `lompat 1s ease-in-out ${i*0.15}s infinite` }} />
              ))}
            </div>
            <p className="mb-1 font-semibold text-slate-300">Sedang mensimulasikan {jumlahRonde} putaran diskusi...</p>
            <p className="text-xs text-slate-600">Proses ini memakan waktu sekitar 10–30 detik, mohon tunggu.</p>
          </div>
        )}

        {/* ══ HASIL ══ */}
        {hasil && (
          <div ref={hasilRef} className="space-y-5 duration-500 animate-in fade-in">

            {/* ── Riwayat intervensi (badge) ── */}
            {riwayatSim.length > 0 && (
              <div className="flex items-center gap-2 flex-wrap print:hidden">
                <span className="text-xs text-slate-600">Riwayat simulasi:</span>
                {riwayatSim.map((r, i) => (
                  <span key={i} className="rounded-full border border-white/10 px-3 py-1 text-[11px] text-slate-500">
                    Run #{i + 1} {r.intervensi ? `— "${r.intervensi.slice(0, 30)}..."` : "(awal)"}
                  </span>
                ))}
                <span className="rounded-full bg-amber-500/20 border border-amber-500/40 px-3 py-1 text-[11px] text-amber-300 font-bold">
                  ▶ Run #{riwayatSim.length + 1} {hasil.intervensi ? "(dengan intervensi)" : ""}
                </span>
              </div>
            )}

            {/* ── Bar status + ekspor ── */}
            <div className="flex flex-wrap items-center justify-between gap-3 print:hidden">
              <div className="flex flex-wrap items-center gap-3">
                <span className={`rounded-full px-4 py-1.5 text-xs font-bold text-white ${INFO_STATUS[status].kelas}`}>
                  {INFO_STATUS[status].label}
                </span>
                <span className="text-xs text-slate-500">
                  Topik: <span className="font-medium text-slate-300">"{topik}"</span>
                  {hasil.intervensi && <span className="text-amber-400"> · 🔀 {hasil.intervensi.slice(0, 40)}...</span>}
                  {" · "}{daftarRonde.length} putaran · {(rondeIni?.agen ?? []).length} agen
                </span>
              </div>
              <div className="relative">
                <button
                  onClick={() => setBukaEkspor(v => !v)}
                  className="flex items-center gap-2 rounded-xl border border-white/10 bg-[#0C0F1D] px-4 py-2 text-xs font-bold text-slate-300 hover:border-indigo-500 hover:text-white transition"
                >
                  📥 Unduh Laporan ▾
                </button>
                {bukaEkspor && (
                  <div className="absolute right-0 top-11 z-50 w-56 rounded-2xl border border-white/10 bg-[#131726] p-2 shadow-2xl">
                    {[
                      { ikon: "🖨️", label: "Cetak / Simpan PDF",  aksi: () => { eksporPDF(); setBukaEkspor(false); } },
                      { ikon: "📊", label: "Unduh Excel / CSV",    aksi: () => { eksporCSV(hasil, topik); setBukaEkspor(false); } },
                      { ikon: "📄", label: "Unduh Word (.docx)",   aksi: () => { eksporWord(hasil, topik, analisis).catch(e => alert(e.message)); setBukaEkspor(false); } },
                    ].map(({ ikon, label, aksi }) => (
                      <button key={label} onClick={aksi}
                        className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-xs text-slate-300 hover:bg-white/10 transition">
                        <span className="text-base">{ikon}</span> {label}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* ── GOD'S EYE INTERVENTION ── tampil setelah simulasi ada ── */}
            <PanelIntervensi
              topik={topik}
              kategori={kategori}
              jumlahRonde={jumlahRonde}
              agenCustom={agenCustom}
              onHasilBaru={handleHasilIntervensi}
              memuat={memuat}
              setMemuat={setMemuat}
              apiBase={apiBase}
            />

            {/* ── Ringkasan ── */}
            <Kartu>
              <JudulSeksi>📋 Ringkasan Hasil</JudulSeksi>
              <p className="text-sm leading-7 text-slate-300 print:text-slate-800">{narasi || "—"}</p>
              {Object.keys(prediksi).length > 0 && (
                <div className="mt-5 space-y-2.5">
                  <p className="text-xs font-semibold text-slate-500">Kemungkinan hasil akhir:</p>
                  {Object.entries(prediksi).map(([k, v]) => (
                    <div key={k} className="flex items-center gap-3">
                      <span className="w-28 shrink-0 text-xs text-slate-400">{k}</span>
                      <div className="flex-1 h-2 overflow-hidden rounded-full bg-white/5">
                        <div className="h-full rounded-full transition-all" style={{ width: `${v}%`, backgroundColor: WARNA_SKENARIO[k] ?? "#6366f1" }} />
                      </div>
                      <span className="w-8 shrink-0 text-right text-xs font-bold" style={{ color: WARNA_SKENARIO[k] }}>{v}%</span>
                    </div>
                  ))}
                </div>
              )}
            </Kartu>

            {/* ── Navigasi putaran ── */}
            {daftarRonde.length > 1 && (
              <div className="flex flex-wrap items-center gap-2 print:hidden">
                <span className="text-xs text-slate-500">Lihat putaran:</span>
                {daftarRonde.map((_, i) => (
                  <button key={i} onClick={() => setRondeAktif(i)}
                    className={`rounded-xl px-4 py-1.5 text-xs font-bold transition ${rondeAktif === i ? "bg-indigo-600 text-white" : "border border-white/10 text-slate-500 hover:border-indigo-400 hover:text-white"}`}
                  >
                    Putaran {i + 1}
                  </button>
                ))}
              </div>
            )}

            {/* ── Grid chart ── */}
            <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
              <Kartu>
                <JudulSeksi>📊 Peta Dukungan — Putaran {rondeAktif + 1}</JudulSeksi>
                <p className="mb-4 text-xs text-slate-500">Skor 0 = sangat menolak, 100 = sangat mendukung.</p>
                <div style={{ height: 220 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={dataBar} margin={{ bottom: 0 }}>
                      <XAxis dataKey="nama" tick={{ fontSize: 9, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
                      <YAxis domain={[0,100]} hide />
                      <Tooltip
                        cursor={{ fill: "rgba(99,102,241,0.07)" }}
                        contentStyle={{ background: "#0C0F1D", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 10, fontSize: 11 }}
                        formatter={(v, _, p) => [`${v}/100 — ${LABEL_SENTIMEN[p.payload.label] ?? "-"}`, "Skor dukungan"]}
                      />
                      <Bar dataKey="skor" radius={[6,6,0,0]} barSize={34}>
                        {dataBar.map((e, i) => <Cell key={i} fill={e.warna} />)}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
                <div className="mt-3 flex gap-4 text-[11px] text-slate-500">
                  {Object.entries(WARNA_SENTIMEN).map(([k, w]) => (
                    <span key={k} className="flex items-center gap-1.5">
                      <span className="inline-block h-2 w-2 rounded-full" style={{ backgroundColor: w }} />
                      {LABEL_SENTIMEN[k]}
                    </span>
                  ))}
                </div>
              </Kartu>

              {dataTren.length > 1 ? (
                <Kartu>
                  <JudulSeksi>📈 Perubahan Sikap Tiap Putaran</JudulSeksi>
                  <p className="mb-4 text-xs text-slate-500">Nilai positif = cenderung mendukung, negatif = cenderung menolak.</p>
                  <div style={{ height: 220 }}>
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={dataTren}>
                        <XAxis dataKey="label" tick={{ fontSize: 9, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
                        <YAxis domain={[-1,1]} hide />
                        <Tooltip
                          contentStyle={{ background: "#0C0F1D", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 10, fontSize: 11 }}
                          formatter={v => [v > 0 ? `+${v} (Mendukung)` : v < 0 ? `${v} (Menolak)` : `${v} (Netral)`, ""]}
                        />
                        <Legend wrapperStyle={{ fontSize: 10, color: "#94a3b8" }} />
                        {Object.keys(sentimenAgr).map(nama => (
                          <Line key={nama} type="monotone" dataKey={nama}
                            stroke={warnaAgen[nama]} strokeWidth={2} dot={{ r: 3 }} activeDot={{ r: 5 }} />
                        ))}
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                </Kartu>
              ) : (
                <Kartu>
                  <JudulSeksi>👥 Siapa Saja Agennya?</JudulSeksi>
                  <div className="space-y-2.5">
                    {(rondeIni?.agen ?? []).map((a, i) => (
                      <div key={i} className="flex items-start gap-3 rounded-xl bg-white/5 p-3">
                        <div className="mt-1 h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: WARNA_SENTIMEN[a.sentimen?.label] }} />
                        <div>
                          <div className="mb-1 flex items-center gap-2">
                            <span className="text-xs font-bold text-slate-200">{a.nama}</span>
                            <BadgeSentimen label={a.sentimen?.label} />
                          </div>
                          <p className="text-xs leading-relaxed text-slate-400 italic">"{a.pendapat}"</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </Kartu>
              )}
            </div>

            {/* ── MEMORI AGEN (baru) ── */}
            <KartuMemoriAgen rondeDetail={daftarRonde} warnaAgen={warnaAgen} />

            {/* ── Log diskusi ── */}
            <Kartu>
              <JudulSeksi>💬 Jalannya Diskusi — Putaran {rondeAktif + 1}</JudulSeksi>
              <p className="mb-4 text-xs text-slate-500">Berikut pendapat masing-masing agen pada putaran ini.</p>
              <div className="custom-scrollbar max-h-96 space-y-5 overflow-y-auto pr-2">
                {(rondeIni?.agen ?? []).map((a, i) => {
                  const warna = WARNA_SENTIMEN[a.sentimen?.label] ?? "#6366f1";
                  return (
                    <div key={i} className="flex gap-4">
                      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-[11px] font-black"
                        style={{ backgroundColor: warna + "22", border: `1.5px solid ${warna}`, color: warna }}>
                        {a.nama.slice(0, 2).toUpperCase()}
                      </div>
                      <div className="flex-1">
                        <div className="mb-1.5 flex flex-wrap items-center gap-2">
                          <span className="text-sm font-bold text-slate-200">{a.nama}</span>
                          <BadgeSentimen label={a.sentimen?.label} />
                        </div>
                        <p className="text-sm leading-7 text-slate-300 print:text-slate-700">{a.pendapat}</p>
                      </div>
                    </div>
                  );
                })}
              </div>
            </Kartu>

            {/* ── Peta koneksi isu (GraphRAG) ── */}
            {grafData.entitas?.length > 0 && (
              <Kartu>
                <JudulSeksi>🔗 Pihak & Hubungan yang Terlibat</JudulSeksi>
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  {grafData.entitas.map((e, i) => (
                    <div key={i} className="flex items-center justify-between rounded-xl bg-white/5 px-4 py-2.5">
                      <span className="text-sm font-medium text-slate-200">{e.nama}</span>
                      <div className="flex items-center gap-2">
                        <span className="rounded bg-white/10 px-2 py-0.5 text-[9px] font-bold uppercase text-slate-400">{e.tipe}</span>
                        <BadgeSentimen label={e.sentimen_umum} />
                      </div>
                    </div>
                  ))}
                </div>
                {grafData.relasi?.length > 0 && (
                  <div className="mt-4 space-y-1.5">
                    <p className="mb-2 text-xs font-semibold text-slate-500">Hubungan antar pihak:</p>
                    {grafData.relasi.map((r, i) => (
                      <p key={i} className="text-xs text-slate-400">
                        <span className="font-medium text-indigo-300">{r.dari}</span>
                        <span className="mx-2 text-slate-600">→ {r.label} →</span>
                        <span className="font-medium text-indigo-300">{r.ke}</span>
                      </p>
                    ))}
                  </div>
                )}
              </Kartu>
            )}

            {/* ── Mulai ulang ── */}
            <div className="pb-6 text-center print:hidden">
              <button
                onClick={() => { setHasil(null); setTopik(""); setRiwayatSim([]); setAgenCustom([]); setTimeout(() => inputRef.current?.focus(), 100); }}
                className="text-xs text-slate-600 underline underline-offset-4 hover:text-slate-400 transition"
              >
                Mulai simulasi baru
              </button>
            </div>
          </div>
        )}
      </div>

      <style jsx global>{`
        @keyframes lompat {
          0%, 80%, 100% { transform: translateY(0); opacity: 0.3; }
          40%            { transform: translateY(-9px); opacity: 1; }
        }
        .custom-scrollbar::-webkit-scrollbar       { width: 3px; }
        .custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: #1e293b; border-radius: 10px; }
        @media print {
          @page { size: A4 portrait; margin: 20mm; }
          body  { background: white !important; -webkit-print-color-adjust: exact; }
          .print\\:hidden { display: none !important; }
        }
      `}</style>
    </main>
  );
}