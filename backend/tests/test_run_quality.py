"""Test penjaga kualitas run (ambang fallback)."""

from backend.simulation import _hitung_kualitas


def _ronde(fallback_n: int, total: int = 10) -> list[dict]:
    agen = [{"fallback": i < fallback_n} for i in range(total)]
    return [{"ronde": 1, "agen": agen}]


class TestAmbangKualitas:
    def test_rate_010_ok(self):
        hasil = _hitung_kualitas(_ronde(1))
        assert hasil == {
            "fallback_count": 1,
            "total_giliran": 10,
            "fallback_rate": 0.1,
            "status": "ok",
        }

    def test_rate_020_warning(self):
        hasil = _hitung_kualitas(_ronde(2))
        assert hasil["status"] == "warning"
        assert hasil["fallback_rate"] == 0.2

    def test_rate_030_degraded(self):
        hasil = _hitung_kualitas(_ronde(3))
        assert hasil["status"] == "degraded"
        assert hasil["fallback_rate"] == 0.3

    def test_rate_050_degraded(self):
        assert _hitung_kualitas(_ronde(5))["status"] == "degraded"

    def test_tanpa_giliran_ok(self):
        assert _hitung_kualitas([]) == {
            "fallback_count": 0,
            "total_giliran": 0,
            "fallback_rate": 0.0,
            "status": "ok",
        }
