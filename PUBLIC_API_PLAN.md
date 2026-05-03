# PUBLIC_API_PLAN — API publique CARBON WORLD

> **Décision** : 2026-04-20 (session Opus 4.7)
> **Statut** : draft, en attente de validation Cyril avant implémentation
> **Contexte parent** :
> - `CLAUDE.md` § "Plan partenariats — Cheval de Troie API gratuite contre logo"
> - `CLAUDE.md` § "Monétisation — API premium secteur privé"
> - `CLAUDE.md` § "Feuille de route immédiate — Exposer /api/v1/events public rate-limited"
> - `CLAUDE.md` § 0 (reframe 2026-04-20, retravailler la pêche)

---

## 🎯 Pourquoi maintenant

L'API est **l'infrastructure centrale** de la stratégie produit de CARBON WORLD. Trois mouvements convergent pour imposer sa livraison maintenant :

1. **Cheval de Troie institutionnel** (CLAUDE.md, décision 2026-04-18) : accès API gratuit pour ONG / médias / think tanks / chercheurs en échange de logo sur `/partenaires` + citation. Cible immédiate : Vakita, The Shift Project, IDDRI, Reporterre, Greenpeace FR, Fondation GoodPlanet, Institut Veolia.

2. **Monétisation B2B** (CLAUDE.md) : tier Enterprise payant pour départements RSE, banques, assureurs, fonds d'impact (500-2 000 €/mois). Un seul client = salaire Cyril.

3. **Résolution des feeds RSS cassés de 20 ONG-cibles** (Phase 1, 2026-04-20) : Global Witness, HRW, ClientEarth, Survival International, IEN, WWF, IUCN, Oxfam, FERN, WECAN, Amazon Frontlines, etc. — toutes alignées mission mais inaccessibles en scraping. Seule solution : leur proposer d'**écrire** via API.

Une API unique, trois tiers, trois publics.

---

## 🏗 Architecture

### Tier 1 — Public free (lecture seule)

Pas d'authentification. Rate limit par IP.

```
GET /api/v1/events                    Paginated list of scored events
GET /api/v1/events/:id                Single event with full 4D analysis
GET /api/v1/stats                     Global stats (supply, burn/mint ratio, event count)
GET /api/v1/sources                   List of RSS sources (region, category, language)
GET /api/v1/health                    Liveness probe
```

- Rate limit : **100 req/jour/IP** (sliding window)
- Format : JSON + éventuellement CSV pour `/events`
- CORS ouvert (`Access-Control-Allow-Origin: *`) pour embed externe
- Headers standards : `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`
- Documentation OpenAPI 3.1 servie sur `/api/v1/openapi.json` + UI Swagger sur `/api/docs`

**Publics cibles** : étudiants, citoyens, développeurs curieux, médias qui veulent un aperçu.

### Tier 2 — Partner (lecture illimitée + écriture)

Authentification : Bearer token. Clés générées manuellement via CLI (`worker/generate_api_key.py <org> <tier>`). Stockage : table SQLite `api_keys` (colonnes : `key_hash`, `organization`, `contact_email`, `tier`, `created_at`, `read_quota_daily`, `write_quota_daily`, `revoked_at`).

```
GET /api/v1/events                    Unlimited, includes drafts + pending review
GET /api/v1/events/:id                Full detail + audit trail
GET /api/v1/events/:id/on-chain       Solana TX verification data
GET /api/v1/stats                     Extended stats, region breakdown, SDG heatmap

POST /api/v1/events                   Submit a new event for scoring
POST /api/v1/events/:id/comment       Annotate an existing event (partners' context)
```

- Rate limit : **read illimité**, **write 5 events/jour/clé** (anti-spam)
- Auth : `Authorization: Bearer <api_key>`
- Conditions d'accès : affichage logo CARBON WORLD sur le site du partenaire + citation systématique quand des données de l'API sont reprises

**Publics cibles initiaux (gratuit, contre logo)** :

| Type | Exemples |
|---|---|
| **Médias indépendants climat** | Vakita, Reporterre, Mediapart, Brut, Le Media, Blast |
| **Think tanks** | The Shift Project, IDDRI, Institut Veolia, Fondation GoodPlanet, The B Team, Climate Institute |
| **ONG litige / terrain** | Global Witness, Human Rights Watch, ClientEarth, Amnesty International, Earthjustice, Survival International, Indigenous Environmental Network, Center for Biological Diversity, WWF, IUCN, Oxfam, FERN, WECAN, Amazon Frontlines, Minority Rights Group, Rainforest Action Network, FoE Europe, Third World Network, Fairtrade International, Conservation International |
| **Chercheurs individuels** | Chercheurs GIEC/IDDRI identifiés via LinkedIn |
| **Écoles / universités** | Institut Veolia, Sciences Po École des affaires internationales, IRD Paris, CNRS |

