"use client";

import { useState, useEffect } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";

export default function AetherSwarmDashboard() {
  const [mounted, setMounted] = useState(false);
  const [topik, setTopik] = useState("");
  const [hasil, setHasil] = useState(null);
  const [loading, setLoading] = useState(false);
  const [loadingText, setLoadingText] = useState("Initializing...");

  useEffect(() => {
    setMounted(true);
  }, []);

  const startAnalysis = async () => {
    if (!topik) return;
    setLoading(true);
    setHasil(null);
    try {
      const res = await fetch("http://127.0.0.1:8000/start-simulation", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ topik, kategori: "General" }),
      });
      const data = await res.json();
      setHasil(data.data);
    } catch (err) {
      alert("System Offline.");
    }
    setLoading(false);
  };

  const parseData = (rawText) => {
    if (!rawText)
      return { chatLog: [], agents: [], isChaos: false, synthesis: "" };

    const lines = rawText
      .split("\n")
      .map((l) => l.trim())
      .filter((l) => l);
    let chatLog = [];
    let agents = [];
    let isChaos = false;

    lines.forEach((line) => {
      // Deteksi Baris Tabel (Agent)
      if (
        line.includes("|") &&
        !line.toLowerCase().includes("partisipan") &&
        !line.includes("---")
      ) {
        const cols = line
          .split("|")
          .map((c) => c.trim())
          .filter((c) => c);
        if (cols.length >= 3) {
          const [nama, sentimen, prediksi] = cols;
          let score = 50,
            color = "#6366F1",
            bg = "bg-slate-100 text-slate-500";
          const s = sentimen.toLowerCase();

          if (
            s.includes("menentang") ||
            s.includes("kritis") ||
            s.includes("negatif")
          ) {
            score = 20;
            color = "#EF4444";
            bg = "bg-red-50 text-red-600 border-red-200";
          } else if (s.includes("khawatir") || s.includes("waspada")) {
            score = 45;
            color = "#F59E0B";
            bg = "bg-amber-50 text-amber-600 border-amber-200";
          } else if (
            s.includes("dukung") ||
            s.includes("setuju") ||
            s.includes("positif")
          ) {
            score = 85;
            color = "#10B981";
            bg = "bg-emerald-50 text-emerald-600 border-emerald-200";
          }

          if (
            prediksi.toLowerCase().includes("chaos") ||
            prediksi.toLowerCase().includes("ricuh") ||
            score < 30
          )
            isChaos = true;
          agents.push({ nama, sentimen, prediksi, score, color, bg });
        }
      }
      // Deteksi Baris Narasi (Chat Log)
      else if (!line.includes("|") && line.length > 5) {
        chatLog.push(line);
      }
    });

    // --- LOGIKA SYNTHESIS (KESIMPULAN ULANG) ---
    const neg = agents.filter((a) => a.score < 50).length;
    const pos = agents.filter((a) => a.score >= 70).length;
    let synthesis = "";

    if (isChaos) {
      synthesis = `RISIKO TINGGI: Terdapat dominasi sentimen negatif (${neg} agen). Mayoritas memprediksi adanya eskalasi konflik dan gangguan stabilitas sistemik. Diperlukan tindakan preventif segera karena narasi perlawanan sangat kuat.`;
    } else if (pos > neg) {
      synthesis = `STABIL: Situasi cenderung terkendali. Meskipun ada kekhawatiran minor, dukungan kolektif (${pos} agen) memberikan basis stabilitas yang kuat terhadap isu "${topik}".`;
    } else {
      synthesis = `FRAGMENTASI: Opini massa terbelah secara signifikan. Tidak ada konsensus tunggal, menciptakan ketidakpastian (ambiguitas) yang bisa bergeser ke arah mana pun tergantung pemicu eksternal berikutnya.`;
    }

    return { chatLog, agents, isChaos, synthesis };
  };

  const p = parseData(hasil?.analisis);

  if (!mounted) return null;

  return (
    <main className="min-h-screen bg-[#F8FAFC] p-4 md:p-12 text-slate-900 print:bg-white print:p-0">
      <div className="max-w-6xl mx-auto">
        {/* HEADER */}
        <header className="mb-10 flex justify-between items-end border-b-2 border-slate-200 pb-6">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <div className="w-3 h-3 bg-indigo-600 rounded-full animate-pulse"></div>
              <h1 className="text-2xl font-black tracking-tighter uppercase">
                Aether Swarm{" "}
                <span className="text-slate-400">Intelligence</span>
              </h1>
            </div>
            <p className="text-[10px] font-mono text-slate-500 uppercase tracking-[0.3em]">
              Protocol Version: 4.0.1 // encrypted_link_established
            </p>
          </div>
          <div className="text-right print:hidden">
            {hasil && (
              <button
                onClick={() => window.print()}
                className="bg-slate-900 text-white text-[10px] font-bold px-6 py-2 rounded-full hover:bg-indigo-600 transition-all"
              >
                EXPORT OFFICIAL REPORT (PDF)
              </button>
            )}
          </div>
        </header>

        {/* INPUT - Hidden on Print */}
        <div className="bg-white p-2 rounded-2xl shadow-2xl shadow-slate-200/50 border border-slate-100 mb-10 flex gap-2 print:hidden">
          <input
            className="flex-1 p-4 outline-none font-medium text-slate-600"
            value={topik}
            onChange={(e) => setTopik(e.target.value)}
            placeholder="Tuliskan seed simulasi (contoh: Kenaikan harga beras)..."
          />
          <button
            onClick={startAnalysis}
            disabled={loading}
            className="bg-indigo-600 text-white px-10 rounded-xl font-bold uppercase text-xs tracking-widest disabled:opacity-50"
          >
            {loading ? "PROCESING..." : "ANALYZE"}
          </button>
        </div>

        {hasil && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 animate-in fade-in duration-1000">
            {/* COLUMN LEFT: MAIN ANALYTICS */}
            <div className="lg:col-span-7 space-y-6">
              {/* Verdict & Synthesis (KESIMPULAN BARU) */}
              <div className="bg-white p-8 rounded-3xl border border-slate-200 shadow-sm relative overflow-hidden print:border-slate-800 print:border-2">
                <div
                  className={`absolute top-0 right-0 px-4 py-1 text-[10px] font-black text-white uppercase ${
                    p.isChaos ? "bg-red-600" : "bg-emerald-600"
                  }`}
                >
                  {p.isChaos ? "Danger: Volatile" : "Status: Stable"}
                </div>
                <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest block mb-2">
                  Synthesis Conclusion
                </span>
                <p className="text-lg font-bold leading-relaxed text-slate-800 mb-6">
                  {p.synthesis}
                </p>
                <div className="bg-slate-50 p-4 rounded-xl border-l-4 border-slate-300 italic text-slate-600 text-sm">
                  "{p.chatLog[0]}"
                </div>
              </div>

              {/* Chart */}
              <div className="bg-white p-8 rounded-3xl border border-slate-200 shadow-sm print:border-slate-800 print:border-2">
                <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest block mb-8 font-mono">
                  Statistical Sentiment Map
                </span>
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={p.agents}>
                      <XAxis
                        dataKey="nama"
                        tick={{ fontSize: 10, fontWeight: "bold" }}
                        axisLine={false}
                        tickLine={false}
                      />
                      <YAxis domain={[0, 100]} hide />
                      <Bar dataKey="score" radius={[4, 4, 4, 4]} barSize={50}>
                        {p.agents.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.color} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* LIVE CONVERSATION LOG (DIPERBAIKI) */}
              <div className="bg-slate-900 p-8 rounded-3xl shadow-xl print:bg-white print:text-black print:border-2 print:border-slate-800">
                <div className="flex justify-between items-center mb-6">
                  <span className="text-[10px] font-black text-indigo-400 uppercase tracking-widest font-mono">
                    Live Simulation Log
                  </span>
                  <div className="flex gap-1">
                    <div className="w-1 h-1 bg-indigo-500 rounded-full"></div>
                    <div className="w-1 h-1 bg-indigo-500 rounded-full opacity-50"></div>
                    <div className="w-1 h-1 bg-indigo-500 rounded-full opacity-20"></div>
                  </div>
                </div>
                <div className="space-y-4 max-h-60 overflow-y-auto pr-4 custom-scrollbar font-mono text-[11px] leading-relaxed">
                  {p.chatLog.slice(1).map((msg, idx) => (
                    <div key={idx} className="flex gap-4 group">
                      <span className="text-indigo-500 shrink-0 font-bold">
                        [{idx + 1}]
                      </span>
                      <p className="text-slate-400 group-hover:text-indigo-200 transition-colors print:text-slate-700 italic">
                        {msg}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* COLUMN RIGHT: AGENT NODES */}
            <div className="lg:col-span-5 space-y-6">
              <div className="bg-white p-8 rounded-3xl border border-slate-200 shadow-sm h-full print:border-slate-800 print:border-2">
                <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest block mb-8 font-mono">
                  Agent Node Predictions
                </span>
                <div className="space-y-8">
                  {p.agents.map((item, i) => (
                    <div
                      key={i}
                      className="relative pl-6 border-l-2 border-slate-100"
                    >
                      <div
                        className="absolute -left-[5px] top-0 w-2 h-2 rounded-full"
                        style={{ backgroundColor: item.color }}
                      ></div>
                      <div className="flex justify-between items-center mb-2">
                        <span className="text-xs font-black uppercase text-slate-700">
                          {item.nama}
                        </span>
                        <span
                          className={`text-[8px] font-bold px-2 py-0.5 rounded border uppercase ${item.bg}`}
                        >
                          {item.sentimen}
                        </span>
                      </div>
                      <p className="text-[13px] text-slate-600 font-medium leading-relaxed mb-3">
                        {item.prediksi}
                      </p>
                      <div className="h-1 w-full bg-slate-50 rounded-full overflow-hidden">
                        <div
                          className="h-full"
                          style={{
                            width: `${item.score}%`,
                            backgroundColor: item.color,
                          }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* PRINT STYLES */}
      <style jsx global>{`
        .custom-scrollbar::-webkit-scrollbar {
          width: 3px;
        }
        .custom-scrollbar::-webkit-scrollbar-track {
          background: transparent;
        }
        .custom-scrollbar::-webkit-scrollbar-thumb {
          background: #334155;
          border-radius: 10px;
        }

        @media print {
          @page {
            size: portrait;
            margin: 15mm;
          }
          body {
            background: white !important;
            -webkit-print-color-adjust: exact;
          }
          .print\:hidden {
            display: none !important;
          }
          .shadow-sm,
          .shadow-xl,
          .shadow-2xl {
            box-shadow: none !important;
          }
          .bg-slate-900 {
            background: white !important;
            color: black !important;
            padding: 0 !important;
          }
          .text-slate-400,
          .text-indigo-400 {
            color: #475569 !important;
          }
          .grid {
            display: block !important;
          }
          .lg\:col-span-7,
          .lg\:col-span-5 {
            width: 100% !important;
            margin-bottom: 2rem !important;
          }
          .rounded-3xl {
            border-radius: 8px !important;
          }
        }
      `}</style>
    </main>
  );
}
