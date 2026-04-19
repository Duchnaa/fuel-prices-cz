#!/usr/bin/env python3
"""
fetch_prices.py — Stahuje průměrné ceny pohonných hmot v ČR
a aktualizuje data/prices.json.

Zdroje (v pořadí fallbacku):
  1. CCS.cz  — tabulka průměrných CEN
  2. kurzy.cz — scraping z ceníkové stránky
  3. GreenCar.cz — alternativní zdroj
"""

import json
import os
import re
import sys
from datetime import date, datetime

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("ERROR: Chybí závislosti. Spusť: pip install requests beautifulsoup4 lxml")
    sys.exit(1)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(SCRIPT_DIR, "..", "data", "prices.json")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "cs-CZ,cs;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

TIMEOUT = 20


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_price(text: str) -> float | None:
    """Extrahuje číslo ceny z textu, napr. '37,20 Kč' → 37.20"""
    if not text:
        return None
    # Odstraň mezery, nahraď čárku tečkou
    cleaned = text.strip().replace("\xa0", "").replace(" ", "")
    m = re.search(r"(\d{2,3})[,.](\d{1,2})", cleaned)
    if m:
        val = float(f"{m.group(1)}.{m.group(2)}")
        # Sanity check: ceny paliv v ČR jsou 15–80 Kč/l
        if 15.0 <= val <= 80.0:
            return val
    return None


def _normalize(prices: dict) -> dict:
    """Zaokrouhlí hodnoty na 2 desetinná místa."""
    return {k: round(float(v), 2) for k, v in prices.items() if v is not None}


# ---------------------------------------------------------------------------
# Zdroj 1: CCS.cz
# ---------------------------------------------------------------------------

def fetch_from_ccs() -> dict | None:
    """
    CCS zveřejňuje průměrné ceny pohonných hmot na stránce:
    https://www.ccs.cz/cs/karty-a-ceny/ceny-pohonnych-hmot
    Tabulka obvykle obsahuje řádky s názvy paliv a CEN.
    """
    url = "https://www.ccs.cz/cs/karty-a-ceny/ceny-pohonnych-hmot"
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
    except Exception as e:
        print(f"  CCS: request failed — {e}")
        return None

    soup = BeautifulSoup(r.text, "lxml")
    prices: dict = {}

    # Zkusíme najít všechny tabulky
    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            cells = row.find_all(["td", "th"])
            if len(cells) < 2:
                continue
            label = cells[0].get_text(" ", strip=True).lower()
            # Vezmi poslední buňku jako cenu (nebo druhou)
            for cell in reversed(cells[1:]):
                price = _parse_price(cell.get_text(strip=True))
                if price is None:
                    continue
                if "natural 95" in label or "ba 95" in label or "95" in label and "natural" in label:
                    prices.setdefault("natural95", price)
                elif "nafta" in label or "diesel" in label:
                    prices.setdefault("diesel", price)
                elif "natural 98" in label or "ba 98" in label or "98" in label and "natural" in label:
                    prices.setdefault("natural98", price)
                elif "lpg" in label or "autopl" in label:
                    prices.setdefault("lpg", price)
                break

    # Záložní: hledej strukturovaná data jako JSON-LD nebo data atributy
    if len(prices) < 2:
        for tag in soup.find_all(attrs={"data-price": True}):
            label = (tag.get("data-name", "") + " " + tag.get_text()).lower()
            price = _parse_price(tag.get("data-price", ""))
            if price is None:
                continue
            if "95" in label:
                prices.setdefault("natural95", price)
            elif "nafta" in label or "diesel" in label:
                prices.setdefault("diesel", price)
            elif "98" in label:
                prices.setdefault("natural98", price)
            elif "lpg" in label:
                prices.setdefault("lpg", price)

    if len(prices) >= 2:
        print(f"  CCS: úspěch — {prices}")
        return _normalize(prices)

    print("  CCS: nepodařilo se parsovat dostatek dat")
    return None


# ---------------------------------------------------------------------------
# Zdroj 2: kurzy.cz — API endpoint
# ---------------------------------------------------------------------------

def fetch_from_kurzy_api() -> dict | None:
    """
    kurzy.cz poskytuje ceny paliv přes API nebo jako JSON na svých stránkách.
    """
    urls_to_try = [
        "https://api.kurzy.cz/paliva/",
        "https://www.kurzy.cz/api/paliva/",
    ]

    for url in urls_to_try:
        try:
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            r.raise_for_status()
            data = r.json()
        except Exception:
            continue

        prices: dict = {}
        items = data if isinstance(data, list) else (data.get("data") or data.get("paliva") or [])

        for item in (items if isinstance(items, list) else [data]):
            if not isinstance(item, dict):
                continue
            name = str(item.get("nazev", "") + " " + item.get("name", "") + " " + item.get("typ", "")).lower()
            raw_price = item.get("cena") or item.get("price") or item.get("hodnota")
            price = _parse_price(str(raw_price)) if raw_price is not None else None
            if price is None:
                continue
            if "95" in name and ("natural" in name or "benzin" in name or "ba" in name):
                prices.setdefault("natural95", price)
            elif "nafta" in name or "diesel" in name:
                prices.setdefault("diesel", price)
            elif "98" in name and ("natural" in name or "benzin" in name or "ba" in name):
                prices.setdefault("natural98", price)
            elif "lpg" in name:
                prices.setdefault("lpg", price)

        if len(prices) >= 2:
            print(f"  kurzy.cz API: úspěch — {prices}")
            return _normalize(prices)

    print("  kurzy.cz API: nepodařilo se získat data")
    return None


