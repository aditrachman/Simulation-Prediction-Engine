# backend/services/agent_turn.py
# Satu giliran agen = satu call LLM yang mengembalikan JSON terstruktur.
#
# Kontrak output:
#   {"stance": "menolak|netral|mendukung", "score": -1..1,
#    "alasan": "<=35 kata", "sesuai_topik": bool,
#    "berubah_karena": "string" | null}
#
# Aturan:
#   - stance dan score diambil langsung dari JSON, tidak diklasifikasi ulang.
#   - JSON invalid / sesuai_topik false / berubah tanpa alasan -> retry 1x.
#   - Masih gagal -> fallback ke stance ronde sebelumnya, "fallback": true.

import json
import re

STANCES = ("menolak", "netral", "mendukung")

TURN_MAX_TOKENS = 220
MAKS_KATA_ALASAN = 35

_FALLBACK_ALASAN = "(agen tidak memberikan output valid)"

TURN_SYSTEM_SUFFIX = (
    "\n\nFORMAT OUTPUT (WAJIB): balas HANYA satu objek JSON, tanpa teks lain, "
    "tanpa markdown, tanpa backtick.\n"
    '{"stance":"menolak|netral|mendukung","score":<-1..1>,'
    '"alasan":"<=35 kata","sesuai_topik":true|false,'
    '"berubah_karena":"alasan perubahan atau null"}\n'
    "- stance: posisimu terhadap topik.\n"
    "- score: -1 (menolak kuat) sampai 1 (mendukung kuat).\n"
    f"- alasan: argumen utamamu, maksimal {MAKS_KATA_ALASAN} kata, tetap pakai gaya bicaramu.\n"
    "- sesuai_topik: false hanya kalau kamu memang tidak bisa membahas topik ini.\n"
    "- berubah_karena: wajib diisi kalau posisimu berbeda dari ronde sebelumnya; "
    "null kalau tidak berubah."
)

TURN_RETRY_SUFFIX = (
    "\n\nOutput sebelumnya tidak valid atau tidak lengkap. "
    "Balas ulang HANYA satu objek JSON valid sesuai format di atas."
)

TURN_RETRY_ALASAN_SUFFIX = (
    "\n\nPosisimu berbeda dari ronde sebelumnya. Isi berubah_karena "
    "dengan pemicu konkret perubahan itu."
)


def _potong_kata(teks: str, maks: int = MAKS_KATA_ALASAN) -> str:
    kata = teks.split()
    if len(kata) <= maks:
        return " ".join(kata)
    return " ".join(kata[:maks])


def _ekstrak_objek(raw: str) -> str | None:
    """Ambil objek JSON pertama dari teks (model kadang menambah kalimat pembuka)."""
    if not raw:
        return None
    teks = re.sub(r"```(?:json)?|```", "", raw).strip()
    awal = teks.find("{")
    if awal < 0:
        return None
    # Coba dari kurung kurawal pertama sampai akhir; kalau gagal, cari penutup terakhir.
    for kandidat in (teks[awal:], teks[awal:teks.rfind("}") + 1]):
        if not kandidat:
            continue
        try:
            json.loads(kandidat)
            return kandidat
        except json.JSONDecodeError:
            continue
    return None


def _score_dari_stance(stance: str) -> float:
    return {"mendukung": 0.6, "netral": 0.0, "menolak": -0.6}[stance]


def parse_turn(raw: str) -> dict | None:
    """
    Parse output agen jadi dict tervalidasi. Return None kalau tidak bisa dipakai.

    Field yang hilang diisi default; stance wajib valid karena itu inti kontrak.
    """
    kandidat = _ekstrak_objek(raw)
    if kandidat is None:
        return None
    try:
        data = json.loads(kandidat)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None

    stance = str(data.get("stance", "")).strip().lower()
    if stance not in STANCES:
        return None

    try:
        score = float(data.get("score"))
    except (TypeError, ValueError):
        score = _score_dari_stance(stance)
    score = max(-1.0, min(1.0, round(score, 2)))

    alasan = _potong_kata(str(data.get("alasan") or "").strip())
    if not alasan:
        return None

    sesuai_topik = data.get("sesuai_topik", True)
    if not isinstance(sesuai_topik, bool):
        sesuai_topik = str(sesuai_topik).strip().lower() not in {"false", "0", "tidak", "no"}

    berubah = data.get("berubah_karena")
    if berubah is not None:
        berubah = _potong_kata(str(berubah).strip(), maks=25) or None

    return {
        "stance": stance,
        "score": score,
        "alasan": alasan,
        "sesuai_topik": sesuai_topik,
        "berubah_karena": berubah,
        "fallback": False,
    }


def alasan_retry(turn: dict | None, prev_stance: str | None) -> str | None:
    """Alasan giliran perlu diulang. None = output sudah layak."""
    if turn is None:
        return "invalid_json"
    if not turn["sesuai_topik"]:
        return "tidak_sesuai_topik"
    if prev_stance and turn["stance"] != prev_stance and not turn["berubah_karena"]:
        return "berubah_tanpa_alasan"
    return None


def turn_fallback(prev_stance: str | None, prev_score: float | None = None) -> dict:
    """Giliran gagal total: pertahankan posisi ronde sebelumnya."""
    stance = prev_stance if prev_stance in STANCES else "netral"
    if prev_score is not None:
        score = max(-1.0, min(1.0, float(prev_score)))
    else:
        score = _score_dari_stance(stance)
    return {
        "stance": stance,
        "score": score,
        "alasan": _FALLBACK_ALASAN,
        "sesuai_topik": None,
        "berubah_karena": None,
        "fallback": True,
    }


def execute_turn(
    llm,
    system_p: str,
    user_p: str,
    prev_stance: str | None = None,
    prev_score: float | None = None,
) -> dict:
    """
    Jalankan satu giliran agen: 1 call LLM, retry maksimal 1x.

    llm dipanggil sebagai llm(system_prompt, user_prompt) -> str.
    """
    system_p = system_p + TURN_SYSTEM_SUFFIX
    turn = parse_turn(llm(system_p, user_p))
    alasan = alasan_retry(turn, prev_stance)

    if alasan is None:
        return turn

    retry_p = user_p + TURN_RETRY_SUFFIX
    if alasan == "berubah_tanpa_alasan":
        retry_p += TURN_RETRY_ALASAN_SUFFIX
    retry_turn = parse_turn(llm(system_p, retry_p))

    # Pakai hasil retry kalau bisa diparse, kalau tidak pakai hasil pertama (kalau ada).
    if retry_turn is not None:
        turn = retry_turn
    elif turn is None:
        return turn_fallback(prev_stance, prev_score)

    return turn
