#!/usr/bin/env python3
"""
fetch_prices.py — Stahuje maximální přípustné ceny benzinu a nafty
z webu Ministerstva financí ČR pomocí Playwright.

Zdroj:
  https://mf.gov.cz/cs/kontrola-a-regulace/cenova-regulace-a-kontrola/
  maximalni-pripustne-ceny-benzinu-a-nafty

Ceny jsou publikovány v textu článku (ne v HTML tabulce). Script
parsuje prostý text stránky regexem.

Logika platnosti (fallback pokud datum nelze přečíst ze stránky):
  - Po–Čt: vydané ceny platí pro ZÍTŘEK
  - Pá:    vydané ceny platí pro pátek, So, Ne i Po
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
# České názvy měsíců → číslo
# ---------------------------------------------------------------------------

MONTHS_CS: dict[str, str] = {
    "ledna":    "01", "února":    "02", "března":   "03", "dubna":    "04",
    "května":   "05", "června":   "06", "července": "07", "srpna":    "08",
    "září":     "09", "října":    "10", "listopadu": "11", "prosince": "12",
}

# ---------------------------------------------------------------------------
# Zkompilované regexpy
# ---------------------------------------------------------------------------

# "Maximální přípustná cena benzinu: 41,33 Kč s DPH / litr"
RE_N95_CAP = re.compile(
    r"Maximáln[íi]\s+p[řr][íi]pustn[áa]\s+cena\s+benzinu[^:\n]*"
    r":\s*([\d]+[,.]?\d*)\s*Kč",
    re.IGNORECASE,
)

# "Maximální přípustná cena nafty: 43,13 Kč s DPH / litr"
RE_DIESEL_CAP = re.compile(
    r"Maximáln[íi]\s+p[řr][íi]pustn[áa]\s+cena\s+nafty[^:\n]*"
    r":\s*([\d]+[,.]?\d*)\s*Kč",
    re.IGNORECASE,
)

# "Hypotetická cena benzinu bez regulace marží: 46,78 Kč s DPH / litr"
RE_N95_HYPO = re.compile(
    r"Hypotetick[áa]\s+cena\s+benzinu[^:\n]*"
    r":\s*([\d]+[,.]?\d*)\s*Kč",
    re.IGNORECASE,
)

# "Hypotetická cena nafty bez regulace marží a daňových změn: 50,31 Kč s DPH / litr"
RE_DIESEL_HYPO = re.compile(
    r"Hypotetick[áa]\s+cena\s+nafty[^:\n]*"
    r":\s*([\d]+[,.]?\d*)\s*Kč",
    re.IGNORECASE,
)

# Formát 1: "Účinnost: od 18. dubna 2026 00:00 do 20. dubna 2026 24:00 na celém území ČR"
RE_VALIDITY_F1 = re.compile(
    r"Účinnost[^:\n]*:\s*od\s+(\d{1,2}\.\s*\w+\s+\d{4})"
    r".*?do\s+(\d{1,2}\.\s*\w+\s+\d{4})",
    re.IGNORECASE | re.DOTALL,
)

# Formát 2: "Účinnost: 21. dubna 2026 od 00:00 do 24:00 na celém území ČR"
RE_VALIDITY_F2 = re.compile(
    r"Účinnost[^:\n]*:\s+(\d{1,2}\.\s*\w+\s+\d{4})\s+od\s+\d{1,2}:\d{2}\s+do\s+\d{1,2}:\d{2}",
    re.IGNORECASE,
)

# Formát 3: "Účinnost: od 21. dubna 2026 00:00 do 24:00"
RE_VALIDITY_F3 = re.compile(
    r"Účinnost[^:\n]*:\s*od\s+(\d{1,2}\.\s*\w+\s+\d{4})\s+\d{1,2}:\d{2}\s+do\s+\d{1,2}:\d{2}",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Pomocné funkce
# ---------------------------------------------------------------------------

def parse_czech_date(text: str) -> str | None:
    """'18. dubna 2026' → '2026-04-18'; vrátí None pokud parsování selže."""
    m = re.search(r"(\d{1,2})\.\s*(\w+)\s+(\d{4})", text.strip())
    if not m:
        return None
    day       = int(m.group(1))
    month_cs  = m.group(2).lower()
    year      = m.group(3)
    month     = MONTHS_CS.get(month_cs)
    if not month:
        print(f"  WARN: neznámý název měsíce '{month_cs}'")
        return None
    return f"{year}-{month}-{day:02d}"


def extract_price(m: re.Match | None) -> float | None:
    """Z regex match vytáhne číslo a ověří rozsah 15–100 Kč/l."""
    if not m:
        return None
    try:
        val = float(m.group(1).replace(",", "."))
        return round(val, 2) if 15.0 <= val <= 100.0 else None
    except ValueError:
        return None


def fallback_valid_from() -> str:
    """
    Fallback datum platnosti (pokud ho nelze přečíst ze stránky):
      - pátek  → dnešní datum
      - Po–Čt  → zítřek
    """
    today = date.today()
    if today.weekday() == 4:  # pátek
        return today.isoformat()
    return (today + timedelta(days=1)).isoformat()


# ---------------------------------------------------------------------------
# Scraping MF ČR
# ---------------------------------------------------------------------------

def fetch_from_mf() -> dict | None:
    """
    Načte stránku MF ČR, parsuje textový obsah a vrátí:
      {
        "prices":     { "natural95_cap": float, "diesel_cap": float,
                        "natural95_without_cap": float?, "diesel_without_cap": float? },
        "valid_from": "YYYY-MM-DD",
        "valid_to":   "YYYY-MM-DD" | None,
      }
    Nebo None při selhání.
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

            # Počkáme na hlavní obsah článku; při selhání fallback na networkidle
            try:
                page.wait_for_selector(
                    "main, article, #main, .content",
                    timeout=PAGE_TIMEOUT,
                )
            except PlaywrightTimeout:
                print("  INFO: selektor hlavního obsahu nenalezen, čekám na networkidle…")
                page.wait_for_load_state("networkidle", timeout=PAGE_TIMEOUT)

            # Celý textový obsah stránky
            text = page.inner_text("body")

            # ---- Debug výpis ----
            print("\n--- STRÁNKA (prvních 2000 znaků) ---")
            print(text[:2000])
            print("--- KONEC VÝPISU ---\n")

            # ---- Parsování cen ----
            n95_cap     = extract_price(RE_N95_CAP.search(text))
            diesel_cap  = extract_price(RE_DIESEL_CAP.search(text))
            n95_hypo    = extract_price(RE_N95_HYPO.search(text))
            diesel_hypo = extract_price(RE_DIESEL_HYPO.search(text))

            print(f"  Natural 95 cap        : {n95_cap}")
            print(f"  Nafta cap             : {diesel_cap}")
            print(f"  Natural 95 bez regulace: {n95_hypo}")
            print(f"  Nafta bez regulace    : {diesel_hypo}")

            if not n95_cap or not diesel_cap:
                print("  CHYBA: Maximální ceny nebyly nalezeny v textu stránky.")
                return None

            # ---- Parsování platnosti ----
            valid_from: str | None = None
            valid_to:   str | None = None

            vm1 = RE_VALIDITY_F1.search(text)
            vm2 = RE_VALIDITY_F2.search(text)
            vm3 = RE_VALIDITY_F3.search(text)
            if vm1:
                valid_from = parse_czech_date(vm1.group(1))
                valid_to   = parse_czech_date(vm1.group(2))
                print(f"  Účinnost (formát 1) od: {valid_from}  do: {valid_to}")
            elif vm2:
                valid_from = parse_czech_date(vm2.group(1))
                valid_to   = valid_from
                print(f"  Účinnost (formát 2) od/do: {valid_from}")
            elif vm3:
                valid_from = parse_czech_date(vm3.group(1))
                valid_to   = valid_from
                print(f"  Účinnost (formát 3) od/do: {valid_from}")
            else:
                print("  WARN: 'Účinnost' řádek nenalezen v textu (žádný formát).")

            if not valid_from:
                valid_from = fallback_valid_from()
                print(f"  Platnost od (fallback weekday): {valid_from}")

            prices: dict = {"natural95_cap": n95_cap, "diesel_cap": diesel_cap}
            if n95_hypo    is not None:
                prices["natural95_without_cap"] = n95_hypo
            if diesel_hypo is not None:
                prices["diesel_without_cap"] = diesel_hypo

            return {"prices": prices, "valid_from": valid_from, "valid_to": valid_to}

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
            "last_updated":  datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "valid_from":    date.today().isoformat(),
            "valid_to":      None,
            "current":       {},
            "government_cap": {"active": True},
            "history":       [],
        }