# ---------------------------------------------------------------------------
# Zdroj 3: kurzy.cz — scraping HTML stránky
# ---------------------------------------------------------------------------

def fetch_from_kurzy_scrape() -> dict | None:
    """
    Scrapuje ceny z HTML stránky kurzy.cz/komodity/benzin-cena/
    """
    pages = [
        ("natural95", "https://www.kurzy.cz/komodity/benzin-cena/"),
        ("diesel",    "https://www.kurzy.cz/komodity/nafta-cena/"),
        ("natural98", "https://www.kurzy.cz/komodity/natural-98-cena/"),
        ("lpg",       "https://www.kurzy.cz/komodity/lpg-cena/"),
    ]

    prices: dict = {}
    for fuel_key, url in pages:
        try:
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "lxml")

            # Hledáme "aktuální cena" element
            price = None
            for selector in [
                ".current-price", ".cena", "#cena", ".price-actual",
                "[class*='current']", "[class*='price']",
            ]:
                tag = soup.select_one(selector)
                if tag:
                    price = _parse_price(tag.get_text(strip=True))
                    if price:
                        break

            # Fallback: projdi všechny tabulky a hledej číslo s Kč
            if not price:
                for td in soup.find_all(["td", "span", "div"]):
                    txt = td.get_text(strip=True)
                    if "kč" in txt.lower() or "czk" in txt.lower():
                        price = _parse_price(txt)
                        if price:
                            break

            if price:
                prices[fuel_key] = price
                print(f"  kurzy.cz scrape {fuel_key}: {price}")

        except Exception as e:
            print(f"  kurzy.cz scrape {fuel_key}: chyba — {e}")

    if len(prices) >= 2:
        return _normalize(prices)
    return None


# ---------------------------------------------------------------------------
# Zdroj 4: GreenCar.cz
# ---------------------------------------------------------------------------

def fetch_from_greencar() -> dict | None:
    """
    GreenCar.cz publikuje průměrné ceny pohonných hmot.
    """
    url = "https://www.greencar.cz/ceny-pohonnych-hmot/"
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
    except Exception as e:
        print(f"  GreenCar: request failed — {e}")
        return None

    soup = BeautifulSoup(r.text, "lxml")
    prices: dict = {}

    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            cells = row.find_all(["td", "th"])
            if len(cells) < 2:
                continue
            label = cells[0].get_text(" ", strip=True).lower()
            for cell in reversed(cells[1:]):
                price = _parse_price(cell.get_text(strip=True))
                if price is None:
                    continue
                if "95" in label:
                    prices.setdefault("natural95", price)
                elif "nafta" in label or "diesel" in label:
                    prices.setdefault("diesel", price)
                elif "98" in label:
                    prices.setdefault("natural98", price)
                elif "lpg" in label:
                    prices.setdefault("lpg", price)
                break

    if len(prices) >= 2:
        print(f"  GreenCar: úspěch — {prices}")
        return _normalize(prices)

    print("  GreenCar: nepodařilo se parsovat data")
    return None


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
            "current": {
                "natural95": 37.20,
                "diesel": 36.10,
                "natural98": 40.50,
                "lpg": 19.20,
            },
            "history": [],
            "government_cap": {
                "active": False,
                "cap_price_natural95": None,
                "cap_price_diesel": None,
                "info": "",
            },
        }


def save_prices(new_prices: dict) -> None:
    existing = load_existing()
    today_str = date.today().isoformat()
    now_str = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    # Doplň chybějící paliva ze stávajících dat
    for key in ("natural95", "diesel", "natural98", "lpg"):
        if key not in new_prices:
            new_prices[key] = existing["current"].get(key)

    existing["last_updated"] = now_str
    existing["current"] = new_prices

    # Aktualizuj historii
    history: list = existing.get("history", [])
    history = [h for h in history if h.get("date") != today_str]
    history.append({"date": today_str, **new_prices})
    history.sort(key=lambda x: x["date"])
    existing["history"] = history[-90:]  # Uchovej max 90 dní

    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

    print(f"✓ Uloženo: {new_prices}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=== Stahuji ceny pohonných hmot ===")
    print(f"Datum: {date.today().isoformat()}")

    sources = [
        ("CCS.cz",           fetch_from_ccs),
        ("kurzy.cz API",     fetch_from_kurzy_api),
        ("kurzy.cz scrape",  fetch_from_kurzy_scrape),
        ("GreenCar.cz",      fetch_from_greencar),
    ]

    prices = None
    for name, fn in sources:
        print(f"\n→ Zkouším {name}…")
        try:
            prices = fn()
        except Exception as e:
            print(f"  Neočekávaná chyba: {e}")
            prices = None

        if prices and len(prices) >= 2:
            print(f"✓ Data získána z {name}")
            break
    else:
        print("\n⚠️  Všechny zdroje selhaly. Ponechávám stávající data.")
        sys.exit(0)

    save_prices(prices)
    print("\n=== Hotovo ===")


if __name__ == "__main__":
    main()
