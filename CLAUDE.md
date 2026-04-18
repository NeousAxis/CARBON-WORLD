# CARBON WORLD — Plan du projet

> **Projet** : Token Solana (CBWD) piloté par une IA cloud (Groq/Qwen3-32b) qui mesure les décisions humaines affectant le vivant et ajuste le supply en conséquence (BURN = positif, MINT = négatif).
> **Fondateur** : Cyril Leger (Neous Axis)
> **État au 2026-04-17** : Mainnet actif, pipeline sur VPS Hetzner (€4.31/mois), passkey auth sur /review, repo public.

---

## 🎯 Contexte (NE PAS REDEMANDER)

### Ce qui existe déjà
- **Token CBWD** sur **Solana mainnet** (migration 2026-04-16) :
  - Decimals : 6, Symbol : CBWD, Name : Carbon World
  - Mint authority : `2LJspFTWw5VFTZjRNo9Va1VQTEjARAjSuCH7LR6K8AZW`
- **VPS Hetzner** (projet "CARBON WORLD", Falkenstein) :
  - IPv4 : `157.90.250.40`
  - Ubuntu 24.04, CX23 (2 vCPU / 4GB / 40GB), €4.31/mois
  - User `carbon` (sudo NOPASSWD), Python 3.12 + venv
  - Deploy key GitHub `vps-hetzner-writer` (read-write)
  - Cron 15 min : `~/CARBON-WORLD/launcher/run_vps.sh`
- **Frontend** : Next.js 16 **hébergé sur le VPS**, passkey auth /review (WebAuthn)
  - Service systemd : `carbon-web.service` → `next-server` sur `:3000`
  - Reverse proxy : **Caddy** (80/443) avec certificat Let's Encrypt auto
  - URL prod : `https://carbon-token.xyz` (A record Infomaniak → 157.90.250.40)
  - **Vercel désactivé** (2026-04-17) — GitHub integration débranchée, plus aucun deploy cloud
  - Passkey registré (Touch ID), env vars `SESSION_SECRET` / `PASSKEY_CREDENTIAL` / `RP_ID=carbon-token.xyz` / `RP_ORIGIN=https://carbon-token.xyz` côté VPS
- **Domaine** : `carbon-token.xyz` → VPS (A 157.90.250.40, AAAA IPv6). `www` CNAME vercel-dns reliquat à nettoyer.
- **Livre blanc** : `~/Library/Mobile Documents/com~apple~CloudDocs/CARBON-TOKEN/`
- **Repo GitHub** : `https://github.com/NeousAxis/CARBON-WORLD` (PUBLIC depuis 2026-04-17)

### Architecture finale
- Worker **Python natif** (plus de n8n, plus de Ollama local)
- IA **cloud Groq** : `qwen/qwen3-32b` via API (classifier + analyst) + `llama-3.3-70b-versatile` (analyst B)
- Déclenchement **cron 15 min** sur VPS Hetzner (plus de launchd)
- Data : SQLite local sur VPS + export JSON committé sur GitHub main
- Le cron VPS détecte les changements dans `web/` (hors `web/data/`) et rebuild Next.js + `systemctl restart carbon-web` automatiquement

---

## 🧠 Cadre décisionnel IA (version enrichie)

### Étape 1 — Validation
Est-ce une action concrète gouvernementale / institutionnelle ? Si non → `validation=false`, stop.

### Étape 2 — Analyse duale éthique (CŒUR DU SYSTÈME)
Pour CHAQUE événement, identification systématique des aspects positifs ET négatifs au travers des **7 référentiels** :
1. 17 UN Sustainable Development Goals
2. Universal Declaration of Human Rights (1948)
3. ILO Core Labor Standards
4. Universal Declaration of Animal Rights (1978)
5. UN Convention on the Rights of the Child
6. UN Declaration on the Rights of Indigenous Peoples
7. Planetary Boundaries (9 limites scientifiques)

→ `positive_aspects[]` (desc + sdgs + magnitude 1-10)
→ `negative_aspects[]` (desc + sdgs + violated_rights + magnitude 1-10)
→ `ethical_synthesis` (paragraphe texte)

### Étape 3 — Cadre 4D appliqué à la position NETTE
| Dimension | Poids | Question |
|---|---|---|
| SNAPSHOT | 25% | Impact net aujourd'hui (positifs − négatifs) |
| TRAJECTORY | 20% | Direction de la tendance sous-jacente |
| REVALUATION | 15% | Triggers qui pourraient basculer le jugement |
| PROSPECTIVE | 40% | 3 scénarios futurs du net (2-30 ans) |