def save_prices(result: dict) -> None:
    existing   = load_existing()
    now_str    = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    prices     = result["prices"]
    vf         = result["valid_from"]
    vt         = result.get("valid_to")

    existing["last_updated"] = now_str
    existing["valid_from"]   = vf
    existing["valid_to"]     = vt

    today_iso = date.today().isoformat()
    if vf <= today_iso:
        # Ceny platí dnes nebo zpětně → rovnou do current
        existing["current"]   = prices
        existing["next_day"]  = existing.get("next_day")  # beze změny
        print(f"  → uloženo do current (valid_from {vf} <= dnes {today_iso})")
    else:
        # Ceny platí od zítřka nebo later → do next_day, current beze změny
        existing["next_day"]  = {"valid_from": vf, **prices}
        print(f"  → uloženo do next_day (valid_from {vf} > dnes {today_iso})")

    existing["government_cap"] = {
        "active":             True,
        "cap_price_natural95": prices["natural95_cap"],
        "cap_price_diesel":    prices["diesel_cap"],
        "valid_from":          vf,
        "valid_to":            vt,
    }

    # Záznam v historii je indexován datem platnosti (valid_from)
    history: list = existing.get("history", [])
    history = [h for h in history if h.get("date") != vf]
    history.append({"date": vf, **prices})
    history.sort(key=lambda x: x["date"])
    existing["history"] = history[-30:]

    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

    print(f"✓ Uloženo do next_day — valid_from: {vf}, valid_to: {vt}")
    print(f"  Ceny: {prices}")


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    today   = date.today()
    weekday = today.weekday()
    dny     = ["Po", "Út", "St", "Čt", "Pá", "So", "Ne"]

    print("=== Maximální přípustné ceny paliv — MF ČR ===")
    print(f"Datum spuštění : {today.isoformat()} ({dny[weekday]})")
    print(f"Fallback valid_from: {fallback_valid_from()}")

    print("\n→ Načítám data z MF ČR (Playwright/Chromium)…")
    result = None
    try:
        result = fetch_from_mf()
    except Exception as exc:
        print(f"  Neočekávaná chyba: {exc}")

    if not result:
        print("\n⚠️  Data se nepodařilo získat. Stávající prices.json je zachován beze změny.")
        sys.exit(0)  # Workflow nespadne, GitHub Actions necommitne nic

    save_prices(result)
    print("\n=== Hotovo ===")


if __name__ == "__main__":
    main()
