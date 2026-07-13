"use client";
import { useState, useMemo } from "react";

// ─── Warna per sentimen ──────────────────────────────────────────
const WARNA = {
  positif: { teks: "#1a7a3a", bg: "#1a7a3a", muda: "#e6f7ee", terang: "#4caf50" },
  netral:  { teks: "#6b6b6b", bg: "#6b6b6b", muda: "#f0f0f0", terang: "#9e9e9e" },
  negatif: { teks: "#c62828", bg: "#c62828", muda: "#fce8e8", terang: "#ef5350" },
};

// ─── Palet warna vibrant per sentimen ──────────────────────────
const PALET = {
  positif: ["#1b5e20", "#2e7d32", "#388e3c", "#43a047", "#4caf50", "#66bb6a", "#81c784", "#a5d6a7"],
  netral:  ["#424242", "#616161", "#757575", "#9e9e9e", "#bdbdbd", "#8d8d8d", "#6d6d6d", "#525252"],
  negatif: ["#b71c1c", "#c62828", "#d32f2f", "#e53935", "#f44336", "#ef5350", "#e57373", "#ef9a9a"],
};

// ─── Ukuran font minimum & maksimum (px) ────────────────────────
const FONT_MIN = 13;
const FONT_MAX = 54;

function scaleFont(berat, beratMin, beratMax) {
  if (beratMax === beratMin) return (FONT_MIN + FONT_MAX) / 2;
  const normalized = (berat - beratMin) / (beratMax - beratMin);
  return FONT_MIN + Math.pow(normalized, 0.8) * (FONT_MAX - FONT_MIN);
}

function hashColor(kata, palet) {
  let hash = 0;
  for (let i = 0; i < kata.length; i++) {
    hash = kata.charCodeAt(i) + ((hash << 5) - hash);
  }
  return palet[Math.abs(hash) % palet.length];
}

// ─── Rotasi acak dari hash ────────────────────────────────────
function hashRotation(kata) {
  let hash = 0;
  for (let i = 0; i < kata.length; i++) {
    hash = kata.charCodeAt(i) + ((hash << 7) - hash);
  }
  // Sebagian besar horizontal (0°), sisanya miring tipis
  const r = Math.abs(hash) % 100;
  if (r < 60) return 0;
  if (r < 80) return (hash % 2 === 0 ? 1 : -1) * (5 + Math.abs(hash) % 10);
  return (hash % 2 === 0 ? 1 : -1) * (10 + Math.abs(hash) % 15);
}

// ─── Komponen WordCloud ─────────────────────────────────────────
export default function WordCloud({ data, className = "" }) {
  const tabs = [
    { key: "positif", label: "Setuju 👍", warna: WARNA.positif },
    { key: "netral",  label: "Netral 😐",  warna: WARNA.netral },
    { key: "negatif", label: "Tidak Setuju 👎", warna: WARNA.negatif },
  ];

  // Auto-pilih tab pertama yang punya data kalo tab aktif kosong
  const [tab, setTab] = useState(() => "positif");
  const effectiveTab = useMemo(() => {
    if (data?.[tab]?.length) return tab;
    const first = tabs.find((t) => data?.[t.key]?.length);
    return first ? first.key : tab;
  }, [tab, data]);

  const activeWords = data?.[effectiveTab] ?? [];
  const total = data?.total ?? {};

  // Hitung rentang berat untuk scaling font
  const { beratMin, beratMax } = useMemo(() => {
    if (!activeWords.length) return { beratMin: 0, beratMax: 1 };
    const beratList = activeWords.map((w) => w.berat);
    return {
      beratMin: Math.min(...beratList),
      beratMax: Math.max(...beratList),
    };
  }, [activeWords]);

  if (!data) {
    return (
      <section className={className}>
        <h2 className="display-sm mb-4" style={{ fontWeight: 400 }}>Word Cloud — Frekuensi Kata</h2>
        <div className="card text-center py-8 text-sm text-[#6c6a64] italic">
          Belum ada data opini untuk ditampilkan.
        </div>
      </section>
    );
  }

  return (
    <section className={className}>
      <h2 className="display-sm mb-4" style={{ fontWeight: 400 }}>
        Word Cloud — Frekuensi Kata
      </h2>

      {/* Tab sentimen */}
      <div className="flex gap-1.5 mb-5">
        {tabs.map((t) => {
          const aktif = effectiveTab === t.key;
          const count = total[t.key] ?? 0;
          return (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className="rounded-[10px] px-4 py-2 text-xs font-semibold tracking-wide transition-all duration-200"
              style={{
                backgroundColor: aktif ? t.warna.muda : "#f5f0e8",
                color: aktif ? t.warna.teks : "#6c6a64",
                border: `1.5px solid ${aktif ? t.warna.teks : "transparent"}`,
                boxShadow: aktif ? `0 2px 8px ${t.warna.teks}25` : "none",
              }}
            >
              {t.label}{" "}
              <span className="opacity-60" style={{ fontSize: 10 }}>
                ({count} kata)
              </span>
            </button>
          );
        })}
      </div>

      {/* Word cloud area */}
      <div
        className="card overflow-hidden"
        style={{
          minHeight: 180,
          background: `radial-gradient(ellipse at 50% 50%, ${WARNA[effectiveTab].muda} 0%, #faf9f5 80%)`,
        }}
      >
        <div
          className="flex flex-wrap items-center justify-center gap-1 px-4 py-6"
          style={{ lineHeight: 1.2 }}
        >
          {activeWords.map((w) => {
            const fontSize = scaleFont(w.berat, beratMin, beratMax);
            const warna = hashColor(w.kata, PALET[effectiveTab]);
            const rotate = hashRotation(w.kata);
            const isBold = w.berat > (beratMin + beratMax) * 0.6;
            return (
              <span
                key={w.kata}
                title={`${w.kata} (${w.frekuensi}x)`}
                className="inline-block cursor-default select-none transition-all duration-200 ease-out hover:scale-125 hover:opacity-100"
                style={{
                  fontSize: `${fontSize}px`,
                  fontWeight: isBold ? 700 : 500,
                  color: warna,
                  opacity: 0.55 + (w.berat / beratMax) * 0.45,
                  padding: "2px 4px",
                  transform: `rotate(${rotate}deg)`,
                  textShadow: warna + "15 0 1px 2px",
                  letterSpacing: fontSize > 30 ? "-0.02em" : "normal",
                }}
              >
                {w.kata}
              </span>
            );
          })}
        </div>

        {/* Info footer */}
        <div className="border-t border-[#e6dfd8] bg-white/60 backdrop-blur-sm px-4 py-2 flex flex-wrap justify-between text-[10px] text-[#6c6a64]">
          <span>
            {total.all ?? 0} total kata tersaring · {activeWords.length} kata teratas
          </span>
          <span className="italic">
            Stopword & kata pendek dihapus
          </span>
        </div>
      </div>
    </section>
  );
}
