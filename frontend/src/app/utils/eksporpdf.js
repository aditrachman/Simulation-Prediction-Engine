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
function buildHtmlDokumen({ topik, tanggal, hasil, rondeList, narasi, prediksiBar, tabelRonde, tabelMemori, penggerak, rekomendasi, aktorKunciHTML, swingVoterHTML }) {
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

<div class="footer">
  Laporan ini dibuat otomatis oleh <strong>VoxSwarm</strong> — Sistem Simulasi Opini Multi-Agen  |  ${tanggal}
</div>

</div>
<script>window.onload = () => window.print();<\/script>
</body>
</html>`;
}

// ── Export utama ───────────────────────────────────────────────────────────────
export function eksporPDF(hasil, topik, analisis, aktorAnalisis) {
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
  });

  const blob = new Blob([html], { type: "text/html;charset=utf-8" });
  const url  = URL.createObjectURL(blob);
  window.open(url, "_blank");
  setTimeout(() => URL.revokeObjectURL(url), 60000);
}