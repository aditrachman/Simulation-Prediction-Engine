# backend/core/memory_store.py
# Phase 5: Structured Memory — memori agen yang tidak hanya list teks.
# Tracks: stance history, argument uniqueness, relationships antar agen.
# Memory summary tanpa LLM — pure rule-based.

from __future__ import annotations

import re
from typing import Optional


def _extract_key_terms(teks: str, max_terms: int = 5) -> list[str]:
    """
    Ekstrak istilah kunci dari teks pendapat (tanpa LLM).
    Strategi: ambil noun phrases, kata setelah "karena/sebab/akibat", dan kata unik.
    """
    if not teks:
        return []
    teks_lower = teks.lower()
    terms = set()

    # Kata setelah kata kunci kausal
    for marker in ["karena ", "sebab ", "akibat ", "sehingga ", "dampak "]:
        for m in re.finditer(rf"{marker}(\w+(?:\s+\w+)?)", teks_lower):
            terms.add(m.group(1).strip())

    # Kata benda/frasa 2-kata yang mungkin jadi topik
    bigrams = re.findall(r"\b(\w+\s+\w+)\b", teks_lower)
    for bg in bigrams:
        if any(k in bg for k in ["anggaran", "kebijakan", "data", "studi", "survei", "riset",
                                   "masyarakat", "pemerintah", "ekonomi", "sosial", "dampak",
                                   "solusi", "masalah", "regulasi", "program", "dana", "hasil"]):
            terms.add(bg)

    # Kata unik >= 5 huruf (hindari kata umum)
    for w in set(re.findall(r"\b[a-z]{5,}\b", teks_lower)):
        if w not in {"tetapi", "namuntetapi", "sebagai", "adalah", "dengan", "karena",
                     "sedangkan", "sementara", "demikian", "sehingga", "mereka",
                     "dirinya", "sendiri", "semakin", "seluruh", "sangat", "tentang",
                     "melalui", "dalam", "untuk", "secara", "antara", "setiap",
                     "sudah", "belum", "masih", "dapat", "harus", "akan", "telah",
                     "banyak", "semua", "kepada", "bagi", "tanpa", "serta",
                     "maupun", "ataupun", "kendati", "kecuali"}:
            terms.add(w)

    return list(terms)[:max_terms]


def _compute_argument_similarity(arg_a: str, arg_b: str) -> float:
    """
    Hitung kemiripan antara dua argumen secara rule-based.
    Returns 0.0 (beda total) sampai 1.0 (identik).
    """
    if not arg_a or not arg_b:
        return 0.0
    a_terms = set(_extract_key_terms(arg_a, max_terms=10))
    b_terms = set(_extract_key_terms(arg_b, max_terms=10))
    if not a_terms or not b_terms:
        return 0.0
    intersection = a_terms & b_terms
    union = a_terms | b_terms
    return len(intersection) / len(union)


# ---------------------------------------------------------------------------
# ArgumentMemory — lacak argumen unik setiap agen
# ---------------------------------------------------------------------------

class ArgumentMemory:
    """Lacak argumen unik yang sudah disampaikan agen."""

    def __init__(self):
        self._entries: list[dict] = []  # {"ronde": int, "teks": str, "terms": [str]}

    def add(self, ronde: int, pendapat: str) -> bool:
        """
        Tambah argumen baru. Returns True jika argumen ini UNIK (belum pernah mirip).
        Returns False jika terlalu mirip dengan argumen sebelumnya (repetisi).
        """
        terms = _extract_key_terms(pendapat)
        if not terms:
            return True  # Gagal ekstrak terms, anggap unik

        # Cek kemiripan dengan argumen sebelumnya
        for prev in self._entries:
            similarity = _compute_argument_similarity(pendapat, prev.get("teks", ""))
            if similarity > 0.4:
                return False  # Terlalu mirip → repetisi

        self._entries.append({"ronde": ronde, "teks": pendapat, "terms": terms})
        return True

    @property
    def unique_arguments(self) -> list[str]:
        """Daftar argumen unik (teks lengkap)."""
        return [e["teks"] for e in self._entries]

    @property
    def unique_terms(self) -> set[str]:
        """Semua istilah unik yang pernah disebut."""
        terms: set[str] = set()
        for e in self._entries:
            terms.update(e.get("terms", []))
        return terms

    def get_fresh_argument_prompt(self, max_args: int = 2) -> str:
        """
        Bangun prompt untuk mendorong agen memberikan argumen baru.
        """
        if not self._entries:
            return ""
        used_terms = self.unique_terms
        if not used_terms:
            return ""
        return (
            f"Topik yang udah kamu bahas: {', '.join(list(used_terms)[:5])}. "
            f"Cari sudut pandang BARU — jangan ulangin topik yang sama."
        )

    def count_repetitions(self) -> int:
        """Hitung ulang berapa kali argumen mirip muncul."""
        if len(self._entries) < 2:
            return 0
        reps = 0
        for i in range(1, len(self._entries)):
            sim = _compute_argument_similarity(
                self._entries[i]["teks"], self._entries[i - 1]["teks"]
            )
            if sim > 0.4:
                reps += 1
        return reps


