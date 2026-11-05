import Link from "next/link";
import "./case-study.css";

const ORDER = ["menolak", "netral", "mendukung"];

function distText(d) {
  return ORDER.filter((k) => d[k] > 0)
    .map((k) => `${d[k]} ${k}`)
    .join(" · ");
}

function StanceBar({ dist, size = "lg" }) {
  const items = ORDER.filter((k) => dist[k] > 0);
  return (
    <div className={`cs-bar cs-bar-${size}`} role="img" aria-label={distText(dist)}>
      {items.map((k) => (
        <div key={k} className={`cs-seg cs-${k}`} style={{ flex: `${dist[k]} 1 0` }}>
          {dist[k]}
        </div>
      ))}
    </div>
  );
}

function Legend({ dist }) {
  return (
    <div className="cs-legend">
      {ORDER.filter((k) => dist[k] > 0).map((k) => (
        <span key={k}>
          <i className={`cs-dot cs-${k}`} />
          {dist[k]} {k}
        </span>
      ))}
    </div>
  );
}

const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);

const STEPS = [
  { no: "1", name: "Situasi", href: "#babak1" },
  { no: "2", name: "Para pihak", href: "#babak2" },
  { no: "3", name: "Jalannya debat", href: "#babak3" },
  { no: "4", name: "Titik balik", href: "#babak4" },
  { no: "5", name: "Ke depan", href: "#babak5" },
  { no: "+", name: "Uji kebijakan", href: "#whatif" },
];

