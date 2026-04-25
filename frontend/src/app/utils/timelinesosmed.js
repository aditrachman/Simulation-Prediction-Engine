"use client";

// ─── TimelineSosmed.js ────────────────────────────────────────────────────────
// Komponen feed sosial media simulasi VoxSwarm
// Sub-komponen: warnaHandle · Avatar · KartuPost · PanelProfilAgen
//               LaporanSosmed · TimelineSosmed (default export)
// ─────────────────────────────────────────────────────────────────────────────

import { useState, useMemo } from "react";

// ── Shared ────────────────────────────────────────────────────────────────────
const Kartu = ({ children, className = "" }) => (
  <div className={`rounded-2xl border border-white/8 bg-[#0C0F1D] p-5 page-break-avoid print-card ${className}`}>
    {children}
  </div>
);

const JudulSeksi = ({ ikon, children }) => (
  <div className="mb-4 flex items-center gap-2">
    {ikon && <span className="text-base">{ikon}</span>}
    <p className="text-[11px] font-bold tracking-widest text-slate-500 uppercase">{children}</p>
  </div>
);

// ── Warna & util ─────────────────────────────────────────────────────────────
const WARNA_HANDLE = [
  "#818cf8", "#34d399", "#fbbf24", "#f87171",
  "#a78bfa", "#22d3ee", "#f472b6", "#2dd4bf",
  "#fb923c", "#c084fc",
];

function warnaHandle(nama) {
  let h = 0;
  for (let i = 0; i < nama.length; i++) h = (h * 31 + nama.charCodeAt(i)) & 0xffff;
  return WARNA_HANDLE[h % WARNA_HANDLE.length];
}

const SENT_CFG = {
  positif: { label: "Mendukung", bg: "bg-emerald-500/10", text: "text-emerald-400", border: "border-emerald-500/20" },
  netral:  { label: "Netral",    bg: "bg-slate-500/10",   text: "text-slate-400",   border: "border-slate-500/20"   },
  negatif: { label: "Menolak",   bg: "bg-red-500/10",     text: "text-red-400",     border: "border-red-500/20"     },
};

// ── Avatar ────────────────────────────────────────────────────────────────────
const Avatar = ({ nama, size = 9 }) => {
  const w = warnaHandle(nama);
  const px = { 4: "h-4 w-4 text-[8px]", 5: "h-5 w-5 text-[8px]", 7: "h-7 w-7 text-[9px]", 8: "h-8 w-8 text-[10px]", 9: "h-9 w-9 text-[10px]", 10: "h-10 w-10 text-[11px]" }[size] ?? "h-9 w-9 text-[10px]";
  return (
    <div
      className={`${px} shrink-0 rounded-full flex items-center justify-center font-black`}
      style={{ backgroundColor: w + "20", border: `1.5px solid ${w}60`, color: w }}
    >
      {nama.slice(0, 2).toUpperCase()}
    </div>
  );
};

