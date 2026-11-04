"""Test FASE 3c: pemicu diisi panggilan kecil, stance percobaan pertama dikunci."""

import json

from backend.services.agent_turn import execute_turn


def _turn(stance="netral", score=0.0, alasan="Distribusi belum jelas.", berubah=""):
    return json.dumps(
        {
            "stance": stance,
            "score": score,
            "alasan": alasan,
            "sesuai_topik": True,
            "berubah_karena": berubah,
        }
    )


def _llm(teks: list[str]):
    calls: list[tuple[str, str]] = []

    def _call(system_p, user_p, **kwargs):
        calls.append((system_p, user_p))
        idx = min(len(calls) - 1, len(teks) - 1)
        return teks[idx]

    return _call, calls


class TestPemicuTidakMenggeserStance:
    def test_stance_score_alasan_percobaan_pertama_dikunci(self):
        llm, calls = _llm([
            _turn("netral", 0.0, "Program masih abu-abu, perlu data."),
            json.dumps({"berubah_karena": "Data kepuasan muncul di ringkasan."}),
        ])
        hasil = execute_turn(llm, "sistem", "pertanyaan", prev_stance="menolak")

        assert hasil["stance"] == "netral"
        assert hasil["score"] == 0.0
        assert hasil["alasan"] == "Program masih abu-abu, perlu data."
        assert hasil["berubah_karena"] == "Data kepuasan muncul di ringkasan."
        assert hasil["perubahan_tanpa_alasan"] is False
        # 2 panggilan: giliran + pengisi pemicu (bukan regenerate penuh).
        assert len(calls) == 2

    def test_panggilan_pengisi_memuat_stance_dan_pemicu(self):
        llm, calls = _llm([
            _turn("mendukung", 0.5),
            json.dumps({"berubah_karena": "Bukti distribusi membaik."}),
        ])
        execute_turn(llm, "sistem", "pertanyaan", prev_stance="menolak")

        assert "Stance-mu di ronde ini: mendukung" in calls[1][1]
        assert "Tulis HANYA pemicu perubahan" in calls[1][1]
        assert "Posisi sebelumnya: menolak" in calls[1][1]

    def test_pengisi_gagal_menandai_perubahan_tanpa_alasan(self):
        llm, calls = _llm([
            _turn("netral", 0.0),
            "bukan json {",  # parse_pemicu menolak teks berisi '{'
        ])
        hasil = execute_turn(llm, "sistem", "pertanyaan", prev_stance="menolak")

        assert len(calls) == 2
        assert hasil["stance"] == "netral"
        assert hasil["berubah_karena"] is None
        assert hasil["perubahan_tanpa_alasan"] is True

    def test_pengisi_kosong_menandai_perubahan_tanpa_alasan(self):
        llm, _ = _llm([_turn("netral", 0.0), json.dumps({"berubah_karena": "  "})])
        hasil = execute_turn(llm, "sistem", "pertanyaan", prev_stance="menolak")

        assert hasil["perubahan_tanpa_alasan"] is True
        assert hasil["berubah_karena"] is None

    def test_pengisi_error_tidak_membuat_giliran_gagal(self):
        def llm(system_p, user_p, **kwargs):
            if "Tulis HANYA pemicu" in user_p:
                raise RuntimeError("timeout")
            return _turn("mendukung", 0.4)

        hasil = execute_turn(llm, "sistem", "pertanyaan", prev_stance="menolak")
        assert hasil["stance"] == "mendukung"
        assert hasil["fallback"] is False
        assert hasil["perubahan_tanpa_alasan"] is True

    def test_pemicu_terpisah_dipakai_untuk_pengisi(self):
        teks_utama, calls_utama = _llm([_turn("netral", 0.0)])
        teks_pemicu, calls_pemicu = _llm([json.dumps({"berubah_karena": "Audit baru."})])

        hasil = execute_turn(
            teks_utama, "sistem", "pertanyaan",
            prev_stance="menolak", llm_pemicu=teks_pemicu,
        )
        assert len(calls_utama) == 1
        assert len(calls_pemicu) == 1
        assert hasil["berubah_karena"] == "Audit baru."


class TestRetryLainTidakBerubah:
    def test_json_invalid_tetap_retry_penuh(self):
        llm, calls = _llm([
            "bukan json",
            _turn("menolak", -0.5, "Data belum ada."),
        ])
        hasil = execute_turn(llm, "sistem", "pertanyaan", prev_stance="mendukung")

        assert len(calls) == 2
        assert "Output sebelumnya tidak valid" in calls[1][1]
        assert hasil["stance"] == "menolak"
        assert hasil["fallback"] is False

    def test_tidak_sesuai_topik_tetap_retry_penuh(self):
        tidak_sesuai = json.dumps({
            "stance": "netral", "score": 0.0, "alasan": "Tidak relevan.",
            "sesuai_topik": False, "berubah_karena": "",
        })
        llm, calls = _llm([tidak_sesuai, _turn("netral", 0.0, "Sekarang relevan.")])
        hasil = execute_turn(llm, "sistem", "pertanyaan")

        assert len(calls) == 2
        assert hasil["alasan"] == "Sekarang relevan."
        assert hasil["fallback"] is False
