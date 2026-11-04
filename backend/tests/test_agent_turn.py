"""Test jalur giliran agen JSON (FASE 1)."""

import json

import pytest

from backend.services import agent_turn
from backend.services.agent_turn import (
    alasan_retry,
    execute_turn,
    parse_turn,
    turn_fallback,
)


def _llm(teks: str):
    """Bikin fake llm yang selalu mengembalikan teks tertentu + hitung call."""
    calls = []

    def _call(system_p, user_p):
        calls.append((system_p, user_p))
        return teks if isinstance(teks, str) else teks[min(len(calls), len(teks)) - 1]

    return _call, calls


def _turn(**kwargs):
    data = {
        "stance": "menolak",
        "score": -0.7,
        "alasan": "Data distribusi belum jelas, jadi klaim tepat sasaran belum bisa dipercaya.",
        "sesuai_topik": True,
        "berubah_karena": None,
    }
    data.update(kwargs)
    return json.dumps(data)


class TestParseTurn:
    def test_json_valid(self):
        hasil = parse_turn(_turn())
        assert hasil["stance"] == "menolak"
        assert hasil["score"] == -0.7
        assert hasil["fallback"] is False
        assert hasil["sesuai_topik"] is True
        assert hasil["berubah_karena"] is None

    def test_json_dengan_fence_dan_kalimat_pembuka(self):
        mentah = "Ini jawabanku:\n```json\n" + _turn(stance="mendukung", score=0.5) + "\n```"
        hasil = parse_turn(mentah)
        assert hasil["stance"] == "mendukung"
        assert hasil["score"] == 0.5

    @pytest.mark.parametrize(
        "teks",
        [
            "bukan json sama sekali",
            '{"stance":"ragu","score":0,"alasan":"x","sesuai_topik":true}',
            '{"score":0.2,"alasan":"tanpa stance","sesuai_topik":true}',
            '{"stance":"netral","score":0.2,"alasan":"","sesuai_topik":true}',
            '{"stance":"netral","score":',
        ],
    )
    def test_menolak_json_rusak_atau_tidak_lengkap(self, teks):
        assert parse_turn(teks) is None

    def test_score_di_clamp_dan_alasan_dipotong(self):
        panjang = " ".join(f"kata{i}" for i in range(60))
        hasil = parse_turn(_turn(score=-3.5, alasan=panjang))
        assert hasil["score"] == -1.0
        assert len(hasil["alasan"].split()) == agent_turn.MAKS_KATA_ALASAN


class TestValidasiPerubahan:
    def test_tanpa_perubahan_stance_tidak_butuh_alasan(self):
        turn = parse_turn(_turn(stance="menolak", berubah_karena=None))
        assert alasan_retry(turn, prev_stance="menolak") is None

    def test_perubahan_stance_tanpa_alasan_butuh_retry(self):
        turn = parse_turn(_turn(stance="netral", berubah_karena=None))
        assert alasan_retry(turn, prev_stance="menolak") == "berubah_tanpa_alasan"

    def test_perubahan_stance_dengan_alasan_lolos(self):
        turn = parse_turn(_turn(stance="netral", berubah_karena="Data gizi resmi baru dirilis."))
        assert alasan_retry(turn, prev_stance="menolak") is None

    def test_sesuai_topik_false_butuh_retry(self):
        turn = parse_turn(_turn(sesuai_topik=False))
        assert alasan_retry(turn, prev_stance=None) == "tidak_sesuai_topik"

    def test_json_invalid_butuh_retry(self):
        assert alasan_retry(None, prev_stance="menolak") == "invalid_json"


class TestExecuteTurn:
    def test_kasus_normal_satu_call(self):
        llm, calls = _llm(_turn())
        hasil = execute_turn(llm, "sistem", "pertanyaan", prev_stance="menolak")
        assert len(calls) == 1
        assert hasil["fallback"] is False
        assert hasil["stance"] == "menolak"
        assert agent_turn.TURN_SYSTEM_SUFFIX in calls[0][0]

    def test_json_invalid_retry_lalu_fallback(self):
        teks = ["bukan json", "tetap bukan json"]
        llm, calls = _llm(teks)
        hasil = execute_turn(
            llm, "sistem", "pertanyaan", prev_stance="menolak", prev_score=-0.4
        )
        assert len(calls) == 2
        assert hasil["fallback"] is True
        assert hasil["stance"] == "menolak"
        assert hasil["score"] == -0.4

    def test_fallback_tanpa_stance_sebelumnya_jadi_netral(self):
        hasil = turn_fallback(None)
        assert hasil["stance"] == "netral"
        assert hasil["score"] == 0.0
        assert hasil["fallback"] is True

    def test_retry_berhasil_diperbaiki(self):
        teks = ["bukan json", _turn(stance="mendukung", score=0.6)]
        llm, calls = _llm(teks)
        hasil = execute_turn(llm, "sistem", "pertanyaan", prev_stance="mendukung")
        assert len(calls) == 2
        assert hasil["stance"] == "mendukung"
        assert hasil["fallback"] is False

    def test_berubah_tanpa_alasan_retry_dengan_instruksi(self):
        teks = [
            _turn(stance="netral", berubah_karena=None),
            _turn(stance="netral", berubah_karena="Angka kepuasan tidak menunjukkan sasaran."),
        ]
        llm, calls = _llm(teks)
        hasil = execute_turn(llm, "sistem", "pertanyaan", prev_stance="menolak")
        assert len(calls) == 2
        assert "Posisimu berbeda dari ronde sebelumnya" in calls[1][1]
        assert hasil["berubah_karena"] == "Angka kepuasan tidak menunjukkan sasaran."

    def test_tetap_tanpa_alasan_setelah_retry_tetap_diterima(self):
        teks = [
            _turn(stance="netral", berubah_karena=None),
            _turn(stance="netral", berubah_karena=None),
        ]
        llm, calls = _llm(teks)
        hasil = execute_turn(llm, "sistem", "pertanyaan", prev_stance="menolak")
        assert len(calls) == 2
        assert hasil["stance"] == "netral"
        assert hasil["berubah_karena"] is None
        assert hasil["fallback"] is False
