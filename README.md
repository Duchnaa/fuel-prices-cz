# ⛽ Cenové stropy pohonných hmot v ČR

Statická webová stránka zobrazující aktuální maximální přípustné ceny benzinu a nafty v České republice stanovené Ministerstvem financí ČR — s automatickou denní aktualizací přes GitHub Actions.

**🌐 Live ukázka:** https://duchnaa.github.io/fuel-prices-cz/

---

## Proč tento projekt vznikl?

Od 8. dubna 2026 vláda ČR zavedla cenové stropy na pohonné hmoty jako reakci na uzavření Hormuzského průlivu a rekordní skok cen ropy. Ministerstvo financí vydává nové maximální ceny každý pracovní den ve 14:00 — tento web je automaticky stahuje a zobrazuje přehledně na jednom místě.

---

## Funkce

- 📊 **Aktuální cenové stropy** — Natural 95 a Nafta B7 dle MF ČR
- 🔮 **Nové ceny od zítřka** — zobrazí chystané ceny ihned po jejich zveřejnění ve 14:00
- 💡 **Úspora oproti tržní ceně** — kolik strop reálně šetří na litru
- 🧮 **Kalkulačka úspory** — zadej km/měsíc a spotřebu, zobrazí měsíční úsporu v Kč
- 📈 **Graf vývoje** — přehled stropů od 8. dubna 2026
- 🌙 **Dark mode** — automaticky podle systémových preferencí
- 📱 **Responzivní design** — funguje na mobilu i desktopu
- ⚡ **Automatická aktualizace** — každý pracovní den po 14:00 bez nutnosti zásahu

---

## Jak to funguje

```
MF ČR vydá nové ceny ve 14:00
        ↓
GitHub Actions spustí Python scraper (Playwright/Chromium)
        ↓
Scraper načte stránku MF ČR a parsuje ceny + datum platnosti
        ↓
Ceny se uloží do data/prices.json jako "next_day"
        ↓
O půlnoci midnight-switch přesune next_day → current
        ↓
GitHub Pages automaticky nasadí aktuální verzi webu
```

---

## Struktura projektu

```
fuel-prices-cz/
├── index.html                           # Hlavní stránka (CSS + JS inline)
├── data/
│   └── prices.json                      # Aktuální + historická data (přepisováno Actions)
├── scripts/
│   └── fetch_prices.py                  # Python scraper (Playwright)
├── .github/
│   └── workflows/
│       ├── update-prices.yml            # Stahuje nové ceny každý pracovní den po 14:00
│       └── midnight-switch.yml          # O půlnoci přepne next_day → current
└── README.md
```

---

## Použité technologie

- **GitHub Pages** — hosting zdarma
- **GitHub Actions** — automatizace bez serveru
- **Playwright** — headless Chrome pro scraping JS stránek
- **Vanilla JS + SVG** — bez frameworků, žádné závislosti
- **Google Fonts** — Inter + Instrument Serif

---

## Spuštění vlastní kopie

1. Forkni repozitář
2. Jdi do **Settings → Pages → Source: main / (root)** → Save
3. Jdi do **Settings → Actions → General → Workflow permissions → Read and write** → Save
4. Spusť workflow ručně: **Actions → Aktualizace cen → Run workflow**
5. Web bude dostupný na `https://<tvoje-jmeno>.github.io/fuel-prices-cz/`

---

## Zdroj dat

[Ministerstvo financí ČR — Maximální přípustné ceny benzinu a nafty](https://mf.gov.cz/cs/kontrola-a-regulace/cenova-regulace-a-kontrola/maximalni-pripustne-ceny-benzinu-a-nafty)

---

## Licence

MIT — volně použitelné a upravitelné.