### Étape 4 — Décision
**Score final = Snapshot × 0.25 + Trajectory × 0.20 + Revaluation × 0.15 + Prospective × 0.40**
- Score ≥ 6 → **BURN**
- Score ≤ 4 → **MINT**
- Entre → **NEUTRAL**

### Étape 5 — Montant CBWD
**Amount = Base_scale × |Score| × Context_multiplier × (Confidence/10)**

Échelles : Local 1K-10K · Régional 10K-100K · National 100K-1M · International 1M-10M

### Exemple intégré (Coupe du Monde Qatar)
- **Positive** : infrastructure (+SDG 9, 11), dev économique (+SDG 8)
- **Negative** : morts travailleurs migrants (−SDG 3, 8, 10, 16 + UDHR Art. 4, 23, ILO), empreinte carbone désert (−SDG 13)
- **Synthesis** : violations systématiques des droits humains et décès l'emportent largement sur les bénéfices
- **Décision** : MINT (punitif)

### ⚠ Règles d'écriture des prompts & classes de bugs

Le cadre 7 référentiels + 4D est solide, mais le LLM sous-jacent commet des erreurs récurrentes de calibration et de contexte. Source de vérité dédiée : **[AGENTS_PROMPT_RULES.md](AGENTS_PROMPT_RULES.md)**.

Contient :
- Principes de design (pas de checklists rigides, ancrage quantitatif, règle des 2+ occurrences avant patch)
- Calibration des échelles (magnitude, confidence, scores 4D) avec ancrages chiffrés
- Classes de bugs recensées (nivellement magnitudes ✅ fixé 2026-04-18, hallucination structurelle, tension ordre/signal moral)
- Anti-patterns (règles qu'on a été tenté d'ajouter mais rejetées, avec raison)
- Historique des modifs de prompt (commit, impact mesuré)
- Process pour ajouter une nouvelle règle (toujours avec A/B test de score)

**À lire avant tout patch de prompt analyst / classifier / reconciler / sentinel.**

---

## 🏗 Architecture technique — Pipeline 8 agents (mainnet)

```
VPS Hetzner cron (*/15 min)
  → launcher/run_vps.sh
    → git pull + worker/main.py + git push export

Pipeline (8 phases) :
┌──────────────┐
│  COLLECTOR    │  Pure Python, 0 LLM
│  46 sources   │  ~30s, round-robin mondial
│  RSS + dedup  │
└──────┬───────┘
       ↓ raw articles
┌──────────────┐
│  CLASSIFIER   │  Groq qwen3-32b, think=false
│  Triage       │  ~2s / article avec rate-limit 2s
│  valid/invalid│  50 articles cap / run
└──────┬───────┘
       ↓ only VALID (~20-30%)
┌──────────────┐
│  ANALYST A    │  Groq qwen3-32b (analyse 4D complète)
│  ANALYST B    │  Groq llama-3.3-70b-versatile (lecture indépendante)
│  dual reading │  Prompts 6600 chars, rate-limit 8s
└──────┬───────┘
       ↓ A + B verdicts merged
┌──────────────┐
│  RECONCILER   │  Arbitre les désaccords A/B
└──────┬───────┘
       ↓
┌──────────────┐
│  SENTINEL     │  Coherence check final (GPT-OSS-120B ou équivalent)
│  anti-bug     │  Flag scale mismatch, polarity errors, etc.
└──────┬───────┘
       ↓ ok → Writer / flagged → review_queue
┌──────────────┐
│  SCORER       │  Pure Python, formules + montant CBWD
│  WRITER       │  SQLite + Solana mainnet TX
│  EXPORTER     │  export.json (events) + review_queue.json
│  REPORTER     │  Résumé run, logs structurés
└──────────────┘
       ↓
  Solana mainnet (mint authority signer)
       ↓
  git push → GitHub → VPS cron rebuild Next.js + restart carbon-web → /api/review/queue (auth-gated)
```

**Temps estimé** : ~3 min/run (Groq cloud, pas de GPU local)

**Modèles LLM — stratégie multi-providers free tier** :

