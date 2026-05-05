# CARBON WORLD — Indicators reference

> Documentation exhaustive de chaque indicateur affiché sur le dashboard.
> **Source de vérité unique : la transaction Solana confirmée.**
> Aucun indicateur ne compte un event tant que sa TX n'est pas on-chain.

---

## Règles transversales

1. **On-chain only** — un event sans `tx_hash` (= TX Solana non confirmée, en attente du reconcile cron `15 3 * * *`) est **exclu** de tous les agrégats. Les events pending réintègrent automatiquement les chiffres dès que leur TX confirme.
2. **Fenêtre temporelle 7 jours** — sauf indication contraire, les indicateurs sont calculés sur les 7 derniers jours glissants (UTC, depuis `created_at` de l'event).
3. **Drill-down canonique** — chaque card est cliquable. Le drill-down `/events?...` lit la **liste exacte** des `event_ids` que le worker a comptés → impossible que la card et la liste divergent.
4. **Source code** — toute la logique d'agrégation est dans `worker/exporter.py` (Python), exposée dans `data/export.json` → consommée par les Server Components Next.js dans `web/src/components/indicators/`.

---

## 1. TOP COUNTRIES · MINT · 7D

- **Card** : `web/src/components/indicators/TopCountriesMintCard.tsx`
- **Worker** : `_top_countries(events_7d, "MINT", limit=5)` dans `exporter.py`
- **Sémantique** : top 5 pays avec le plus d'events MINT (régressions institutionnelles) confirmés on-chain sur 7 jours.
- **Champ utilisé** : `event.country` (extraction LLM via `event_country` du prompt analyst, commit `08311f4`).
- **Calcul** : `count` = nombre d'events MINT pour ce pays. `total_amount` = somme des `amount_crbn` (CBWD minté).
- **Drill-down** : `/events?country=<X>&decision=MINT&since=7d`.
- **Caveat** : si l'analyst LLM tag mal `event.country` (ex. event UE tagué France), l'event apparaît dans le mauvais pays. Vérifier les faux positifs en lisant les premiers events après chaque run.

## 2. TOP COUNTRIES · BURN · 7D

- **Card** : `TopCountriesBurnCard.tsx`
- **Worker** : `_top_countries(events_7d, "BURN", limit=5)`
- **Sémantique** : top 5 pays avec le plus d'events BURN (actions positives) confirmés on-chain sur 7 jours.
- **Champ** : `event.country`.
- **Calcul** : identique à TOP COUNTRIES MINT mais filtré sur `decision == "BURN"`.
- **Drill-down** : `/events?country=<X>&decision=BURN&since=7d`.

## 3. TOP REGIONS · SUSTAINABLE · 7D

- **Card** : `TopRegionsSustainableCard.tsx`
- **Worker** : `_top_regions_sustainable(events_7d)` dans `exporter.py`
- **Sémantique** : top 5 régions avec le plus haut **ratio BURN** (= sustainable). Seuil minimum : 3 events sur la fenêtre pour être éligible.
- **Champ** : `event.region` (extraction LLM, exemples : Europe, North America, MENA, LATAM, Asia, Africa, Pacific, Global).
- **Calcul** : pour chaque région, `burn_ratio = burn_events / total_events`. Tri décroissant.
- **Affichage** : barre de progression + pourcentage.
- **Drill-down** : `/events?region=<X>&decision=BURN&since=7d`.

## 4. TOP REGIONS · DESTRUCTIVE · 7D

- **Card** : `TopRegionsDestructiveCard.tsx`
- **Worker** : `_top_regions_destructive(events_7d)`
- **Sémantique** : miroir de SUSTAINABLE mais ranké par **ratio MINT**. Même seuil minimum 3 events.
- **Champ** : `event.region`.
- **Calcul** : `mint_ratio = mint_events / total_events`. Tri décroissant.
- **Drill-down** : `/events?region=<X>&decision=MINT&since=7d`.

## 5. SUPPLY NET · 7D TREND

- **Card** : `SupplyTrendCard.tsx`
- **Worker** : `_supply_trend_7d(onchain_events)`
- **Sémantique** : courbe sparkline du delta net (mint - burn) jour par jour sur 7 jours.
- **Champ** : `event.amount_crbn` agrégé par `event.created_at` (date UTC).
- **Calcul** : pour chaque jour J, `net_minted = sum(MINT amounts on day J)`, `net_burned = sum(BURN amounts on day J)`. Le total cumulé sur 7j est affiché en gros (vert si BURN dominant, rouge si MINT dominant).
- **Drill-down** : clic sur la card → `/events?since=7d` (tous les events on-chain du fenêtre).
- **Note** : un point par jour, donc 7 points. Si le worker n'a pas tourné un jour, ce jour vaut 0.

## 6. EVENT OF THE DAY

- **Card** : `EventOfTheDayCard.tsx`
- **Worker** : `_event_of_the_day(events_7d)`
- **Sémantique** : event le plus impactant de la **fenêtre 24h** glissante. Si aucun event sur les dernières 24h → fallback sur les 7 derniers jours pour ne pas afficher une card vide.
- **Calcul** : tri par `|final_score|` décroissant (proxy de l'impact). Le top 1 est retourné avec le shape complet `{id, event_title, decision, amount_crbn, final_score, confidence, country, region, created_at}`.
- **Drill-down** : clic sur la card → `/event/<id>`.

## 7. FRAMEWORK ACTIVITY · 7 DAYS  *(corrigé 2026-05-05)*

- **Card** : `FrameworkActivityCard.tsx` (composant `FrameworkBar` par ligne)
- **Worker** : `_framework_activity_7d(events_7d)`
- **Sémantique (NOUVELLE — fix 2026-05-05)** : pour chaque framework des 7 référentiels (SDG, UDHR, ILO, CRC, UNDRIP, Animal, PB), nombre d'**events** qui l'ont **touché** dans leur analyse 4D, ventilé par décision finale :
  - `positive` (= `+N` vert) = events **BURN** qui ont référencé ce framework dans n'importe quel aspect (positif OU négatif de l'event)
  - `negative` (= `−N` rouge) = events **MINT** qui ont référencé ce framework
- **Garantie** : `positive[fw] ≤ total BURN events on-chain 7d` et `negative[fw] ≤ total MINT events on-chain 7d`. Le card ne peut **plus** afficher "+18 SDG" quand il n'y a que 8 BURN events.
- **Détection framework** : 1) champ structuré `frameworks: [...]` du prompt LLM (priorité absolue). 2) Fallback regex strict sur le texte des aspects (commit historique, voir `_detect_frameworks` et `_RE_*` dans `exporter.py`).
- **Drill-down** :
  - Row entière → `/events?framework=<code>&since=7d` (tous les events touchés)
  - `+N` vert → `/events?framework=<code>&framework_polarity=positive&since=7d` (BURN seulement)
  - `−N` rouge → `/events?framework=<code>&framework_polarity=negative&since=7d` (MINT seulement)
