# ⛽ Ceny paliv v ČR

Statická webová stránka zobrazující aktuální průměrné ceny pohonných hmot v České republice s automatickou denní aktualizací přes GitHub Actions.

**Live ukázka:** `https://<tvůj-username>.github.io/fuel-prices-cz/`

---

## Obsah

- [Funkce](#funkce)
- [Struktura projektu](#struktura-projektu)
- [Jak spustit vlastní verzi](#jak-spustit-vlastní-verzi)
- [Nastavení GitHub Pages](#nastavení-github-pages)
- [Nastavení GitHub Actions](#nastavení-github-actions)
- [Zdroje dat](#zdroje-dat)
- [Lokální vývoj](#lokální-vývoj)

---

## Funkce

- 📊 Aktuální ceny: Natural 95, Nafta
- 📈 Graf vývoje cen od 8.4. 2026
- 🔼🔽 Barevné indikátory trendu (zelená = zlevnění, červená = zdražení)
- 📊 Statistiky: nejlevnější/nejdražší
- 🏛️ Banner při aktivním vládním stropu cen
- 📱 Responzivní design (mobil + desktop)
- 🌙 Dark mode
- ⚡ Automatická aktualizace každý den ve 14:05

---

## Struktura projektu

```
fuel-prices-cz/
├── index.html                          # Hlavní stránka
├── style.css                           # Styly (dark mode, česká trikolóra)
├── app.js                              # JavaScript (Chart.js, renderování)
├── data/
│   └── prices.json                     # Aktuální + historická data (přepisováno Actions)
├── scripts/
│   └── fetch_prices.py                 # Python scraper pro GitHub Actions
├── .github/
│   └── workflows/
│       └── update-prices.yml           # Workflow: denní aktualizace v 8:00 UTC
└── README.md
```

---

## Jak spustit vlastní verzi

### 1. Forkni nebo naklonuj repozitář

```bash
# Fork přes GitHub UI nebo:
gh repo fork <original-repo> --clone
cd fuel-prices-cz
```

Nebo vytvoř nový repozitář a nakopíruj soubory:

```bash
git init fuel-prices-cz
cd fuel-prices-cz
# Nakopíruj všechny soubory z tohoto projektu
git add .
git commit -m "init: fuel prices website"
git remote add origin https://github.com/<tvůj-username>/fuel-prices-cz.git
git push -u origin main
```

---

## Nastavení GitHub Pages

1. Přejdi do svého repozitáře na GitHub
2. Klikni na **Settings** (ozubené kolečko)
3. V levém menu vyber **Pages**
4. Pod **Source** zvol:
   - **Branch:** `main`
   - **Folder:** `/ (root)`
5. Klikni **Save**
6. Počkej 1–2 minuty, poté bude stránka dostupná na:
   `https://<tvůj-username>.github.io/fuel-prices-cz/`

> **Tip:** GitHub Pages může trvat až 10 minut, než se stránka poprvé zobrazí.

---

## Nastavení GitHub Actions

GitHub Actions potřebuje oprávnění zapisovat do repozitáře (commit + push dat).

### Nastavení write permissions pro Actions

1. Přejdi do **Settings** repozitáře
2. V levém menu vyber **Actions → General**
3. Sroluj na **Workflow permissions**
4. Vyber **Read and write permissions**
5. Zaškrtni **Allow GitHub Actions to create and approve pull requests** (volitelné)
6. Klikni **Save**

### Ruční spuštění workflow

Workflow se spouští automaticky každý den v 8:00 UTC. Pro manuální spuštění:

1. Přejdi na záložku **Actions** v repozitáři
2. Vyber workflow **Aktualizace cen pohonných hmot**
3. Klikni **Run workflow → Run workflow**

---

## Zdroje dat

Python script `scripts/fetch_prices.py` zkouší tyto zdroje v pořadí:

| Priorita | Zdroj | URL |
|----------|-------|-----|
| 1. | CCS.cz | `ccs.cz/cs/karty-a-ceny/ceny-pohonnych-hmot` |
| 2. | kurzy.cz API | `api.kurzy.cz/paliva/` |
| 3. | kurzy.cz scraping | `kurzy.cz/komodity/benzin-cena/` |
| 4. | GreenCar.cz | `greencar.cz/ceny-pohonnych-hmot/` |

Pokud všechny zdroje selžou, workflow skončí bez chyby a zachová poslední platná data.

---

## Formát dat (prices.json)

```json
{
  "last_updated": "2026-04-19T08:00:00",
  "current": {
    "natural95": 37.20,
    "diesel": 36.10,
    "natural98": 40.50,
    "lpg": 19.20
  },
  "history": [
    {
      "date": "2026-04-19",
      "natural95": 37.20,
      "diesel": 36.10,
      "natural98": 40.50,
      "lpg": 19.20
    }
  ],
  "government_cap": {
    "active": false,
    "cap_price_natural95": null,
    "cap_price_diesel": null,
    "info": ""
  }
}
```

### Vládní strop na ceny

Pokud chceš zobrazit banner o vládním stropu, nastav v `prices.json`:

```json
"government_cap": {
  "active": true,
  "cap_price_natural95": 40.00,
  "cap_price_diesel": 38.00,
  "info": "Vládní strop na pohonné hmoty je aktivní od 1. 5. 2026."
}
```

---

## Lokální vývoj

### Spuštění webu lokálně

```bash
# Pomocí Pythonu (jednoduchý HTTP server)
python -m http.server 8000
# Otevři: http://localhost:8000

# Nebo pomocí Node.js
npx serve .
```

> **Důležité:** Kvůli CORS politice musíš spustit HTTP server. Přímé otevření `index.html` z disku nebude načítat `prices.json`.

### Ruční spuštění Python scriptu

```bash
cd fuel-prices-cz
pip install requests beautifulsoup4 lxml
python scripts/fetch_prices.py
```

---

## Technologie

- **Frontend:** Čistý HTML5 + CSS3 + Vanilla JavaScript (žádné frameworky)
- **Grafy:** [Chart.js](https://www.chartjs.org/) 4.x (načteno z CDN)
- **Scraping:** Python 3.12 + `requests` + `BeautifulSoup4`
- **CI/CD:** GitHub Actions
- **Hosting:** GitHub Pages

---

## Přizpůsobení

### Změna barvy akcentu

V `style.css` uprav CSS proměnné:

```css
:root {
  --blue: #003087;   /* Česká modrá */
  --red:  #D7141A;   /* Česká červená */
}
```

### Přidání dalšího paliva

1. Přidej klíč do `data/prices.json` (sekce `current` i `history`)
2. V `app.js` rozšiř objekt `FUEL_META`
3. V `index.html` přidej novou `.fuel-card`
4. V `scripts/fetch_prices.py` přidej parsing pro nové palivo

---

## Licence

MIT — volně použitelné a upravitelné.
