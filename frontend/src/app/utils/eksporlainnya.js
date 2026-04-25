// ─── eksporLainnya.js ─────────────────────────────────────────────────────────
// Modul ekspor CSV dan Word (.docx) untuk VoxSwarm.
// Dipanggil dari page.js:
//   import { eksporCSV, eksporWord } from "./eksporLainnya";
// ─────────────────────────────────────────────────────────────────────────────

const LABEL_SENTIMEN = { positif: "Mendukung", netral: "Netral", negatif: "Menolak" };

// ── Util: bersihkan teks dari emoji/karakter non-ASCII ───────────────────────
function cleanTextForExport(teks) {
  if (!teks) return "";
  return teks
    .replace(/[^\x00-\x7F]/g, "")
    .replace(/  +/g, " ")
    .split("\n").map(l => l.trim()).join("\n")
    .trim();
}

// ── Util: buat nama file yang aman ───────────────────────────────────────────
function safeFilename(topik, ext) {
  return `VoxSwarm_${topik.slice(0, 30).replace(/\s+/g, "_")}.${ext}`;
}

// ── Util: trigger download dari blob URL ──────────────────────────────────────
function triggerDownload(url, filename) {
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

// ── eksporCSV ────────────────────────────────────────────────────────────────
// Mengekspor seluruh data ronde ke file .csv dengan BOM UTF-8.
export function eksporCSV(hasil, topik) {
  if (!hasil) return;

  const baris = [["Putaran", "Nama Agen", "Pendapat", "Sentimen", "Skor (-1 s/d 1)"]];

  (hasil.ronde_detail ?? []).forEach(ronde => {
    (ronde.agen ?? []).forEach(a => {
      baris.push([
        ronde.ronde,
        a.nama,
        `"${cleanTextForExport(a.pendapat ?? "").replace(/"/g, "'")}"`,
        LABEL_SENTIMEN[a.sentimen?.label] ?? a.sentimen?.label ?? "-",
        a.sentimen?.skor ?? 0,
      ]);
    });
  });

  const isi  = baris.map(r => r.join(",")).join("\n");
  const blob = new Blob(["\uFEFF" + isi], { type: "text/csv;charset=utf-8;" });
  const url  = URL.createObjectURL(blob);
  triggerDownload(url, safeFilename(topik, "csv"));
}

// ── eksporWord ───────────────────────────────────────────────────────────────
// Mengekspor laporan ke file .docx menggunakan library docx (lazy-loaded).
export async function eksporWord(hasil, topik, analisis) {
  if (!hasil) return;

  // Lazy-load library docx dari CDN jika belum tersedia
  if (!window.docx) {
    await new Promise((resolve, reject) => {
      const s = document.createElement("script");
      s.src = "https://unpkg.com/docx@8.5.0/build/index.js";
      s.onload = resolve;
      s.onerror = () => reject(new Error("Gagal memuat library docx."));
      document.head.appendChild(s);
    });
  }

  const {
    Document, Paragraph, TextRun,
    Table, TableRow, TableCell,
    HeadingLevel, AlignmentType, WidthType, Packer,
  } = window.docx;

  const tanggal    = new Date().toLocaleDateString("id-ID", { day: "numeric", month: "long", year: "numeric" });
  const narasi     = cleanTextForExport(
    analisis.split("\n").filter(l => !l.includes("|") && l.trim()).join(" ").slice(0, 800)
  );
  const rondeAkhir = (hasil.ronde_detail ?? []).at(-1);

  // Baris tabel agen dari putaran terakhir
  const barisAgen = (rondeAkhir?.agen ?? []).map(a =>
    new TableRow({
      children: [
        new TableCell({ children: [new Paragraph({ text: a.nama })] }),
        new TableCell({ children: [new Paragraph({ text: LABEL_SENTIMEN[a.sentimen?.label] ?? "-", alignment: AlignmentType.CENTER })] }),
        new TableCell({ children: [new Paragraph({ text: a.pendapat ?? "-" })] }),
      ],
    })
  );

  // Header tabel berwarna
  const headerTabel = new TableRow({
    tableHeader: true,
    children: ["Nama Agen", "Sikap", "Pendapat"].map(h =>
      new TableCell({
        shading: { fill: "4338CA" },
        children: [new Paragraph({
          children: [new TextRun({ text: h, bold: true, color: "FFFFFF" })],
          alignment: AlignmentType.CENTER,
        })],
      })
    ),
  });

  // Paragraf metadata dokumen
  const metaParagraphs = [
    new Paragraph({ children: [new TextRun({ text: "Topik: ", bold: true }), new TextRun(topik)] }),
    new Paragraph({ children: [new TextRun({ text: "Tanggal: ", bold: true }), new TextRun(tanggal)] }),
    new Paragraph({ children: [new TextRun({ text: "Jumlah Putaran: ", bold: true }), new TextRun(String(hasil.jumlah_ronde ?? "-"))] }),
    ...(hasil.intervensi
      ? [new Paragraph({ children: [new TextRun({ text: "Intervensi: ", bold: true }), new TextRun(hasil.intervensi)] })]
      : []),
  ];

  // Paragraf prediksi skenario
  const prediksiParagraphs = Object.entries(hasil.prediksi ?? {}).map(([k, v]) =>
    new Paragraph({ children: [new TextRun({ text: `${k}: `, bold: true }), new TextRun(`${v}%`)] })
  );

  const doc = new Document({
    sections: [{
      children: [
        new Paragraph({ text: "LAPORAN SIMULASI VOXSWARM", heading: HeadingLevel.TITLE, alignment: AlignmentType.CENTER }),
        new Paragraph({ text: "" }),
        ...metaParagraphs,
        new Paragraph({ text: "" }),
        new Paragraph({ text: "RINGKASAN ANALISIS", heading: HeadingLevel.HEADING_1 }),
        new Paragraph({ text: narasi }),
        new Paragraph({ text: "" }),
        new Paragraph({ text: "PREDIKSI SKENARIO", heading: HeadingLevel.HEADING_1 }),
        ...prediksiParagraphs,
        new Paragraph({ text: "" }),
        new Paragraph({ text: "PENDAPAT AGEN (PUTARAN TERAKHIR)", heading: HeadingLevel.HEADING_1 }),
        new Table({
          width: { size: 100, type: WidthType.PERCENTAGE },
          rows: [headerTabel, ...barisAgen],
        }),
        new Paragraph({ text: "" }),
        new Paragraph({
          text: "Laporan ini dibuat otomatis oleh VoxSwarm — Sistem Simulasi Opini Multi-Agen.",
          alignment: AlignmentType.CENTER,
        }),
      ],
    }],
  });

  const buffer = await Packer.toBlob(doc);
  const url    = URL.createObjectURL(buffer);
  triggerDownload(url, safeFilename(topik, "docx"));
}