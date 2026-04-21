# ⛽ Ceny paliv v ČR

Statická webová stránka zobrazující aktuální průměrné ceny pohonných hmot v České republice s automatickou denní aktualizací přes GitHub Actions.

**Live ukázka:** `https://duchnaa.github.io/fuel-prices-cz/`

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
├── data/
│   └── prices.json                     # Aktuální + historická data (přepisováno Actions)
├── scripts/
│   └── fetch_prices.py                 # Python scraper pro GitHub Actions
├── .github/
│   └── workflows/
│       └── update-prices.yml           # Workflow: denní aktualizace v 8:00 UTC
└── README.md
```


## Licence

MIT — volně použitelné a upravitelné.
