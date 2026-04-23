"use client";

import { useState, useEffect, useRef, useMemo } from "react";
import Link from "next/link";
import {
  BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Cell,
  LineChart, Line, Tooltip, Legend, CartesianGrid, ReferenceLine,
} from "recharts";

// ─── Konstanta ────────────────────────────────────────────────────────
const WARNA_SENTIMEN  = { positif: "#22c55e", netral: "#6366f1", negatif: "#ef4444" };
const LABEL_SENTIMEN  = { positif: "Mendukung", netral: "Netral", negatif: "Menolak" };
const WARNA_SKENARIO  = { Konsensus: "#22c55e", Polarisasi: "#ef4444", "Status Quo": "#6366f1" };
const WARNA_AGEN_LIST = ["#6366f1","#22c55e","#f59e0b","#ef4444","#8b5cf6","#06b6d4","#ec4899","#14b8a6"];

// ─── Export utils ─────────────────────────────────────────────────────
// ─── Util: Bersihkan teks dari emoji untuk ekspor profesional ──────────
function cleanTextForExport(teks) {
  if (!teks) return "";
  return teks
    .replace(/[^\x00-\x7F]/g, "")
    .replace(/  +/g, " ")
    .split("\n").map(l => l.trim()).join("\n")
    .trim();
}

