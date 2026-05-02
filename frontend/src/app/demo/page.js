"use client";
import { eksporPDF } from "../utils/eksporpdf";
import { eksporCSV } from "../utils/eksporlainnya";
import { eksporWord } from "../utils/eksporlainnya";
import TimelineSosmed from "../utils/timelinesosmed";

import { useState, useEffect, useRef, useMemo } from "react";
import Link from "next/link";
import {
  BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Cell,
  LineChart, Line, Tooltip, Legend, CartesianGrid, ReferenceLine,
} from "recharts";

// ─── Konstanta ────────────────────────────────────────────────────────
const WARNA_SENTIMEN  = { positif: "#22c55e", netral: "#6366f1", negatif: "#ef4444" };
const LABEL_SENTIMEN  = { positif: "Positif", netral: "Netral", negatif: "Negatif" };
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


// ─── Komponen: Badge Sumber Prediksi ─────────────────────────────────
const PrediksiSourceBadge = ({ source, note }) => {
  if (!source) return null;
  if (source === "ml") {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-green-900/40 border border-green-500/40 px-3 py-1 text-[11px] font-bold text-green-300">
        🤖 ML Model
      </span>
    );
  }
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full bg-slate-800 border border-white/10 px-3 py-1 text-[11px] font-bold text-slate-400 cursor-help"
      title={note ?? "Model belum aktif — perlu lebih banyak sampel"}
    >
      📐 Rule-based {note ? `(${note})` : ""}
    </span>
  );
};


