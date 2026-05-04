// ─── eksporPDF.js ────────────────────────────────────────────────────────────
// Modul terpisah untuk generate & membuka laporan PDF dari VoxSwarm.
// Dipanggil dari page.js dengan: eksporPDF(hasil, topik, analisis, aktorAnalisis)
// ─────────────────────────────────────────────────────────────────────────────

// ── Konstanta warna (lokal, bukan re-export dari page.js) ─────────────────────
const LABEL   = { positif: "Mendukung", netral: "Netral", negatif: "Menolak" };
const WARNA_B = { positif: "#16a34a",   netral: "#4338ca", negatif: "#dc2626" };
const WARNA_BG= { positif: "#dcfce7",   netral: "#e0e7ff", negatif: "#fee2e2" };
const WARNA_SK= { Konsensus: "#16a34a", Polarisasi: "#dc2626", "Status Quo": "#4338ca" };

// ── Util: bersihkan teks dari emoji/markdown untuk ekspor ─────────────────────
function cleanTextForExport(teks) {
  if (!teks) return "";
  return teks
    .replace(/[^\x00-\x7F]/g, "")
    .replace(/  +/g, " ")
    .split("\n").map(l => l.trim()).join("\n")
    .trim();
}

// ── Builder: narasi bersih dari analisis mentah ───────────────────────────────
function buildNarasi(analisis) {
  return cleanTextForExport(
    analisis
      .split("\n")
      .filter(l => {
        const t = l.trim();
        return t && !t.includes("|") && !/^#{1,4}\s/.test(t) && !/^\*{1,2}[^*]+\*{1,2}$/.test(t);
      })
      .join(" ")
      .replace(/\*{1,2}/g, "")
      .slice(0, 1200)
  );
}

