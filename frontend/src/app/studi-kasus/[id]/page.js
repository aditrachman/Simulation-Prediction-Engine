import { notFound } from "next/navigation";
import CaseStudyView from "@/app/components/case-study/CaseStudyView";
import mbgStatic from "@/data/mbg-tepat-sasaran.json";

export const dynamic = "force-dynamic";
export const revalidate = 0;

async function getCaseStudy(id, apiBase) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 8000);

  try {
    const res = await fetch(`${apiBase}/case-study/${id}`, {
      cache: "no-store",
      headers: { "Content-Type": "application/json" },
      signal: controller.signal,
    });

    clearTimeout(timeout);

    if (res.status === 404) return { status: 404 };
    if (res.status === 409) return { status: 409 };
    if (!res.ok) return { status: res.status };

    const data = await res.json();
    return { status: 200, data };
  } catch (err) {
    clearTimeout(timeout);
    if (err.name === "AbortError") {
      return { status: 0, error: "timeout" };
    }
    return { status: 0, error: err };
  }
}

function ErrorCard({ id, title, children }) {
  return (
    <div className="cs">
      <div className="cs-wrap cs-section">
        <div className="cs-card" role="alert">
          <h2 className="cs-h2">{title}</h2>
          <p className="cs-lead">{children}</p>
          <div className="cs-btns">
            <a className="cs-btn is-primary" href={`/studi-kasus/${id}`}>
              Muat Ulang
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}

export default async function CaseStudyPage({ params }) {
  const { id } = await params;
  const result = await getCaseStudy(id, process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000");

  // 404 - not found
  if (result.status === 404) {
    // TODO: hapus pengecualian ini setelah preset asli dibuat lewat make_preset
    if (id === "mbg-tepat-sasaran") {
      return (
        <CaseStudyView
          data={mbgStatic}
          banner="Menampilkan data contoh: studi kasus ini belum dibuat di server."
        />
      );
    }
    notFound();
  }

  // 409 - degraded quality
  if (result.status === 409) {
    return (
      <ErrorCard id={id} title="Studi kasus tidak ditampilkan">
        Studi kasus ini tidak ditampilkan karena kualitas datanya rendah (terlalu banyak
        giliran memakai nilai cadangan).
      </ErrorCard>
    );
  }

  // Fetch threw (network/timeout) or server error: static fallback for the MBG case only
  if (result.status === 0 || result.status >= 500) {
    if (id === "mbg-tepat-sasaran") {
      return (
        <CaseStudyView
          data={mbgStatic}
          banner="Menampilkan data contoh: server tidak terjangkau. Tidak dapat menghubungi server simulasi, jadi yang tampil adalah salinan statis data MBG."
        />
      );
    }
    return (
      <ErrorCard id={id} title="Gagal memuat studi kasus">
        Tidak dapat menghubungi server. Silakan coba lagi nanti.
      </ErrorCard>
    );
  }

  // Other non-ok status (400, 401, 403, 429, ...): error card, never the fallback data
  if (result.status !== 200) {
    return (
      <ErrorCard id={id} title="Gagal memuat studi kasus">
        Server menolak permintaan (status {result.status}). Silakan coba lagi nanti.
      </ErrorCard>
    );
  }

  // Success - render the case study
  return <CaseStudyView data={result.data} />;
}
