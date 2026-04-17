# MEMORY — Journal du projet CARBON WORLD

> Mis à jour à chaque étape. Source de vérité pour "ce qui a été fait / tenté / appris".

---

## 🔖 Résumé de fin de session 2026-04-14

**En une phrase** : Phase 1 (worker IA) et Phase 2 (automation launchd) sont **entièrement terminées et installées**. Le système tournera tout seul 3×/jour demain.

**Architecture finale validée** :
- Python 3.13 + venv @ `~/CARBON-WORLD/venv/`
- Worker : 8 modules en anglais @ `~/CARBON-WORLD/worker/`
- Data : SQLite local @ `~/CARBON-WORLD/data/carbon.db`
- IA : Ollama + `qwen3:32b` (Gemma 4 échoué, Qwen3 validé 3/3)
- Prompt : 6639 chars, analyse duale + 7 référentiels éthiques + cadre 4D
- RSS : 33 sources actives, round-robin mondial (6 continents)
- Scheduler : launchd `com.neousaxis.carbonworld` chargé en gui/501
- Manual trigger : `~/Desktop/CARBON WORLD - Lancer.command` cliquable

**Aucun service externe payant** (Supabase abandonné car limite 2 projets, tout est local).

**Coûts récurrents** : **0 €/mois**.

### 🔴 INCIDENT 2026-04-16 — Sous-agent dans le mauvais repo
- Un sous-agent Sonnet avec `isolation: "worktree"` implicite a travaillé dans un worktree basé sur le home dir (`~`) qui est un repo git géant
- Le breadcrumb UI affichait "kernel-earth / Implement Carbone Token functionality" → un autre projet !
- **Cause** : `~/CARBON-WORLD/` n'avait pas son propre `.git` → héritait du repo parent `~`
- **Fix** : `git init` dans `~/CARBON-WORLD/`, initial commit (31 fichiers, 2673 lignes)
- **Règle ajoutée** : NE JAMAIS utiliser `isolation: "worktree"`, NE JAMAIS travailler hors du repo CARBON-WORLD. Sous-agents utilisent des branches dans le repo dédié.
- **Voir RULES.md Section 0 (GIT)**

### 2026-04-16 — Fix pollution ~/.git (kernel-earth déplacé)
- Le home directory `~` était un clone de `github.com/NeousAxis/kernel-earth` → polluait TOUTES les sessions Claude Code
- Migration effectuée dans une session séparée :
  - `~/.git` → `~/kernel-earth/.git`
  - 16 fichiers trackés déplacés (Dockerfile, server.js, api/, src/, frontend/, etc.)
  - 2 worktrees stales purgés
  - Remote origin intact
- **Résultat** : `~/.git` n'existe plus, `~/kernel-earth/` fonctionne indépendamment, `~/CARBON-WORLD/.git` intouché
- Note : kernel-earth a un rebase interrompu (29 commits) → `git rebase --abort` si besoin

### 2026-04-16 — Pipeline multi-agents construit et testé ✅
- Refonte architecture : monolithique → 6 agents spécialisés
- Agents créés : collector, classifier, analyst, scorer, writer, reporter
- 2 modèles LLM : `qwen3:14b` (classifier, rapide ~1s) + `qwen3:32b` (analyst, profond ~48s)
- Nouveau dossier `agents/` (7 fichiers) et `prompts/` (3 fichiers) + `ollama_client.py`
- `main.py` réécrit comme orchestrateur pipeline 6 phases
- Commit initial fait sur `main` (3d27e88) + commit fix rules (aeb52b8)

### 2026-04-16 — Bug Qwen3 "thinking mode" → fix `think=False`
- **Problème** : `qwen3:14b` ET `qwen3:32b` retournaient des réponses vides (21/25 articles failed)
- **Cause** : Qwen3 active un mode "thinking" par défaut — le modèle met sa réflexion dans un champ `thinking` séparé et ne produit rien dans `response` si `num_predict` est trop bas
- **Fix** : ajout de `think=False` aux deux appels `client.chat()` dans `ollama_client.py`
- **Résultat** : classifier passe de ~7s/article (avec thinking gaspillé) à ~1s/article, 100% de réponses