// ── Builder: HTML tabel per ronde ─────────────────────────────────────────────
function buildTabelRonde(rondeList) {
  return rondeList.map(ronde => {
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
}

// ── Builder: HTML bar prediksi skenario ──────────────────────────────────────
function buildPrediksiBar(prediksi) {
  return Object.entries(prediksi).map(([k, v]) => `
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:10px">
      <span style="width:100px;font-size:12px;color:#374151;font-weight:600">${k}</span>
      <div style="flex:1;height:10px;background:#e2e8f0;border-radius:99px;overflow:hidden">
        <div style="height:100%;width:${v}%;background:${WARNA_SK[k] ?? "#6366f1"};border-radius:99px"></div>
      </div>
      <span style="width:36px;text-align:right;font-size:12px;font-weight:700;color:${WARNA_SK[k] ?? "#6366f1"}">${v}%</span>
    </div>`).join("");
}

// ── Builder: HTML tabel evolusi memori per agen ───────────────────────────────
function buildTabelMemori(rondeList) {
  const memoriPerAgen = {};
  rondeList.forEach(r => {
    (r.agen ?? []).forEach(a => {
      if (!memoriPerAgen[a.nama]) memoriPerAgen[a.nama] = [];
      memoriPerAgen[a.nama].push({ ronde: r.ronde, pendapat: a.pendapat, sentimen: a.sentimen });
    });
  });

  return Object.entries(memoriPerAgen).map(([nama, riwayat]) => {
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
}

// ── Builder: HTML kartu aktor kunci ──────────────────────────────────────────
function buildAktorKunciHTML(aktorKunci) {
  return aktorKunci.map(a => {
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
      <p style="font-size:10px;color:#94a3b8;margin:0 0 4px">Jika berubah: ${a.dampak_jika_berubah}</p>
      <div style="display:flex;align-items:center;gap:8px">
        <span style="font-size:10px;color:#64748b">Pengaruh</span>
        <div style="flex:1;height:6px;background:#e2e8f0;border-radius:99px"><div style="height:100%;width:${pct}%;background:#6366f1;border-radius:99px"></div></div>
        <span style="font-size:10px;font-weight:700;color:#6366f1">${pct}%</span>
      </div>
    </div>`;
  }).join("");
}

// ── Builder: HTML kartu swing voter ──────────────────────────────────────────
function buildSwingVoterHTML(swingVoter) {
  return swingVoter.map(a => {
    const arahWarna = a.potensi_arah === "mendukung" ? "#16a34a" : "#dc2626";
    const vol       = Math.min(100, Math.round((a.volatilitas ?? 0) * 100));
    const volWarna  = vol > 60 ? "#dc2626" : vol > 30 ? "#d97706" : "#16a34a";

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
}

// ── Builder: HTML seksi laporan ML ───────────────────────────────────────────
function buildMLSection(mlData) {
  if (!mlData || !mlData.metrics || !mlData.metrics.ok) return "";

  const m     = mlData.metrics;
  const debug = mlData.debug ?? null;

  const accColor = m.accuracy_pct >= 80 ? "#16a34a" : m.accuracy_pct >= 60 ? "#d97706" : "#dc2626";

  // ── Bar akurasi ──
  const accBar = `
    <div style="margin-bottom:14px">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">
        <span style="font-size:12px;font-weight:700;color:#1e293b">Ketepatan Prediksi</span>
        <span style="font-size:18px;font-weight:900;color:${accColor}">${m.accuracy_pct}%</span>
      </div>
      <div style="height:8px;background:#e2e8f0;border-radius:99px;overflow:hidden">
        <div style="height:100%;width:${m.accuracy_pct}%;background:${accColor};border-radius:99px"></div>
      </div>
      <div style="display:flex;justify-content:space-between;margin-top:4px">
        <span style="font-size:10px;color:#94a3b8">Metode: <strong>${m.eval_method}</strong></span>
        <span style="font-size:10px;color:#94a3b8">Dataset: <strong>${m.n_samples} sampel</strong>${m.n_feedback_labels > 0 ? ` (${m.n_feedback_labels} label manual)` : ""}</span>
      </div>
    </div>`;

  // ── Peringatan overfitting ──
  const overfitWarn = (m.accuracy_pct >= 95 && m.n_samples < 20)
    ? `<div style="background:#fefce8;border:1px solid #fcd34d;border-radius:8px;padding:8px 12px;margin-bottom:12px">
        <p style="font-size:10px;font-weight:700;color:#92400e;margin:0 0 2px">Perhatian: Akurasi tinggi dengan data sedikit bisa berarti model menghafal, bukan belajar.</p>
        <p style="font-size:10px;color:#78350f;margin:0">Tambahkan lebih banyak simulasi untuk hasil yang lebih dapat dipercaya.</p>
       </div>`
    : "";

  // ── Kartu per skenario ──
  const perClassCards = (m.classes ?? []).map(c => {
    const pc = m.per_class?.[c];
    if (!pc) return "";
    const f1Pct = Math.round(pc.f1 * 100);
    const f1Col = f1Pct >= 70 ? "#16a34a" : f1Pct >= 50 ? "#d97706" : "#dc2626";
    return `<div style="flex:1;min-width:140px;padding:10px 12px;border:1px solid #e2e8f0;border-radius:8px;background:#f8fafc">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px">
        <span style="font-size:11px;font-weight:700;color:#1e293b">${c}</span>
        <span style="font-size:13px;font-weight:900;color:${f1Col}">${f1Pct}%</span>
      </div>
      <div style="height:5px;background:#e2e8f0;border-radius:99px;overflow:hidden;margin-bottom:6px">
        <div style="height:100%;width:${f1Pct}%;background:${f1Col};border-radius:99px"></div>
      </div>
      <div style="font-size:10px;color:#64748b">
        Ketepatan: <strong>${Math.round(pc.precision * 100)}%</strong> &nbsp;
        Kelengkapan: <strong>${Math.round(pc.recall * 100)}%</strong>
      </div>
      <div style="font-size:10px;color:#94a3b8;margin-top:1px">Data: ${pc.support} kasus</div>
    </div>`;
  }).join("");

  // ── Confusion matrix ──
  let cmTable = "";
  if (m.confusion_matrix && m.classes) {
    const thStyle = `style="background:#1e1b4b;color:#e0e7ff;text-align:center;padding:5px 8px;font-size:10px"`;
    const rows = m.confusion_matrix.map((row, ri) => {
      const cells = row.map((val, ci) => {
        const isDiag = ri === ci;
        const bg = isDiag && val > 0 ? "#dcfce7" : val > 0 ? "#fee2e2" : "#fff";
        const col = isDiag && val > 0 ? "#15803d" : val > 0 ? "#dc2626" : "#94a3b8";
        return `<td style="text-align:center;padding:5px 8px;font-size:11px;font-weight:${isDiag ? "900" : "400"};background:${bg};color:${col}">${val}</td>`;
      }).join("");
      return `<tr><td style="padding:5px 8px;font-size:10px;font-weight:700;color:#374151;text-align:right">${m.classes[ri]}</td>${cells}</tr>`;
    }).join("");
    const headerCols = m.classes.map(c => `<th ${thStyle}>${c}</th>`).join("");
    cmTable = `
      <p style="font-size:10px;color:#64748b;margin-bottom:6px">Baris = kenyataan · Kolom = tebakan VoxSwarm · Hijau = benar · Merah = meleset</p>
      <table style="border-collapse:collapse;font-size:11px;margin-bottom:12px">
        <thead><tr><th style="background:#1e1b4b;color:#e0e7ff;padding:5px 8px;font-size:10px"></th>${headerCols}</tr></thead>
        <tbody>${rows}</tbody>
      </table>`;
  }

  // ── Distribusi label (dari debug) ──
  let labelDist = "";
  if (debug?.label_distribution) {
    const bars = Object.entries(debug.label_distribution).map(([lbl, cnt]) => {
      const pct = debug.label_pct?.[lbl] ?? 0;
      return `<div style="display:flex;align-items:center;gap:10px;margin-bottom:5px">
        <span style="font-size:10px;color:#374151;width:90px;flex-shrink:0">${lbl}</span>
        <div style="flex:1;height:6px;background:#e2e8f0;border-radius:99px;overflow:hidden">
          <div style="height:100%;width:${pct}%;background:#6366f1;border-radius:99px"></div>
        </div>
        <span style="font-size:10px;color:#64748b;width:30px;text-align:right">${cnt}</span>
      </div>`;
    }).join("");

    const riskColor = debug.overfitting_risk === "HIGH" ? "#dc2626"
                    : debug.overfitting_risk === "MEDIUM" ? "#d97706" : "#16a34a";

    const imbalanceNote = debug.imbalance_warning
      ? `<p style="font-size:10px;color:#d97706;margin-top:4px">Data tidak seimbang — label "${debug.dominant_label}" mendominasi lebih dari 70%.</p>`
      : "";

    labelDist = `
      <div style="margin-top:14px;padding:10px 12px;border:1px solid #e2e8f0;border-radius:8px;background:#f8fafc">
        <p style="font-size:10px;font-weight:700;color:#475569;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">Distribusi Label Training</p>
        ${bars}
        ${imbalanceNote}
        <p style="font-size:10px;margin-top:6px">Risiko overfitting: <strong style="color:${riskColor}">${debug.overfitting_risk}</strong>
          &nbsp;·&nbsp; Total data: <strong>${debug.n_total}</strong>
          &nbsp;·&nbsp; Dummy: <strong>${debug.source_distribution?.dummy ?? 0}</strong>
          &nbsp;·&nbsp; Feedback: <strong>${debug.source_distribution?.feedback ?? 0}</strong>
        </p>
      </div>`;
  }

  // ── Weighted average footer ──
  const wAvg = m.weighted_avg;
  const wF1 = Math.round((wAvg?.f1 ?? 0) * 100);

  return `
    <div class="section no-break page-break">
      <div class="section-title">Laporan Machine Learning — Prediksi Cerdas VoxSwarm</div>
      <p style="font-size:11px;color:#64748b;margin-bottom:14px;line-height:1.6">
        Model ini belajar dari pola simulasi yang sudah dijalankan untuk memprediksi
        skenario diskusi yang belum terjadi. Semakin banyak data, semakin akurat prediksinya.
      </p>
      ${overfitWarn}
      ${accBar}
      <p style="font-size:10px;font-weight:700;color:#475569;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">Ketepatan per Skenario</p>
      <div style="display:flex;flex-wrap:wrap;gap:10px;margin-bottom:14px">${perClassCards}</div>
      <div style="background:#f0f4ff;border-radius:8px;padding:8px 12px;margin-bottom:14px;display:flex;justify-content:space-between;align-items:center">
        <span style="font-size:11px;color:#374151">Skor gabungan (weighted F1)</span>
        <span style="font-size:14px;font-weight:900;color:#4338ca">${wF1}%</span>
      </div>
      <p style="font-size:10px;font-weight:700;color:#475569;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px">Tebakan vs Kenyataan (Confusion Matrix)</p>
      ${cmTable}
      ${labelDist}
    </div>`;
}

// ── Builder: CSS string untuk dokumen HTML ────────────────────────────────────
function buildCSS() {
  return `
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: "Segoe UI", Arial, sans-serif; font-size: 12px; color: #1e293b; background: #fff; padding: 0; }
  .page { max-width: 794px; margin: 0 auto; padding: 36px 44px; }

  .cover { background: linear-gradient(135deg, #1e1b4b 0%, #312e81 50%, #1e3a5f 100%); color: white; padding: 48px 44px 40px; margin-bottom: 32px; }
  .cover-label { font-size: 10px; font-weight: 700; letter-spacing: 3px; text-transform: uppercase; color: #a5b4fc; margin-bottom: 16px; }
  .cover-title { font-size: 22px; font-weight: 800; line-height: 1.3; color: #fff; margin-bottom: 20px; }
  .cover-meta { display: flex; flex-wrap: wrap; gap: 20px; margin-top: 24px; }
  .cover-meta-item { font-size: 11px; color: #c7d2fe; }
  .cover-meta-item strong { color: #e0e7ff; display: block; font-size: 10px; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 2px; }
  .cover-divider { height: 1px; background: rgba(255,255,255,0.15); margin: 20px 0; }

  .section { margin-bottom: 28px; }
  .section-title { font-size: 11px; font-weight: 800; letter-spacing: 2px; text-transform: uppercase; color: #4338ca; border-bottom: 2px solid #e0e7ff; padding-bottom: 6px; margin-bottom: 14px; padding-left: 10px; border-left: 3px solid #6366f1; }

  .narasi { font-size: 12px; line-height: 1.75; color: #374151; background: #f8fafc; border-left: 3px solid #6366f1; padding: 14px 16px; border-radius: 0 8px 8px 0; }

  table { width: 100%; border-collapse: collapse; font-size: 11px; }
  th { background: #1e1b4b; color: #e0e7ff; text-align: left; padding: 7px 10px; font-size: 10px; letter-spacing: 0.5px; }
  td { padding: 6px 10px; border-bottom: 1px solid #f1f5f9; color: #374151; vertical-align: top; line-height: 1.5; }
  tr:nth-child(even) td { background: #f8fafc; }

  .badge { display: inline-block; padding: 2px 8px; border-radius: 99px; font-size: 10px; font-weight: 700; white-space: nowrap; }
  .footer { text-align: center; font-size: 10px; color: #94a3b8; border-top: 1px solid #e2e8f0; padding-top: 16px; margin-top: 32px; }

  @media print {
    @page { size: A4 portrait; margin: 12mm 14mm; }
    body { print-color-adjust: exact; -webkit-print-color-adjust: exact; }
    .no-break { page-break-inside: avoid; break-inside: avoid; }
    .page-break { page-break-before: always; }
  }`;
}

// ── Builder: HTML dokumen lengkap ─────────────────────────────────────────────
function buildHtmlDokumen({ topik, tanggal, hasil, rondeList, narasi, prediksiBar, tabelRonde, tabelMemori, penggerak, rekomendasi, aktorKunciHTML, swingVoterHTML, mlData }) {
  return `<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="UTF-8"/>
<title>Laporan VoxSwarm — ${topik}</title>
<style>${buildCSS()}</style>
</head>
<body>

<div class="cover">
  <div class="cover-label">VoxSwarm — Laporan Simulasi Opini Multi-Agen</div>
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

<div class="section no-break">
  <div class="section-title">Ringkasan Analisis</div>
  <div class="narasi">${narasi || "-"}</div>
</div>

<div class="section no-break">
  <div class="section-title">Prediksi Skenario</div>
  ${prediksiBar || "<p style='color:#94a3b8'>Tidak ada data prediksi.</p>"}
</div>

<div class="section no-break">
  <div class="section-title">Prediksi Aktor Kunci &amp; Swing Voter</div>
  <div style="background:#fef3c7;border:1px solid #fcd34d;border-radius:8px;padding:12px 16px;margin-bottom:16px;display:flex;gap:10px;align-items:flex-start">
    
    <div>
      <p style="font-size:10px;font-weight:700;color:#92400e;margin:0 0 2px;text-transform:uppercase;letter-spacing:1px">Aktor Paling Menentukan</p>
      <p style="font-size:14px;font-weight:800;color:#1e293b;margin:0 0 4px">${penggerak}</p>
      ${rekomendasi ? `<p style="font-size:11px;color:#78350f;margin:0">${rekomendasi}</p>` : ""}
    </div>
  </div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
    <div>
      <p style="font-size:10px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:1.5px;margin-bottom:8px">Aktor Kunci</p>
      ${aktorKunciHTML || '<p style="color:#94a3b8;font-size:11px">Tidak ada data.</p>'}
    </div>
    <div>
      <p style="font-size:10px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:1.5px;margin-bottom:8px">Swing Voter</p>
      ${swingVoterHTML || '<p style="color:#94a3b8;font-size:11px">Semua agen konsisten.</p>'}
    </div>
  </div>
</div>

<div class="section">
  <div class="section-title">Pendapat Agen per Putaran</div>
  ${tabelRonde}
</div>

<div class="section page-break">
  <div class="section-title">Evolusi Pendapat Agen</div>
  <p style="font-size:11px;color:#64748b;margin-bottom:14px">Perubahan sikap setiap agen dari putaran ke putaran.</p>
  ${tabelMemori}
</div>

${buildMLSection(mlData)}

<div class="footer">
  Laporan ini dibuat otomatis oleh <strong>VoxSwarm</strong> — Sistem Simulasi Opini Multi-Agen  |  ${tanggal}
</div>

</div>
<script>window.onload = () => window.print();<\/script>
</body>
</html>`;
}

// ── Export utama ───────────────────────────────────────────────────────────────
export function eksporPDF(hasil, topik, analisis, aktorAnalisis, mlData = null) {
  if (!hasil) return;

  const tanggal    = new Date().toLocaleDateString("id-ID", { day: "numeric", month: "long", year: "numeric" });
  const rondeList  = hasil.ronde_detail ?? [];

  const html = buildHtmlDokumen({
    topik,
    tanggal,
    hasil,
    rondeList,
    narasi:         buildNarasi(analisis),
    prediksiBar:    buildPrediksiBar(hasil.prediksi ?? {}),
    tabelRonde:     buildTabelRonde(rondeList),
    tabelMemori:    buildTabelMemori(rondeList),
    penggerak:      aktorAnalisis?.aktor_penggerak ?? "-",
    rekomendasi:    aktorAnalisis?.rekomendasi ?? "",
    aktorKunciHTML: buildAktorKunciHTML(aktorAnalisis?.aktor_kunci ?? []),
    swingVoterHTML: buildSwingVoterHTML(aktorAnalisis?.swing_voter ?? []),
    mlData,
  });

  const blob = new Blob([html], { type: "text/html;charset=utf-8" });
  const url  = URL.createObjectURL(blob);
  window.open(url, "_blank");
  setTimeout(() => URL.revokeObjectURL(url), 60000);
}