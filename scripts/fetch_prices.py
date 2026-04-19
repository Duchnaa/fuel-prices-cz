#!/usr/bin/env python3
"""
fetch_prices.py — Stahuje maximální přípustné ceny benzinu a nafty
z webu Ministerstva financí ČR pomocí Playwright.

Zdroj:
  https://mf.gov.cz/cs/kontrola-a-regulace/cenova-regulace-a-kontrola/
  maximalni-pripustne-ceny-benzinu-a-nafty

Logika platnosti cen:
  - Po–Čt: ceny vydané dnes platí pro ZÍTŘEK
  - Pá:    ceny vydané v pátek platí pro pátek, sobotu, neděli i pondělí
"""

import json
import os
import re
import sys
from datetime import date, datetime, timedelta

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
except ImportError:
    print("ERROR: Chybí playwright. Spusť: pip install playwright && playwright install chromium")
    sys.exit(1)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE   = os.path.join(SCRIPT_DIR, "..", "data", "prices.json")

MF_URL = (
    "https://mf.gov.cz/cs/kontrola-a-regulace/cenova-regulace-a-kontrola/"
    "maximalni-pripustne-ceny-benzinu-a-nafty"
)

PAGE_TIMEOUT = 30_000  # ms


# ---------------------------------------------------------------------------
# Datum platnosti
# ---------------------------------------------------------------------------

def valid_from_date() -> str:
    """
    Vrátí datum, od kterého vydané ceny platí:
      - pátek (weekday=4): platí od dnešního pátku
      - Po–Čt:             platí od zítřka
    """
    today = date.today()
    if today.weekday() == 4:
        return today.isoformat()
    return (today + timedelta(days=1)).isoformat()


# ---------------------------------------------------------------------------
# Parsování ceny
# ---------------------------------------------------------------------------

def parse_price(text: str) -> float | None:
    """'41,67 Kč/l' nebo '44.36' → 44.36; vrátí None pokud není v rozsahu 15–100."""
    if not text:
        return None
    cleaned = text.strip().replace("\xa0", "").replace("\u202f", "").replace(" ", "")
    m = re.search(r"(\d{2,3})[,.](\d{1,2})", cleaned)
    if m:
        val = float(f"{m.group(1)}.{m.group(2)}")
        if 15.0 <= val <= 100.0:
            return val
    return None


# ---------------------------------------------------------------------------
# Scraping MF ČR
# ---------------------------------------------------------------------------

def fetch_from_mf() -> dict | None:
    """
    Načte stránku MF ČR a z tabulky vytáhne maximální ceny:
      natural95_cap  — Natural 95 (Kč/l)
      diesel_cap     — Motorová nafta B7 (Kč/l)

    Vrátí dict nebo None při selhání.
    """
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(
            locale="cs-CZ",
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()
        page.set_default_timeout(PAGE_TIMEOUT)

        try:
            print(f"  GET {MF_URL}")
            page.goto(MF_URL, wait_until="domcontentloaded")
            page.wait_for_selector("table", timeout=PAGE_TIMEOUT)

            rows = page.query_selector_all("table tr")
            print(f"  Nalezeno řádků v tabulkách: {len(rows)}")

            natural95_cap: float | None = None
            diesel_cap:    float | None = None

            for row in rows:
                cells = row.query_selector_all("td, th")
                if len(cells) < 2:
                    continue

                texts    = [c.inner_text().strip() for c in cells]
                row_lower = " ".join(texts).lower()

                # --- Natural 95 ---
                if natural95_cap is None:
                    is_n95 = (
                        "natural 95" in row_lower
                        or "natural95"  in row_lower
                        or "ba 95"      in row_lower
                        or ("95" in row_lower and ("benzin" in row_lower or "natural" in row_lower))
                    )
                    if is_n95:
                        for t in reversed(texts[1:]):
                            p = parse_price(t)
                            if p:
                                natural95_cap = p
                                print(f"  Natural 95 cap = {p} Kč/l  ← '{t}'")
                                break

                # --- Nafta B7 ---
                if diesel_cap is None:
                    is_b7 = (
                        "b7" in row_lower
                        or "motorová nafta" in row_lower
                        or ("nafta" in row_lower and "b7" in row_lower)
                        or ("diesel" in row_lower and "b7" in row_lower)
                        # širší match: řádek obsahuje jen "nafta" bez dalšího upřesnění
                        or (
                            "nafta" in row_lower
                            and "natural" not in row_lower
                            and natural95_cap is not None  # Natural 95 jsme už zpracovali
                        )
                    )
                    if is_b7:
                        for t in reversed(texts[1:]):
                            p = parse_price(t)
                            if p:
                                diesel_cap = p
                                print(f"  Nafta B7 cap   = {p} Kč/l  ← '{t}'")
                                break

                if natural95_cap and diesel_cap:
                    break  # máme obě ceny, nepokračujeme

            # --- Fallback debug výpis ---
            if not (natural95_cap and diesel_cap):
                print("  WARN: nepodařilo se automaticky určit obě ceny.")
                print("  Vypisuji všechny řádky tabulky s číselnou hodnotou:")
                for row in rows:
                    cells = row.query_selector_all("td, th")
                    texts = [c.inner_text().strip() for c in cells]
                    if any(parse_price(t) for t in texts):
                        print(f"    {texts}")
                return None

            return {
                "natural95_cap": round(natural95_cap, 2),
                "diesel_cap":    round(diesel_cap,    2),
            }

        except PlaywrightTimeout:
            print("  CHYBA: Timeout při načítání stránky MF ČR")
            return None
        except Exception as exc:
            print(f"  CHYBA: {exc}")
            return None
        finally:
            browser.close()


# ---------------------------------------------------------------------------
# JSON I/O
# ---------------------------------------------------------------------------

def load_existing() -> dict:
    try:
        with open(DATA_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "last_updated": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "valid_from":   date.today().isoformat(),
            "current":      {},
            "history":      [],
        }


def save_prices(new_prices: dict) -> None:
    existing  = load_existing()
    now_str   = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    vf        = valid_from_date()

    existing["last_updated"] = now_str
    existing["valid_from"]   = vf
    existing["current"]      = new_prices

    # Přepíšeme záznam pro den valid_from (ne pro dnešek)
    history = existing.get("history", [])
    history = [h for h in history if h.get("date") != vf]
    history.append({"date": vf, **new_prices})
    history.sort(key=lambda x: x["date"])
    existing["history"] = history[-30:]

    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

    print(f"✓ Uloženo — valid_from: {vf}, ceny: {new_prices}")


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    today   = date.today()
    weekday = today.weekday()  # 0 = pondělí, 4 = pátek

    print("=== Maximální přípustné ceny paliv — MF ČR ===")
    print(f"Dnešní datum : {today.isoformat()} ({['Po','Út','St','Čt','Pá','So','Ne'][weekday]})")
    print(f"Ceny platí od: {valid_from_date()}")

    print("\n→ Načítám data z MF ČR (Playwright/Chromium)…")
    prices = None
    try:
        prices = fetch_from_mf()
    except Exception as exc:
        print(f"  Neočekávaná chyba: {exc}")

    if not prices:
        print("\n⚠️  Data se nepodařilo získat. Stávající data jsou zachována.")
        sys.exit(0)  # Workflow nespadne, zachová poslední platná data

    print(f"\n✓ Data získána: {prices}")
    save_prices(prices)
    print("=== Hotovo ===")


if __name__ == "__main__":
    main()