### 2026-04-16 — Premier run pipeline complet ✅ (DONNÉES RÉELLES)
- **868 articles** collectés (31/33 sources, DeSmog + Rio Times en HTTP 403)
- **25 classifiés** par `qwen3:14b` → 2 VALID, 23 INVALID (correct)
- **1 analysé** en profondeur par `qwen3:32b` (48s) → MINT
- **1 décision sauvée** en DB :
  - MINT 1,200,000 CBWD | EU + Member States pledge €811M for Sudan | score=1.96 | conf=7/10
  - Le scorer a corrigé une incohérence de score prospectif du LLM (2.10 → 1.40 recalculé)
- **Temps total** : ~2 min 15s (bien sous les 15 min estimées)
- **20 événements** en DB au total (16 pré-existants des runs launchd + 4 de cette session)
- DB : `~/CARBON-WORLD/data/carbon.db` — vérifié fonctionnel

### 2026-04-16 — Phase 3 Frontend déployé ✅
- **Stack** : Next.js 16.2.4 + Tailwind CSS v4 + TypeScript
- **Hébergement** : Vercel (production)
- **Données** : JSON exporté depuis SQLite → `web/data/export.json` (copié auto par exporter)
- **Repo GitHub** : https://github.com/NeousAxis/CARBON-WORLD (privé)
- **4 pages** :
  - `/` — Dashboard financier : ticker bar, supply chart SVG, donut, live ticker, event log
  - `/event/[id]` — Détail événement avec justification éthique + lien Solana Explorer
  - `/about` — Explication du système, 7 référentiels, cadre 4D
  - `/sources` — Liste des 46 sources avec région, catégorie, langue, statut LIVE/DOWN