// ─── Komponen: Panel Feedback Ground Truth ────────────────────────────
const PanelFeedback = ({ topikHash, apiBase, feedbackLabel, setFeedbackLabel, feedbackConf, setFeedbackConf, feedbackCatatan, setFeedbackCatatan, feedbackLoading, setFeedbackLoading, feedbackResult, setFeedbackResult }) => {
  if (!topikHash) return null;

  const kirimFeedback = async () => {
    setFeedbackLoading(true);
    setFeedbackResult(null);
    try {
      const res = await fetch(`${apiBase}/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          topik_hash:   topikHash,
          label_aktual: feedbackLabel,
          confidence:   feedbackConf,
          catatan:      feedbackCatatan,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Gagal mengirim feedback.");
      setFeedbackResult({ ok: true, data: data.data, message: data.message });
    } catch (err) {
      setFeedbackResult({ ok: false, message: err.message });
    }
    setFeedbackLoading(false);
  };

  const confPct = Math.round(feedbackConf * 100);
  const confLabel = confPct <= 33 ? "Kurang yakin" : confPct <= 66 ? "Cukup yakin" : "Sangat yakin";

  const LABEL_OPTIONS = [
    { value: "Konsensus",  display: "✅ Konsensus — semua pihak setuju / isu mereda" },
    { value: "Polarisasi", display: "⚡ Polarisasi — masyarakat terbelah, debat panas" },
    { value: "Status Quo", display: "😐 Status Quo — situasi tidak banyak berubah" },
  ];

  return (
    <Kartu>
      <JudulSeksi>💡 Apa yang Sebenarnya Terjadi?</JudulSeksi>
      <p className="mb-4 text-xs text-slate-400 leading-relaxed">
        Bantu sistem belajar! Setelah isu ini berkembang di dunia nyata,
        pilih outcome yang paling sesuai. Makin banyak koreksi yang kamu beri,
        makin akurat prediksi VoxSwarm ke depannya.
      </p>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 mb-4">
        {/* Label */}
        <div>
          <label className="block text-[11px] font-bold text-slate-400 mb-1.5">Outcome yang terjadi</label>
          <div className="flex flex-col gap-2">
            {LABEL_OPTIONS.map(({ value, display }) => (
              <button
                key={value}
                onClick={() => setFeedbackLabel(value)}
                className={`rounded-lg px-3 py-2 text-xs font-semibold border text-left transition ${
                  feedbackLabel === value
                    ? "bg-indigo-600 border-indigo-500 text-white"
                    : "border-white/10 text-slate-400 hover:border-indigo-400 hover:text-white"
                }`}
              >
                {display}
              </button>
            ))}
          </div>
        </div>

        {/* Confidence */}
        <div>
          <label className="block text-[11px] font-bold text-slate-400 mb-1">
            Seberapa yakin kamu dengan pilihan ini?
          </label>
          <p className="text-xs font-bold text-indigo-300 mb-2">{confLabel}</p>
          <input
            type="range" min="0" max="1" step="0.05"
            value={feedbackConf}
            onChange={e => setFeedbackConf(parseFloat(e.target.value))}
            className="w-full h-1.5 rounded-full appearance-none bg-white/10 accent-indigo-500"
          />
          <div className="flex justify-between text-[10px] text-slate-600 mt-1">
            <span>Kurang yakin</span>
            <span>Sangat yakin</span>
          </div>
        </div>
      </div>

      {/* Catatan */}
      <div className="mb-4">
        <label className="block text-[11px] font-bold text-slate-400 mb-1.5">Ceritakan konteksnya (opsional)</label>
        <textarea
          value={feedbackCatatan}
          onChange={e => setFeedbackCatatan(e.target.value)}
          placeholder="Misal: Setelah demo besar-besaran, pemerintah akhirnya mencabut kebijakan ini..."
          maxLength={1000}
          rows={2}
          className="w-full rounded-xl border border-white/10 bg-[#0E1220] px-3 py-2 text-xs text-slate-300 placeholder:text-slate-600 outline-none focus:border-indigo-500 transition resize-none"
        />
      </div>

      <div className="flex items-center gap-3">
        <button
          onClick={kirimFeedback}
          disabled={feedbackLoading}
          className="rounded-xl bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 px-5 py-2 text-xs font-bold text-white transition"
        >
          {feedbackLoading ? "⏳ Menyimpan..." : "💾 Simpan Koreksi"}
        </button>

        {feedbackResult && (
          <div className={`text-xs font-semibold ${feedbackResult.ok ? "text-green-400" : "text-red-400"}`}>
            {feedbackResult.ok
              ? <>
                  ✓ Koreksi disimpan! VoxSwarm akan belajar dari ini.
                  {feedbackResult.data?.retrain_triggered && (
                    <span className="ml-2 block text-amber-300 font-normal">🔄 Sistem sedang memperbarui model prediksinya...</span>
                  )}
                </>
              : `✕ ${feedbackResult.message}`
            }
          </div>
        )}
      </div>
    </Kartu>
  );
};


// ─── Komponen: Panel ML Model Performance ────────────────────────────
const PanelMLMetrics = ({ apiBase }) => {
  const [metrics,  setMetrics]  = useState(null);
  const [loading,  setLoading]  = useState(false);

  const fetchMetrics = () => {
    setLoading(true);
    fetch(`${apiBase}/ml-metrics`)
      .then(r => r.json())
      .then(d => setMetrics(d.metrics ?? null))
      .catch(() => setMetrics(null))
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchMetrics(); }, []);

  if (loading) return (
    <Kartu>
      <div className="flex items-center gap-2 text-xs text-slate-500">
        <div className="h-2 w-2 rounded-full bg-indigo-500 animate-pulse" />
        Memuat performa model ML...
      </div>
    </Kartu>
  );

  if (!metrics || !metrics.ok) {
    const nSampel    = metrics?.n_samples   ?? 0;
    const minSampel  = metrics?.min_samples ?? 5;
    const sisa       = Math.max(0, minSampel - nSampel);
    const progPct    = Math.min(100, (nSampel / minSampel) * 100);

    return (
      <Kartu>
        <JudulSeksi>🤖 ML Prediction Engine</JudulSeksi>
        <div className="rounded-xl border border-indigo-500/20 bg-indigo-950/20 p-4">
          <p className="text-sm font-bold text-indigo-300 mb-1">
            {sisa > 0
              ? `Butuh ${sisa} simulasi lagi untuk mengaktifkan ML`
              : (metrics?.message ?? "Model sedang disiapkan...")}
          </p>
          <p className="text-xs text-slate-500 leading-relaxed">
            VoxSwarm akan mulai belajar dari pola diskusi setelah cukup data terkumpul.
            Setiap simulasi yang kamu jalankan membantu sistem jadi lebih cerdas.
          </p>
          {/* Progress bar menuju MIN_SAMPLES */}
          <div className="mt-3 h-1.5 w-full rounded-full bg-white/10 overflow-hidden">
            <div
              className="h-full rounded-full bg-indigo-500 transition-all duration-700"
              style={{ width: `${progPct}%` }}
            />
          </div>
          <p className="mt-1 text-[10px] text-slate-600">
            {nSampel} / {minSampel} simulasi terkumpul
          </p>
        </div>
      </Kartu>
    );
  }

  const { accuracy_pct, eval_method, n_samples, n_feedback_labels, confusion_matrix: cm, classes, per_class, macro_avg, weighted_avg } = metrics;
  const accColor = accuracy_pct >= 80 ? "#22c55e" : accuracy_pct >= 60 ? "#f59e0b" : "#ef4444";
  const K_ABBR = { "Konsensus": "K", "Polarisasi": "P", "Status Quo": "SQ" };

  return (
    <Kartu>
      <div className="flex items-center justify-between mb-5">
        <JudulSeksi>🤖 ML Model Performance</JudulSeksi>
        <button
          onClick={fetchMetrics}
          className="text-[10px] text-slate-600 hover:text-indigo-400 transition border border-white/10 rounded-lg px-2.5 py-1 font-bold"
        >
          ↻ Refresh
        </button>
      </div>

      {/* ── Sub-section 1: Header ── */}
      <div className="mb-6 rounded-xl border border-white/10 bg-white/3 p-4">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-black text-white">Akurasi: {accuracy_pct}%</span>
          <span className="text-[11px] text-slate-500">{eval_method}</span>
        </div>
        <div className="h-2 w-full rounded-full bg-white/10 overflow-hidden mb-2">
          <div
            className="h-full rounded-full transition-all duration-700"
            style={{ width: `${accuracy_pct}%`, backgroundColor: accColor }}
          />
        </div>
        <p className="text-[11px] text-slate-500">
          Dataset: <span className="text-slate-300 font-semibold">{n_samples} sampel</span>
          {n_feedback_labels > 0 && <span> (<span className="text-indigo-300">{n_feedback_labels} dengan label manual</span>)</span>}
        </p>
      </div>

      {/* ── Sub-section 2: Confusion Matrix ── */}
      {cm && cm.length > 0 && (
        <div className="mb-6">
          <p className="text-[11px] font-bold text-slate-400 uppercase tracking-widest mb-3">Confusion Matrix</p>
          <div className="overflow-x-auto">
            <table className="w-full text-[11px] border-collapse">
              <thead>
                <tr>
                  <th className="p-2 text-slate-600 font-normal text-right">Aktual →</th>
                  {classes.map(c => (
                    <th key={c} className="p-2 text-center text-slate-400 font-bold">
                      Pred {K_ABBR[c] ?? c}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {cm.map((row, ri) => (
                  <tr key={ri}>
                    <td className="p-2 text-right font-bold text-slate-400">{classes[ri]}</td>
                    {row.map((val, ci) => {
                      const isDiag = ri === ci;
                      const cellClass = isDiag
                        ? "bg-green-900/40 text-green-300 font-black"
                        : val > 0
                          ? "bg-red-900/20 text-red-400"
                          : "text-slate-600";
                      return (
                        <td key={ci} className={`p-2 text-center rounded ${cellClass}`}>
                          {val}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── Sub-section 3: Per-class metrics ── */}
      <div>
        <p className="text-[11px] font-bold text-slate-400 uppercase tracking-widest mb-3">Per-Kelas Metrics</p>
        <table className="w-full text-[11px] border-collapse">
          <thead>
            <tr>
              <th className="pb-1.5 text-left text-slate-500 font-bold">Kelas</th>
              <th className="pb-1.5 text-center text-slate-500 font-bold">Precision</th>
              <th className="pb-1.5 text-center text-slate-500 font-bold">Recall</th>
              <th className="pb-1.5 text-center text-slate-500 font-bold">F1</th>
              <th className="pb-1.5 text-center text-slate-500 font-bold">Support</th>
            </tr>
          </thead>
          <tbody>
            {classes.map(c => {
              const m = per_class[c];
              if (!m) return null;
              const f1Pct = Math.round(m.f1 * 100);
              return (
                <tr key={c} className="border-t border-white/5">
                  <td className="py-2 pr-2 font-bold text-slate-300">{c}</td>
                  {["precision","recall","f1"].map(metric => (
                    <td key={metric} className="py-2 px-1 text-center">
                      <div className="flex flex-col items-center gap-0.5">
                        <span className="font-semibold text-slate-200">{Math.round(m[metric] * 100)}%</span>
                        <div className="h-1 w-12 rounded-full bg-white/10 overflow-hidden">
                          <div className="h-full rounded-full bg-indigo-500" style={{ width: `${Math.round(m[metric] * 100)}%` }} />
                        </div>
                      </div>
                    </td>
                  ))}
                  <td className="py-2 text-center text-slate-400">{m.support}</td>
                </tr>
              );
            })}
            {/* Macro avg */}
            <tr className="border-t border-white/10">
              <td className="py-1.5 pr-2 italic text-slate-500">Macro Avg</td>
              {["precision","recall","f1"].map(metric => (
                <td key={metric} className="py-1.5 px-1 text-center italic text-slate-500">
                  {Math.round(macro_avg[metric] * 100)}%
                </td>
              ))}
              <td className="py-1.5 text-center text-slate-600">—</td>
            </tr>
            {/* Weighted avg */}
            <tr className="border-t border-white/5">
              <td className="py-1.5 pr-2 italic text-slate-500">Weighted Avg</td>
              {["precision","recall","f1"].map(metric => (
                <td key={metric} className="py-1.5 px-1 text-center italic text-slate-500">
                  {Math.round(weighted_avg[metric] * 100)}%
                </td>
              ))}
              <td className="py-1.5 text-center text-slate-600">—</td>
            </tr>
          </tbody>
        </table>
      </div>
    </Kartu>
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
  // ── State topik_hash & prediksi source ──
  const [topikHash,      setTopikHash]      = useState(null);
  const [prediksiSource, setPrediksiSource] = useState(null);   // "ml" | "rule_based"
  const [prediksiNote,   setPrediksiNote]   = useState(null);
  // ── State feedback ground truth ──
  const [feedbackLabel,      setFeedbackLabel]      = useState("Konsensus");
  const [feedbackConf,       setFeedbackConf]       = useState(1.0);
  const [feedbackCatatan,    setFeedbackCatatan]    = useState("");
  const [feedbackLoading,    setFeedbackLoading]    = useState(false);
  const [feedbackResult,     setFeedbackResult]     = useState(null);   // hasil submit
  // ── State ML metrics ──
  const [mlMetrics,      setMlMetrics]      = useState(null);
  const [loadingMetrics, setLoadingMetrics] = useState(false);

  const inputRef = useRef(null);
  const hasilRef = useRef(null);
  const apiBase  = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

  useEffect(() => {
    setTerpasang(true);
    fetch(`${apiBase}/categories`)
      .then(r => r.json())
      .then(d => { if (d.kategori?.length) setKategoriList(d.kategori); })
      .catch(() => {});
    // Fetch ML metrics saat mount
    setLoadingMetrics(true);
    fetch(`${apiBase}/ml-metrics`)
      .then(r => r.json())
      .then(d => setMlMetrics(d.metrics ?? null))
      .catch(() => setMlMetrics(null))
      .finally(() => setLoadingMetrics(false));
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
    setTopikHash(null);
    setPrediksiSource(null);
    setPrediksiNote(null);
    setFeedbackResult(null);
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
      // Simpan topik_hash & prediksi source dari response
      setTopikHash(data.data?.topik_hash ?? null);
      setPrediksiSource(data.data?.prediksi_source ?? null);
      setPrediksiNote(data.data?.ml_info?.note ?? null);
      setFeedbackResult(null);   // reset feedback panel
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

  const narasiRaw = analisis
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
    .slice(0, 1200);

  const narasi = narasiRaw.includes(".")
    ? narasiRaw.slice(0, narasiRaw.lastIndexOf(".") + 1)
    : narasiRaw;

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
                <PrediksiSourceBadge source={prediksiSource} note={prediksiNote} />
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

            {/* ── Feedback Ground Truth ── */}
            <PanelFeedback
              topikHash={topikHash}
              apiBase={apiBase}
              feedbackLabel={feedbackLabel}
              setFeedbackLabel={setFeedbackLabel}
              feedbackConf={feedbackConf}
              setFeedbackConf={setFeedbackConf}
              feedbackCatatan={feedbackCatatan}
              setFeedbackCatatan={setFeedbackCatatan}
              feedbackLoading={feedbackLoading}
              setFeedbackLoading={setFeedbackLoading}
              feedbackResult={feedbackResult}
              setFeedbackResult={setFeedbackResult}
            />

            {/* ── ML Model Performance ── */}
            <PanelMLMetrics apiBase={apiBase} />

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