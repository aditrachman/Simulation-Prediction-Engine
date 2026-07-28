#!/usr/bin/env python3
"""
Validasi sentimen fix — ngecek apakah positif udah kedeteksi.
Run: python3 test_sentimen_validasi.py
"""

import sys
sys.path.insert(0, '/home/aditrachman/Documents/COLLAGE/SMT 4/Rekayasa perangkat lunak/Simulation-Prediction-Engine')

from backend import sentiment_ml, sentiment

TESTS = [
    # (teks, topik, expected_label, catatan)
    # --- Positif eksplisit ---
    ("saya setuju dengan program MBG", "MBG", "positif", "positif eksplisit"),
    ("saya mendukung kebijakan ini", "pendidikan", "positif", "positif dukung"),
    ("program ini sangat membantu masyarakat", "MBG", "positif", "positif membantu"),

    # --- Positif datar (yang sebelumnya miss) ---
    ("program MBG sangat tepat ke masyarakat", "MBG", "positif", "⭐ positif datar — yg tadinya netral"),
    ("kebijakan ini tepat sasaran", "ekonomi", "positif", "positif datar tepat sasaran"),
    ("program ini bermanfaat untuk rakyat", "kesehatan", "positif", "positif bermanfaat"),

    # --- Negatif eksplisit ---
    ("saya menolak kebijakan ini", "MBG", "negatif", "negatif tolak"),
    ("program ini merugikan rakyat", "MBG", "negatif", "negatif rugi"),

    # --- Negatif implisit ---
    ("apakah program ini benar-benar efektif?", "MBG", "negatif", "negatif implisit retoris"),
    ("belum terbukti efektif", "MBG", "negatif", "negatif implisit belum"),
    ("kebijakan ini perlu ditinjau ulang", "pajak", "negatif", "negatif implisit perlu ditinjau"),

    # --- Netral ---
    ("saya perlu data lebih lanjut", "ekonomi", "netral", "netral butuh data"),
    ("ada sisi positif dan negatif", "MBG", "netral", "netral dua sisi"),
]

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"


def test_ml():
    print(f"\n{CYAN}{'='*60}{RESET}")
    print(f"{BOLD}🧪 TEST ML PREDICT (sentiment_ml.py){RESET}")
    print(f"{CYAN}{'='*60}{RESET}")

    ok = 0
    fail = 0
    for teks, topik, expected, catatan in TESTS:
        result = sentiment_ml.predict(teks)
        if result is None:
            print(f"  {RED}✗{RESET} {catatan}: model None")
            fail += 1
            continue
        label = result["label"]
        conf = result["confidence"]
        skor = result["skor"]
        marker = "✓" if label == expected else "✗"
        color = GREEN if label == expected else RED
        print(f"  {color}{marker}{RESET} [{label:8} | conf={conf:.2f} | skor={skor:+.2f}] {teks[:60]:60s}  ({catatan})")
        if label == expected:
            ok += 1
        else:
            fail += 1

    print(f"\n  {BOLD}ML: {ok}/{len(TESTS)} ok, {fail} fail{RESET}")

    # Verifikasi khusus: positif datar
    print(f"\n  {YELLOW}🔍 Cek khusus — positive datar harus positif:{RESET}")
    for teks, topik, expected, catatan in TESTS:
        if "positif datar" in catatan or "⭐" in catatan:
            result = sentiment_ml.predict(teks)
            if result:
                label = result["label"]
                conf = result["confidence"]
                skor = result["skor"]
                marker = "✓" if label == "positif" else "✗"
                color = GREEN if label == "positif" else RED
                print(f"    {color}{marker}{RESET} [{label:8} | conf={conf:.2f} | skor={skor:+.2f}] {teks[:60]}")

    return ok, fail


def test_full():
    print(f"\n{CYAN}{'='*60}{RESET}")
    print(f"{BOLD}🧪 TEST FULL PIPELINE (sentiment.py — mode ml){RESET}")
    print(f"{CYAN}{'='*60}{RESET}")

    ok = 0
    fail = 0
    for teks, topik, expected, catatan in TESTS:
        try:
            result = sentiment.score_sentiment(teks, topik, sentiment_mode="ml")
        except Exception as e:
            print(f"  {RED}✗{RESET} {catatan}: error {e}")
            fail += 1
            continue
        label = result["label"]
        skor = result["skor"]
        marker = "✓" if label == expected else "✗"
        color = GREEN if label == expected else RED
        print(f"  {color}{marker}{RESET} [{label:8} | skor={skor:+.2f}] {teks[:60]:60s}  ({catatan})")
        if label == expected:
            ok += 1
        else:
            fail += 1

    print(f"\n  {BOLD}Full pipeline: {ok}/{len(TESTS)} ok, {fail} fail{RESET}")
    return ok, fail


if __name__ == "__main__":
    ml_ok, ml_fail = test_ml()
    full_ok, full_fail = test_full()

    print(f"\n{GREEN}{'='*60}{RESET}")
    print(f"{BOLD}📊 SUMMARY{RESET}")
    print(f"  ML predict:        {GREEN if ml_fail == 0 else RED}{ml_ok}/{ml_ok+ml_fail}{RESET}")
    print(f"  Full pipeline:     {GREEN if full_fail == 0 else RED}{full_ok}/{full_ok+full_fail}{RESET}")
    print(f"{GREEN}{'='*60}{RESET}")