- **Design** : Lunaris Dark (fond #111111, cards #1A1A1A, accent orange #FF8400, JetBrains Mono, corners carrés)
- **Exporter** : `worker/exporter.py` écrit `data/export.json` + copie dans `web/data/`
- **Domaine** : `carbon-token.xyz` acheté, pas encore configuré dans Vercel

### 2026-04-16 — 13 sources science/innovation/bonnes nouvelles ajoutées
- Nature News, Science (AAAS), The Lancet, Phys.org, ScienceDaily, WHO News
- MIT Technology Review, Ars Technica Science, New Scientist, WIRED Science
- Positive News, Good News Network, Reasons to be Cheerful
- **Total : 46 sources (44 actives, 2 down : DeSmog + Rio Times)**
- Page `/sources` créée sur le frontend pour lister toutes les sources

### 2026-04-16 — Horaires launchd mis à jour
- Ancien : 08:00, 14:00, 20:00
- **Nouveau : 08:00, 14:00, 17:00** (jusqu'à passage en live 24/24)
- Plist rechargé via `launchctl bootstrap`

### 2026-04-16 — Phase 4 Solana TERMINÉE ✅ (devnet)
- **Libs** : `solana` 0.36.11 + `solders` 0.27.1
- **Module** : `worker/solana_executor.py`
  - Instructions SPL Token construites manuellement (pas de dépendance `spl-token`)
  - `_build_mint_to_ix()` : opcode 7, mint vers treasury ATA
  - `_build_burn_ix()` : opcode 8, burn depuis treasury ATA
  - Keypair chargé depuis `~/.config/solana/id.json`
  - Blockhash `finalized` + `skip_preflight=True` (devnet timing issues)
- **Wallet** : `2LJspFTWw5VFTZjRNo9Va1VQTEjARAjSuCH7LR6K8AZW`
  - **C'est le mint authority** du token CBWD
  - Balance : ~2 SOL devnet
  - ATA treasury confirmée : `2iNtuKTthWRGiDoK4VZYQJ7dC8t4d2DkR1dbLQx5QqFK`
- **Tests réussis** :
  - MINT 1 CBWD → tx `35GDHHJfhQA9yjKExUNRh2GAAzZBiHZpLwFRkM5basqNr9NTmkmUzZq3w53ma7vueGZ72eAX1x1MpUaKChUR2Q8p`
  - BURN 1 CBWD → tx `2LewaQitwcvJZ29RiLTUVPftwVh1SbSJDvr8Gw74syCj6Uuksw7oTRoQuA6r2RAhH1vRZ4aFx25F7catSmz8M8BJ`
- **Intégration pipeline** : `writer.py` appelle `execute_decision()` après chaque save, puis `update_tx_hash()` en DB
- **Conversion** : `amount_crbn` (ex: 1200000) × 10^6 = raw Solana units

### 2026-04-16 — Migration Groq Cloud + GitHub Actions (24x/jour) ✅
- **Provider LLM** : `LLM_PROVIDER=groq` dans `.env` (bascule Ollama ↔ Groq)
- **Modèle Groq** : `qwen/qwen3-32b` — même modèle qu'Ollama local, hébergé chez Groq
- **API key** : `gsk_LJJ...` stockée dans `.env` + GitHub Secret `GROQ_API_KEY`
- **Rate limiting** : 2s entre appels classifier, 8s entre appels analyst (free tier Groq = 30 req/min + 6000 TPM)
- **`/no_think`** ajouté au prompt système pour désactiver le thinking mode de Qwen3 sur Groq
- **`_strip_think_tags()`** dans le client pour nettoyer les `<think>` résiduels
- **GitHub Actions** : `.github/workflows/pipeline.yml`
  - Cron : `7 * * * *` (toutes les heures, minute 7)
  - `workflow_dispatch` pour déclenchement manuel
  - Python 3.13, pip cache, 15 min timeout
  - Secrets : `GROQ_API_KEY` + `SOLANA_KEYPAIR`
  - Auto-commit `export.json` après chaque run
  - Permission `contents: write` pour le push
- **Solana keypair** : `~/.config/solana/id.json` → GitHub Secret `SOLANA_KEYPAIR`
- **Test réussi** : pipeline Groq → MINT 750K CBWD (Tepco Niigata) → Solana TX confirmée
- **Coût estimé** : ~$1/mois (Groq free tier + GitHub Actions public)

### 2026-04-16 — Token metadata + logo enregistrés on-chain ✅
- Logo : symbole C abstrait orange sur fond noir (Pillow-generated, 512x512 PNG)
- Metadata Metaplex : name="Carbon World", symbol="CBWD", URI vers GitHub raw
- TX création metadata : `4Z8K6tKV...`
- TX update URI : `4fW6ztbp...`
- Logo affiché dans la navbar du site

### 2026-04-17 — Passkey (WebAuthn) auth + API sécurisée pour /review ✅
- Remplacement du mot de passe localStorage hardcodé par **authentification WebAuthn / Apple Passkeys**
- Compatible Apple Mots de passe (iCloud Keychain), Touch ID / Face ID
- Deps ajoutées : `@simplewebauthn/server@13`, `@simplewebauthn/browser@13`, `jose@5`
- API routes : `/api/auth/{register,login,logout,me}/{challenge,verify}`, `/api/review/queue`
- Challenges en cookies signés (stateless, 5 min TTL)
- Session JWT HS256 httpOnly, 24h TTL
- Credential stocké en env var `PASSKEY_CREDENTIAL` (base64 JSON) en prod
- Bootstrap : `/review/setup?secret=XXX` gated par `SETUP_SECRET` (à supprimer après registration)
- Data `review_queue.json` maintenant servie uniquement via API auth-gated (plus de fetch direct)
- **Bug fix** : `echo | vercel env add` ajoute un `\n` final — remplacé par `printf` (no newline)
- Passkey prod registré : Touch ID sur `web-neousaxis-neous-axis-projects.vercel.app`
- Credential backup base64 : voir `.credential.json` local ou env var Vercel

### 2026-04-17 — Migration GitHub Actions → VPS Hetzner ✅
- **Serveur** : Hetzner CX23, Ubuntu 24.04, Falkenstein (DE)
  - IPv4 : `157.90.250.40`
  - 2 vCPU x86, 4GB RAM, 40GB SSD
  - **Coût : €4.31/mois**
  - Firewall : SSH 22 + HTTP 80 + HTTPS 443 + ICMP ouverts
- **User** : `carbon` (sudo NOPASSWD), SSH key ed25519 de Cyril
- **Setup** : Python 3.12 + venv + requirements.txt (pas besoin de 3.13)
- **Secrets copiés** : `.env` et `~/.config/solana/id.json` via scp
- **Deploy key GitHub** : `vps-hetzner-writer` (read-write), ed25519 généré sur le VPS
- **Script cron** : `~/CARBON-WORLD/launcher/run_vps.sh`
  - Pull main, run pipeline, commit + push export.json si changement
  - Logs rotatifs (20 derniers) dans `~/CARBON-WORLD/logs/cron_*.log`
- **Cron** : `*/15 * * * * /home/carbon/CARBON-WORLD/launcher/run_vps.sh` — **4 runs/heure**
- **GitHub Actions schedule désactivé** dans `.github/workflows/pipeline.yml` (workflow_dispatch gardé en fallback)
- **Repo passé en public** pour faciliter les clones publics (pas de secrets trouvés dans l'historique git)

### 2026-04-17 — Nouveau projet Hetzner Cloud dédié "CARBON WORLD"
- Projet isolé des autres projets Hetzner (billing, API token, firewalls séparés)
- SSH key ed25519 de Cyril ajoutée au projet (nom : "Macbook")

## 📌 Prochaine étape immédiate
1. ~~Pipeline multi-agents~~ → **FAIT** ✅
2. ~~Phase 3 frontend~~ → **FAIT** ✅
3. ~~Phase 4 Solana devnet~~ → **FAIT** ✅
4. ~~Migration Groq + GitHub Actions~~ → **FAIT** ✅
5. ~~Passkey auth /review~~ → **FAIT** ✅ (2026-04-17)
6. ~~Migration pipeline → VPS Hetzner~~ → **FAIT** ✅ (2026-04-17)
7. ~~Repo public~~ → **FAIT** ✅ (2026-04-17)
8. **Niveau 1 live UX** : frontend polling + animations compteurs + flash new events
9. Fix chart genesis (ligne 0 → 1.3M cohérente)
10. Configurer le domaine `carbon-token.xyz` dans Vercel (DNS)
11. Phase 5 : liquidité DEX mainnet

**Ce qui reste avant mainnet** :
1. Premier vrai run production (15-20 min) — à faire demain
2. Frontend Next.js sur Vercel (Phase 3)
3. Intégration Solana devnet mint/burn (Phase 4)
4. Migration mainnet + VPS (Phase 5)
5. Ajout Twitter/X via RSSHub Docker self-hosted (optionnel, plus tard)

**Configuration `.env` en production** :
```
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=qwen3:32b
OLLAMA_TIMEOUT_SECONDS=240
OLLAMA_REPEAT_PENALTY=1.15
MAX_ARTICLES_PER_RUN=25
MIN_HOURS_BETWEEN_RUNS=5
```

---

---

## ✅ Fait

### 2026-04-14 — Setup initial
- Création du dossier projet `~/CARBON-WORLD/` avec sous-dossiers `worker/`, `launcher/`, `logs/`
- Création de `CLAUDE.md` (plan)
- Création de `RULES.md` (rôle orchestrateur, règles)
- Création de `MEMORY.md` (ce fichier)
- Vérification environnement local :
  - ✅ Ollama installé, modèle `gemma4:26b` disponible (17 GB)
  - ✅ Autres modèles dispo : `qwen3:14b`, `qwen3:32b`, `qwen2.5-coder:32b`, `qwen2.5-coder:32b-8k`
  - ✅ `claude-library` à `~/claude-library/`
  - ✅ Supabase projet actif
  - ✅ Token CBWD déjà minté sur devnet

### 2026-04-14 — Phase 1 Worker v1 (Gemma 4) — ÉCHOUÉ
- Premier sous-agent Sonnet a livré 10 fichiers Python fonctionnels
- Tests exécutés : install venv, import modules, ping Ollama, fetch RSS, test Gemma 4 sur 4 articles
- **Résultat** : Gemma 4 26B inutilisable (boucles pathologiques, JSON cassé, bug de répétition tokens)
- Décision : abandonner Gemma 4, passer à Qwen3:32b

### 2026-04-14 — Refonte v2 : code en anglais + cadre éthique multi-référentiels
- Nouvelle spec par Cyril :
  1. **Tout le code en anglais** (variables, logs, prompts, JSON) — docs projet restent en français
  2. **Cadre éthique enrichi** : analyse duale positif/négatif via 7 référentiels (17 SDGs + UDHR + ILO + Animal Rights + CRC + UNDRIP + Planetary Boundaries)
  3. Exemple type : Coupe du Monde Qatar (infrastructure + MAIS morts travailleurs migrants --)
- Délégation refonte complète à sous-agent Sonnet → 8 fichiers réécrits en anglais
- Nouveau prompt système `SYSTEM_PROMPT` (6639 caractères) avec :
  - Step 1 : validation concrète/actionnable
  - Step 2 : dual ethical analysis (positive_aspects + negative_aspects + ethical_synthesis)
  - Step 3 : 4D temporal (snapshot/trajectory/revaluation/prospective)
  - Step 4 : final_score → BURN/MINT/NEUTRAL
  - Step 5 : amount_cbwd avec formule
  - Step 6 : confidence 1-10

### 2026-04-14 — RSS sources mises à jour
Nouvelles sources actives (5/6) :
- ✅ UN News Climate (30 articles)
- ✅ The Guardian Climate (13 articles)
- ✅ The Guardian Environment (22 articles)
- ✅ BBC Science & Environment (32 articles)
- ❌ Reuters Agency Environment (feed malformed, à remplacer plus tard)
- ✅ Climate Home News (40 articles)
**Total : 137 articles/run dédoublonnés** (vs 30 avant)

### 2026-04-14 — Test v2 avec Qwen3:32b → ✅ SUCCÈS TOTAL
3/3 tests parfaits :
1. **Belarus forests** (constat) → INVALID correctement
2. **Guardian newsletter** (média) → INVALID correctement
3. **Argentina glacier law** (vraie loi votée) → VALID + analyse duale riche :
   - Positive : SDG 8, 9 (mining growth, mag 5)
   - Negative : SDG 6,13,14 + UNDRIP Art 29 + Planetary Boundary (mag 9) ET SDG 15 + UDHR 25 + CRC 24 (mag 7)
   - Synthesis cohérente
   - 4D scores : snap=-6.2, traj=-2.3, reval=0, prosp=-3.1
   - Final -3.8 → **MINT 750,000 CBWD** (confidence 7/10)

**Performance** : 28-75s/article, médiane ~45s → 15-25 min pour 20 articles. OK pour cron 2×/jour.

**Modèle validé** : `qwen3:32b` via Ollama, options `temperature=0.2 num_predict=2500 num_ctx=8192 repeat_penalty=1.15 format=json` timeout 240s.

### 2026-04-14 — Migration Supabase → SQLite local (Cyril ne peut pas créer de nouveau projet Supabase)
- Limite Supabase : 2 projets actifs par organisation (déjà documenté dans CLAUDE.md App Store)
- Décision : **SQLite local** à `~/CARBON-WORLD/data/carbon.db`
- Délégation refonte `db.py` à sous-agent Sonnet
- Utilise `sqlite3` standard library (zéro dépendance externe)
- Mode WAL pour concurrence
- Auto-création de la table et des 2 index au premier accès
- Dedup via contrainte `UNIQUE(event_url)` + catch `IntegrityError`
- Dépendance `supabase` retirée de `requirements.txt`
- Variables `SUPABASE_*` retirées de `config.py` et `.env`

### 2026-04-14 — Tests SQLite ✅
- Auto-création DB path + dirs ✅
- Schema tables + indexes ✅
- INSERT + récupération row ✅
- event_exists lookup ✅
- Dedup IntegrityError géré gracieusement ✅
- close_connection cleanup ✅

### 2026-04-14 — Test end-to-end pipeline complet ✅
Run : `python main.py --force` avec `MAX_ARTICLES_PER_RUN=2`
- RSS fetch : 137 articles (5 sources actives, Reuters Agency morte)
- Filter : 0 déjà en base
- Cap : 2 articles
- Qwen3:32b analyse : 2/2 → VALID=false (UN statements d'intention, pas des décisions)
- Save : 0 (correct, les invalid ne sont pas sauvés)
- Exit 0, total 74s (médiane 36s/article)
- `last_run.json` écrit correctement
- Logs clairs en anglais, fichier `logs/worker.log` rotation 10MB × 3

**PHASE 1 TECHNIQUEMENT TERMINÉE** — système fonctionne end-to-end.

---

### 2026-04-14 — Phase 2 Automation livrée et installée ✅
Délégation sous-agent Sonnet, 6 fichiers créés dans `launcher/` :
- `run.sh` : script shell, active venv, run python main.py, log horodaté, forward CLI args, PIPESTATUS pour exit code
- `com.neousaxis.carbonworld.plist` : Label, 3 runs/jour (**08:00, 14:00, 20:00** — Cyril a demandé d'ajouter le run de 14h), RunAtLoad, Nice=5, ProcessType=Background, PATH + LC_ALL, stdout/stderr redirigés
- `install.sh` : bootout previous → cp plist → bootstrap gui/$(id -u) → enable → chmod +x → copie commande bureau
- `uninstall.sh` : bootout + rm plist + rm desktop shortcut
- `CARBON WORLD - Lancer.command` : bash script exécutable depuis Finder, lance run.sh --force, `read -p` pour garder terminal ouvert
- `README.md` : doc install/uninstall/vérification

Tests exécutés :
- run.sh --force → OK 60s, 2 articles INVALID correctement rejetés
- install.sh → service chargé dans launchd, RunAtLoad déclenché immédiatement
- Service verified : `launchctl list | grep carbonworld` → actif
- launchd run complet : 55s, exit 0, logs dans launchd.out
- Service idle post-run, prêt pour prochains triggers cron

**PHASE 2 TERMINÉE** — le système tourne tout seul 3×/jour + rattrapage boot/wake.

### 2026-04-14 — Extension massive des sources RSS (couverture mondiale)
Cyril m'a reproché de focaliser sur l'Occident. Refonte complète de `rss_fetcher.py` :
- **33 sources actives** couvrant 6 continents (vs 5 avant)
- Batch test de 31 candidats mondiaux → 25 alive + 8 LatAm/Oceania ajoutées
- Ajout d'une fonction `_round_robin_interleave` : chaque run prend 1 article de chaque source puis 2e de chaque etc → garantit diversité géographique même avec `MAX_ARTICLES_PER_RUN=25`
- Test vérifié : 25 premiers articles = 25 sources distinctes (1/source)

Sources par région :
- International : UN News, EU Commission
- Europe/US : Guardian x2, BBC, Climate Home, Carbon Brief, Inside Climate, Grist, DeSmog
- Francophonie : Le Monde x2, France 24 x2, RFI x2 (AFP redistribué)
- Afrique : AllAfrica x2
- Asie : The Hindu, Japan Times, SCMP, Xinhua, Nikkei, Mongabay
- Amérique Latine : Folha x2 (BR), Clarín (AR), Americas Quarterly, Rio Times, Mongabay LATAM
- Océanie : ABC Australia, The Conversation AU
- Moyen-Orient : Al Jazeera

**Twitter/X abandonné pour phase 1** : rsshub.app 404, xcancel 403, Bluesky 404 sur politiciens.
Options restantes (à évaluer plus tard) : X API Basic $100/mois OU RSSHub self-hosted Docker OU migration pay quand le token a de la valeur.

**`.env` production** : `MAX_ARTICLES_PER_RUN=25`, `MIN_HOURS_BETWEEN_RUNS=5` → ~19 min/run × 3/jour = ~57 min CPU/jour.

## 📌 Prochaine étape : Phase 3 — Frontend `carbon-token.xyz`
- Hébergement : **Vercel** (Cyril l'utilise déjà, CLI installé) — validé par Cyril
- Stack : Next.js ou site statique
- Source des données : à décider (JSON export GitHub / Turso / Cloudflare D1 / API locale via tunnel)

---

## 🧭 Décisions techniques

### 2026-04-14 — Choix de stack
- **Langage** : Python 3 (pas de Node, pas de n8n). Raison : natif, simple, testable, versionnable, bonnes libs Solana (`solders`) et Ollama (`ollama-python`).
- **IA** : `gemma4:26b` local via Ollama HTTP API (`localhost:11434`). Raison : Cyril l'a déjà installé, pas de coût API, vie privée.
- **Déclenchement** : `launchd` (pas `cron`). Raison : macOS natif, supporte `RunAtLoad` (rattrapage si Mac éteint).
- **Rattrapage** : fichier `last_run.json` + vérification à chaque lancement (> 12h → run immédiat).
- **DB** : Supabase existant, table `carbon_events` déjà créée.
- **Phase Solana** : différée. Phase 1 = worker IA + DB uniquement. Mint/burn réels en phase 4.

---

## 🐛 Erreurs / Solutions

### 2026-04-14 — Gemma 4 26B : boucles de répétition pathologiques
**Problème** : Sur 4 articles testés, Gemma 4 26B produit un JSON inutilisable :
- Boucles infinies de tokens ("facto-facto-facto...", "institutionnelle-institutionnelle...", "input-input-input...")
- Strings non terminées → parse JSON échoue
- Champs inventés (ex: `reason_ext`)
- Types incorrects (ex: `reason: -10` au lieu d'une string)

**Diagnostic** : La logique de validation 4D fonctionne (le modèle choisit correctement `validation=false` pour un état des lieux ONU), mais le format de sortie est cassé dès qu'il doit écrire une longue string en français avec accents. Bug connu des Gemma 2/3/4 : "token repetition loop" sur tâches multilingues structurées.

**Tentatives** : `format="json"` côté Ollama activé → ne suffit pas.

**Solution retenue** : TESTER qwen3:32b / qwen2.5-coder:32b-8k en alternative (déjà installés localement, meilleurs en JSON structuré).

**Fallback si Qwen échoue** : simplifier le schéma JSON en anglais + ajouter `repeat_penalty=1.3` côté Ollama.

### 2026-04-14 — Flux RSS Euronews morts (404)
**Problème** : Les deux flux Euronews Green du livre blanc original retournent 404 :
- `https://www.euronews.com/rss?level=vertical&name=green` → 404
- `https://fr.euronews.com/rss?format=mrss&level=vertical&name=green` → 404

Reuters Environment aussi mort (attendu, Reuters a fermé ses RSS publics en 2020).

**Seule source qui marche** : UN News Climate → 30 articles/run.

**Solution à mettre en place** : ajouter de nouvelles sources RSS actives (The Guardian Environment, BBC Environment, Le Monde Planète, climate.nasa.gov, etc.). À faire après validation du modèle IA.

---

## 📌 À retenir

- **NE JAMAIS redemander** : mint address, treasury ATA, Supabase URL, nom du modèle Ollama → tout est dans `CLAUDE.md` et les fichiers iCloud.
- **NE JAMAIS** utiliser n8n pour ce projet (Cyril a déjà eu une mauvaise expérience).
- **Cyril est agressif quand on lui fait perdre du temps** — efficacité > politesse.