L'archi multi-agents est **parallèle par design** (Analyst A || Analyst B dans un ThreadPoolExecutor) pour éviter un ralentissement ~20× vs séquentiel. Le free tier Groq (30 RPM par modèle + plafond compte global) sature quand A et B partent en même temps → 429 fréquents en prod.

**Solution : éclater la charge sur plusieurs providers free tier**, un compte/provider par "voie" d'appel, buckets de quota indépendants.

| Agent | Provider | Modèle | RPM free |
|---|---|---|---|
| Classifier | **Groq** | `qwen/qwen3-32b` | 30 |
| Analyst A | **Groq** | `qwen/qwen3-32b` (même compte/modèle que classifier, OK car appels séquentiels après classif) | 30 |
| Analyst B | **Cerebras** (à configurer) | `llama-3.3-70b` | 30 |
| Reconciler | **Groq** | `qwen/qwen3-32b` | (ré-utilise quota) |
| Sentinel | **Groq** | `openai/gpt-oss-120b` (ou équivalent) | 30 |

Extension possible : Gemini free (15 RPM) ou OpenRouter free pour un 3e bucket de failover.

Chaque provider a sa propre variable `.env` (`GROQ_API_KEY`, `CEREBRAS_API_KEY`, etc.), le client LLM (`worker/ollama_client.py`) route l'appel en fonction de l'agent appelant.

**Gain attendu** : parallèle A||B sans collision de quota → 0 € / mois, 0 429 en prod.

**Fallback payant si insuffisant** : Groq paid tier ~$3-5 / mois, drop-in (juste upgrade de la clé, pas de changement code).

**Solana mainnet** :
- Wallet signer : `~/.config/solana/id.json` sur VPS → `2LJspFTWw5VFTZjRNo9Va1VQTEjARAjSuCH7LR6K8AZW`
- Ce wallet est le **mint authority** du token CBWD
- MINT = `mintTo` vers treasury ATA (augmente supply)
- BURN = `burn` depuis treasury ATA (réduit supply)
- Chaque tx enregistrée dans SQLite (`tx_hash`) et visible sur Solana Explorer

**Review queue (safety net)** :
- Events flagués par Sentinel → pas de TX Solana, en attente human review
- Page `/review` sur frontend, protégée par passkey WebAuthn
- CLI : `python worker/resolve_review.py <id> <approve|reverse|reject>`

---

## 🚨 À FAIRE — priorités ouvertes (2026-04-18)

### 1. Élargir les canaux de détection d'actions positives