### Tier 3 — Enterprise (monétisation B2B)

Même infrastructure que Tier 2 mais facturation mensuelle + SLA + support.

- 500 €/mois : 1000 events/jour en lecture, 50 en écriture, export CSV/Parquet mensuel
- 2 000 €/mois : illimité, export temps réel via webhook, consulting trimestriel

**Publics cibles** : entreprises RSE (Axa, Danone, Total énergies, BNP Paribas, L'Oréal), cabinets conseil (EY, Deloitte, PwC), fonds d'impact (Generation IM, Impact Partners). Un seul signe = €6k/an = salaire de base Cyril.

Pas d'outreach immédiat sur ce tier — on l'ouvre officiellement **après** avoir 3-5 logos institutionnels visibles sur `/partenaires` (crédibilité prérequise).

---

## 📄 Spec POST `/api/v1/events`

Utilisé par les partenaires Tier 2 pour pousser leurs events.

### Payload JSON

```json
{
  "title": "Court victory halts Belo Sun gold mining in the Amazon",
  "description": "500-2000 chars EN/FR/ES/PT. What happened, who acted, where, when, measurable impact. Factual tone, no marketing.",
  "source_url": "https://amazonwatch.org/news/2026/0420-belo-sun-ruling",
  "published_at": "2026-04-20T14:30:00Z",
  "organization": "Amazon Watch",
  "event_type": "legal_win",
  "region": "BR / Amazon",
  "sdgs_hint": [13, 15, 16, 17],
  "evidence_urls": [
    "https://courtfiling.br/case-2026-0432",
    "https://mongabay.com/2026/04/belo-sun-confirmed"
  ],
  "language": "en"
}
```

### `event_type` — énumération fermée

- `legal_win` — victoire juridique / réglementaire
- `community_action` — action communautaire mesurable
- `conservation_win` — résultat écologique mesurable
- `indigenous_rights` — reconnaissance / victoire droits autochtones
- `labor_rights` — victoire syndicale / travailleur / ILO
- `policy_influence` — politique publique infléchie
- `whistleblower` — lanceur d'alerte / rapport d'investigation
- `corporate_regression` — décision corporate régressive (pour MINT)
- `institutional_decision` — grande décision institutionnelle (BURN ou MINT)

### Traitement par le pipeline

Le classifier 7-agents **reste exécuté** sur chaque soumission — pas de bypass. Cohérence éthique maintenue. Mais l'event arrive annoté :

- `source_type = "partner_direct"` (vs `"rss_scraped"`)
- `trust_weight = 1.0` (vs 0.7 pour RSS)
- `prior_validation = true` → passé dans le prompt de l'Analyst ("This event was submitted directly by a verified partner organization. Treat the source as reliable while still evaluating all dimensions.")

Effet : réduit les faux-INVALID sur les events légitimes mais au phrasing non-mainstream (cas Mozambican women cooperative), tout en gardant la rigueur du scoring.

### Réponse

```json
{
  "status": "accepted",
  "submission_id": "sub_20260420_amazonwatch_001",
  "queue_position": 3,
  "estimated_scoring_time_seconds": 180,
  "callback_url": "https://carbon-world.xyz/api/v1/submissions/sub_20260420_amazonwatch_001"
}
```

Le partenaire peut poller la `callback_url` ou recevoir un webhook si configuré (`POST /api/v1/keys/:id/webhook` pour l'enregistrer).

---

## 🛠 Infrastructure à construire

### Côté web (Next.js 16 sur VPS)

Fichiers à créer :

```
web/app/api/v1/
├── events/
│   ├── route.ts              GET list + POST submit
│   └── [id]/
│       ├── route.ts          GET single event
│       ├── on-chain/
│       │   └── route.ts      GET Solana verification
│       └── comment/
│           └── route.ts      POST annotation
├── stats/
│   └── route.ts              GET global stats
├── sources/
│   └── route.ts              GET source list
├── submissions/
│   └── [id]/
│       └── route.ts          GET submission status (callback target)
├── keys/
│   └── [id]/
│       └── webhook/
│           └── route.ts      POST register webhook URL
├── health/
│   └── route.ts              GET liveness
└── openapi.json/
    └── route.ts              GET OpenAPI 3.1 spec

web/lib/api/
├── auth.ts                   Bearer token verification + key lookup
├── rate-limit.ts             Sliding-window rate limiter (in-memory + optional Redis later)
├── schema.ts                 zod schemas for POST /events validation
└── response.ts               Standard response helpers (success, error, rate-limit headers)

web/app/api/docs/
└── page.tsx                  Swagger UI (lightweight static page)
```

### Côté DB (SQLite)

Nouvelles tables :

```sql
CREATE TABLE api_keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key_hash TEXT NOT NULL UNIQUE,                 -- SHA-256 of the raw key
    organization TEXT NOT NULL,
    contact_email TEXT NOT NULL,
    tier TEXT NOT NULL CHECK (tier IN ('partner', 'enterprise')),
    read_quota_daily INTEGER NOT NULL DEFAULT 0,   -- 0 = unlimited
    write_quota_daily INTEGER NOT NULL DEFAULT 5,
    webhook_url TEXT,
    created_at TEXT NOT NULL,
    last_used_at TEXT,
    revoked_at TEXT,
    notes TEXT                                     -- free-form internal memo
);

CREATE TABLE api_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    api_key_id INTEGER REFERENCES api_keys(id),
    ip_address TEXT,                               -- for public tier (no api_key_id)
    endpoint TEXT NOT NULL,
    method TEXT NOT NULL,
    status_code INTEGER NOT NULL,
    timestamp TEXT NOT NULL
);
CREATE INDEX idx_api_usage_key_date ON api_usage(api_key_id, timestamp);
CREATE INDEX idx_api_usage_ip_date ON api_usage(ip_address, timestamp);

CREATE TABLE submissions (
    id TEXT PRIMARY KEY,                           -- e.g. sub_20260420_amazonwatch_001
    api_key_id INTEGER REFERENCES api_keys(id),
    raw_payload_json TEXT NOT NULL,
    received_at TEXT NOT NULL,
    processed_at TEXT,
    resulting_event_id INTEGER REFERENCES carbon_events(id),
    status TEXT NOT NULL CHECK (status IN ('pending', 'classifying', 'scored', 'rejected_invalid', 'rejected_duplicate'))
);
```

### Côté worker Python

Modifications :

- `worker/collector.py` (ou équivalent) : au début de chaque run, vérifier la table `submissions` pour les `status='pending'` et les merger dans la file du classifier avec `source_type="partner_direct"`, `trust_weight=1.0`
- `worker/prompts/analyst_prompt.py` : support d'une section conditionnelle en user_msg si `prior_validation=true` ("This event was submitted directly by a verified partner organization…")
- `worker/generate_api_key.py` : nouveau script CLI pour générer une clé (32 chars, SHA-256 stocké en DB, plain text affiché 1 fois et jamais resaved)

### Sécurité

- Clés générées avec `secrets.token_urlsafe(32)`, hash SHA-256 en DB
- Pas de JWT pour simplicité — les Bearer keys sont des opaque tokens
- Rate limiting en mémoire (Map<string, number[]>) avec purge horaire ; Redis optionnel si charge > 10k req/jour
- CORS : `*` pour GET public, restreint par origin pour POST partner (validé contre `partner_origin` dans la table api_keys)
- HSTS déjà en place via Caddy (audit 2026-04-18)
- Input validation : zod sur tous les POST payloads, rejette si schema ne match pas avec 422 + détails
- Audit log complet dans `api_usage`

---

## 📮 Pitch template — inviter un partenaire à rejoindre

### Version française

> **Sujet** : Accès API gratuit à l'indice éthique CARBON WORLD — pour [Nom de l'organisation]
>
> Bonjour [Prénom Nom],
>
> Je suis Neous Axis, fondateur de **CARBON WORLD** — un indice scientifique open-source qui score en temps réel l'impact éthique des décisions humaines affectant le vivant, basé sur 7 référentiels des Nations Unies (17 ODD, UDHR, OIT, CRC, UNDRIP, droits des animaux, limites planétaires). Le token CBWD existe sur Solana uniquement comme **preuve cryptographique d'intégrité** des analyses — c'est un outil scientifique, pas un actif spéculatif.
>
> Notre pipeline IA lit ~400 articles/jour issus de 157 sources mondiales. Il identifie les décisions à fort impact puis les pondère via un cadre 4D (Snapshot, Trajectoire, Réévaluation, Prospective). Toutes les analyses sont publiques, horodatées on-chain, vérifiables : [carbon-token.xyz](https://carbon-world.xyz).
>
> **Mon offre pour [Nom de l'organisation]** : accès API gratuit et illimité à l'ensemble des events scorés. Concrètement :
>
> - **Lecture** : `GET /api/v1/events` vous donne accès à toutes les décisions scorées (JSON, CSV). Vous pouvez embed un widget sur votre site, citer nos scores dans vos rapports, les réutiliser librement.
> - **Écriture** (optionnel) : `POST /api/v1/events` vous permet de nous pousser directement vos victoires ou observations terrain — elles entrent dans le pipeline scientifique avec une attribution explicite à [Nom de l'organisation].
>
> Contrepartie : logo de [Nom] sur notre section Partenaires sur la home page (PAS une page dédiée — correction Cyril 2026-04-21) (visible sur chaque event pertinent) et citation de [Nom] chaque fois que vos soumissions sont scorées.
>
> Ce n'est pas un partenariat commercial — c'est un **outil de rayonnement scientifique mutuel**. Vos analyses gagnent en visibilité au-delà de vos cercles habituels, notre indice gagne en diversité et en légitimité.
>
> Si vous êtes intéressé·e, je vous envoie une clé API et 2 pages de doc technique dès demain. Une visio de 20 min pour en parler est aussi possible.
>
> Bien cordialement,
> **Neous Axis** — Fondateur, CARBON WORLD
> hello@carbon-world.xyz | [carbon-world.xyz](https://carbon-world.xyz)

### Version anglaise

> **Subject**: Free API access to the CARBON WORLD ethical index — for [Organization]
>
> Dear [First Last],
>
> I'm Neous Axis, founder of **CARBON WORLD** — an open-source scientific index that scores in real time the ethical impact of human decisions affecting the living world, based on seven UN reference frameworks (17 SDGs, UDHR, ILO, CRC, UNDRIP, Animal Rights, Planetary Boundaries). The CBWD token lives on Solana solely as **cryptographic proof of integrity** — it's a scientific instrument, not a speculative asset.
>
> Our AI pipeline reads ~400 articles/day from 157 worldwide sources. It flags high-impact decisions and weighs them through a 4D framework (Snapshot, Trajectory, Revaluation, Prospective). All analyses are public, on-chain timestamped, verifiable: [carbon-token.xyz](https://carbon-world.xyz).
>
> **My offer for [Organization]**: free, unlimited API access to the full scored event stream. In practice:
>
> - **Read**: `GET /api/v1/events` gives you access to every scored decision (JSON, CSV). Embed a widget on your site, cite our scores in your reports, reuse freely.
> - **Write** (optional): `POST /api/v1/events` lets you push your own victories or field observations — they enter the scientific pipeline with explicit attribution to [Organization].
>
> In exchange: your logo on our `/partners` page (shown on every relevant event) and attribution whenever your submissions get scored.
>
> This is not a commercial partnership — it's a **mutual scientific amplification tool**. Your analyses reach audiences beyond your usual circles, our index gains diversity and legitimacy.
>
> If interested, I can send you an API key and 2 pages of technical docs tomorrow. A 20-minute call to discuss is also possible.
>
> Best regards,
> **Neous Axis** — Founder, CARBON WORLD
> hello@carbon-world.xyz | [carbon-world.xyz](https://carbon-world.xyz)

---

## 🎯 Cibles outreach prioritaires — 3 vagues

### Vague 1 (Semaine 1) — médias + think tanks francophones (déjà prévu dans CLAUDE.md stratégie 2026-04-18)

1. **Vakita** (média indé climat/tech)
2. **The Shift Project** (équipe Jancovici)
3. **IDDRI**
4. **Reporterre**
5. **Greenpeace France**
6. **Fondation GoodPlanet**
7. **Institut Veolia**
8. **Mediapart** (section écologie)

Priorité absolue : ils ont déjà une communauté engagée, leur citation aurait un effet boule de neige immédiat sur la crédibilité.

### Vague 2 (Semaine 2) — ONG internationales litige / terrain (résolution des feeds cassés)

1. **Global Witness**
2. **Human Rights Watch**
3. **ClientEarth**
4. **Amnesty International**
5. **Survival International**
6. **Indigenous Environmental Network**
7. **Amazon Frontlines**
8. **WECAN International**
9. **Third World Network**
10. **Minority Rights Group**

Double bénéfice : fournissent des events écrits (cas d'usage write), et leur citation consolide la crédibilité droits humains / Sud global.

### Vague 3 (Semaine 3-4) — grandes institutions conservation

1. **WWF International**
2. **IUCN**
3. **Oxfam International**
4. **FERN**
5. **Conservation International**
6. **Rainforest Action Network**
7. **Friends of the Earth Europe**
8. **Center for Biological Diversity**
9. **Sierra Club**
10. **Fairtrade International**

Temps de réponse lent attendu (grosses structures). Maintenir la relance à 2 semaines + 6 semaines.

---

## 🛠 Séquençage de livraison

| Étape | Durée estimée | Bloquant |
|---|---|---|
| 1. Validation Cyril de ce plan (archi, spec, pitch, cibles) | discussion | ← **on est ici** |
| 2. Implémentation routes GET (events, stats, sources, health, openapi.json) | 1 j dev | dépend 1. |
| 3. Implémentation auth Bearer + table api_keys + CLI generate_api_key.py | 0.5 j | dépend 1. |
| 4. Implémentation rate-limiting Tier 1 (IP-based) | 0.5 j | dépend 2. |
| 5. Implémentation POST /events + table submissions + intégration pipeline | 1 j | dépend 2+3. |
| 6. Documentation OpenAPI + Swagger UI | 0.5 j | parallèle à 5. |
| 7. Tests (unit + integration) + déploiement VPS | 0.5 j | dépend 5+6. |
| 8. Section Partenaires sur la home page sur le frontend | 0.5 j | parallèle à 5-7. |
| 9. Envoi vague 1 (8 emails médias+think tanks FR) | 1-2h (écriture + envoi manuel Cyril) | dépend 7+8. |
| 10. Itération vagues 2 + 3 selon retours vague 1 | — | feedback-dépendant |

**Total avant premier envoi** : ~4 jours de dev + outreach manuel Cyril.

---

## ⚠️ Risques et contraintes

1. **Personne ne répond vague 1** → on continue avec les 157 sources RSS. L'API reste utile en lecture publique, aucun coût additionnel.
2. **Un partenaire abuse le quota write** → rate-limit 5/j + possibilité de révocation (`revoked_at`). Audit trail complet dans `api_usage`.
3. **Spam via POST /events par un partenaire compromis** → le classifier rejette les events non-actionnables (INVALID). `trust_weight=1.0` ne contourne pas la validation factuelle.
4. **GDPR / données personnelles** → les payloads ne contiennent aucune donnée personnelle au-delà du nom de l'organisation émettrice (publique). `contact_email` = email pro d'un·e responsable, consenti par la signature du partenariat.
5. **Attaque DDoS sur API publique** → Caddy en amont + rate-limit IP-based à 100/jour → largement dissuasif. Cloudflare non nécessaire à ce stade.
6. **Montée en charge** → pipeline classifier déjà le bottleneck. Si on reçoit 100 submissions/jour, on les queue. Pas de risque DB ou endpoint.

---

## 📌 Décision requise avant passage au code

Cyril valide (ou ajuste) :

- [ ] L'architecture 3 tiers (Public free lecture, Partner Bearer lecture+écriture, Enterprise payant plus tard)
- [ ] Les routes GET (events, events/:id, stats, sources, health, openapi.json) et POST (events, events/:id/comment, keys/:id/webhook)
- [ ] Rate limit Tier 1 : **100 req/jour/IP** pour lecture publique (ajustable)
- [ ] Rate limit Tier 2 écriture : **5 events/jour/clé** partner
- [ ] Comportement pipeline : pas de bypass classifier, `source_type="partner_direct"`, `trust_weight=1.0`, `prior_validation=true` en prompt
- [ ] `event_type` énumération fermée (legal_win, community_action, conservation_win, indigenous_rights, labor_rights, policy_influence, whistleblower, corporate_regression, institutional_decision)
- [ ] La liste des 3 vagues d'outreach (8 FR médias/thinks, 10 ONG internationales, 10 grandes institutions)
- [ ] Le pitch email FR/EN (ton, longueur, proposition visio 20 min)
- [ ] Le séquençage (~4 j dev + outreach Cyril) et l'ordre de développement (GET d'abord, POST après)
- [ ] Tier Enterprise : on documente dès maintenant mais on n'active le billing qu'après 3-5 logos visibles sur `/partenaires`

Une fois validé, je délègue l'implémentation à Sonnet avec ce document comme spec autoritaire.
