"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  ResponsiveContainer,
  Cell,
} from "recharts";

export default function VoxSwarmDashboard() {
  const [mounted, setMounted] = useState(false);
  const [topik, setTopik] = useState("");
  const [hasil, setHasil] = useState(null);
  const [loading, setLoading] = useState(false);
  const apiBaseUrl =
    process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

  useEffect(() => {
    setMounted(true);
  }, []);

  const startAnalysis = async () => {
    if (!topik) return;
    setLoading(true);
    setHasil(null);
    try {
      const res = await fetch(`${apiBaseUrl}/start-simulation`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ topik, kategori: "General" }),
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || "Request failed");
      }
      const data = await res.json();
      setHasil(data.data);
    } catch (err) {
      alert(err.message || "System Offline.");
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
    const chatLog = [];
    const agents = [];
    let isChaos = false;

    lines.forEach((line) => {
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
          let score = 50;
          let color = "#6366F1";
          let bg = "bg-slate-100 text-slate-500";
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
          ) {
            isChaos = true;
          }
          agents.push({ nama, sentimen, prediksi, score, color, bg });
        }
      } else if (!line.includes("|") && line.length > 5) {
        chatLog.push(line);
      }
    });

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
    <main className="min-h-screen bg-[#05070F] p-4 text-white md:p-10 print:bg-white print:p-0 print:text-slate-900">
      <div className="mx-auto max-w-6xl">
        <header className="mb-8 rounded-2xl border border-white/10 bg-[#0A0D18] p-5 md:mb-10">
          <div className="mb-4 flex items-center justify-between">
            <Link
              href="/"
              className="rounded-full border border-white/20 px-4 py-1.5 text-[11px] font-bold tracking-wider text-slate-200 uppercase transition hover:border-indigo-300 hover:bg-indigo-500/20"
            >
              Back to Landing
            </Link>
            {hasil && (
              <button
                onClick={() => window.print()}
                className="rounded-full bg-indigo-500 px-5 py-2 text-[11px] font-bold tracking-wider text-white uppercase transition hover:bg-indigo-400 print:hidden"
              >
                Export PDF
              </button>
            )}
          </div>
          <div className="flex items-end justify-between border-b border-white/10 pb-4">
            <div>
              <div className="mb-1 flex items-center gap-3">
                <div className="h-3 w-3 animate-pulse rounded-full bg-indigo-500"></div>
                <h1 className="text-2xl font-black tracking-widest uppercase">
                  VoxSwarm <span className="text-slate-400">Intelligence</span>
                </h1>
              </div>
              <p className="font-mono text-[10px] tracking-[0.3em] text-slate-400 uppercase">
                Protocol Version: 4.0.1 // encrypted_link_established
              </p>
            </div>
            <p className="hidden text-[11px] font-semibold tracking-[0.2em] text-indigo-300 uppercase md:block">
              Predict Anything
            </p>
          </div>
        </header>

        <div className="mb-8 rounded-2xl border border-white/10 bg-[#0A0D18] p-2 shadow-2xl shadow-indigo-950/30 print:hidden">
          <div className="flex flex-col gap-2 md:flex-row">
            <input
              className="w-full rounded-xl border border-white/10 bg-[#0E1220] p-4 text-sm text-slate-100 outline-none placeholder:text-slate-500 focus:border-indigo-400"
              value={topik}
              onChange={(e) => setTopik(e.target.value)}
              placeholder="Tuliskan seed simulasi (contoh: Kenaikan harga beras)..."
            />
            <button
              onClick={startAnalysis}
              disabled={loading}
              className="rounded-xl bg-indigo-500 px-10 py-3 text-xs font-bold tracking-widest text-white uppercase transition hover:bg-indigo-400 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {loading ? "PROCESING..." : "ANALYZE"}
            </button>
          </div>
        </div>

        {!hasil && (
          <section className="rounded-2xl border border-white/10 bg-[#0A0D18] p-10 text-center">
            <p className="mb-2 text-xs font-semibold tracking-[0.24em] text-indigo-300 uppercase">
              Live Simulation Console
            </p>
            <h2 className="mb-4 text-3xl leading-tight font-black">
              Start your first VoxSwarm prediction
            </h2>
            <p className="mx-auto max-w-2xl text-sm leading-7 text-slate-300">
              Input a topic above and run analysis to generate sentiment map,
              simulation log, and synthesis conclusion in one flow.
            </p>
          </section>
        )}

        {hasil && (
          <div className="grid grid-cols-1 gap-6 duration-1000 animate-in fade-in lg:grid-cols-12">
            <div className="space-y-6 lg:col-span-7">
              <div className="relative overflow-hidden rounded-2xl border border-white/10 bg-[#0A0D18] p-7 shadow-lg shadow-indigo-950/20 print:border-slate-300 print:bg-white">
                <div
                  className={`absolute top-0 right-0 px-4 py-1 text-[10px] font-black text-white uppercase ${
                    p.isChaos ? "bg-red-600" : "bg-emerald-600"
                  }`}
                >
                  {p.isChaos ? "Danger: Volatile" : "Status: Stable"}
                </div>
                <span className="mb-2 block text-[10px] font-black tracking-widest text-indigo-300 uppercase">
                  Synthesis Conclusion
                </span>
                <p className="mb-6 text-lg leading-relaxed font-bold text-white print:text-slate-900">
                  {p.synthesis}
                </p>
                <div className="rounded-xl border-l-4 border-indigo-400 bg-indigo-500/10 p-4 text-sm text-slate-200 italic print:border-slate-400 print:bg-slate-100 print:text-slate-700">
                  "{p.chatLog[0]}"
                </div>
              </div>

              <div className="rounded-2xl border border-white/10 bg-[#0A0D18] p-7 shadow-lg shadow-indigo-950/20 print:border-slate-300 print:bg-white">
                <span className="mb-6 block font-mono text-[10px] font-black tracking-widest text-indigo-300 uppercase">
                  Statistical Sentiment Map
                </span>
                <div style={{ width: "100%", height: 320, minHeight: 320 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={p.agents}>
                      <XAxis
                        dataKey="nama"
                        tick={{ fontSize: 10, fontWeight: "bold", fill: "#94A3B8" }}
                        axisLine={false}
                        tickLine={false}
                      />
                      <YAxis domain={[0, 100]} hide />
                      <Bar dataKey="score" radius={[6, 6, 6, 6]} barSize={48}>
                        {p.agents.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.color} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>

              <div className="rounded-2xl border border-white/10 bg-[#0A0D18] p-7 shadow-lg shadow-indigo-950/20 print:border-slate-300 print:bg-white">
                <div className="mb-6 flex items-center justify-between">
                  <span className="font-mono text-[10px] font-black tracking-widest text-indigo-300 uppercase">
                    Live Simulation Log
                  </span>
                  <div className="flex gap-1">
                    <div className="h-1 w-1 rounded-full bg-indigo-500"></div>
                    <div className="h-1 w-1 rounded-full bg-indigo-500 opacity-50"></div>
                    <div className="h-1 w-1 rounded-full bg-indigo-500 opacity-20"></div>
                  </div>
                </div>
                <div className="custom-scrollbar max-h-72 space-y-4 overflow-y-auto pr-4 font-mono text-[11px] leading-relaxed">
                  {p.chatLog.slice(1).map((msg, idx) => (
                    <div key={idx} className="group flex gap-4">
                      <span className="shrink-0 font-bold text-indigo-400">
                        [{idx + 1}]
                      </span>
                      <p className="text-slate-300 transition-colors group-hover:text-indigo-200 print:text-slate-700 italic">
                        {msg}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="space-y-6 lg:col-span-5">
              <div className="h-full rounded-2xl border border-white/10 bg-[#0A0D18] p-7 shadow-lg shadow-indigo-950/20 print:border-slate-300 print:bg-white">
                <span className="mb-7 block font-mono text-[10px] font-black tracking-widest text-indigo-300 uppercase">
                  Agent Node Predictions
                </span>
                <div className="space-y-8">
                  {p.agents.map((item, i) => (
                    <div
                      key={i}
                      className="relative border-l-2 border-white/10 pl-6 print:border-slate-200"
                    >
                      <div
                        className="absolute top-0 -left-[5px] h-2 w-2 rounded-full"
                        style={{ backgroundColor: item.color }}
                      ></div>
                      <div className="mb-2 flex items-center justify-between">
                        <span className="text-xs font-black text-slate-100 uppercase print:text-slate-800">
                          {item.nama}
                        </span>
                        <span
                          className={`rounded border px-2 py-0.5 text-[8px] font-bold ${item.bg} uppercase`}
                        >
                          {item.sentimen}
                        </span>
                      </div>
                      <p className="mb-3 text-[13px] leading-relaxed font-medium text-slate-300 print:text-slate-600">
                        {item.prediksi}
                      </p>
                      <div className="h-1 w-full overflow-hidden rounded-full bg-white/10 print:bg-slate-100">
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