**Problème identifié** : le pipeline actuel (46 sources RSS institutionnelles/presse) capture surtout les **décisions gouvernementales nationales**. Il rate massivement les **actions positives locales** menées par des communautés, ONG, collectifs citoyens. Exemples concrets mentionnés par Cyril :
- Sauvetage en cours d'une baleine à bosse échouée en Allemagne (2026-04-18)
- Centaines d'actions locales aux USA qui contrent les coupes budgétaires de Trump sur l'environnement (communautés, states blue, coalitions d'ONG)
- Initiatives citoyennes dans le Sud global que les médias occidentaux ne couvrent pas

**Conséquence actuelle** : biais systémique vers le MINT (décisions institutionnelles souvent ambiguës ou régressives) et sous-représentation du BURN (actions positives souvent locales et communautaires, invisibles pour la presse mainstream).

**Pistes** :
- Sources spécialisées positives (déjà partiellement : Positive News, Good News Network, Reasons to be Cheerful — vérifier activité)
- Agrégateurs d'actions communautaires : Mongabay local desks, Grist Solutions, Yes Magazine, Shareable, Commons Transition
- Plateformes d'action collective : campagnes terminées avec succès sur Change.org, Avaaz, WeMove, SumOfUs
- Rapports d'ONG actives : Greenpeace Reports, WWF Conservation News, ClientEarth legal wins, Sea Shepherd operations, Wild Welfare
- Plateformes crowdsourcées : Wikinews "Solutions", Pandemic of Love, Trust for Public Land projects
- Hashtags solutions sur X/Bluesky (#ClimateSolutions, #CommunityAction) via RSSHub self-hosted
- Adapter le classifier pour **accepter comme VALID** : "community-led action with measurable impact", "successful NGO legal challenge", "local conservation win", pas seulement "government decision"

**Impact attendu** : rééquilibrer le ratio BURN/MINT et rendre la token supply reflétant mieux la réalité — le monde n'est pas unilatéralement négatif, il y a un tissu d'actions positives qu'il faut capter.

### 2. Audit sécurité complet + refonte passkey

**Périmètre audit** :
- Code worker Python (prompts injection, secrets leakage, eval/exec, désérialisation JSON)
- VPS Hetzner : firewall, fail2ban, SSH config, Caddy config, TLS cipher suites, en-têtes HTTPS
- Docker : Uptime Kuma isolation, images à jour
- Solana keypair : permissions filesystem, process isolation, backup offline
- DB SQLite : accès filesystem, backups
- API routes Next.js : CORS, CSP, rate limiting, input validation
- Secrets : `.env`, GitHub Secrets, rotation
- Dépendances : npm audit, pip audit, CVE scan des conteneurs Docker
- Supply chain : lockfiles intégrité, git signed commits

**Refaire passkey WebAuthn** :
- La passkey actuelle est liée au MacBook de Cyril uniquement
- Besoins : accès multi-device (iPhone, iPad, backup), credential rotation, procédure de révocation si device perdu
- Envisager : plusieurs passkeys enregistrées OU upgrade vers Passkey sync via iCloud Keychain (déjà compatible avec l'implémentation `@simplewebauthn/server`)
- Documenter la procédure "j'ai perdu mon device, comment je me reconnecte"
- Vérifier que le challenge cookie a une bonne expiration (5 min OK), JWT session HS256 (algo solide)
- Rejouer le flow bootstrap `/review/setup?secret=XXX` avec `SETUP_SECRET` rotated

---

## 📋 Phases de livraison

### ✅ Phase 1 — Worker IA (TERMINÉE)
- [x] Structure Python (venv 3.13, requirements minimal, config .env)
- [x] Fetcher RSS multi-sources — **46 sources mondiales** round-robin anti-biais
- [x] Déduplication via SQLite local (UNIQUE constraint + IntegrityError)
- [x] Client Ollama → `qwen3:32b` (Gemma 4 écarté après échec tests)
- [x] Prompt système enrichi — analyse duale éthique + 7 référentiels + cadre 4D
- [x] Parser JSON strict + fallback regex + validation
- [x] Écriture **SQLite local** (Supabase abandonné car 2-projets/org limit)
- [x] Logs structurés (rotation 10 MB × 3)
- [x] Système `last_run.json` pour rattrapage

### ✅ Phase 2 — Déclenchement automatique (TERMINÉE)
- [x] Plist `launchd` : **3×/jour (08:00, 14:00, 17:00 local)** + RunAtLoad
- [x] Script shell `run.sh` (active venv → python main.py → log horodaté)
- [x] Commande bureau cliquable `~/Desktop/CARBON WORLD - Lancer.command`
- [x] `MIN_HOURS_BETWEEN_RUNS=5` protège contre double-runs
- [x] Installation script : `bash install.sh` + `uninstall.sh`
- [x] Service chargé et testé en conditions réelles

### ✅ Phase 3 — Frontend (TERMINÉE, auto-hébergé sur VPS depuis 2026-04-17)
- [x] Stack : Next.js 16 + Tailwind CSS v4 + TypeScript
- [x] Hébergement prod : **VPS Hetzner** (Caddy reverse proxy + systemd `carbon-web.service` sur :3000)
- [x] Certificat TLS : Let's Encrypt via Caddy (renewal auto)
- [x] Design : **Lunaris Dark** (fond #111111, accent orange #FF8400, JetBrains Mono)
- [x] Source données : JSON export auto (`worker/exporter.py` → `web/data/export.json`)
- [x] Dashboard financier : ticker bar, supply chart SVG, donut breakdown, event log table, live ticker
- [x] Page `/event/[id]` : détail événement + justification éthique + lien Solana Explorer
- [x] Page `/about` : explication du système, 7 référentiels, cadre 4D
- [x] Page `/sources` : liste des 46 sources avec région, catégorie, langue, statut
- [x] Repo GitHub : `https://github.com/NeousAxis/CARBON-WORLD` (public)
- [x] Domaine : `carbon-token.xyz` A → 157.90.250.40, AAAA → 2a01:4f8:c013:7043::1
- [x] Vercel désactivé (2026-04-17) — GitHub integration débranchée

### ✅ Phase 4 — Intégration Solana (TERMINÉE sur devnet)
- [x] Lib Python `solana` (0.36.11) + `solders` (0.27.1)
- [x] Module `worker/solana_executor.py` : mint_to + burn via SPL Token instructions manuelles
- [x] Wallet signer : `~/.config/solana/id.json` → `2LJspFTWw5VFTZjRNo9Va1VQTEjARAjSuCH7LR6K8AZW`
- [x] Ce wallet = **mint authority** du token CBWD sur devnet
- [x] MINT testé : `35GDHHJ...` ✅
- [x] BURN testé : `2LewaQi...` ✅
- [x] Writer intégré : après chaque save en DB, exécute la tx Solana et écrit le `tx_hash`
- [x] `db.update_tx_hash()` pour enregistrer le hash après confirmation

### ⏳ Phase 5 — Mainnet + VPS
- [x] Recréation mint sur mainnet (2026-04-16)
- [x] Migration worker → VPS Hetzner (2026-04-17)
- [x] Migration frontend → VPS Hetzner (2026-04-17)
- [ ] Liquidité initiale DEX — **REPORTÉE** : token reste indicateur scientifique virtuel jusqu'à traction institutionnelle (détails §Stratégie d'activation ci-dessous)
- [ ] Monitoring (Uptime Kuma ou similaire)
- [ ] Ajout Twitter/X via RSSHub Docker OU X API Basic
- [ ] Fix rate-limit Groq 429 via **multi-providers free tier** : Analyst B sur Cerebras (llama-3.3-70b), Groq garde classifier/analyst A/reconciler/sentinel. 0 € / mois, 0 collision de quota.

---

## 🚀 Stratégie d'activation — token indicateur + crédibilité institutionnelle d'abord

**Décision (2026-04-18)** : les deux voies de lancement token (Pump.fun + Raydium manuel) sont **écartées** à ce stade.

**Raisons** :
- Pump.fun impose de créer le token via leur plateforme → nous perdrions notre Mint Authority actuelle, or elle est indispensable pour **arbitrer les décisions IA hésitantes** (human-override sur events flagués, cas Seine-Saint-Denis / Hormuz / Cuba récents)
- Raydium manuel sans budget = exposition immédiate aux whales/snipers (pas de fonds pour LP lock ou anti-sniper)
- Lancer un token sans communauté institutionnelle crédible = rug assuré ou, pire, naming crédibilité brûlée avant même d'exister

### Pivot : CBWD = indicateur scientifique virtuel, PAS un produit financier (pour l'instant)

**Concept** : le token CBWD existe techniquement sur Solana (supply variable via MINT/BURN selon les events), mais **aucun pool DEX public n'est créé**. Sa valeur monétaire sera activée uniquement quand une communauté institutionnelle aura validé la métrique.

**Narratif à tenir partout (site, pitch, réseaux)** :
> *"CBWD est un indice de mesure de l'impact éthique des décisions mondiales, similaire au CO₂ en ppm ou à la température en °C. C'est un outil scientifique open-source, pas un actif spéculatif. Son activation en marché ouvert n'aura lieu qu'après validation par un réseau de références institutionnelles."*

**Avantages immédiats** :
- Zéro risque de sniping / rug pull (pas de pool à attaquer)
- Rassure les institutionnels qui fuient la crypto-spéculation
- Mint Authority devient un **argument scientifique** (calibration par l'équipe, pas un red flag financier)
- On continue d'opérer le pipeline IA + mainnet MINT/BURN comme aujourd'hui — c'est une preuve d'intégrité on-chain des analyses, pas un actif tradable

### Plan partenariats — "Cheval de Troie" API gratuite contre logo

**Principe** : accès gratuit au flux JSON/API pour ONG, médias indépendants, think tanks climat. Condition : affichage du logo sur notre page `/partenaires` + citation de CARBON WORLD comme source dans leurs analyses.

**Cibles prioritaires (2026-04-18)** :
- **Vakita** (média indépendant climat/tech)
- **The Shift Project** (équipe Jancovici)
- **IDDRI** (Institut du développement durable et relations internationales)
- **Reporterre**, **Greenpeace France**, **Fondation GoodPlanet**
- **Institut Veolia**
- **GIEC / IPCC** (via chercheur LinkedIn, pas voie institutionnelle directe)

**Pitch type (email / DM LinkedIn)** :
> *"Je suis le fondateur de CARBON WORLD, une IA open-source qui score éthiquement les décisions climatiques mondiales en temps réel (basée sur 7 référentiels ONU : 17 ODD, UDHR, OIT, CRC, UNDRIP, Animal Rights, Planetary Boundaries). Contrairement aux études statiques, nous fournissons un flux de données vivant et vérifiable.*
>
> *Nous offrons un accès API gratuit à [nom de l'organisation] pour enrichir vos analyses. Notre token CBWD existe sur Solana uniquement comme preuve d'intégrité des données — volontairement non-spéculatif. Nous cherchons simplement des partenaires de référence pour valider la métrique. Votre logo sur notre dashboard suffirait."*

**Effet boule de neige attendu** :
- Un think tank reconnu affiche un graphique CBWD → son audience engagée découvre le projet
- Crédibilité immédiate transitive ("si Jancovici cite ces données, c'est sérieux")
- Communauté se crée organiquement sans aucun marketing crypto

### Monétisation (3 pistes complémentaires, sans lancer le token)

**1. API premium pour secteur privé** (cash-flow direct)
- Gratuit : ONG, médias, think tanks, chercheurs
- Payant : entreprises RSE, banques, assureurs, lobbyistes, fonds d'impact
- Pitch : *"Votre département RSE a besoin de scorer vos fournisseurs en temps réel ? Analyser l'impact éthique de vos décisions de lobbying ? API Enterprise 500-2 000 €/mois."*
- **Un seul client à 500€/mois = salaire de base pour Cyril**. Deux = viabilité.

**2. Grants / subventions** (crédibilité → financement non-dilutif)
- Dès qu'on a 3-5 logos institutionnels sur `/partenaires`, éligibilité à :
  - **Horizon Europe** (bourses recherche / innovation, €10k-€100k)
  - **Fondation de France**, **Fondation GoodPlanet** (projets intérêt général, €5k-€50k)
  - **NGI (Next Generation Internet)** pour open-source européen
- On ne vend rien, on demande une bourse pour "maintenir une infrastructure open-source de vérité climatique"

**3. Valorisation future du token** (*long terme, 12+ mois*)
- Une fois 10-20 institutions utilisent CBWD comme référence, la demande devient réelle
- ALORS on lance le pool Raydium (avec les SOL accumulés via grants + API premium)
- LP burn immédiat, prix contrôlé car c'est nous qui posons la liquidité initiale avec une communauté vraiment formée
- **Mint Authority conservée** jusqu'à ce jour pour garantir la calibration scientifique

### Feuille de route immédiate (Semaine 1)

**Dashboard / site** :
- [ ] Ajouter page `/partenaires` (ou `/data-feed`) avec liste logos partenaires + conditions d'accès API gratuit
- [ ] Ajouter section "API & Partenariats" visible en home avec baseline : *"Token CBWD : actif de preuve d'intégrité — non-listé / non-spéculatif à ce jour"*
- [ ] Générer 3 exemples de rapports PDF propres (graphiques clairs des 27 events, méthodologie 7 référentiels + 4D) pour pitch

**Campagne outreach** :
- [ ] 10 emails ciblés (Vakita / Shift Project / IDDRI / Reporterre / Greenpeace / GoodPlanet / Veolia / 2-3 chercheurs GIEC-IDDRI)
- [ ] Objectif : **UN seul "oui, testons votre API"** en 2 semaines
- [ ] Dès obtention du 1er logo : épingler en gros sur `/` et attendre trafic qualifié

**Infrastructure technique** :
- [ ] Exposer `/api/v1/events` public, rate-limited (free tier : 100 req/jour par IP ; institutionnel avec token : illimité)
- [ ] Documenter OpenAPI / Swagger simple
- [ ] Ajouter `Access-Control-Allow-Origin` pour embed logos/widgets externes

### Règle d'or : ne JAMAIS communiquer CBWD comme "crypto à acheter"

Tant que le pool n'existe pas, toute communication doit positionner CBWD comme :
- **Indicateur scientifique** (comme °C, ppm, pH océan)
- **Infrastructure open-source d'intérêt public**
- **Pas un investissement, pas un actif tradable**

Si un contact demande "comment acheter CBWD ?", la réponse est :
> *"CBWD n'est pas encore listé en marché public. C'est un choix : nous voulons d'abord faire valider la métrique par la communauté scientifique avant toute activation financière. Vous pouvez rejoindre notre newsletter pour être prévenu du lancement."*

---

## 🌐 Standard de langue

- **Code** : anglais uniquement (variables, logs, prompts IA, schémas JSON)
- **Docs projet** (CLAUDE/MEMORY/RULES.md) : français (pour Cyril)
- **Frontend** (phase 3) : bilingue EN/FR

## ✅ Statut actuel — Fin de session 2026-04-14

### Ce qui fonctionne en production
- ✅ **Worker Python** (8 fichiers EN) intégré au `launchd` macOS
- ✅ **Qwen3:32b local** via Ollama valide les analyses éthiques 4D (testé 3/3 cas)
- ✅ **SQLite local** à `~/CARBON-WORLD/data/carbon.db` auto-créée
- ✅ **33 sources RSS mondiales** round-robin (6 continents)
- ✅ **3 runs/jour automatiques** (08:00, 14:00, 20:00) + rattrapage boot
- ✅ **Commande bureau** `~/Desktop/CARBON WORLD - Lancer.command`

### Ce qu'il reste à faire
1. **Premier vrai run production** : `bash ~/CARBON-WORLD/launcher/run.sh --force` (15-20 min)
2. **Phase 3 frontend** : Next.js sur Vercel, source de données à trancher
3. **Phase 4 Solana** : mint/burn réels devnet puis mainnet
4. **Twitter/X** : soit API Basic $100/mois, soit RSSHub Docker self-hosted

### Pour reprendre
- **OUVRIR CLAUDE CODE DEPUIS `~/CARBON-WORLD/`** : `cd ~/CARBON-WORLD && claude`
- Lire `MEMORY.md` en premier — section "Fait" + "Prochaine étape"
- Le pipeline tourne sur le VPS Hetzner `157.90.250.40` (cron 15 min)
- SSH : `ssh carbon@157.90.250.40`
- Logs VPS : `~/CARBON-WORLD/logs/cron_*.log` (20 derniers gardés)

### Commandes utiles
```bash
# --- LOCAL MAC ---
# Pull la dernière data depuis GitHub
cd ~/CARBON-WORLD && git pull origin main

# --- VPS HETZNER ---
# SSH dans le VPS
ssh carbon@157.90.250.40

# Run manuel du pipeline sur VPS (force run complet)
ssh carbon@157.90.250.40 "~/CARBON-WORLD/launcher/run_vps.sh"

# Dernier log cron VPS
ssh carbon@157.90.250.40 "ls -t ~/CARBON-WORLD/logs/cron_*.log | head -1 | xargs tail -50"

# Voir la DB sur VPS
ssh carbon@157.90.250.40 "sqlite3 ~/CARBON-WORLD/data/carbon.db 'SELECT id, decision, amount_crbn, final_score, event_title FROM carbon_events ORDER BY id DESC LIMIT 10;'"

# Status cron VPS
ssh carbon@157.90.250.40 "crontab -l"

# --- GITHUB ACTIONS (fallback manuel) ---
# Si VPS down, déclencher pipeline depuis UI GitHub : Actions → CARBON WORLD Pipeline → Run workflow

# --- FRONTEND VPS ---
# Rebuild manuel du front (normalement fait auto par run_vps.sh si web/ change)
ssh carbon@157.90.250.40 "cd ~/CARBON-WORLD/web && npm run build && sudo systemctl restart carbon-web"

# Logs du service web
ssh carbon@157.90.250.40 "sudo journalctl -u carbon-web -n 50 --no-pager"

# Logs Caddy (reverse proxy)
ssh carbon@157.90.250.40 "sudo journalctl -u caddy -n 50 --no-pager"
```

### Secrets / credentials
- `~/CARBON-WORLD/.env` (local Mac + VPS) — `GROQ_API_KEY`, `CEREBRAS_API_KEY` (pour Analyst B free tier), etc.
- `~/.config/solana/id.json` (local Mac + VPS) — mint authority keypair `2LJspF…`
- VPS env vars passkey (dans l'unit systemd `carbon-web.service` ou `~/CARBON-WORLD/web/.env.production`) : `SESSION_SECRET`, `PASSKEY_CREDENTIAL`, `RP_ID=carbon-token.xyz`, `RP_ORIGIN=https://carbon-token.xyz`
- GitHub Secrets (fallback) : `GROQ_API_KEY`, `SOLANA_KEYPAIR`
- VPS SSH key : `~/.ssh/github_deploy` (deploy key write access)
