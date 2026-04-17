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

**Modèles LLM (Groq cloud)** :
- `qwen/qwen3-32b` : classifier + analyst A
- `llama-3.3-70b-versatile` : analyst B (bias diversity)
- Sentinel : plus gros modèle pour coherence check

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
- [ ] Liquidité initiale DEX (Raydium) ← next step produit
- [ ] Monitoring (Uptime Kuma ou similaire)
- [ ] Ajout Twitter/X via RSSHub Docker OU X API Basic
- [ ] Fix rate-limit Groq 429 (tier free saturé, prod retourne souvent 0 event)

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
- `~/CARBON-WORLD/.env` (local Mac + VPS) — Groq API key, etc.
- `~/.config/solana/id.json` (local Mac + VPS) — mint authority keypair `2LJspF…`
- VPS env vars passkey (dans l'unit systemd `carbon-web.service` ou `~/CARBON-WORLD/web/.env.production`) : `SESSION_SECRET`, `PASSKEY_CREDENTIAL`, `RP_ID=carbon-token.xyz`, `RP_ORIGIN=https://carbon-token.xyz`
- GitHub Secrets (fallback) : `GROQ_API_KEY`, `SOLANA_KEYPAIR`
- VPS SSH key : `~/.ssh/github_deploy` (deploy key write access)