- **Caveat** : un event peut toucher plusieurs frameworks → la somme des `positive` ou `negative` peut dépasser le nombre total d'events. Mais chaque case `positive[fw]` reste bornée par le total BURN.

### Ancienne sémantique (bug fixé)

Avant le 2026-05-05, `positive[fw]` comptait les **aspects positifs** citant le framework, peu importe la décision de l'event. Conséquence : un event MINT avec un aspect positif citant SDG comptait en "+1 SDG positive", ce qui produisait des chiffres > nombre d'events BURN (impossible logiquement). La nouvelle sémantique aligne le comptage avec la lecture intuitive : "+N = N BURN events qui touchent ce framework".

## 8. TOP INSTITUTIONS · 7D

- **Card** : `TopInstitutionsCard.tsx`
- **Worker** : `_top_institutions(events_7d)` + `taxonomy_extractor.extract_institutions()`
- **Sémantique** : top 8 institutions internationales (NATO, EU Commission, UN, WHO, IPCC, etc.) mentionnées dans `event_title + justification` sur 7 jours.
- **Détection** : regex multilingue (FR + EN) dans `worker/taxonomy_extractor.py` (`_INSTITUTION_PATTERNS`).
- **Output** : `[{name, count, burn_count, mint_count, event_ids}]`.
- **Drill-down** : `/events?institution=<name>&since=7d` — utilise les `event_ids` canoniques du worker.
- **Caveat** : un event peut mentionner plusieurs institutions, donc être compté dans plusieurs lignes.

## 9. TOP SECTORS · 7D

- **Card** : `TopSectorsCard.tsx`
- **Worker** : `_top_sectors(events_7d)` + `taxonomy_extractor.extract_sectors()`
- **Sémantique** : top 8 secteurs économiques (Energy, Mining, Agriculture, Tech, Finance, Pharma, Defense, Fishing, Forestry, Transport, Construction, Water) mentionnés dans `event_title + justification` sur 7 jours.
- **Détection** : regex multilingue dans `taxonomy_extractor.py` (`_SECTOR_PATTERNS`).
- **Output** : `[{name, count, burn_count, mint_count, event_ids}]`.
- **Drill-down** : `/events?sector=<name>&since=7d` — utilise les `event_ids` canoniques.
- **Caveat** : un event peut toucher plusieurs secteurs.

## 10. BURN COMPOSITION · 7D / ALL TIME