# ---------------------------------------------------------------------------
# RelationshipMemory — lacak hubungan antar agen
# ---------------------------------------------------------------------------

class RelationshipMemory:
    """Lacak hubungan/trust antar agen berdasarkan sentimen alignment."""

    def __init__(self):
        # {nama_agen: [{"ronde": int, "alignment": float, "sentimen_self": float, "sentimen_other": float}, ...]}
        self._relations: dict[str, list[dict]] = {}

    def update(
        self,
        ronde: int,
        target_nama: str,
        sentimen_self: float,
        sentimen_other: float,
    ) -> None:
        """
        Update hubungan dengan target_nama berdasarkan perbandingan sentimen.
        alignment positif = setuju, negatif = tidak setuju.
        """
        alignment = 0.0
        if sentimen_self != 0.0 and sentimen_other != 0.0:
            # Semakin dekat skor, semakin setuju
            difference = abs(sentimen_self - sentimen_other)
            alignment = 1.0 - min(difference, 1.0)
            # Arah: sama-sama positif atau sama-sama negatif
            if (sentimen_self > 0) == (sentimen_other > 0):
                alignment = alignment  # Setuju
            else:
                alignment = -alignment  # Tidak setuju

        if target_nama not in self._relations:
            self._relations[target_nama] = []
        self._relations[target_nama].append({
            "ronde": ronde,
            "alignment": round(alignment, 2),
            "sentimen_self": round(sentimen_self, 2),
            "sentimen_other": round(sentimen_other, 2),
        })

    def get_trust_summary(self) -> str:
        """
        Ringkasan hubungan tanpa LLM.
        """
        if not self._relations:
            return ""
        allies = []
        rivals = []
        for target, entries in self._relations.items():
            if not entries:
                continue
            avg_align = sum(e["alignment"] for e in entries) / len(entries)
            if avg_align > 0.2:
                allies.append(target)
            elif avg_align < -0.2:
                rivals.append(target)

        parts = []
        if allies:
            parts.append(f"Kamu sepemikiran dengan: {', '.join(allies)}.")
        if rivals:
            parts.append(f"Kamu beda pendapat sama: {', '.join(rivals)}.")
        return " ".join(parts)


# ---------------------------------------------------------------------------
# AgentMemoryStore — gabungan semua track memori
# ---------------------------------------------------------------------------

class AgentMemoryStore:
    """
    Structured memory untuk satu agen.
    Digunakan bersama dengan dict memori lama (backward compatible).
    """

    def __init__(self, agent_nama: str):
        self.agent_nama = agent_nama
        self.arguments = ArgumentMemory()
        self.relationships = RelationshipMemory()

    def add_round(
        self,
        ronde: int,
        pendapat: str,
        sentimen: dict,
        all_opinions: list[dict] | None = None,
    ) -> dict:
        """
        Proses satu ronde: update argument + relationship.
        
        Args:
            ronde: Nomor ronde
            pendapat: Teks pendapat agen
            sentimen: {"label": ..., "skor": ...}
            all_opinions: Semua pendapat di ronde ini (untuk relationship tracking)
        
        Returns:
            {"is_fresh": bool, "repetition_count": int}
        """
        is_fresh = self.arguments.add(ronde, pendapat)

        # Update relationship dengan agen lain
        if all_opinions:
            self_skor = sentimen.get("skor", 0.0) or 0.0
            for other in all_opinions:
                other_nama = other.get("nama", "")
                if other_nama == self.agent_nama:
                    continue
                other_skor = other.get("sentimen", {}).get("skor", 0.0) or 0.0
                self.relationships.update(
                    ronde=ronde,
                    target_nama=other_nama,
                    sentimen_self=self_skor,
                    sentimen_other=other_skor,
                )

        return {
            "is_fresh": is_fresh,
            "repetition_count": self.arguments.count_repetitions(),
        }

    def build_context(self, memori: list[dict]) -> str:
        """
        Bangun konteks prompt untuk agen tanpa LLM.
        Mirip dengan build_memory_context() di memory.py tapi tanpa summarize LLM.
        """
        if not memori:
            return ""

        parts = []

        # Stance context dari memori terakhir
        terakhir = memori[-1]
        skor = terakhir.get("skor")
        label = self._stance_label(skor)
        skor_str = f" (skor {skor:.2f})" if skor is not None else ""

        parts.append(f"Posisi kamu sekarang: {label}{skor_str}")

        # Jika ada argumen fresh, sebutkan
        if self.arguments.unique_arguments:
            latest_arg = self.arguments.unique_arguments[-1]
            parts.append(f"Terakhir kamu bilang: \"{latest_arg[:80]}\"")

        # Repetition warning
        reps = self.arguments.count_repetitions()
        if reps >= 1:
            parts.append(
                "Kamu udah ngomong ini beberapa kali. Coba sudut pandang atau data BARU."
            )

        # Trust summary
        trust_str = self.relationships.get_trust_summary()
        if trust_str:
            parts.append(trust_str)

        return " ".join(parts)

    @staticmethod
    def _stance_label(skor: float | None) -> str:
        if skor is None:
            return "NETRAL"
        if skor > 0.2:
            return "MENDUKUNG"
        if skor < -0.2:
            return "MENOLAK"
        return "NETRAL"