// ── BadgeSentimen ─────────────────────────────────────────────────────────────
const BadgeSentimen = ({ label }) => {
  const cfg = SENT_CFG[label] ?? SENT_CFG.netral;
  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold ${cfg.bg} ${cfg.text} ${cfg.border}`}>
      {cfg.label}
    </span>
  );
};

// ── KartuPost ─────────────────────────────────────────────────────────────────
const KartuPost = ({ post: postRaw, postMap, aksiList, onLikeInfo }) => {
  const [bukaThread, setBukaThread] = useState(false);

  const post       = postMap?.[postRaw.id] ?? postRaw;
  const w          = warnaHandle(post.nama ?? "?");
  const sentLabel  = post.sentimen?.label;
  const isViral    = post.is_viral;
  const isSistem   = post.akun_id === "SYSTEM";
  const isOtoritas = post.nama?.toLowerCase().includes("pemerintah") || post.nama?.toLowerCase().includes("pejabat");

  const likes      = Array.isArray(post.likes)   ? post.likes   : [];
  const replies    = Array.isArray(post.replies)  ? post.replies : [];
  const quotes     = Array.isArray(post.quotes)   ? post.quotes  : [];
  const likeCount  = likes.length;
  const replyCount = replies.length;
  const quoteCount = quotes.length;
  const likerNames = likes.map(h => h.replace(/^@/, "").replace(/_/g, " "));

  const replyPosts = replies.map(rid => postMap?.[rid]).filter(Boolean).slice(0, 4);
  const parentPost = post.tipe === "reply" && post.reply_to
    ? postMap?.[post.reply_to]
    : post.tipe === "quote" && post.quote_of
      ? postMap?.[post.quote_of]
      : null;

  const kebijakanAksi = aksiList?.find(a =>
    (a.tipe === "reply_otoritas" || a.tipe === "quote_otoritas") &&
    (a.target_id === post.id || a.post?.id === post.id) && a.kebijakan_baru
  );

  // ── Breaking news ───────────────────────────────────────────────────────
  if (isSistem) {
    return (
      <div className="flex items-start gap-3 rounded-2xl border border-amber-500/30 bg-amber-950/15 px-4 py-3.5">
        <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-amber-500/15 text-sm">
          🚨
        </div>
        <div>
          <p className="mb-0.5 text-[10px] font-black uppercase tracking-widest text-amber-500">Breaking News</p>
          <p className="text-sm font-semibold leading-snug text-amber-200">
            {post.konten?.replace("🚨 BREAKING: ", "")}
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className={`rounded-2xl border bg-[#0C0F1D] transition-all ${
      isViral
        ? "border-amber-500/30 shadow-[0_0_20px_rgba(245,158,11,0.07)]"
        : "border-white/6 hover:border-white/12"
    }`}>
      <div className="p-4">
        <div className="flex items-start gap-3">
          <Avatar nama={post.nama ?? "?"} size={9} />
          <div className="flex-1 min-w-0">

            {/* Nama + badge baris atas */}
            <div className="mb-2 flex flex-wrap items-center gap-1.5">
              <span className="text-sm font-bold text-white">{post.nama}</span>
              <span className="text-xs text-slate-500">{post.handle}</span>
              {isOtoritas && (
                <span className="rounded-full bg-blue-500/15 border border-blue-500/25 px-2 py-0.5 text-[10px] font-bold text-blue-400">
                  🏛 Otoritas
                </span>
              )}
              {isViral && (
                <span className="rounded-full bg-amber-500/15 border border-amber-500/30 px-2 py-0.5 text-[10px] font-black text-amber-400 animate-pulse">
                  🔥 VIRAL
                </span>
              )}
              {post.tipe === "reply" && (
                <span className="rounded-full bg-cyan-500/10 border border-cyan-500/20 px-2 py-0.5 text-[10px] font-semibold text-cyan-400">
                  💬 Membalas
                </span>
              )}
              {post.tipe === "quote" && (
                <span className="rounded-full bg-violet-500/10 border border-violet-500/20 px-2 py-0.5 text-[10px] font-semibold text-violet-400">
                  🔁 Mengutip
                </span>
              )}
              {sentLabel && <BadgeSentimen label={sentLabel} />}
            </div>

            {/* Parent fallback */}
            {post.tipe !== "post" && post.parent_nama && !parentPost && (
              <div className="mb-2 flex items-center gap-1.5 text-[11px] text-slate-500">
                <span>{post.tipe === "reply" ? "↩" : "↗"}</span>
                <span className="font-semibold text-slate-400">{post.parent_nama}</span>
                <span className="text-slate-600">{post.parent_handle}</span>
              </div>
            )}

            {/* Parent preview */}
            {parentPost && (
              <div className="mb-3 rounded-xl border border-white/6 bg-white/[0.03] px-3 py-2 text-xs">
                <div className="flex items-center gap-1.5 mb-1">
                  <Avatar nama={parentPost.nama ?? "?"} size={4} />
                  <span className="font-bold text-slate-300">{parentPost.nama}</span>
                  <span className="text-slate-500">{parentPost.handle}</span>
                </div>
                <p className="text-slate-500 leading-snug">
                  {parentPost.konten?.slice(0, 100)}{parentPost.konten?.length > 100 ? "…" : ""}
                </p>
              </div>
            )}

            {/* Konten utama */}
            <p className="text-sm leading-relaxed text-slate-200">{post.konten}</p>

            {/* Kebijakan otoritas */}
            {kebijakanAksi?.kebijakan_baru && (
              <div className="mt-3 rounded-xl border border-blue-500/20 bg-blue-950/15 px-3 py-2.5">
                <p className="text-[10px] font-bold text-blue-400 mb-1">📋 Kebijakan Baru</p>
                <p className="text-xs leading-relaxed text-blue-200">{kebijakanAksi.kebijakan_baru}</p>
              </div>
            )}

            {/* Engagement row */}
            <div className="mt-3 flex items-center gap-0.5 text-[11px]">
              <button
                onClick={() => likeCount > 0 && onLikeInfo?.({ ...post, likerNames })}
                className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 transition font-semibold ${
                  likeCount > 0
                    ? "text-rose-400 bg-rose-500/10 hover:bg-rose-500/20 cursor-pointer"
                    : "text-slate-700 cursor-default"
                }`}
              >
                <span>{likeCount > 0 ? "❤️" : "🤍"}</span>
                <span>{likeCount}</span>
              </button>
              <span className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 font-semibold ${
                replyCount > 0 ? "text-cyan-400 bg-cyan-500/10" : "text-slate-700"
              }`}>
                <span>💬</span><span>{replyCount}</span>
              </span>
              <span className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 font-semibold ${
                quoteCount > 0 ? "text-violet-400 bg-violet-500/10" : "text-slate-700"
              }`}>
                <span>🔁</span><span>{quoteCount}</span>
              </span>
              {(post.reach ?? 0) > 0 && (
                <span className="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-slate-600">
                  <span>👁</span><span>{post.reach}</span>
                </span>
              )}
              {replyPosts.length > 0 && (
                <button
                  onClick={() => setBukaThread(v => !v)}
                  className="ml-auto text-[10px] font-semibold text-indigo-400 hover:text-indigo-300 transition px-2.5 py-1.5 rounded-lg hover:bg-indigo-500/10"
                >
                  {bukaThread ? "▲ Tutup" : `▼ ${replyPosts.length} balasan`}
                </button>
              )}
            </div>

            {/* Siapa yang like */}
            {likeCount > 0 && (
              <div className="mt-2 flex items-center gap-1.5 flex-wrap">
                <span className="text-[10px] text-slate-600">Disukai:</span>
                {likerNames.slice(0, 5).map((n, i) => (
                  <div key={i} className="flex items-center gap-1 rounded-full bg-white/5 border border-white/8 px-2 py-0.5">
                    <Avatar nama={n} size={4} />
                    <span className="text-[10px] text-slate-400 capitalize">{n}</span>
                  </div>
                ))}
                {likerNames.length > 5 && (
                  <span className="text-[10px] text-slate-600">+{likerNames.length - 5} lainnya</span>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Thread inline */}
      {bukaThread && replyPosts.length > 0 && (
        <div className="border-t border-white/5 mx-4 mb-4 pt-3 pl-12 space-y-3 border-l border-l-white/5">
          {replyPosts.map(r => (
            <div key={r.id} className="flex gap-2.5">
              <Avatar nama={r.nama ?? "?"} size={7} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-0.5 flex-wrap">
                  <span className="text-xs font-bold text-slate-300">{r.nama}</span>
                  <span className="text-[10px] text-slate-600">{r.handle}</span>
                  {r.likes?.length > 0 && (
                    <span className="ml-auto text-[10px] text-rose-400 flex items-center gap-1">
                      ❤️ {r.likes.length}
                    </span>
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

// ── ModalLike ─────────────────────────────────────────────────────────────────
const ModalLike = ({ post, onTutup }) => (
  <div
    className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm"
    onClick={onTutup}
  >
    <div
      className="w-80 rounded-2xl border border-white/10 bg-[#0C0F1D] p-5 shadow-2xl"
      onClick={e => e.stopPropagation()}
    >
      <p className="text-sm font-bold text-white mb-1">❤️ Disukai oleh</p>
      <p className="text-[11px] text-slate-500 mb-3 truncate">"{post.konten?.slice(0, 60)}…"</p>
      {!post.likerNames?.length
        ? <p className="text-xs text-slate-500">Belum ada yang like.</p>
        : (
          <div className="space-y-2 max-h-60 overflow-y-auto">
            {post.likerNames.map((n, i) => (
              <div key={i} className="flex items-center gap-2.5">
                <Avatar nama={n} size={7} />
                <span className="text-sm text-slate-300 capitalize">{n}</span>
              </div>
            ))}
          </div>
        )}
      <button
        onClick={onTutup}
        className="mt-4 w-full rounded-xl bg-white/5 py-2 text-xs text-slate-400 hover:bg-white/10 transition"
      >
        Tutup
      </button>
    </div>
  </div>
);

// ── PanelProfilAgen ───────────────────────────────────────────────────────────
const PanelProfilAgen = ({ profilAgen }) => {
  if (!profilAgen?.length) return null;
  return (
    <Kartu>
      <JudulSeksi ikon="👥">Profil Akun — Siapa Paling Berpengaruh?</JudulSeksi>
      <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:grid-cols-4">
        {profilAgen.map((a, i) => {
          const w = warnaHandle(a.nama);
          return (
            <div key={i} className="rounded-xl border border-white/6 bg-white/[0.02] p-3 flex flex-col gap-2">
              <div className="flex items-center gap-2">
                <Avatar nama={a.nama} size={8} />
                <div className="min-w-0">
                  <p className="text-xs font-bold text-white truncate leading-tight">{a.nama}</p>
                  <p className="text-[10px] text-slate-500 truncate">{a.handle}</p>
                </div>
              </div>
              <div className="flex flex-wrap gap-1">
                {a.is_authority && (
                  <span className="rounded-full bg-blue-500/15 border border-blue-500/25 px-1.5 py-0.5 text-[9px] font-bold text-blue-400">
                    🏛 Otoritas
                  </span>
                )}
                {a.is_counter && (
                  <span className="rounded-full bg-orange-500/15 border border-orange-500/25 px-1.5 py-0.5 text-[9px] font-bold text-orange-400">
                    ⚡ Kontra
                  </span>
                )}
              </div>
              <div className="grid grid-cols-2 gap-x-2 gap-y-0.5 text-[10px] text-slate-500">
                <span>👥 {a.followers}</span>
                <span>📝 {a.total_post}</span>
                <span>❤️ {a.total_likes_dapat}</span>
                <span>👁 {a.following}</span>
              </div>
              <div className="h-1 rounded-full bg-white/5 overflow-hidden">
                <div
                  className="h-full rounded-full transition-all"
                  style={{
                    width: `${Math.min(100, (a.followers + a.total_likes_dapat) * 10)}%`,
                    backgroundColor: w,
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </Kartu>
  );
};

// ── LaporanSosmed ─────────────────────────────────────────────────────────────
const LaporanSosmed = ({ hasilSosmed }) => {
  if (!hasilSosmed) return null;

  const analisis      = hasilSosmed.analisis    ?? {};
  const statBe        = hasilSosmed.statistik   ?? {};
  const topInfluencer = analisis.top_influencers ?? [];
  const profilAgen    = hasilSosmed.profil_agen ?? [];
  const semuaPost     = hasilSosmed.semua_post  ?? [];

  const sentimenCounts = { positif: 0, netral: 0, negatif: 0 };
  semuaPost.forEach(p => {
    const lb = p.sentimen?.label ?? "netral";
    if (lb in sentimenCounts) sentimenCounts[lb]++;
  });
  const totalSentimen = Object.values(sentimenCounts).reduce((a, b) => a + b, 0) || 1;

  const SENT_BAR = [
    { label: "Mendukung", key: "positif", col: "#34d399" },
    { label: "Netral",    key: "netral",  col: "#818cf8" },
    { label: "Menolak",   key: "negatif", col: "#f87171" },
  ];

  const engStats = [
    { label: "Likes",   nilai: statBe.total_likes   ?? semuaPost.reduce((s, p) => s + (p.likes?.length ?? 0), 0),  icon: "❤️", col: "#f87171" },
    { label: "Balasan", nilai: statBe.total_replies ?? semuaPost.filter(p => p.tipe === "reply").length,              icon: "💬", col: "#22d3ee" },
    { label: "Kutipan", nilai: statBe.total_quotes  ?? semuaPost.filter(p => p.tipe === "quote").length,              icon: "🔁", col: "#a78bfa" },
  ];

  const semuaNol = engStats.every(s => s.nilai === 0);

  return (
    <Kartu>
      <JudulSeksi ikon="📊">Laporan Hasil Simulasi</JudulSeksi>

      {analisis.narasi && (
        <div className="mb-5 rounded-xl border border-white/6 bg-white/[0.02] p-4">
          <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-2">Ringkasan Eksekutif</p>
          <p className="text-sm leading-7 text-slate-300">{analisis.narasi}</p>
        </div>
      )}

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        {/* Engagement */}
        <div>
          <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-3">Statistik Engagement</p>
          <div className="grid grid-cols-3 gap-2 mb-2">
            {engStats.map((s, i) => (
              <div key={i} className="rounded-xl border p-3 text-center"
                style={{ borderColor: s.col + "25", backgroundColor: s.col + "08" }}>
                <div className="text-lg mb-1">{s.icon}</div>
                <div className="text-xl font-black" style={{ color: s.col }}>{s.nilai}</div>
                <div className="text-[10px] text-slate-600 mt-0.5">{s.label}</div>
              </div>
            ))}
          </div>
          {semuaNol && (
            <div className="rounded-lg border border-amber-500/20 bg-amber-950/10 px-3 py-2">
              <p className="text-[10px] text-amber-500/80 leading-relaxed">
                ℹ️ Angka 0 karena backend belum mengisi interaksi antar-agen.
                Aktifkan logika interaksi di endpoint <code className="text-amber-400">/start-social</code>.
              </p>
            </div>
          )}
        </div>

        {/* Sentimen */}
        <div>
          <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-3">Distribusi Sentimen Post</p>
          <div className="space-y-3">
            {SENT_BAR.map(s => {
              const pct = Math.round((sentimenCounts[s.key] / totalSentimen) * 100);
              return (
                <div key={s.key}>
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-xs text-slate-400">{s.label}</span>
                    <span className="text-xs font-bold" style={{ color: s.col }}>{pct}%</span>
                  </div>
                  <div className="h-2 rounded-full bg-white/5 overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all"
                      style={{ width: pct + "%", backgroundColor: s.col, opacity: 0.8 }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Top Influencer */}
      {topInfluencer.length > 0 && (
        <div className="mt-5 pt-5 border-t border-white/5">
          <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-3">Top Influencer</p>
          <div className="space-y-2">
            {topInfluencer.slice(0, 3).map((inf, i) => {
              const w      = warnaHandle(inf.nama);
              const profil = profilAgen.find(a => a.nama === inf.nama);
              const medals = ["🥇", "🥈", "🥉"];
              return (
                <div key={i} className="flex items-center gap-3 rounded-xl bg-white/[0.02] border border-white/6 p-3">
                  <span className="text-base shrink-0">{medals[i]}</span>
                  <div className="h-8 w-8 shrink-0 rounded-full flex items-center justify-center text-[10px] font-black"
                    style={{ backgroundColor: w + "20", border: "1.5px solid " + w + "60", color: w }}>
                    {inf.nama.slice(0, 2).toUpperCase()}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-bold text-slate-200 truncate">{inf.nama}</p>
                    <p className="text-[10px] text-slate-600">
                      {profil?.followers ?? 0} followers · {profil?.total_post ?? 0} post
                    </p>
                  </div>
                  <div className="text-right shrink-0">
                    <p className="text-sm font-black text-amber-400">{inf.engagement_score}</p>
                    <p className="text-[10px] text-slate-600">eng.</p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Ranking akun */}
      {analisis.ranking_akun?.length > 0 && (
        <div className="mt-5 pt-5 border-t border-white/5">
          <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-3">Ranking Akun Berpengaruh</p>
          <div className="flex flex-wrap gap-2">
            {analisis.ranking_akun.map((a, i) => (
              <div key={i} className="flex items-center gap-1.5 rounded-full border border-white/8 bg-white/[0.03] px-3 py-1.5">
                <span className="text-[10px] font-black text-slate-500">#{i + 1}</span>
                <Avatar nama={a.nama} size={5} />
                <span className="text-xs font-semibold text-slate-300">{a.handle}</span>
                <span className="text-[10px] text-slate-600">{a.followers} followers</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </Kartu>
  );
};

// ── TimelineSosmed (default export) ──────────────────────────────────────────
export default function TimelineSosmed({ hasilSosmed, topik }) {
  const [tickAktif,    setTickAktif]    = useState(0);
  const [filterMode,   setFilterMode]   = useState("semua");
  const [likeInfoPost, setLikeInfoPost] = useState(null);

  if (!hasilSosmed) return null;

  const tickDetail   = hasilSosmed.tick_detail   ?? [];
  const semuaPost    = hasilSosmed.semua_post    ?? [];
  const profilAgen   = hasilSosmed.profil_agen   ?? [];
  const viralPosts   = hasilSosmed.viral_posts   ?? [];
  const analisis     = hasilSosmed.analisis      ?? {};
  const logAktivitas = hasilSosmed.log_aktivitas ?? [];
  const statBe       = hasilSosmed.statistik     ?? {};

  // Build postMap
  const postMap = {};
  semuaPost.forEach(p => { postMap[p.id] = p; });

  // ── Statistik: prioritas backend → hitung dari data post ──────────────
  const totalPost    = statBe.total_post    ?? semuaPost.filter(p => p.tipe === "post" && p.akun_id !== "SYSTEM").length;
  const totalLikes   = statBe.total_likes   ?? semuaPost.reduce((s, p) => s + (p.likes?.length ?? 0), 0);
  const totalReplies = statBe.total_replies ?? semuaPost.filter(p => p.tipe === "reply").length;
  const totalQuotes  = statBe.total_quotes  ?? semuaPost.filter(p => p.tipe === "quote").length;
  const totalViral   = statBe.viral_count   ?? viralPosts.length;

  const STAT_ITEMS = [
    { label: "Post",    nilai: totalPost,    icon: "📝", col: "#818cf8" },
    { label: "Likes",   nilai: totalLikes,   icon: "❤️", col: "#f87171" },
    { label: "Balasan", nilai: totalReplies, icon: "💬", col: "#22d3ee" },
    { label: "Kutipan", nilai: totalQuotes,  icon: "🔁", col: "#a78bfa" },
    { label: "Viral",   nilai: totalViral,   icon: "🔥", col: "#fbbf24" },
  ];

  // Filter post
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
  }, [filterMode, viralPosts, tickDetail, tickAktif, semuaPost]);

  // Kebijakan dari otoritas
  const semuaKebijakan = logAktivitas
    .filter(a => (a.tipe === "reply_otoritas" || a.tipe === "quote_otoritas") && a.kebijakan_baru)
    .map(a => ({ kebijakan: a.kebijakan_baru, agen: a.agen }));

  return (
    <div className="space-y-4">

      {/* ── Kartu Topik ── */}
      <div className="rounded-2xl border border-violet-500/20 bg-violet-950/10 p-4">
        <div className="flex items-start gap-3">
          <div className="h-10 w-10 shrink-0 rounded-xl bg-violet-500/15 border border-violet-500/30 flex items-center justify-center text-lg">
            📢
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1.5 flex-wrap">
              <span className="text-xs font-bold text-violet-300">Isu yang Disimulasikan</span>
              <span className="rounded-full bg-violet-500/15 border border-violet-500/25 px-2 py-0.5 text-[10px] font-bold text-violet-400">
                TOPIK
              </span>
              <span className="text-[10px] text-slate-500">
                {profilAgen.length} agen · {tickDetail.length} momen · {semuaPost.length} post
              </span>
            </div>
            <p className="text-base font-bold text-white leading-snug">{topik}</p>
            {hasilSosmed.intervensi && (
              <div className="mt-2 flex items-center gap-2 text-xs text-amber-300">
                <span>⚡</span>
                <span>Breaking news: <span className="font-bold">"{hasilSosmed.intervensi}"</span></span>
              </div>
            )}
            <div className="mt-3 flex flex-wrap gap-1.5">
              {profilAgen.map((a, i) => (
                <div key={i} className="flex items-center gap-1 rounded-full bg-white/5 border border-white/8 px-2 py-0.5">
                  <Avatar nama={a.nama} size={4} />
                  <span className="text-[10px] text-slate-400">{a.handle}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* ── Statistik Ringkas ── */}
      <div className="grid grid-cols-5 gap-2">
        {STAT_ITEMS.map((s, i) => (
          <div key={i} className="rounded-xl border p-3 text-center"
            style={{ borderColor: s.col + "25", backgroundColor: s.col + "08" }}>
            <div className="text-base mb-1">{s.icon}</div>
            <div className="text-xl font-black" style={{ color: s.col }}>{s.nilai}</div>
            <div className="text-[10px] text-slate-600 mt-0.5">{s.label}</div>
          </div>
        ))}
      </div>

      {/* ── Kebijakan dari otoritas ── */}
      {semuaKebijakan.length > 0 && (
        <div className="rounded-2xl border border-blue-500/20 bg-blue-950/10 p-4">
          <div className="flex items-center gap-2 mb-3">
            <span className="text-base">🏛</span>
            <span className="text-sm font-bold text-blue-300">Respons & Kebijakan Baru dari Otoritas</span>
            <span className="rounded-full bg-blue-500/15 px-2 py-0.5 text-[10px] font-bold text-blue-400">
              {semuaKebijakan.length}
            </span>
          </div>
          <div className="space-y-2">
            {semuaKebijakan.map((k, i) => (
              <div key={i} className="rounded-xl border border-blue-500/15 bg-blue-900/10 px-3 py-2.5">
                <p className="text-[10px] text-blue-500 font-bold mb-1">📋 {k.agen}</p>
                <p className="text-sm text-blue-100 leading-relaxed">{k.kebijakan}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Analisis Narasi ── */}
      {analisis.narasi && (
        <Kartu>
          <JudulSeksi ikon="🧠">Analisis Dinamika Sosmed</JudulSeksi>
          <p className="text-sm leading-7 text-slate-300">{analisis.narasi}</p>
        </Kartu>
      )}

      {/* ── Laporan Lengkap ── */}
      <LaporanSosmed hasilSosmed={hasilSosmed} />

      {/* ── Profil Agen ── */}
      <PanelProfilAgen profilAgen={profilAgen} />

      {/* ── Filter Bar (sticky) ── */}
      <div className="sticky top-0 z-10 rounded-xl border border-white/8 bg-[#06080F]/90 px-3 py-2.5 backdrop-blur-sm print:hidden">
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex gap-1.5">
            {[
              { id: "semua",    label: "🌐 Semua" },
              { id: "viral",    label: "🔥 Viral" },
              { id: "timeline", label: "⏱ Per Momen" },
            ].map(f => (
              <button key={f.id} onClick={() => setFilterMode(f.id)}
                className={`rounded-lg px-3 py-1.5 text-xs font-bold transition ${
                  filterMode === f.id
                    ? "bg-violet-600 text-white"
                    : "border border-white/8 text-slate-500 hover:border-violet-400/50 hover:text-white"
                }`}>
                {f.label}
              </button>
            ))}
          </div>
          {filterMode === "timeline" && (
            <div className="flex gap-1.5 flex-wrap">
              {tickDetail.map((t, i) => (
                <button key={i} onClick={() => setTickAktif(i)}
                  className={`rounded-lg px-2.5 py-1.5 text-xs font-bold transition ${
                    tickAktif === i
                      ? "bg-violet-600 text-white"
                      : "border border-white/8 text-slate-500 hover:border-violet-400/50 hover:text-white"
                  }`}>
                  Momen {t.tick}
                </button>
              ))}
            </div>
          )}
          <span className="ml-auto text-[11px] text-slate-600">{postTampil.length} post</span>
        </div>
      </div>

      {/* ── Trending per momen ── */}
      {filterMode === "timeline" && tickDetail[tickAktif]?.trending?.length > 0 && (
        <div className="rounded-xl border border-amber-500/20 bg-amber-950/10 px-4 py-3">
          <p className="text-[11px] font-bold text-amber-400 mb-2">
            🔥 Trending — Momen {tickDetail[tickAktif].tick}
          </p>
          <div className="space-y-2">
            {tickDetail[tickAktif].trending.slice(0, 3).map((p, i) => {
              const fresh = postMap[p.id] ?? p;
              return (
                <div key={i} className="flex items-center gap-2 text-xs">
                  <span className="text-amber-600 font-black w-4 shrink-0">#{i + 1}</span>
                  <Avatar nama={fresh.nama ?? "?"} size={5} />
                  <span className="text-slate-400 shrink-0 font-semibold">{fresh.handle}</span>
                  <span className="text-slate-300 flex-1 truncate">{fresh.konten?.slice(0, 60)}…</span>
                  <span className="text-rose-400 shrink-0 font-bold">❤️ {fresh.likes?.length ?? 0}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ── Feed Post ── */}
      <div className="space-y-3">
        {postTampil.length === 0 && (
          <div className="rounded-2xl border border-dashed border-white/8 p-10 text-center text-sm text-slate-600">
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

      {likeInfoPost && (
        <ModalLike post={likeInfoPost} onTutup={() => setLikeInfoPost(null)} />
      )}
    </div>
  );
}