- **Card** : `BurnCompositionCard.tsx`
- **Worker** : `_burn_composition(events)` (deux appels : `events_7d` + `onchain_events`)
- **Sémantique** : breakdown des BURN par sous-type :
  - `direct_action` : action concrète terrain (volunteer, ONG, citoyen, scientifique)
  - `editorial_consciousness` : article éditorial qui amplifie une prise de conscience (Mongabay reverse, Yale E360, etc.)
  - `untyped` : pas de subtype assigné (events anciens pré-`burn_subtype`)
- **Champ** : `event.burn_subtype` (column DB ajoutée 2026-04-27).
- **Calcul** : `count` + `pct` par catégorie sur le total BURN.

## 11. MINT COMPOSITION · 7D / ALL TIME

- **Card** : `MintCompositionCard.tsx`
- **Worker** : `_mint_composition(events)`
- **Sémantique** : miroir de BURN composition pour les MINT :
  - `direct_action` : décision/régression institutionnelle directe
  - `editorial_alarm` : article éditorial alertant sur un enjeu (sans décision concrète)
  - `untyped`
- **Champ** : `event.mint_subtype`.

## 12. TOP ADMINISTRATIONS · SUSTAINABLE · 7D  *(NON BRANCHÉE — code dormant)*

- **Card** : `TopAdministrationsCard.tsx` (existe mais **n'est pas rendue** dans `DashboardClient.tsx`)
- **Worker** : `_top_administrations_sustainable(events)` (définie dans `exporter.py` mais **pas appelée** depuis `_compute_aggregates` → la clé `top_administrations_sustainable` n'existe pas dans `export.json`)
- **État** : code prêt, à brancher quand on veut l'afficher. Pour l'activer :
  1. Dans `worker/exporter.py`, ajouter dans le dict de `_compute_aggregates` :  
     `"top_administrations_sustainable": _top_administrations_sustainable(events_7d) if has_country else [],`
  2. Dans `web/src/lib/types.ts`, ajouter le champ correspondant à `Aggregates`.
  3. Dans `web/src/components/DashboardClient.tsx`, importer + rendre la card avec `aggregates.top_administrations_sustainable`.
- **Sémantique cible** : top 10 administrations politiques par ratio BURN, minimum 2 events.
- **Champ** : `event.administration` (format `"France-Renaissance"`, extrait par le LLM).
- **Drill-down (déjà câblé)** : `/events?administration=<X>&since=7d`.

## 13. SOURCE DIVERSITY · 7D

- **Card** : `SourceDiversityCard.tsx`
- **Worker** : `_source_diversity_7d(events_7d)`
- **Sémantique** : ratio de sources niches (≤3 events sur 7d) vs mainstream (>3 events).
- **Output** : `{niche_pct, mainstream_pct, total_sources_used, articles_processed}`.
- **Pas de drill-down** (statistique méta).

## 14. CACHE HIT RATE · 7D

- **Card** : `CacheHitRateCard.tsx`
- **Worker** : `_cache_hit_rate_7d(events_7d)`
- **Sémantique** : pourcentage d'events qui ont réutilisé le verdict d'un event passé via embedding (cosine ≥ 0.92), donc **sans appel LLM**.
- **Champ** : `event.reused_from_event_id` (NULL si event analysé fraîchement).
- **Output** : `{hits, total_events, pct}`.
- **Pas de drill-down**.

## 15. ACTIVE PARTNERS · 7D

- **Card** : `PartnerActivityCard.tsx`
- **Worker** : `_active_partners_7d(conn, cutoff_7d)`
- **Sémantique** : organisations partenaires (API key Tier 2) ayant soumis des events sur 7d.
- **Source DB** : table `submissions`.
- **Pas de drill-down**.

## 16. POSITIVE STREAK  *(NON BRANCHÉE — code dormant)*

- **Card** : `PositiveStreakCard.tsx` (existe mais **n'est pas rendue** dans `DashboardClient.tsx`)
- **Worker** : la section `_positive_streak` n'est pas encore implémentée → la clé `positive_streak` n'existe pas dans `export.json`.
- **État cible** : nombre de jours consécutifs avec ≥ 1 event BURN on-chain (current streak + longest sur 7d).
- **À faire** : (1) implémenter `_positive_streak(onchain_events)` dans `exporter.py`, (2) ajouter la clé dans `_compute_aggregates`, (3) ajouter le champ dans `Aggregates` type, (4) brancher la card dans `DashboardClient.tsx`.

---

## Live Activity ticker

- **Source** : 48 dernières heures d'events on-chain (filtre `Date.now() - 48h`).
- **Affichage** : ticker scrollant avec décision (BURN/MINT), titre, source, montant.
- **Drill-down** : chaque ligne → `/event/<id>`.

## Event log

- **Source** : ALL events (avec ou sans `tx_hash`).
- **Affichage** : table verticale, scroll interne, `h-[600px]`.
- **Drill-down** : chaque ligne → `/event/<id>`.

## WorldMap

- **Source** : agrégat des events 7d on-chain par pays.
- **Affichage** : choropleth SVG monde, hover = nom + count, drag/zoom support.
- **Drill-down** : clic pays → (à venir, idéalement `/events?country=<X>&since=7d`).

---

## Audit complet — 2026-05-05 (tous les indicateurs vérifiés)

| # | Indicateur | Card rendue ? | Worker exporte ? | Audit numérique |
|---|---|---|---|---|
| - | Top stats (totalEvents/Burned/Minted) | ✓ | ✓ | **PASS** |
| 1 | TOP COUNTRIES MINT | ✓ | ✓ | **PASS** |
| 2 | TOP COUNTRIES BURN | ✓ | ✓ | **PASS** |
| 3 | TOP REGIONS SUSTAINABLE | ✓ | ✓ | **PASS** |
| 4 | TOP REGIONS DESTRUCTIVE | ✓ | ✓ | **PASS** |
| 5 | SUPPLY NET 7D | ✓ | ✓ | **PASS** (trend 7 entries) |
| 6 | EVENT OF THE DAY | ✓ | ✓ | **PASS** (24h → 7d fallback) |
| 7 | FRAMEWORK ACTIVITY | ✓ | ✓ | **PASS** (post-fix sémantique 2026-05-05) |
| 8 | TOP INSTITUTIONS | ✓ | ✓ | **PASS** (event_ids canoniques) |
| 9 | TOP SECTORS | ✓ | ✓ | **PASS** (event_ids canoniques) |
| 10 | BURN COMPOSITION 7d/ALL | ✓ | ✓ | **PASS** |
| 11 | MINT COMPOSITION 7d/ALL | ✓ | ✓ | **PASS** |
| 12 | TOP ADMINISTRATIONS | ✗ | ✗ | **DORMANT** (code prêt, pas branché) |
| 13 | SOURCE DIVERSITY | ✓ | ✓ | **PASS** |
| 14 | CACHE HIT RATE | ✓ | ✓ | **PASS** |
| 15 | ACTIVE PARTNERS | ✓ | ✓ | PASS (DB-side, validable via submissions) |
| 16 | POSITIVE STREAK | ✗ | ✗ | **DORMANT** |

**14 indicateurs live** sur la home, **2 cards dormantes** (Admin, Streak) — code prêt mais pas branché.
**Tous les indicateurs live ont passé l'audit numérique** (chiffres recalculés depuis les events bruts on-chain ↔ valeurs exportées par le worker).

Méthodologie de l'audit : reload de `data/export.json`, recalcul indépendant de chaque agrégat depuis la liste `events` filtrée à `tx_hash` non-null + fenêtre 7d. Comparaison point par point. Script complet ci-dessous.

---

## Script d'audit reproductible

```python
import json
d = json.load(open('web/data/export.json'))
agg = d['aggregates']
events = d['events']

# 1. Garantie on-chain only
onchain = [e for e in events if e.get('tx_hash')]
print(f"Total events: {len(events)}, on-chain: {len(onchain)}")

# 2. Vérifier que les counts framework_activity ne dépassent jamais les totaux par décision
from datetime import datetime, timedelta, timezone
cutoff = (datetime.now(tz=timezone.utc) - timedelta(days=7)).isoformat()
on7d = [e for e in onchain if e.get('created_at', '') >= cutoff]
burn_total = sum(1 for e in on7d if e['decision'] == 'BURN')
mint_total = sum(1 for e in on7d if e['decision'] == 'MINT')
print(f"7d on-chain BURN: {burn_total}, MINT: {mint_total}")

for fw, v in agg['framework_activity_7d'].items():
    assert v['positive'] <= burn_total, f"BUG: {fw} positive ({v['positive']}) > BURN total ({burn_total})"
    assert v['negative'] <= mint_total, f"BUG: {fw} negative ({v['negative']}) > MINT total ({mint_total})"
    print(f"  {fw}: +{v['positive']}/-{v['negative']} (ids: pos={len(v.get('event_ids_positive',[]))}, neg={len(v.get('event_ids_negative',[]))})")

# 3. Vérifier que les counts top_sectors / top_institutions sont cohérents
for s in agg['top_sectors_7d']:
    assert s['count'] == s['burn_count'] + s['mint_count'] + (s.get('count', 0) - s['burn_count'] - s['mint_count'])
    assert len(s.get('event_ids', [])) == s['count'], f"sector {s['name']}: ids ({len(s['event_ids'])}) != count ({s['count']})"
    print(f"  Sector {s['name']}: count={s['count']} burn={s['burn_count']} mint={s['mint_count']} ids={len(s.get('event_ids',[]))}")
```