function eksporPDF(hasil, topik, analisis, aktorAnalisis) {
  if (!hasil) return;

  const tanggal = new Date().toLocaleDateString("id-ID", { day: "numeric", month: "long", year: "numeric" });
  const LABEL   = { positif: "Mendukung", netral: "Netral", negatif: "Menolak" };
  const WARNA_B = { positif: "#16a34a", netral: "#4338ca", negatif: "#dc2626" };
  const WARNA_BG= { positif: "#dcfce7", netral: "#e0e7ff", negatif: "#fee2e2" };

  // Narasi bersih
  const narasi = cleanTextForExport(analisis
    .split("\n")
    .filter(l => { const t = l.trim(); return t && !t.includes("|") && !/^#{1,4}\s/.test(t) && !/^\*{1,2}[^*]+\*{1,2}$/.test(t); })
    .join(" ").replace(/\*{1,2}/g, "").slice(0, 1200));

  const prediksi  = hasil.prediksi  ?? {};
  const rondeList = hasil.ronde_detail ?? [];
  const WARNA_SK  = { Konsensus: "#16a34a", Polarisasi: "#dc2626", "Status Quo": "#4338ca" };

  // Tabel semua ronde
  const tabelRonde = rondeList.map(ronde => {
    const baris = (ronde.agen ?? []).map(a => {
      const lb = a.sentimen?.label ?? "netral";
      return `<tr>
        <td>${a.nama}</td>
        <td><span class="badge" style="background:${WARNA_BG[lb]};color:${WARNA_B[lb]};border:1px solid ${WARNA_B[lb]}40">${LABEL[lb] ?? lb}</span></td>
        <td style="color:#374151">${a.sentimen?.skor ?? 0}</td>
        <td>${a.pendapat ?? "-"}</td>
      </tr>`;
    }).join("");
    return `
      <h3 style="margin:24px 0 8px;font-size:13px;font-weight:700;color:#1e293b;border-left:3px solid #6366f1;padding-left:10px">
        Putaran ${ronde.ronde}
      </h3>
      <table>
        <thead><tr><th>Agen</th><th>Sikap</th><th>Skor</th><th>Pendapat</th></tr></thead>
        <tbody>${baris}</tbody>
      </table>`;
  }).join("");

  // Prediksi bar
  const prediksiBar = Object.entries(prediksi).map(([k, v]) => `
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:10px">
      <span style="width:100px;font-size:12px;color:#374151;font-weight:600">${k}</span>
      <div style="flex:1;height:10px;background:#e2e8f0;border-radius:99px;overflow:hidden">
        <div style="height:100%;width:${v}%;background:${WARNA_SK[k] ?? "#6366f1"};border-radius:99px"></div>
      </div>
      <span style="width:36px;text-align:right;font-size:12px;font-weight:700;color:${WARNA_SK[k] ?? "#6366f1"}">${v}%</span>
    </div>`).join("");

  // Evolusi memori per agen
  const memoriPerAgen = {};
  rondeList.forEach(r => {
    (r.agen ?? []).forEach(a => {
      if (!memoriPerAgen[a.nama]) memoriPerAgen[a.nama] = [];
      memoriPerAgen[a.nama].push({ ronde: r.ronde, pendapat: a.pendapat, sentimen: a.sentimen });
    });
  });
  const tabelMemori = Object.entries(memoriPerAgen).map(([nama, riwayat]) => {
    const akhir = riwayat.at(-1)?.sentimen?.label ?? "netral";
    const baris = riwayat.map(item => {
      const lb = item.sentimen?.label ?? "netral";
      return `<tr>
        <td style="text-align:center;font-weight:700;color:#6366f1">P${item.ronde}</td>
        <td><span class="badge" style="background:${WARNA_BG[lb]};color:${WARNA_B[lb]};border:1px solid ${WARNA_B[lb]}40">${LABEL[lb] ?? lb}</span></td>
        <td style="color:#6b7280;font-size:11px">${item.sentimen?.skor ?? 0}</td>
        <td style="font-style:italic;color:#374151">"${item.pendapat ?? ""}"</td>
      </tr>`;
    }).join("");
    return `
      <div style="margin-bottom:4px;font-size:12px;font-weight:700;color:#1e293b;display:flex;align-items:center;gap:8px">
        ${nama}
        <span class="badge" style="background:${WARNA_BG[akhir]};color:${WARNA_B[akhir]};border:1px solid ${WARNA_B[akhir]}40">${LABEL[akhir] ?? akhir}</span>
      </div>
      <table style="margin-bottom:16px">
        <thead><tr><th style="width:32px">Ronde</th><th style="width:90px">Sikap</th><th style="width:40px">Skor</th><th>Pendapat</th></tr></thead>
        <tbody>${baris}</tbody>
      </table>`;
  }).join("");

  // Aktor kunci & swing voter section untuk PDF
  const aktorKunci   = aktorAnalisis?.aktor_kunci  ?? [];
  const swingVoter   = aktorAnalisis?.swing_voter  ?? [];
  const penggerak    = aktorAnalisis?.aktor_penggerak ?? "-";
  const rekomendasi  = aktorAnalisis?.rekomendasi  ?? "";

  const aktorKunciHTML = aktorKunci.map(a => {
    const lb   = a.sikap_label ?? "Netral";
    const wBg  = { Mendukung: "#dcfce7", Menolak: "#fee2e2", Netral: "#e0e7ff" }[lb] ?? "#f1f5f9";
    const wCol = { Mendukung: "#166534", Menolak: "#991b1b", Netral: "#3730a3" }[lb] ?? "#475569";
    const pct  = Math.round((a.pengaruh_skor ?? 0) * 100);
    return `<div style="margin-bottom:10px;padding:10px 12px;border:1px solid #e2e8f0;border-radius:8px;background:#f8fafc">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">
        <strong style="font-size:12px;color:#1e293b">${a.nama}</strong>
        <span style="font-size:10px;font-weight:700;padding:2px 8px;border-radius:99px;background:${wBg};color:${wCol}">${lb}</span>
      </div>
      <p style="font-size:11px;color:#475569;margin:0 0 4px">${a.alasan}</p>
      <p style="font-size:10px;color:#94a3b8;margin:0 0 4px">⚡ Jika berubah: ${a.dampak_jika_berubah}</p>
      <div style="display:flex;align-items:center;gap:8px">
        <span style="font-size:10px;color:#64748b">Pengaruh</span>
        <div style="flex:1;height:6px;background:#e2e8f0;border-radius:99px"><div style="height:100%;width:${pct}%;background:#6366f1;border-radius:99px"></div></div>
        <span style="font-size:10px;font-weight:700;color:#6366f1">${pct}%</span>
      </div>
    </div>`;
  }).join("");

  const swingVoterHTML = swingVoter.map(a => {
    const arahWarna = a.potensi_arah === "mendukung" ? "#16a34a" : "#dc2626";
    const vol = Math.min(100, Math.round((a.volatilitas ?? 0) * 100));
    const volWarna = vol > 60 ? "#dc2626" : vol > 30 ? "#d97706" : "#16a34a";
    return `<div style="margin-bottom:10px;padding:10px 12px;border:1px solid #e2e8f0;border-radius:8px;background:#f8fafc">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">
        <strong style="font-size:12px;color:#1e293b">${a.nama}</strong>
        <span style="font-size:10px;font-weight:700;padding:2px 8px;border-radius:99px;border:1px solid ${arahWarna}50;color:${arahWarna};background:${arahWarna}15">→ ${a.potensi_arah}</span>
      </div>
      <p style="font-size:11px;color:#475569;margin:0 0 4px">${a.alasan_volatil}</p>
      <p style="font-size:10px;color:#94a3b8;margin:0 0 4px">Tren skor: ${a.sikap_awal?.toFixed(2) ?? "?"} → ${a.sikap_akhir?.toFixed(2) ?? "?"}</p>
      <div style="display:flex;align-items:center;gap:8px">
        <span style="font-size:10px;color:#64748b">Volatilitas</span>
        <div style="flex:1;height:6px;background:#e2e8f0;border-radius:99px"><div style="height:100%;width:${vol}%;background:${volWarna};border-radius:99px"></div></div>
        <span style="font-size:10px;font-weight:700;color:${volWarna}">${vol}%</span>
      </div>
    </div>`;
  }).join("");

  const html = `<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="UTF-8"/>
<title>Laporan VoxSwarm — ${topik}</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 12px;
    color: #1e293b;
    background: #fff;
    padding: 0;
  }
  .page { max-width: 794px; margin: 0 auto; padding: 36px 44px; }

  /* Cover */
  .cover {
    background: linear-gradient(135deg, #1e1b4b 0%, #312e81 50%, #1e3a5f 100%);
    color: white;
    padding: 48px 44px 40px;
    margin-bottom: 32px;
  }
  .cover-label { font-size: 10px; font-weight: 700; letter-spacing: 3px; text-transform: uppercase; color: #a5b4fc; margin-bottom: 16px; }
  .cover-title { font-size: 22px; font-weight: 800; line-height: 1.3; color: #fff; margin-bottom: 20px; }
  .cover-meta { display: flex; flex-wrap: wrap; gap: 20px; margin-top: 24px; }
  .cover-meta-item { font-size: 11px; color: #c7d2fe; }
  .cover-meta-item strong { color: #e0e7ff; display: block; font-size: 10px; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 2px; }
  .cover-divider { height: 1px; background: rgba(255,255,255,0.15); margin: 20px 0; }

  /* Sections */
  .section { margin-bottom: 28px; }
  .section-title {
    font-size: 11px; font-weight: 800; letter-spacing: 2px; text-transform: uppercase;
    color: #4338ca; border-bottom: 2px solid #e0e7ff; padding-bottom: 6px; margin-bottom: 14px;
  }
  .section-title span { margin-right: 6px; }

  /* Narasi */
  .narasi { font-size: 12px; line-height: 1.75; color: #374151; background: #f8fafc; border-left: 3px solid #6366f1; padding: 14px 16px; border-radius: 0 8px 8px 0; }

  /* Table */
  table { width: 100%; border-collapse: collapse; font-size: 11px; }
  th { background: #1e1b4b; color: #e0e7ff; text-align: left; padding: 7px 10px; font-size: 10px; letter-spacing: 0.5px; }
  td { padding: 6px 10px; border-bottom: 1px solid #f1f5f9; color: #374151; vertical-align: top; line-height: 1.5; }
  tr:nth-child(even) td { background: #f8fafc; }

  /* Badge */
  .badge { display: inline-block; padding: 2px 8px; border-radius: 99px; font-size: 10px; font-weight: 700; white-space: nowrap; }

  /* Footer */
  .footer { text-align: center; font-size: 10px; color: #94a3b8; border-top: 1px solid #e2e8f0; padding-top: 16px; margin-top: 32px; }

  @media print {
    @page { size: A4 portrait; margin: 12mm 14mm; }
    body { print-color-adjust: exact; -webkit-print-color-adjust: exact; }
    .no-break { page-break-inside: avoid; break-inside: avoid; }
    .page-break { page-break-before: always; }
  }
</style>
</head>
<body>

<!-- COVER -->
<div class="cover">
  <div class="cover-label">🧠 VoxSwarm — Laporan Simulasi Opini Multi-Agen</div>
  <div class="cover-title">${topik}</div>
  <div class="cover-divider"></div>
  <div class="cover-meta">
    <div class="cover-meta-item"><strong>Tanggal</strong>${tanggal}</div>
    <div class="cover-meta-item"><strong>Jumlah Putaran</strong>${hasil.jumlah_ronde ?? "-"}</div>
    <div class="cover-meta-item"><strong>Jumlah Agen</strong>${(rondeList[0]?.agen ?? []).length}</div>
    <div class="cover-meta-item"><strong>Kategori</strong>${hasil.kategori ?? "Umum"}</div>
    ${hasil.intervensi ? `<div class="cover-meta-item"><strong>Intervensi</strong>${hasil.intervensi}</div>` : ""}
  </div>
</div>

<div class="page">

<!-- 1. RINGKASAN -->
<div class="section no-break">
  <div class="section-title"><span>📋</span>Ringkasan Analisis</div>
  <div class="narasi">${narasi || "—"}</div>
</div>

<!-- 2. PREDIKSI -->
<div class="section no-break">
  <div class="section-title"><span>🎯</span>Prediksi Skenario</div>
  ${prediksiBar || "<p style='color:#94a3b8'>Tidak ada data prediksi.</p>"}
</div>

<!-- 3. AKTOR KUNCI -->
<div class="section no-break">
  <div class="section-title"><span>🎯</span>Prediksi Aktor Kunci &amp; Swing Voter</div>

  <div style="background:#fef3c7;border:1px solid #fcd34d;border-radius:8px;padding:12px 16px;margin-bottom:16px;display:flex;gap:10px;align-items:flex-start">
    <span style="font-size:18px">👑</span>
    <div>
      <p style="font-size:10px;font-weight:700;color:#92400e;margin:0 0 2px;text-transform:uppercase;letter-spacing:1px">Aktor Paling Menentukan</p>
      <p style="font-size:14px;font-weight:800;color:#1e293b;margin:0 0 4px">${penggerak}</p>
      ${rekomendasi ? `<p style="font-size:11px;color:#78350f;margin:0">💡 ${rekomendasi}</p>` : ""}
    </div>
  </div>

  <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
    <div>
      <p style="font-size:10px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:1.5px;margin-bottom:8px">🏛️ Aktor Kunci</p>
      ${aktorKunciHTML || '<p style="color:#94a3b8;font-size:11px">Tidak ada data.</p>'}
    </div>
    <div>
      <p style="font-size:10px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:1.5px;margin-bottom:8px">🔄 Swing Voter</p>
      ${swingVoterHTML || '<p style="color:#94a3b8;font-size:11px">Semua agen konsisten.</p>'}
    </div>
  </div>
</div>

<!-- 4. TABEL PER RONDE -->
<div class="section">
  <div class="section-title"><span>💬</span>Pendapat Agen per Putaran</div>
  ${tabelRonde}
</div>

<!-- 5. EVOLUSI MEMORI -->
<div class="section page-break">
  <div class="section-title"><span>🧠</span>Evolusi Pendapat Agen</div>
  <p style="font-size:11px;color:#64748b;margin-bottom:14px">Perubahan sikap setiap agen dari putaran ke putaran.</p>
  ${tabelMemori}
</div>

<div class="footer">
  Laporan ini dibuat otomatis oleh <strong>VoxSwarm</strong> — Sistem Simulasi Opini Multi-Agen &nbsp;·&nbsp; ${tanggal}
</div>

</div><!-- /page -->
<script>window.onload = () => window.print();<\/script>
</body>
</html>`;

  const blob = new Blob([html], { type: "text/html;charset=utf-8" });
  const url  = URL.createObjectURL(blob);
  window.open(url, "_blank");
  setTimeout(() => URL.revokeObjectURL(url), 60000);
}

function eksporCSV(hasil, topik) {
  if (!hasil) return;
  const baris = [["Putaran","Nama Agen","Pendapat","Sentimen","Skor (-1 s/d 1)"]];
  (hasil.ronde_detail ?? []).forEach(ronde => {
    (ronde.agen ?? []).forEach(a => {
      baris.push([
        ronde.ronde, a.nama,
        `"${cleanTextForExport(a.pendapat ?? "").replace(/"/g, "'")}"`,
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
  const narasi    = cleanTextForExport(analisis.split("\n").filter(l => !l.includes("|") && l.trim()).join(" ").slice(0, 800));
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
  const style = {
    positif: "bg-green-900/50 text-green-300 border-green-700 print-badge-mendukung",
    netral:  "bg-indigo-900/50 text-indigo-300 border-indigo-700 print-badge-netral",
    negatif: "bg-red-900/50 text-red-300 border-red-700 print-badge-menolak",
  }[label] ?? "bg-slate-800 text-slate-400 border-slate-600";
  return <span className={`rounded-full border px-2.5 py-0.5 text-[11px] font-semibold ${style}`}>{LABEL_SENTIMEN[label] ?? label ?? "–"}</span>;
};

const Kartu = ({ children, className = "" }) => (
  <div className={`rounded-2xl border border-white/10 bg-[#0C0F1D] p-6 page-break-avoid print-card ${className}`}>{children}</div>
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

// ─── Komponen: Badge Dual-Model Info ─────────────────────────────────
// Menampilkan model mana yang dipakai untuk agen vs analisis (ala MiroFish)
const DualModelBadge = ({ modelInfo }) => {
  if (!modelInfo) return null;
  const shortName = (m) => m?.split("-").slice(0, 3).join("-") ?? "—";
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-xl border border-white/5 bg-[#0C0F1D] px-4 py-2.5 print:hidden">
      <span className="text-[10px] font-bold tracking-widest uppercase text-slate-600">⚡ Dual-Model</span>
      <div className="flex items-center gap-1.5">
        <span className="rounded-md bg-violet-900/50 border border-violet-700/50 px-2 py-0.5 text-[10px] font-semibold text-violet-300">
          Agen: {shortName(modelInfo.agen)}
        </span>
        <span className="text-slate-700 text-xs">+</span>
        <span className="rounded-md bg-cyan-900/50 border border-cyan-700/50 px-2 py-0.5 text-[10px] font-semibold text-cyan-300">
          Analisis: {shortName(modelInfo.analisis)}
        </span>
      </div>
      <span className="text-[10px] text-slate-700">Model kecil → cepat · Model besar → akurat</span>
    </div>
  );
};

// ─── Komponen: Graf Knowledge Interaktif (SVG) ────────────────────────
// Visualisasi entitas & relasi dari GraphRAG sebagai node-edge diagram
// Menggantikan tampilan teks statis, mendekati tampilan MiroFish
const GrafKnowledge = ({ grafData }) => {
  const canvasRef = useRef(null);
  const [hoveredNode, setHoveredNode] = useState(null);
  const [nodes, setNodes] = useState([]);
  const [edges, setEdges] = useState([]);

  const WARNA_TIPE = {
    orang:        "#6366f1",
    organisasi:   "#f59e0b",
    konsep:       "#22c55e",
    kebijakan:    "#06b6d4",
  };
  const WARNA_REL = {
    mendukung:       "#22c55e",
    menolak:         "#ef4444",
    mempengaruhi:    "#f59e0b",
    bergantung_pada: "#8b5cf6",
  };

  useEffect(() => {
    const entitas = grafData?.entitas ?? [];
    if (!entitas.length) return;

    // Tata letak melingkar sederhana (force-layout simulasi ringan)
    const cx = 280, cy = 150, r = 110;
    const builtNodes = entitas.slice(0, 10).map((e, i) => {
      const angle = (i / Math.min(entitas.length, 10)) * 2 * Math.PI - Math.PI / 2;
      // Atur radius berdasarkan jumlah node agar tidak tumpang tindih
      const radius = entitas.length <= 4 ? 80 : entitas.length <= 6 ? 100 : r;
      return {
        id:   e.nama,
        x:    cx + radius * Math.cos(angle),
        y:    cy + radius * Math.sin(angle),
        tipe: e.tipe ?? "konsep",
        sentimen: e.sentimen_umum ?? "netral",
        warna:    WARNA_TIPE[e.tipe] ?? "#6366f1",
      };
    });

    const nodeMap = Object.fromEntries(builtNodes.map(n => [n.id, n]));
    const builtEdges = (grafData?.relasi ?? []).slice(0, 14).map((rel, i) => ({
      id:    i,
      dari:  nodeMap[rel.dari],
      ke:    nodeMap[rel.ke],
      label: rel.label ?? "mempengaruhi",
      warna: WARNA_REL[rel.label] ?? "#6b7280",
    })).filter(e => e.dari && e.ke);

    setNodes(builtNodes);
    setEdges(builtEdges);
  }, [grafData]);

  if (!grafData?.entitas?.length) return null;

  return (
    <Kartu>
      <JudulSeksi>🕸️ Graf Pengetahuan — Peta Relasi Entitas</JudulSeksi>
      <p className="mb-3 text-xs text-slate-500">
        Visualisasi entitas dan hubungan yang diekstrak dari diskusi (GraphRAG-lite).
        Hover pada node untuk detail.
      </p>

      {/* Legend warna relasi */}
      <div className="mb-3 flex flex-wrap gap-3">
        {Object.entries(WARNA_REL).map(([label, warna]) => (
          <span key={label} className="flex items-center gap-1.5 text-[10px] text-slate-500">
            <span className="inline-block h-2 w-5 rounded-full" style={{ backgroundColor: warna }} />
            {label.replace("_", " ")}
          </span>
        ))}
      </div>

      {/* SVG Graf */}
      <div className="relative overflow-hidden rounded-xl bg-[#080b15] border border-white/5" style={{ height: 300 }}>
        <svg ref={canvasRef} width="100%" height="300" viewBox="0 0 560 300">
          {/* Definisi arrowhead */}
          <defs>
            {Object.entries(WARNA_REL).map(([label, warna]) => (
              <marker
                key={label}
                id={`arrow-${label}`}
                viewBox="0 0 10 10"
                refX="16" refY="5"
                markerWidth="5" markerHeight="5"
                orient="auto-start-reverse"
              >
                <path d="M 0 0 L 10 5 L 0 10 z" fill={warna} opacity="0.8" />
              </marker>
            ))}
          </defs>

          {/* Edges */}
          {edges.map(e => {
            const dx = e.ke.x - e.dari.x;
            const dy = e.ke.y - e.dari.y;
            const len = Math.sqrt(dx * dx + dy * dy) || 1;
            // Kurva sedikit untuk tidak overlap dengan edge lain
            const mx = (e.dari.x + e.ke.x) / 2 - dy * 0.15;
            const my = (e.dari.y + e.ke.y) / 2 + dx * 0.15;
            return (
              <g key={e.id}>
                <path
                  d={`M${e.dari.x},${e.dari.y} Q${mx},${my} ${e.ke.x},${e.ke.y}`}
                  fill="none"
                  stroke={e.warna}
                  strokeWidth="1.5"
                  strokeOpacity="0.6"
                  markerEnd={`url(#arrow-${e.label})`}
                />
                {/* Label relasi di tengah kurva */}
                <text
                  x={mx} y={my - 4}
                  textAnchor="middle"
                  fontSize="7"
                  fill={e.warna}
                  opacity="0.8"
                >
                  {e.label.replace("_", " ")}
                </text>
              </g>
            );
          })}

          {/* Nodes */}
          {nodes.map(n => {
            const isHovered = hoveredNode?.id === n.id;
            const r = isHovered ? 22 : 18;
            return (
              <g
                key={n.id}
                onMouseEnter={() => setHoveredNode(n)}
                onMouseLeave={() => setHoveredNode(null)}
                style={{ cursor: "pointer" }}
              >
                {/* Glow effect untuk node yang di-hover */}
                {isHovered && (
                  <circle cx={n.x} cy={n.y} r={r + 8} fill={n.warna} opacity="0.12" />
                )}
                {/* Lingkaran utama */}
                <circle
                  cx={n.x} cy={n.y} r={r}
                  fill={n.warna + "22"}
                  stroke={n.warna}
                  strokeWidth={isHovered ? 2.5 : 1.5}
                />
                {/* Inisial nama */}
                <text
                  x={n.x} y={n.y + 1}
                  textAnchor="middle"
                  dominantBaseline="middle"
                  fontSize="8"
                  fontWeight="bold"
                  fill={n.warna}
                >
                  {n.id.slice(0, 3).toUpperCase()}
                </text>
                {/* Nama lengkap di bawah node */}
                <text
                  x={n.x} y={n.y + r + 11}
                  textAnchor="middle"
                  fontSize="8"
                  fill="#94a3b8"
                >
                  {n.id.length > 14 ? n.id.slice(0, 13) + "…" : n.id}
                </text>
              </g>
            );
          })}
        </svg>

        {/* Tooltip hover node */}
        {hoveredNode && (
          <div className="absolute bottom-3 left-3 rounded-xl border border-white/10 bg-[#0C0F1D] px-3 py-2 text-[11px] shadow-xl">
            <p className="font-bold text-slate-200">{hoveredNode.id}</p>
            <p className="text-slate-500">
              Tipe: <span className="text-slate-300">{hoveredNode.tipe}</span>
              {" · "}
              Sentimen: <span style={{ color: { positif: "#22c55e", negatif: "#ef4444", netral: "#6366f1" }[hoveredNode.sentimen] }}>
                {hoveredNode.sentimen}
              </span>
            </p>
          </div>
        )}
      </div>

      {/* Relasi teks (sebagai referensi) */}
      {edges.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1">
          {edges.slice(0, 6).map((e, i) => (
            <p key={i} className="text-[10px] text-slate-600">
              <span style={{ color: e.warna }} className="font-medium">{e.dari.id}</span>
              <span className="mx-1 text-slate-700">→{e.label}→</span>
              <span style={{ color: e.warna }} className="font-medium">{e.ke.id}</span>
            </p>
          ))}
        </div>
      )}
    </Kartu>
  );
};

// ─── Komponen: Panel Intervensi Sosmed (Breaking News live injection) ──
const PanelIntervensiSosmed = ({ topik, kategori, jumlahTick, agenCustom, onHasilBaru, memuat, setMemuat, apiBase }) => {
  const [intervensi, setIntervensi] = useState("");
  const [tampil,     setTampil]     = useState(false);
  const [pesanError, setPesanError] = useState("");

  const kirimIntervensi = async () => {
    if (!intervensi.trim()) return;
    setPesanError("");
    setMemuat(true);
    try {
      const body = {
        topik:       topik.trim(),
        kategori,
        jumlah_tick: jumlahTick,
        intervensi:  intervensi.trim(),
        agen_custom: agenCustom.length ? agenCustom : undefined,
      };
      const res = await fetch(`${apiBase}/start-social`, {
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
          <span className="text-base">⚡</span>
          <span className="text-sm font-bold text-amber-300">Breaking News — Injeksi Intervensi</span>
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
        Suntikkan breaking news ke dalam simulasi sosmed. Semua agen akan bereaksi terhadap berita baru ini.
      </p>
      {tampil && (
        <div className="space-y-3">
          <textarea
            rows={2}
            className="w-full rounded-xl border border-amber-500/30 bg-[#0E1220] px-4 py-3 text-sm text-slate-100 placeholder:text-slate-600 outline-none focus:border-amber-500 transition resize-none"
            value={intervensi}
            onChange={e => setIntervensi(e.target.value)}
            placeholder='Contoh: "Pemerintah blokir semua media sosial mulai besok"'
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
        </div>
      )}
    </div>
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

// ─── Komponen: Aktor Kunci & Swing Voter ──────────────────────────────
const KartuAktorKunci = ({ aktorAnalisis, warnaAgen }) => {
  if (!aktorAnalisis) return null;

  const aktorKunci  = aktorAnalisis.aktor_kunci  ?? [];
  const swingVoter  = aktorAnalisis.swing_voter  ?? [];
  const penggerak   = aktorAnalisis.aktor_penggerak ?? "-";
  const rekomendasi = aktorAnalisis.rekomendasi  ?? "";

  const WARNA_LABEL = { Mendukung: "#22c55e", Menolak: "#ef4444", Netral: "#6366f1" };
  const BG_LABEL    = { Mendukung: "bg-green-900/40 text-green-300 border-green-700", Menolak: "bg-red-900/40 text-red-300 border-red-700", Netral: "bg-indigo-900/40 text-indigo-300 border-indigo-700" };

  // Bar pengaruh (0–1 → 0–100%)
  const PengaruhBar = ({ skor }) => (
    <div className="flex items-center gap-2 mt-1">
      <div className="flex-1 h-1.5 rounded-full bg-white/5">
        <div className="h-full rounded-full bg-indigo-500" style={{ width: `${Math.round((skor ?? 0) * 100)}%` }} />
      </div>
      <span className="text-[10px] text-indigo-300 font-bold w-7 text-right">{Math.round((skor ?? 0) * 100)}%</span>
    </div>
  );

  // Bar volatilitas (-1..1 jarak → 0..1)
  const VolatilitasBar = ({ vol }) => {
    const pct = Math.min(100, Math.round((vol ?? 0) * 100));
    const warna = pct > 60 ? "#ef4444" : pct > 30 ? "#f59e0b" : "#22c55e";
    return (
      <div className="flex items-center gap-2 mt-1">
        <div className="flex-1 h-1.5 rounded-full bg-white/5">
          <div className="h-full rounded-full" style={{ width: `${pct}%`, backgroundColor: warna }} />
        </div>
        <span className="text-[10px] font-bold w-7 text-right" style={{ color: warna }}>{pct}%</span>
      </div>
    );
  };

  return (
    <Kartu>
      <JudulSeksi>🎯 Prediksi Aktor Kunci & Swing Voter</JudulSeksi>
      <p className="mb-5 text-xs text-slate-500">
        Siapa yang paling menentukan hasil akhir, dan siapa yang masih bisa berpindah pihak.
      </p>

      {/* Aktor Penggerak — highlight utama */}
      <div className="mb-5 rounded-xl border border-amber-500/30 bg-amber-950/20 px-4 py-3 flex items-start gap-3">
        <span className="text-xl shrink-0">👑</span>
        <div>
          <p className="text-xs font-bold text-amber-300 mb-0.5">Aktor Paling Menentukan</p>
          <p className="text-sm font-black text-white">{penggerak}</p>
          {rekomendasi && (
            <p className="mt-1.5 text-xs text-amber-200/70 leading-relaxed">💡 {rekomendasi}</p>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">

        {/* Aktor Kunci */}
        <div>
          <p className="mb-3 text-[11px] font-bold text-slate-400 uppercase tracking-widest">
            🏛️ Aktor Kunci — Pengaruh Tinggi
          </p>
          <div className="space-y-3">
            {aktorKunci.length === 0 && <p className="text-xs text-slate-600">Tidak ada data.</p>}
            {aktorKunci.map((a, i) => {
              const warna = warnaAgen[a.nama] ?? WARNA_AGEN_LIST[i % WARNA_AGEN_LIST.length];
              const lb    = a.sikap_label ?? "Netral";
              return (
                <div key={i} className="rounded-xl border border-white/8 bg-white/3 p-3">
                  <div className="flex items-center gap-2 mb-1">
                    <div className="h-6 w-6 rounded-full flex items-center justify-center text-[9px] font-black shrink-0"
                      style={{ backgroundColor: warna + "22", border: `1.5px solid ${warna}`, color: warna }}>
                      {a.nama.slice(0,2).toUpperCase()}
                    </div>
                    <span className="text-xs font-bold text-slate-200 flex-1 truncate">{a.nama}</span>
                    <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${BG_LABEL[lb] ?? "bg-slate-800 text-slate-400 border-slate-600"}`}>{lb}</span>
                  </div>
                  <p className="text-[11px] text-slate-500 mb-1.5 leading-relaxed">{a.alasan}</p>
                  <p className="text-[10px] text-slate-600 italic mb-1">
                    ⚡ Jika berubah: <span className="text-slate-400 not-italic">{a.dampak_jika_berubah}</span>
                  </p>
                  <p className="text-[10px] text-slate-600 mb-0.5">Bobot pengaruh</p>
                  <PengaruhBar skor={a.pengaruh_skor} />
                </div>
              );
            })}
          </div>
        </div>

        {/* Swing Voter */}
        <div>
          <p className="mb-3 text-[11px] font-bold text-slate-400 uppercase tracking-widest">
            🔄 Swing Voter — Mudah Berubah
          </p>
          <div className="space-y-3">
            {swingVoter.length === 0 && <p className="text-xs text-slate-600">Semua agen cukup konsisten.</p>}
            {swingVoter.map((a, i) => {
              const warna = warnaAgen[a.nama] ?? WARNA_AGEN_LIST[i % WARNA_AGEN_LIST.length];
              const arahWarna = a.potensi_arah === "mendukung" ? "#22c55e" : "#ef4444";
              const skorAwal  = typeof a.sikap_awal  === "number" ? a.sikap_awal.toFixed(2)  : "?";
              const skorAkhir = typeof a.sikap_akhir === "number" ? a.sikap_akhir.toFixed(2) : "?";
              return (
                <div key={i} className="rounded-xl border border-white/8 bg-white/3 p-3">
                  <div className="flex items-center gap-2 mb-1">
                    <div className="h-6 w-6 rounded-full flex items-center justify-center text-[9px] font-black shrink-0"
                      style={{ backgroundColor: warna + "22", border: `1.5px solid ${warna}`, color: warna }}>
                      {a.nama.slice(0,2).toUpperCase()}
                    </div>
                    <span className="text-xs font-bold text-slate-200 flex-1 truncate">{a.nama}</span>
                    <span className="rounded-full px-2 py-0.5 text-[10px] font-bold border"
                      style={{ color: arahWarna, borderColor: arahWarna + "50", backgroundColor: arahWarna + "15" }}>
                      → {a.potensi_arah}
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-500 mb-1.5 leading-relaxed">{a.alasan_volatil}</p>
                  <div className="flex items-center gap-2 text-[10px] text-slate-600 mb-1">
                    <span>Tren: <span className="text-slate-400">{skorAwal} → {skorAkhir}</span></span>
                  </div>
                  <p className="text-[10px] text-slate-600 mb-0.5">Volatilitas sikap</p>
                  <VolatilitasBar vol={a.volatilitas} />
                </div>
              );
            })}
          </div>
        </div>

      </div>
    </Kartu>
  );
};

// ─── WARNA agen sosmed ────────────────────────────────────────────────
const WARNA_HANDLE = ["#6366f1","#22c55e","#f59e0b","#ef4444","#8b5cf6","#06b6d4","#ec4899","#14b8a6","#f97316","#a855f7"];
function warnaHandle(nama) {
  let h = 0; for (let i = 0; i < nama.length; i++) h = (h * 31 + nama.charCodeAt(i)) & 0xffff;
  return WARNA_HANDLE[h % WARNA_HANDLE.length];
}

// ─── Komponen: Avatar sosmed ──────────────────────────────────────────
const Avatar = ({ nama, size = 9 }) => {
  const w = warnaHandle(nama);
  return (
    <div className={`h-${size} w-${size} shrink-0 rounded-full flex items-center justify-center text-[10px] font-black`}
      style={{ backgroundColor: w + "28", border: `1.5px solid ${w}`, color: w }}>
      {nama.slice(0, 2).toUpperCase()}
    </div>
  );
};

// ─── Komponen: Kartu Post Twitter-style ──────────────────────────────
const KartuPost = ({ post: postRaw, postMap, aksiList, onLikeInfo }) => {
  const [bukaThread, setBukaThread] = useState(false);

  // Selalu baca dari postMap supaya likes/replies/quotes selalu fresh (latest state)
  const post = postMap?.[postRaw.id] ?? postRaw;

  const w = warnaHandle(post.nama ?? "?");
  const sentLabel = post.sentimen?.label;
  const sentWarna = { positif: "#22c55e", netral: "#6366f1", negatif: "#ef4444" }[sentLabel] ?? "#6366f1";
  const isViral = post.is_viral;

  // Hitung dari array langsung — jaga-jaga kalau array sudah termutasi
  const likes   = Array.isArray(post.likes)   ? post.likes   : [];
  const replies = Array.isArray(post.replies) ? post.replies : [];
  const quotes  = Array.isArray(post.quotes)  ? post.quotes  : [];
  const likeCount  = likes.length;
  const replyCount = replies.length;
  const quoteCount = quotes.length;

  const isOtoritas = post.nama?.toLowerCase().includes("pemerintah") || post.nama?.toLowerCase().includes("pejabat");
  const isSistem   = post.akun_id === "SYSTEM";
  const tipeWarna  = { reply: "#06b6d4", quote: "#8b5cf6", post: null }[post.tipe];

  // Cari aksi kebijakan terkait post ini
  const kebijakanAksi = aksiList?.find(a =>
    (a.tipe === "reply_otoritas" || a.tipe === "quote_otoritas") &&
    (a.target_id === post.id || a.post?.id === post.id) && a.kebijakan_baru
  );

  // Post yang di-reply / di-quote (untuk konteks)
  const parentPost = post.tipe === "reply" && post.reply_to
    ? postMap?.[post.reply_to]
    : post.tipe === "quote" && post.quote_of
      ? postMap?.[post.quote_of]
      : null;

  // Replies lengkap (baca dari postMap supaya fresh)
  const replyPosts = replies
    .map(rid => postMap?.[rid])
    .filter(Boolean)
    .slice(0, 4);

  // Siapa saja yang like (nama bersih dari handle)
  const likerNames = likes.map(h => h.replace(/^@/, "").replace(/_/g, " "));

  if (isSistem) {
    return (
      <div className="rounded-2xl border border-amber-500/50 bg-amber-950/20 px-4 py-3 flex items-center gap-3">
        <span className="text-2xl shrink-0">🚨</span>
        <div>
          <p className="text-[10px] font-bold text-amber-400 mb-0.5">BREAKING NEWS</p>
          <p className="text-sm font-bold text-amber-200">{post.konten?.replace("🚨 BREAKING: ", "")}</p>
        </div>
        <span className="ml-auto rounded-full bg-amber-500/20 border border-amber-500/40 px-2 py-0.5 text-[10px] font-black text-amber-300">SISTEM</span>
      </div>
    );
  }

  return (
    <div className={`rounded-2xl border bg-[#0C0F1D] p-4 transition-all ${isViral ? "border-amber-500/40 shadow-[0_0_24px_rgba(245,158,11,0.09)]" : "border-white/8"}`}>
      <div className="flex items-start gap-3">
        <Avatar nama={post.nama ?? "?"} size={9} />
        <div className="flex-1 min-w-0">

          {/* ── Baris nama + badge ── */}
          <div className="flex flex-wrap items-center gap-1.5 mb-1">
            <span className="text-sm font-bold text-white">{post.nama}</span>
            <span className="text-xs text-slate-500">{post.handle}</span>
            {isOtoritas && (
              <span className="rounded-full bg-blue-500/20 border border-blue-500/40 px-2 py-0.5 text-[10px] font-bold text-blue-300">🏛️ Otoritas</span>
            )}
            {isViral && (
              <span className="rounded-full bg-amber-500/20 border border-amber-500/40 px-2 py-0.5 text-[10px] font-black text-amber-300 animate-pulse">🔥 VIRAL</span>
            )}
            {post.tipe !== "post" && tipeWarna && (
              <span className="rounded-full px-2 py-0.5 text-[10px] font-bold"
                style={{ backgroundColor: tipeWarna + "22", color: tipeWarna, border: `1px solid ${tipeWarna}40` }}>
                {post.tipe === "reply" ? "💬 Membalas" : "🔁 Mengutip"}
              </span>
            )}
            {sentLabel && (
              <span className="rounded-full px-2 py-0.5 text-[10px]"
                style={{ backgroundColor: sentWarna + "18", color: sentWarna }}>
                {{ positif: "Mendukung", netral: "Netral", negatif: "Menolak" }[sentLabel]}
              </span>
            )}
          </div>

          {/* ── FIX #3b: Label hirarki "Agen A membalas Agen B" dari parent_nama langsung ── */}
          {(post.tipe === "reply" || post.tipe === "quote") && post.parent_nama && !parentPost && (
            <div className="mb-1.5 flex items-center gap-1.5 text-[11px] text-slate-500">
              <span>{post.tipe === "reply" ? "💬 Membalas" : "🔁 Mengutip"}</span>
              <Avatar nama={post.parent_nama} size={4} />
              <span className="font-semibold text-slate-400">{post.parent_nama}</span>
              <span className="text-slate-600">{post.parent_handle}</span>
            </div>
          )}

          {/* ── Konteks: membalas / mengutip siapa (dengan preview konten) ── */}
          {parentPost && (
            <div className="mb-2 rounded-xl border border-white/8 bg-white/3 px-3 py-2 text-xs text-slate-400 flex items-start gap-2">
              <Avatar nama={parentPost.nama ?? "?"} size={5} />
              <div className="min-w-0">
                <span className="font-bold text-slate-300">{parentPost.nama}</span>
                <span className="ml-1 text-slate-500">{parentPost.handle}</span>
                <p className="mt-0.5 text-slate-500 truncate">{parentPost.konten?.slice(0, 90)}{parentPost.konten?.length > 90 ? "…" : ""}</p>
              </div>
            </div>
          )}

          {/* ── Konten post ── */}
          <p className="text-sm leading-relaxed text-slate-200">{post.konten}</p>

          {/* ── Kebijakan baru dari otoritas ── */}
          {kebijakanAksi?.kebijakan_baru && (
            <div className="mt-3 rounded-xl border border-blue-500/30 bg-blue-950/20 px-3 py-2">
              <p className="text-[10px] font-bold text-blue-400 mb-1">📋 KEBIJAKAN DIPERTIMBANGKAN</p>
              <p className="text-xs text-blue-200">{kebijakanAksi.kebijakan_baru}</p>
            </div>
          )}

          {/* ── Engagement row ── */}
          <div className="mt-3 flex items-center gap-1 text-[11px]">
            {/* Like — klik untuk lihat siapa */}
            <button
              onClick={() => likeCount > 0 && onLikeInfo?.({ ...post, likerNames })}
              className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 transition font-semibold
                ${likeCount > 0 ? "text-rose-400 bg-rose-500/10 hover:bg-rose-500/20" : "text-slate-600 cursor-default"}`}
            >
              <span>{likeCount > 0 ? "❤️" : "🤍"}</span>
              <span>{likeCount}</span>
              {likeCount > 0 && <span className="text-[10px] text-rose-500/70">like</span>}
            </button>

            {/* Reply */}
            <span className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 font-semibold
              ${replyCount > 0 ? "text-cyan-400 bg-cyan-500/10" : "text-slate-600"}`}>
              <span>💬</span> <span>{replyCount}</span>
              {replyCount > 0 && <span className="text-[10px] text-cyan-500/70">balas</span>}
            </span>

            {/* Quote */}
            <span className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 font-semibold
              ${quoteCount > 0 ? "text-violet-400 bg-violet-500/10" : "text-slate-600"}`}>
              <span>🔁</span> <span>{quoteCount}</span>
              {quoteCount > 0 && <span className="text-[10px] text-violet-500/70">kutip</span>}
            </span>

            {/* Reach */}
            {(post.reach ?? 0) > 0 && (
              <span className="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-slate-600">
                <span>👁️</span> <span>{post.reach}</span>
              </span>
            )}

            {/* Expand thread */}
            {replyPosts.length > 0 && (
              <button onClick={() => setBukaThread(v => !v)}
                className="ml-auto text-[10px] text-indigo-400 hover:text-indigo-300 transition px-2 py-1 rounded-lg hover:bg-indigo-500/10">
                {bukaThread ? "▲ Tutup" : `▼ ${replyPosts.length} balasan`}
              </button>
            )}
          </div>

          {/* ── Pratinjau siapa yang like (inline, maks 5) ── */}
          {likeCount > 0 && (
            <div className="mt-2 flex items-center gap-1.5 flex-wrap">
              <span className="text-[10px] text-slate-600">Disukai:</span>
              {likerNames.slice(0, 5).map((n, i) => (
                <div key={i} className="flex items-center gap-1 rounded-full bg-white/5 border border-white/8 px-2 py-0.5">
                  <Avatar nama={n} size={4} />
                  <span className="text-[10px] text-slate-400 capitalize">{n}</span>
                </div>
              ))}
              {likerNames.length > 5 && <span className="text-[10px] text-slate-600">+{likerNames.length - 5} lainnya</span>}
            </div>
          )}
        </div>
      </div>

      {/* ── Thread replies inline ── */}
      {bukaThread && replyPosts.length > 0 && (
        <div className="mt-3 ml-12 space-y-2.5 border-l-2 border-white/5 pl-4">
          {replyPosts.map(r => (
            <div key={r.id} className="flex gap-2.5">
              <Avatar nama={r.nama ?? "?"} size={7} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-0.5">
                  <span className="text-xs font-bold text-slate-300">{r.nama}</span>
                  <span className="text-[10px] text-slate-600">{r.handle}</span>
                  {r.likes?.length > 0 && (
                    <span className="ml-auto text-[10px] text-rose-400 flex items-center gap-1">❤️ {r.likes.length}</span>
                  )}
                </div>
                <p className="text-xs text-slate-400 leading-relaxed">{r.konten}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

// ─── Komponen: Panel profil agen sosmed ──────────────────────────────
const PanelProfilAgen = ({ profilAgen }) => {
  if (!profilAgen?.length) return null;
  return (
    <Kartu>
      <JudulSeksi>👥 Profil Akun — Siapa Paling Berpengaruh?</JudulSeksi>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
        {profilAgen.map((a, i) => {
          const w = warnaHandle(a.nama);
          return (
            <div key={i} className="rounded-xl border border-white/8 bg-white/3 p-3 flex flex-col gap-1.5">
              <div className="flex items-center gap-2">
                <Avatar nama={a.nama} size={8} />
                <div className="min-w-0">
                  <p className="text-xs font-bold text-white truncate">{a.nama}</p>
                  <p className="text-[10px] text-slate-500 truncate">{a.handle}</p>
                </div>
              </div>
              {a.is_authority && <span className="rounded-full bg-blue-500/20 border border-blue-500/40 px-2 py-0.5 text-[10px] font-bold text-blue-300 w-fit">🏛️ Otoritas</span>}
              {a.is_counter && <span className="rounded-full bg-orange-500/20 border border-orange-500/40 px-2 py-0.5 text-[10px] font-bold text-orange-300 w-fit">⚡ Kontra</span>}
              <div className="grid grid-cols-2 gap-1 text-[10px] text-slate-500 mt-1">
                <span>👥 {a.followers} follower</span>
                <span>📝 {a.total_post} post</span>
                <span>❤️ {a.total_likes_dapat} likes</span>
                <span>👁️ {a.following} following</span>
              </div>
              {/* Bar influence */}
              <div className="mt-1">
                <div className="h-1 rounded-full bg-white/5 overflow-hidden">
                  <div className="h-full rounded-full transition-all" style={{ width: `${Math.min(100, (a.followers + a.total_likes_dapat) * 10)}%`, backgroundColor: w }} />
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </Kartu>
  );
};

// ─── Komponen: Laporan Sosmed ────────────────────────────────────────
// FIX #4: Ringkasan eksekutif, statistik agregat, sentiment breakdown, top influencers
const LaporanSosmed = ({ hasilSosmed }) => {
  if (!hasilSosmed) return null;

  const analisis      = hasilSosmed.analisis      ?? {};
  const statBe        = hasilSosmed.statistik     ?? {};
  const topInfluencer = analisis.top_influencers  ?? [];
  const profilAgen    = hasilSosmed.profil_agen   ?? [];
  const semuaPost     = hasilSosmed.semua_post    ?? [];

  // Hitung Pro vs Kontra dari sentimen semua post
  const sentimenCounts = { positif: 0, netral: 0, negatif: 0 };
  semuaPost.forEach(p => {
    const lb = p.sentimen?.label ?? "netral";
    if (lb in sentimenCounts) sentimenCounts[lb]++;
  });
  const totalSentimen = Object.values(sentimenCounts).reduce((a, b) => a + b, 0) || 1;

  return (
    <Kartu>
      <JudulSeksi>📊 Laporan Hasil Simulasi Sosmed</JudulSeksi>

      {/* Ringkasan Eksekutif */}
      {analisis.narasi && (
        <div className="mb-5">
          <p className="text-[11px] font-bold text-slate-500 uppercase tracking-widest mb-2">Ringkasan Eksekutif</p>
          <p className="text-sm leading-7 text-slate-300 bg-white/3 rounded-xl p-4 border border-white/5">
            {analisis.narasi}
          </p>
        </div>
      )}

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">

        {/* Statistik Agregat */}
        <div>
          <p className="text-[11px] font-bold text-slate-500 uppercase tracking-widest mb-3">Statistik Engagement</p>
          <div className="grid grid-cols-3 gap-2">
            {[
              { label: "Likes",   nilai: statBe.total_likes   ?? semuaPost.reduce((s,p)=>s+(p.likes?.length??0),0),   warna: "#f43f5e" },
              { label: "Balasan", nilai: statBe.total_replies ?? semuaPost.filter(p=>p.tipe==="reply").length,          warna: "#06b6d4" },
              { label: "Kutipan", nilai: statBe.total_quotes  ?? semuaPost.filter(p=>p.tipe==="quote").length,          warna: "#8b5cf6" },
            ].map((s, i) => (
              <div key={i} className="rounded-xl border p-3 text-center"
                style={{ borderColor: s.warna + "30", backgroundColor: s.warna + "0a" }}>
                <div className="text-2xl font-black" style={{ color: s.warna }}>{s.nilai}</div>
                <div className="text-[10px] text-slate-500 mt-0.5">{s.label}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Sentiment Breakdown */}
        <div>
          <p className="text-[11px] font-bold text-slate-500 uppercase tracking-widest mb-3">Distribusi Sentimen Post</p>
          <div className="space-y-2.5">
            {[
              { label: "Mendukung", key: "positif", warna: "#22c55e" },
              { label: "Netral",    key: "netral",  warna: "#6366f1" },
              { label: "Menolak",   key: "negatif", warna: "#ef4444" },
            ].map(s => {
              const pct = Math.round((sentimenCounts[s.key] / totalSentimen) * 100);
              return (
                <div key={s.key} className="flex items-center gap-3">
                  <span className="text-xs text-slate-400 w-20 shrink-0">{s.label}</span>
                  <div className="flex-1 h-2 rounded-full bg-white/5">
                    <div className="h-full rounded-full transition-all"
                      style={{ width: pct + "%", backgroundColor: s.warna }} />
                  </div>
                  <span className="text-xs font-bold w-8 text-right" style={{ color: s.warna }}>{pct}%</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Top 3 Influencers */}
      {topInfluencer.length > 0 && (
        <div className="mt-5">
          <p className="text-[11px] font-bold text-slate-500 uppercase tracking-widest mb-3">Top 3 Influencer</p>
          <div className="space-y-2">
            {topInfluencer.slice(0, 3).map((inf, i) => {
              const w = warnaHandle(inf.nama);
              const profil = profilAgen.find(a => a.nama === inf.nama);
              return (
                <div key={i} className="flex items-center gap-3 rounded-xl bg-white/3 border border-white/8 p-3">
                  <span className="text-xs font-black text-slate-500 w-4">#{i + 1}</span>
                  <div className="h-8 w-8 shrink-0 rounded-full flex items-center justify-center text-[10px] font-black"
                    style={{ backgroundColor: w + "28", border: "1.5px solid " + w, color: w }}>
                    {inf.nama.slice(0, 2).toUpperCase()}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-bold text-slate-200">{inf.nama}</p>
                    <p className="text-[10px] text-slate-500">
                      {profil?.followers ?? 0} followers · {profil?.total_post ?? 0} post
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-black text-amber-400">{inf.engagement_score}</p>
                    <p className="text-[10px] text-slate-600">eng.</p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </Kartu>
  );
};

// ─── Komponen: Timeline sosmed lengkap ───────────────────────────────
const TimelineSosmed = ({ hasilSosmed, topik }) => {
  const [tickAktif, setTickAktif] = useState(0);
  const [filterMode, setFilterMode] = useState("semua");
  const [likeInfoPost, setLikeInfoPost] = useState(null);

  if (!hasilSosmed) return null;

  const tickDetail   = hasilSosmed.tick_detail   ?? [];
  const semuaPost    = hasilSosmed.semua_post     ?? [];
  const profilAgen   = hasilSosmed.profil_agen    ?? [];
  const viralPosts   = hasilSosmed.viral_posts    ?? [];
  const analisis     = hasilSosmed.analisis       ?? {};
  const logAktivitas = hasilSosmed.log_aktivitas  ?? [];

  // Build postMap dari semua_post (sumber kebenaran paling fresh dari backend)
  const postMap = {};
  semuaPost.forEach(p => { postMap[p.id] = p; });

  // Post yang ditampilkan sesuai filter
  const postTampil = useMemo(() => {
    if (filterMode === "viral") {
      return [...viralPosts].sort((a, b) => {
        const engA = (a.likes?.length ?? 0) + (a.replies?.length ?? 0) * 2 + (a.quotes?.length ?? 0) * 3;
        const engB = (b.likes?.length ?? 0) + (b.replies?.length ?? 0) * 2 + (b.quotes?.length ?? 0) * 3;
        return engB - engA;
      });
    }
    if (filterMode === "timeline") {
      const tick = tickDetail[tickAktif];
      if (!tick) return [];
      return (tick.posts_baru ?? []).map(p => postMap[p.id] ?? p);
    }
    return [...semuaPost].reverse();
  }, [filterMode, viralPosts, tickDetail, tickAktif, semuaPost, postMap]);

  // Kebijakan baru dari otoritas
  const semuaKebijakan = logAktivitas
    .filter(a => (a.tipe === "reply_otoritas" || a.tipe === "quote_otoritas") && a.kebijakan_baru)
    .map(a => ({ kebijakan: a.kebijakan_baru, agen: a.agen, target_id: a.target_id }));

  return (
    <div className="space-y-5">

      {/* ── Kartu "Topik Hari Ini" — starter context ── */}
      <div className="rounded-2xl border border-indigo-500/30 bg-indigo-950/20 p-4 flex items-start gap-3">
        <div className="h-10 w-10 shrink-0 rounded-full bg-indigo-500/20 border border-indigo-500/50 flex items-center justify-center text-lg">📢</div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1 flex-wrap">
            <span className="text-sm font-bold text-indigo-300">Isu yang Disimulasikan</span>
            <span className="rounded-full bg-indigo-500/20 border border-indigo-500/30 px-2 py-0.5 text-[10px] font-bold text-indigo-400">TOPIK</span>
            <span className="text-[10px] text-slate-500">{profilAgen.length} agen · {tickDetail.length} momen · {semuaPost.length} post</span>
          </div>
          <p className="text-base font-bold text-white">{topik}</p>
          {hasilSosmed.intervensi && (
            <div className="mt-2 flex items-center gap-2 text-xs text-amber-300">
              <span>⚡</span>
              <span>Breaking news diinjeksikan: <span className="font-bold">"{hasilSosmed.intervensi}"</span></span>
            </div>
          )}
          <div className="mt-2 flex flex-wrap gap-1.5">
            {profilAgen.map((a, i) => (
              <div key={i} className="flex items-center gap-1 rounded-full bg-white/5 border border-white/8 px-2 py-0.5">
                <Avatar nama={a.nama} size={4} />
                <span className="text-[10px] text-slate-400">{a.handle}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── Statistik ringkas — FIX #3a: baca dari backend statistik ── */}
      {(() => {
        const statBe = hasilSosmed.statistik ?? {};
        const statItems = [
          { label: "Total Post",   nilai: statBe.total_post    ?? semuaPost.filter(p => p.tipe === "post" && p.akun_id !== "SYSTEM").length, ikon: "📝", color: "indigo" },
          { label: "Likes",        nilai: statBe.total_likes   ?? semuaPost.reduce((s, p) => s + (p.likes?.length ?? 0), 0),                 ikon: "❤️", color: "rose" },
          { label: "Balasan",      nilai: statBe.total_replies ?? semuaPost.filter(p => p.tipe === "reply").length,                           ikon: "💬", color: "cyan" },
          { label: "Kutipan",      nilai: statBe.total_quotes  ?? semuaPost.filter(p => p.tipe === "quote").length,                           ikon: "🔁", color: "violet" },
          { label: "Viral",        nilai: statBe.viral_count   ?? viralPosts.length, ikon: "🔥", color: "amber" },
        ];
        const colorMap = { indigo: "#6366f1", cyan: "#06b6d4", rose: "#f43f5e", amber: "#f59e0b", violet: "#8b5cf6" };
        return (
          <div className="grid grid-cols-3 gap-3 sm:grid-cols-5">
            {statItems.map((s, i) => {
              const c = colorMap[s.color];
              return (
                <div key={i} className="rounded-xl border p-3 text-center"
                  style={{ borderColor: c + "30", backgroundColor: c + "0a" }}>
                  <div className="text-xl mb-1">{s.ikon}</div>
                  <div className="text-2xl font-black" style={{ color: c }}>{s.nilai}</div>
                  <div className="text-[10px] text-slate-500 mt-0.5">{s.label}</div>
                </div>
              );
            })}
          </div>
        );
      })()}

      {/* ── Kebijakan Baru dari Otoritas ── */}
      {semuaKebijakan.length > 0 && (
        <div className="rounded-2xl border border-blue-500/30 bg-blue-950/10 p-4">
          <div className="flex items-center gap-2 mb-3">
            <span className="text-lg">🏛️</span>
            <span className="text-sm font-bold text-blue-300">Respons & Kebijakan Baru dari Otoritas</span>
            <span className="rounded-full bg-blue-500/20 px-2 py-0.5 text-[10px] font-bold text-blue-400">{semuaKebijakan.length} kebijakan</span>
          </div>
          <div className="space-y-2">
            {semuaKebijakan.map((k, i) => (
              <div key={i} className="rounded-xl border border-blue-500/20 bg-blue-900/10 px-3 py-2.5">
                <p className="text-[10px] text-blue-500 font-bold mb-1">📋 {k.agen} — merespons post viral</p>
                <p className="text-sm text-blue-100">{k.kebijakan}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Analisis narasi ── */}
      {analisis.narasi && (
        <Kartu>
          <JudulSeksi>🧠 Analisis Dinamika Sosmed</JudulSeksi>
          <p className="text-sm leading-7 text-slate-300">{analisis.narasi}</p>
          {analisis.ranking_akun?.length > 0 && (
            <div className="mt-4">
              <p className="text-xs text-slate-500 mb-2">🏆 Ranking akun berpengaruh:</p>
              <div className="flex flex-wrap gap-2">
                {analisis.ranking_akun.map((a, i) => (
                  <div key={i} className="flex items-center gap-1.5 rounded-full border border-white/10 bg-white/3 px-3 py-1">
                    <span className="text-[10px] font-black text-slate-400">#{i+1}</span>
                    <Avatar nama={a.nama} size={5} />
                    <span className="text-xs font-bold text-slate-300">{a.handle}</span>
                    <span className="text-[10px] text-slate-500">{a.followers} followers</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </Kartu>
      )}

      {/* ── Laporan lengkap: ringkasan, statistik, sentimen, influencer ── */}
      <LaporanSosmed hasilSosmed={hasilSosmed} />

      {/* ── Profil agen ── */}
      <PanelProfilAgen profilAgen={profilAgen} />

      {/* ── Filter & navigasi tick ── */}
      <div className="flex flex-wrap items-center gap-3 print:hidden">
        <div className="flex gap-1.5">
          {[
            { id: "semua",    label: "🌐 Semua Post" },
            { id: "viral",    label: "🔥 Viral" },
            { id: "timeline", label: "⏱️ Per Momen" },
          ].map(f => (
            <button key={f.id} onClick={() => setFilterMode(f.id)}
              className={`rounded-xl px-3 py-1.5 text-xs font-bold transition ${filterMode === f.id ? "bg-indigo-600 text-white" : "border border-white/10 text-slate-500 hover:border-indigo-400 hover:text-white"}`}>
              {f.label}
            </button>
          ))}
        </div>
        {filterMode === "timeline" && (
          <div className="flex gap-1.5 flex-wrap">
            {tickDetail.map((t, i) => (
              <button key={i} onClick={() => setTickAktif(i)}
                className={`rounded-xl px-3 py-1.5 text-xs font-bold transition ${tickAktif === i ? "bg-indigo-600 text-white" : "border border-white/10 text-slate-500 hover:border-indigo-400 hover:text-white"}`}>
                Momen {t.tick}
              </button>
            ))}
          </div>
        )}
        <span className="ml-auto text-[11px] text-slate-600">{postTampil.length} post</span>
      </div>

      {/* ── Trending (per momen) ── */}
      {filterMode === "timeline" && tickDetail[tickAktif]?.trending?.length > 0 && (
        <div className="rounded-xl border border-amber-500/20 bg-amber-950/10 px-4 py-3">
          <p className="text-[11px] font-bold text-amber-400 mb-2">🔥 Trending — Momen {tickDetail[tickAktif].tick}</p>
          <div className="space-y-1.5">
            {tickDetail[tickAktif].trending.slice(0, 3).map((p, i) => {
              const fresh = postMap[p.id] ?? p;
              return (
                <div key={i} className="flex items-center gap-2 text-xs">
                  <span className="text-amber-600 font-black w-4 shrink-0">#{i+1}</span>
                  <Avatar nama={fresh.nama ?? "?"} size={5} />
                  <span className="text-slate-400 shrink-0">{fresh.handle}</span>
                  <span className="text-slate-300 flex-1 truncate">{fresh.konten?.slice(0, 60)}…</span>
                  <span className="text-rose-400 shrink-0 font-bold">❤️ {fresh.likes?.length ?? 0}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ── Feed post ── */}
      <div className="space-y-3">
        {postTampil.length === 0 && (
          <div className="rounded-2xl border border-dashed border-white/10 p-10 text-center text-sm text-slate-600">
            Belum ada post di filter ini.
          </div>
        )}
        {postTampil.map((post, i) => (
          <KartuPost
            key={post.id ?? i}
            post={post}
            postMap={postMap}
            aksiList={logAktivitas}
            onLikeInfo={setLikeInfoPost}
          />
        ))}
      </div>

      {/* ── Modal: detail siapa yang like ── */}
      {likeInfoPost && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm"
          onClick={() => setLikeInfoPost(null)}>
          <div className="w-80 rounded-2xl border border-white/10 bg-[#0C0F1D] p-5 shadow-2xl"
            onClick={e => e.stopPropagation()}>
            <p className="text-sm font-bold text-white mb-1">❤️ Disukai oleh</p>
            <p className="text-[11px] text-slate-500 mb-3 truncate">"{likeInfoPost.konten?.slice(0, 60)}…"</p>
            {likeInfoPost.likerNames?.length === 0
              ? <p className="text-xs text-slate-500">Belum ada yang like.</p>
              : (
                <div className="space-y-2 max-h-60 overflow-y-auto">
                  {likeInfoPost.likerNames.map((n, i) => (
                    <div key={i} className="flex items-center gap-2.5">
                      <Avatar nama={n} size={7} />
                      <span className="text-sm text-slate-300 capitalize">{n}</span>
                    </div>
                  ))}
                </div>
              )}
            <button onClick={() => setLikeInfoPost(null)}
              className="mt-4 w-full rounded-xl bg-white/5 py-2 text-xs text-slate-400 hover:bg-white/10 transition">
              Tutup
            </button>
          </div>
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
  // ── State mode sosmed ──
  const [modeSosmed,     setModeSosmed]     = useState(false);
  const [hasilSosmed,    setHasilSosmed]    = useState(null);
  const [jumlahTick,     setJumlahTick]     = useState(5);
  const [intervensiSos,  setIntervensiSos]  = useState("");

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

  // ── Mulai simulasi sosmed ────────────────────────────────────────
  const mulaiSosmed = async () => {
    if (!topik.trim()) { inputRef.current?.focus(); return; }
    setMemuat(true);
    setHasilSosmed(null);
    try {
      const body = {
        topik: topik.trim(),
        kategori,
        jumlah_tick: jumlahTick,
        intervensi: intervensiSos.trim() || undefined,
        agen_custom: agenCustom.length ? agenCustom : undefined,
      };
      const res = await fetch(`${apiBase}/start-social`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Permintaan gagal.");
      }
      const data = await res.json();
      setHasilSosmed(data.data);
      setTimeout(() => hasilRef.current?.scrollIntoView({ behavior: "smooth" }), 200);
    } catch (err) {
      alert("❌ " + (err.message || "Server tidak dapat dihubungi."));
    }
    setMemuat(false);
  };

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
  const grafData       = hasil?.graf_data ?? { entitas: [], relasi: [] };
  const aktorAnalisis  = hasil?.aktor_analisis ?? null;

  const narasi = analisis
    .split("\n")
    .filter(l => {
      const trimmed = l.trim();
      if (!trimmed) return false;
      if (trimmed.includes("|")) return false;
      if (/^#{1,4}\s/.test(trimmed)) return false;
      if (/^\*{1,2}[^*]+\*{1,2}$/.test(trimmed)) return false;
      if (/^\d+\.\s+(Buat|Tugas|Narasi|Tabel|Prediksi)/i.test(trimmed)) return false;
      return true;
    })
    .join(" ")
    .replace(/\*{1,2}/g, "")
    .slice(0, 700);

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
            <span className="rounded-full bg-indigo-500/20 px-2 py-0.5 text-[10px] font-bold text-indigo-300">v3</span>
          </div>
        </header>

        {/* ══ FORM INPUT ══ */}
        <section className="mb-4 rounded-2xl border border-white/10 bg-[#0C0F1D] p-5 print:hidden">

          {/* ── Mode Toggle ── */}
          <div className="mb-4 flex gap-2">
            <button
              onClick={() => { setModeSosmed(false); setHasilSosmed(null); }}
              className={`flex-1 rounded-xl py-2.5 text-sm font-bold transition flex items-center justify-center gap-2 ${!modeSosmed ? "bg-indigo-600 text-white shadow-lg shadow-indigo-900/40" : "border border-white/10 text-slate-500 hover:text-white hover:border-indigo-500"}`}
            >
              🧠 Mode Debat
              <span className={`rounded-full px-2 py-0.5 text-[10px] ${!modeSosmed ? "bg-white/20 text-white" : "bg-white/5 text-slate-600"}`}>Multi-Ronde</span>
            </button>
            <button
              onClick={() => { setModeSosmed(true); setHasil(null); }}
              className={`flex-1 rounded-xl py-2.5 text-sm font-bold transition flex items-center justify-center gap-2 ${modeSosmed ? "bg-violet-600 text-white shadow-lg shadow-violet-900/40" : "border border-white/10 text-slate-500 hover:text-white hover:border-violet-500"}`}
            >
              📱 Mode Sosmed
              <span className={`rounded-full px-2 py-0.5 text-[10px] ${modeSosmed ? "bg-white/20 text-white" : "bg-white/5 text-slate-600"}`}>Twitter-style</span>
            </button>
          </div>

          <p className="mb-1 text-base font-bold text-white">
            {modeSosmed ? "Simulasikan isu di media sosial" : "Simulasikan isu apa hari ini?"}
          </p>
          <p className="mb-4 text-xs text-slate-500">
            {modeSosmed
              ? "Agen akan berdebat di platform sosmed — posting, like, reply, quote. Pemerintah akan merespons konten viral."
              : "Masukkan topik, pilih kategori dan jumlah putaran diskusi, lalu klik Analisis."}
          </p>

          <div className="mb-3 flex gap-2">
            <input
              ref={inputRef}
              className={`flex-1 rounded-xl border bg-[#0E1220] px-4 py-3 text-sm text-slate-100 placeholder:text-slate-600 outline-none transition ${modeSosmed ? "border-violet-500/30 focus:border-violet-500" : "border-white/10 focus:border-indigo-500"}`}
              value={topik}
              onChange={e => setTopik(e.target.value)}
              onKeyDown={e => e.key === "Enter" && (modeSosmed ? mulaiSosmed() : mulaiAnalisis())}
              placeholder="Contoh: Kenaikan harga BBM, RUU Ketenagakerjaan baru, dll..."
            />
            <button
              onClick={modeSosmed ? mulaiSosmed : mulaiAnalisis}
              disabled={memuat}
              className={`rounded-xl px-7 py-3 text-sm font-bold text-white transition disabled:opacity-50 disabled:cursor-not-allowed ${modeSosmed ? "bg-violet-600 hover:bg-violet-500" : "bg-indigo-600 hover:bg-indigo-500"}`}
            >
              {memuat ? "⏳ Memproses..." : modeSosmed ? "📱 Simulasi →" : "Analisis →"}
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

            {!modeSosmed ? (
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
            ) : (
              <div className="flex items-center gap-2">
                <span className="text-xs text-slate-500">Jumlah momen:</span>
                <div className="flex gap-1">
                  {[2,3,4,5,6,7,8].map(n => (
                    <button key={n} onClick={() => setJumlahTick(n)}
                      className={`h-7 w-7 rounded-lg text-xs font-bold transition ${jumlahTick === n ? "bg-violet-600 text-white" : "border border-white/10 text-slate-500 hover:border-violet-500 hover:text-white"}`}
                    >{n}</button>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Intervensi sosmed */}
          {modeSosmed && (
            <div className="mb-4 rounded-xl border border-amber-500/20 bg-amber-950/10 p-3">
              <p className="text-xs font-bold text-amber-400 mb-1.5">⚡ Breaking News (Opsional)</p>
              <input
                className="w-full rounded-lg border border-amber-500/20 bg-[#0E1220] px-3 py-2 text-sm text-slate-100 placeholder:text-slate-600 outline-none focus:border-amber-500 transition"
                value={intervensiSos}
                onChange={e => setIntervensiSos(e.target.value)}
                placeholder='Contoh: "Pemerintah umumkan kenaikan UMR 30%"'
              />
              <p className="text-[10px] text-amber-700 mt-1">Diinjeksikan di tengah simulasi sebagai breaking news yang mempengaruhi semua agen.</p>
            </div>
          )}

          {/* ── Tambah Agen Custom ── */}
          <PanelAgenCustom agenCustom={agenCustom} setAgenCustom={setAgenCustom} />
        </section>

        {/* ══ KOSONG ══ */}
        {!hasil && !hasilSosmed && !memuat && (
          <div className="rounded-2xl border border-dashed border-white/10 p-16 text-center">
            <div className="mb-3 text-5xl">{modeSosmed ? "📱" : "🧠"}</div>
            <h2 className="mb-2 text-xl font-bold">Belum ada simulasi</h2>
            <p className="text-sm text-slate-500">
              {modeSosmed
                ? <>Masukkan topik di atas dan klik <strong className="text-white">Simulasi</strong> untuk memulai simulasi sosmed.</>
                : <>Masukkan topik di atas dan klik <strong className="text-white">Analisis</strong> untuk memulai.</>}
            </p>
          </div>
        )}

        {/* ══ LOADING ══ */}
        {memuat && (
          <div className="rounded-2xl border border-white/10 bg-[#0C0F1D] p-16 text-center">
            <div className="mx-auto mb-6 flex w-fit gap-2">
              {[0,1,2,3].map(i => (
                <div key={i} className={`h-2.5 w-2.5 rounded-full ${modeSosmed ? "bg-violet-500" : "bg-indigo-500"}`}
                  style={{ animation: `lompat 1s ease-in-out ${i*0.15}s infinite` }} />
              ))}
            </div>
            {modeSosmed ? (
              <>
                <p className="mb-1 font-semibold text-slate-300">Sedang mensimulasikan {jumlahTick} momen di sosmed...</p>
                <p className="text-xs text-slate-600">Agen sedang posting, like, reply, dan quote satu sama lain. Mohon tunggu 20–60 detik.</p>
              </>
            ) : (
              <>
                <p className="mb-1 font-semibold text-slate-300">Sedang mensimulasikan {jumlahRonde} putaran diskusi...</p>
                <p className="text-xs text-slate-600">Menggunakan dual-model: respons agen (cepat) + analisis mendalam. Mohon tunggu 15–45 detik.</p>
              </>
            )}
          </div>
        )}

        {/* ══ HASIL SOSMED ══ */}
        {hasilSosmed && !memuat && (
          <div ref={hasilRef} className="space-y-5 duration-500 animate-in fade-in">
            {/* Header */}
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="rounded-full bg-violet-500/20 border border-violet-500/40 px-3 py-1.5 text-xs font-bold text-violet-300">📱 Mode Sosmed</span>
                <span className="text-xs text-slate-500">
                  Topik: <span className="font-medium text-slate-300">"{topik}"</span>
                  {hasilSosmed.intervensi && <span className="text-amber-400"> · ⚡ {hasilSosmed.intervensi.slice(0,40)}</span>}
                  {" · "}{hasilSosmed.tick_detail?.length ?? 0} momen · {hasilSosmed.profil_agen?.length ?? 0} akun
                </span>
              </div>
              <PanelIntervensiSosmed
                topik={topik}
                kategori={kategori}
                jumlahTick={jumlahTick}
                agenCustom={agenCustom}
                onHasilBaru={(hasilBaru) => setHasilSosmed(hasilBaru)}
                memuat={memuat}
                setMemuat={setMemuat}
                apiBase={apiBase}
              />

              <button
                onClick={() => { setHasilSosmed(null); setTopik(""); setAgenCustom([]); setTimeout(() => inputRef.current?.focus(), 100); }}
                className="text-xs text-slate-600 underline underline-offset-4 hover:text-slate-400 transition"
              >
                Simulasi baru
              </button>
            </div>

            <TimelineSosmed hasilSosmed={hasilSosmed} topik={topik} />
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

            {/* ── Dual-Model Info Badge ── */}
            {hasil.model_info && <DualModelBadge modelInfo={hasil.model_info} />}

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
                      { ikon: "🖨️", label: "Cetak / Simpan PDF",  aksi: () => { eksporPDF(hasil, topik, analisis, aktorAnalisis); setBukaEkspor(false); } },
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

            {/* ── Aktor Kunci & Swing Voter ── */}
            <KartuAktorKunci aktorAnalisis={aktorAnalisis} warnaAgen={warnaAgen} />

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
                        contentStyle={{ background: "#0C0F1D", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 10, fontSize: 11, color: "#e2e8f0" }}
                        labelStyle={{ color: "#94a3b8", fontWeight: 600, marginBottom: 2 }}
                        itemStyle={{ color: "#e2e8f0" }}
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
                  {/* Label sumbu Y */}
                  <div className="mb-2 flex items-center justify-between text-[10px] text-slate-600">
                    <span>← Menolak</span>
                    <span className="text-slate-700">Netral (0)</span>
                    <span>Mendukung →</span>
                  </div>
                  <div style={{ height: 210 }}>
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={dataTren} margin={{ left: 8, right: 8, top: 4, bottom: 4 }}>
                        {/* Garis bantu tengah (netral = 0) */}
                        <CartesianGrid vertical={false} stroke="rgba(255,255,255,0.04)" />
                        <XAxis
                          dataKey="label"
                          tick={{ fontSize: 10, fill: "#64748b" }}
                          axisLine={false}
                          tickLine={false}
                        />
                        <YAxis
                          domain={[-1, 1]}
                          ticks={[-1, -0.5, 0, 0.5, 1]}
                          tick={{ fontSize: 9, fill: "#475569" }}
                          axisLine={false}
                          tickLine={false}
                          tickFormatter={v => v === 0 ? "0" : v > 0 ? `+${v}` : `${v}`}
                          width={28}
                        />
                        <ReferenceLine y={0} stroke="rgba(255,255,255,0.12)" strokeDasharray="4 3" />
                        <Tooltip
                          contentStyle={{
                            background: "#131726",
                            border: "1px solid rgba(255,255,255,0.18)",
                            borderRadius: 10,
                            fontSize: 11,
                            color: "#e2e8f0",
                            padding: "8px 12px",
                            boxShadow: "0 8px 32px rgba(0,0,0,0.8)",
                            opacity: 1,
                          }}
                          wrapperStyle={{ zIndex: 50, opacity: 1 }}
                          labelStyle={{ color: "#94a3b8", fontWeight: 700, marginBottom: 6, fontSize: 11 }}
                          itemStyle={{ color: "#e2e8f0", padding: "1px 0" }}
                          formatter={(v, nama) => {
                            const badge = v > 0.2 ? "✅ Mendukung" : v < -0.2 ? "❌ Menolak" : "➖ Netral";
                            const sign  = v > 0 ? `+${v}` : `${v}`;
                            return [`${sign}  ${badge}`, nama];
                          }}
                        />
                        <Legend
                          wrapperStyle={{ fontSize: 10, paddingTop: 8 }}
                          formatter={nama => <span style={{ color: warnaAgen[nama] ?? "#94a3b8" }}>{nama}</span>}
                        />
                        {Object.keys(sentimenAgr).map(nama => (
                          <Line
                            key={nama}
                            type="monotone"
                            dataKey={nama}
                            stroke={warnaAgen[nama]}
                            strokeWidth={2}
                            dot={{ r: 4, strokeWidth: 0, fill: warnaAgen[nama] }}
                            activeDot={{ r: 6, strokeWidth: 2, stroke: "#0C0F1D" }}
                          />
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

            {/* ── Graf Pengetahuan Interaktif (GraphRAG) ── */}
            <GrafKnowledge grafData={grafData} />

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
          @page { size: A4 portrait; margin: 15mm 18mm; }

          *, *::before, *::after {
            -webkit-print-color-adjust: exact !important;
            print-color-adjust: exact !important;
          }

          body, main {
            background: #ffffff !important;
            color: #1e293b !important;
          }

          .print\\:hidden { display: none !important; }

          * { color: #1e293b !important; }

          .print-card {
            background: #ffffff !important;
            border-color: #e2e8f0 !important;
          }

          .print-badge-mendukung { background: #dcfce7 !important; border-color: #86efac !important; }
          .print-badge-mendukung * { color: #166534 !important; }
          .print-badge-menolak   { background: #fee2e2 !important; border-color: #fca5a5 !important; }
          .print-badge-menolak * { color: #991b1b !important; }
          .print-badge-netral    { background: #e0e7ff !important; border-color: #a5b4fc !important; }
          .print-badge-netral *  { color: #3730a3 !important; }

          .custom-scrollbar {
            max-height: none !important;
            overflow: visible !important;
          }

          .page-break-avoid {
            page-break-inside: avoid;
            break-inside: avoid;
          }

          svg text { fill: #334155 !important; }
        }
      `}</style>
    </main>
  );
}