export default function CaseStudyView({ data }) {
  const { meta, hasil, situasi, kualitas, narator_fallback } = data;
  return (
    <div className="cs">
      {/* HERO + HASIL SINGKAT */}
      <header className="cs-wrap cs-hero">
        <div className="cs-title-block">
          <div className="cs-eyebrow">Studi kasus · {data.kategori ?? "Kebijakan publik"}</div>
          <h1 className="cs-h1">{data.judul}</h1>
          <div className="cs-chips">
            <span className="cs-chip">{meta.peserta} peserta</span>
            <span className="cs-chip">{meta.ronde} ronde debat</span>
            <span className="cs-chip">{meta.sumber} artikel sumber</span>
            <span className="cs-chip">Dijalankan {meta.tanggal}</span>
            {/* FASE 3: chip "Ringkasan otomatis" jika narator_fallback */}
            {narator_fallback && (
              <span className="cs-chip cs-chip-warn">Ringkasan otomatis</span>
            )}
          </div>
        </div>

        <div className="cs-warn" role="note">
          <div className="cs-warn-icon" aria-hidden="true">!</div>
          <div>
            <strong>Baca sebagai gambaran awal, bukan survei.</strong> {data.keterbatasan}
          </div>
        </div>

        {/* FASE 3: warning kualitas jika status === "warning" */}
        {kualitas?.status === "warning" && (
          <div className="cs-warn cs-warn-quality" role="note">
            <div className="cs-warn-icon" aria-hidden="true">!</div>
            <div>
              <strong>Kualitas data:</strong>{" "}
              {kualitas.fallback_count} dari {kualitas.total_giliran} giliran memakai nilai cadangan.
            </div>
          </div>
        )}

        <section className="cs-verdict" aria-label="Hasil singkat">
          <div className="cs-verdict-main">
            <div className="cs-eyebrow cs-eyebrow-muted">Hasil singkat</div>
            <div className="cs-vtext">{hasil.vonis}</div>
            <div className="cs-stack">
              <div className="cs-label">Sikap akhir {meta.peserta} peserta</div>
              <StanceBar dist={hasil.distribusi} />
              <Legend dist={hasil.distribusi} />
            </div>
          </div>
          <div className="cs-verdict-side">
            <div className="cs-reasons">
              <div className="cs-label">Tiga alasan utama</div>
              {hasil.alasan.map((a, i) => (
                <div className="cs-reason" key={i}>
                  <div className="cs-reason-no">{i + 1}</div>
                  <div className="cs-reason-txt">{a}</div>
                </div>
              ))}
            </div>
            <div className="cs-trust">
              <div className="cs-label">Seberapa bisa dipercaya?</div>
              <div className="cs-trust-row">
                <span className="cs-badge">{hasil.kepercayaan.level}</span>
                <span className="cs-trust-note">{hasil.kepercayaan.catatan}</span>
              </div>
            </div>
          </div>
        </section>
      </header>

      {/* STEPPER */}
      <div className="cs-stepper">
        <nav className="cs-wrap cs-stepper-in" aria-label="Babak studi kasus">
          {STEPS.map((s) => (
            <a key={s.href} href={s.href}>
              <span className="cs-stepno">{s.no}</span>
              {s.name}
            </a>
          ))}
        </nav>
      </div>

      {/* BABAK 1 */}
      <section id="babak1" className="cs-wrap cs-section">
        <div className="cs-head">
          <div className="cs-eyebrow">Babak 1 · Situasi</div>
          <h2 className="cs-h2">Apa yang terjadi?</h2>
        </div>
        <div className="cs-row">
          <div className="cs-card cs-card-lg">
            <div className="cs-label">Pemicu isu</div>
            <div className="cs-bignum">{situasi.pemicu.angka}</div>
            <p className="cs-p18">{situasi.pemicu.teks}</p>
          </div>
          <div className="cs-card cs-card-lg cs-card-sand">
            <div className="cs-label">Bahan awal simulasi</div>
            <div className="cs-bullets">
              {situasi.bahan.map((b, i) => (
                <div className="cs-bullet" key={i}>
                  <b>·</b>
                  <span>{b}</span>
                </div>
              ))}
            </div>
            <div className="cs-small cs-src">{situasi.sumber}</div>
          </div>
        </div>
      </section>

      {/* BABAK 2 */}
      <section id="babak2" className="cs-wrap cs-section">
        <div className="cs-head">
          <div className="cs-eyebrow">Babak 2 · Para pihak</div>
          <h2 className="cs-h2">Siapa yang terlibat?</h2>
          <p className="cs-lead">
            {meta.peserta} peserta dari berbagai latar belakang, dikelompokkan menurut sikap akhir mereka.
          </p>
        </div>
        <div className="cs-row cs-row-20">
          {data.kubu.map((k) => (
            <div key={k.nama} className={`cs-card cs-kubu cs-kubu-${k.tipe}`}>
              <div className="cs-kubu-head">
                <div className="cs-kubu-name">{k.nama}</div>
                <div className="cs-kubu-count">{k.agen.length} peserta</div>
              </div>
              <p className="cs-kubu-note">{k.catatan}</p>
              <div className="cs-agents">
                {k.agen.map((a) => (
                  <span className="cs-agent" key={a}>{a}</span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* BABAK 3 */}
      <section id="babak3" className="cs-wrap cs-section">
        <div className="cs-head">
          <div className="cs-eyebrow">Babak 3 · Jalannya debat</div>
          <h2 className="cs-h2">Apa yang terjadi di tiap ronde?</h2>
        </div>
        <div className="cs-rounds">
          {data.ronde.map((r) => (
            <article className="cs-round" key={r.no}>
              <div className="cs-round-l">
                <span className="cs-roundtag">Ronde {r.no}</span>
                <h3 className="cs-round-title">{r.judul}</h3>
                <p className="cs-round-sum">{r.ringkas}</p>
                <div className="cs-stack" style={{ marginTop: 4 }}>
                  <StanceBar dist={r.distribusi} size="sm" />
                  <div className="cs-small">{distText(r.distribusi)}</div>
                </div>
              </div>
              <div className="cs-round-r">
                <p className="cs-quote">“{r.kutipan.teks}”</p>
                <div className="cs-quote-by">
                  <strong>{r.kutipan.agen}</strong>
                  {r.kutipan.jenis === "klaim" ? (
                    <span className="cs-tag cs-tag-claim">Klaim agen, belum diverifikasi</span>
                  ) : (
                    <span className="cs-tag">Kutipan langsung</span>
                  )}
                </div>
              </div>
            </article>
          ))}
        </div>
      </section>

      {/* BABAK 4 */}
      <section id="babak4" className="cs-wrap cs-section">
        <div className="cs-head">
          <div className="cs-eyebrow">Babak 4 · Titik balik</div>
          <h2 className="cs-h2">Apa yang menggeser sikap?</h2>
          <p className="cs-lead">
            Tidak banyak yang berubah. {data.titikBalik.length} peserta bergeser, dan kubu kritikus bertahan dengan alasan baru.
          </p>
        </div>
        <div className="cs-row cs-row-20">
          {data.titikBalik.map((t) => (
            <div className="cs-card" key={t.agen + t.kapan}>
              <div className="cs-shift-name">{t.agen}</div>
              <div className="cs-shift-flow">
                <span className={`cs-pill cs-${t.dari}`}>{cap(t.dari)}</span>
                <span aria-hidden="true">→</span>
                <span className={`cs-pill cs-${t.ke}`}>{cap(t.ke)}</span>
                <span className="cs-when">{t.kapan}</span>
              </div>
              <p className="cs-shift-why">{t.alasan}</p>
            </div>
          ))}
        </div>

        {data.buktiDiperdebatkan && data.buktiDiperdebatkan.length > 0 && (
          <div className="cs-dispute">
            <div className="cs-dispute-head">
              <h3 className="cs-dispute-title">Bukti yang sama, tafsir berlawanan</h3>
              <span className="cs-tag cs-tag-claim">Klaim agen, belum diverifikasi</span>
            </div>
            <div className="cs-dispute-grid">
              {data.buktiDiperdebatkan.map((b) => (
                <div className="cs-dispute-item" key={b.agen}>
                  <div className="cs-label">{b.agen}</div>
                  <p>{b.teks}</p>
                </div>
              ))}
            </div>
          </div>
        )}
      </section>

      {/* BABAK 5 */}
      <section id="babak5" className="cs-wrap cs-section">
        <div className="cs-head">
          <div className="cs-eyebrow">Babak 5 · Ke depan</div>
          <h2 className="cs-h2">Kalau begini terus, apa jadinya?</h2>
          <p className="cs-lead">
            Bukan ramalan persentase, tapi pola “jika … maka …” dari sikap para peserta.
          </p>
        </div>
        <div className="cs-row cs-row-20">
          {data.skenario.map((s, i) => (
            <div className="cs-card cs-sk" key={i}>
              <div className="cs-sk-k">Jika</div>
              <p className="cs-sk-jika">{s.jika}</p>
              <div className="cs-sk-maka">
                <div className="cs-sk-k is-maka">Maka</div>
                <p>{s.maka}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* WHAT-IF */}
      {data.whatif && (
        <section id="whatif" className="cs-wrap cs-section">
          <div className="cs-whatif">
            <div className="cs-head" style={{ gap: 10 }}>
              <div className="cs-eyebrow">Bonus · Uji kebijakan (what-if)</div>
              <h2 className="cs-h2">{data.whatif.judul}</h2>
              <p className="cs-lead">{data.whatif.deskripsi}</p>
            </div>
            <div className="cs-row" style={{ gap: 20 }}>
              <div className="cs-wi-col">
                <div className="cs-wi-label">Sebelum · simulasi awal</div>
                <StanceBar dist={data.whatif.sebelum} size="md" />
                <p className="cs-wi-note">{distText(data.whatif.sebelum)}</p>
              </div>
              {data.whatif.sesudah ? (
                <div className="cs-wi-col">
                  <div className="cs-wi-label">Sesudah · dengan intervensi</div>
                  <StanceBar dist={data.whatif.sesudah} size="md" />
                  <p className="cs-wi-note">{distText(data.whatif.sesudah)}</p>
                </div>
              ) : (
                <div className="cs-wi-col is-empty">
                  <div className="cs-wi-label">Sesudah · dengan intervensi</div>
                  <div className="cs-wi-empty">Belum dijalankan</div>
                  <p className="cs-wi-note">Slot ini terisi otomatis setelah simulasi intervensi selesai.</p>
                </div>
              )}
            </div>
          </div>
        </section>
      )}

      {/* FOOTER - hanya tautan Bagikan tautan (sembunyikan export tanpa endpoint) */}
      <footer className="cs-wrap cs-foot">
        <div className="cs-actions">
          <div className="cs-btns">
            {/* Sembunyikan Unduh PDF, Word, CSV - tidak ada endpoint ekspor */}
            <a className="cs-btn" href="#">Bagikan tautan</a>
          </div>
          <a className="cs-link" href="#babak3">Lihat catatan debat lengkap</a>
        </div>
        <p className="cs-disclaimer">
          Alat ini hanya membuat simulasi dan referensi awal, bukan pengganti survei sungguhan atau riset resmi. Jangan jadikan satu-satunya acuan untuk mengambil keputusan.
        </p>
      </footer>
    </div>
  );
}