import { notFound } from "next/navigation";
import Link from "next/link";
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

export default async function CaseStudyPage({ params }) {
  const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
  const { id } = await params;
  const result = await getCaseStudy(id, process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000");

  // 404 - not found
  if (result.status === 404) {
    notFound();
  }

  // 409 - degraded quality
  if (result.status === 409) {
    return (
      <section className="mx-auto max-w-4xl px-4 py-16">
        <div className="cs-card" role="alert">
          <div className="flex items-start gap-3">
            <div className="shrink-0 text-3xl">⚠️</div>
            <div>
              <h2 className="display-sm text-[#c64545] mb-2">Studi kasus tidak ditampilkan</h2>
              <p className="text-base leading-relaxed text-[#3d3d3a]">
                Studi kasus ini tidak ditampilkan karena kualitas datanya rendah (terlalu banyak
                giliran memakai nilai cadangan).
              </p>
            </div>
          </div>
        </div>
      </section>
    );
  }

  // Network error / timeout / 5xx / other errors
  if (result.status !== 200) {
    // Fallback static mbg-tepat-sasaran.json ONLY for network error, timeout, or 5xx,
    // and ONLY for id "mbg-tepat-sasaran"
    if (id === "mbg-tepat-sasaran") {
      return (
        <section className="mx-auto max-w-4xl px-4 py-16">
          <div className="mb-6 p-4 rounded-[12px] bg-[#fffbeb] border border-[#fcd34d]/30">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-2xl">⚠️</span>
              <strong className="text-[#92400e]">Menampilkan data contoh: server tidak terjangkau.</strong>
            </div>
            <p className="text-sm text-[#92400e]">
              Tidak dapat menghubungi server simulasi. Menampilkan salinan statis data MBG.
            </p>
          </div>
          <CaseStudyView data={mbgStatic} />
        </section>
      );
    }

    // Generic error for other IDs
    return (
      <section className="mx-auto max-w-4xl px-4 py-16">
        <div className="card text-center" style={{ maxWidth: "480px", margin: "0 auto" }}>
          <div className="text-4xl mb-4">⚠️</div>
          <h2 className="display-sm text-[#c64545] mb-3">Gagal memuat studi kasus</h2>
          <p className="text-[#6c6a64] mb-6">
            Tidak dapat menghubungi server. Silakan coba lagi nanti.
          </p>
          <Link
            href={`/studi-kasus/${id}`}
            className="btn-primary"
          >
            Muat Ulang
          </Link>
        </div>
      </section>
    );
  }

  // Success - render the case study
  return (
    <section className="mx-auto max-w-4xl px-4 py-16">
      <CaseStudyView data={result.data} />
    </section>
  );
}