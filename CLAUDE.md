# CARBON WORLD — Plan du projet

> **Projet** : Token Solana (CBWD) piloté par une IA locale qui mesure les décisions humaines affectant le vivant et ajuste le supply en conséquence (BURN = positif, MINT = négatif).
> **Fondateur** : Cyril Leger (Neous Axis)
> **État au 2026-04-14** : Relance du projet après une première tentative ratée sur n8n.

---

## 🎯 Contexte (NE PAS REDEMANDER)

### Ce qui existe déjà
- **Token CBWD** créé sur **Solana devnet** :
  - Mint : `HRqmMnbA18VgstcfjCueAuzVZEoHHbLbbu973AqmK3Fs`
  - Treasury ATA : `2iNtuKTthWRGiDoK4VZYQJ7dC8t4d2DkR1dbLQx5QqFK`
  - Decimals : 6, Symbol : CBWD, Name : Carbon World
- **Supabase projet** actif : `https://drmlsquvwybixocjwdud.supabase.co`
  - Table `carbon_events` (event_title, event_url, event_source, decision, amount_crbn, final_score, confidence, justification, tx_hash, created_at)
- **Domaine** : `carbon-token.xyz` (acheté, pas encore de site)
- **Livre blanc** : `~/Library/Mobile Documents/com~apple~CloudDocs/CARBON-TOKEN/`
- **Ancienne tentative n8n** : fonctionnait mal → abandonnée

### Ce qu'on refait en mieux
- Worker **Python natif** (plus de n8n)
- IA **locale** : `gemma4:26b` via Ollama (déjà installé, 17 GB)
- Déclenchement **2× par jour** via `launchd` (équivalent macOS de cron)
- **Rattrapage automatique** : si le Mac était éteint, le worker s'exécute au réveil ou au prochain lancement
- **Commande bureau cliquable** pour relancer manuellement
- Plus tard : migration VPS + mainnet

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

## 🏗 Architecture technique — Pipeline Multi-Agents

```
launchd (3×/jour + RunAtLoad)
  → launcher/run.sh
    → worker/main.py (orchestrateur)

Pipeline :
┌──────────────┐
│  COLLECTOR    │  Pure Python, 0 LLM
│  33 sources   │  ~30s, round-robin mondial
│  RSS + dedup  │  
└──────┬───────┘
       ↓ raw articles
┌──────────────┐
│  CLASSIFIER   │  qwen3:14b (9 GB, rapide)
│  Triage       │  ~5-8s / article
│  valid/invalid│  Prompt minimaliste ~500 chars
└──────┬───────┘
       ↓ only VALID (~15-20%)
┌──────────────┐
│  ANALYST      │  qwen3:32b (20 GB, profond)
│  Analyse 4D   │  ~60s / article
│  7 référentiels│ Prompt complet 6600 chars
└──────┬───────┘
       ↓ scored events
┌──────────────┐
│  SCORER       │  Pure Python, 0 LLM
│  Vérifie +    │  Formules + montant CBWD
│  calcule      │  
└──────┬───────┘
       ↓ final events
┌──────────────┐
│  WRITER       │  Pure Python → SQLite
│  Persiste     │  data/carbon.db
└──────┬───────┘
       ↓
┌──────────────┐
│  REPORTER     │  Pure Python (template)
│  Résumé run   │  Stats + log structuré
└──────────────┘
       ↓
  Solana devnet (Phase 4, pas encore implémenté)
```

**Temps estimé** : ~8 min/run (vs ~30 min monolithique)
- Collector : 30s (33 sources)
- Classifier : 3 min (25 articles × 8s, qwen3:14b)
- Analyst : 5 min (~5 VALID × 60s, qwen3:32b)
- Scorer + Writer + Reporter : <1s

**2 modèles Ollama utilisés** :
- `qwen3:14b` (classifier — rapide, validation simple)
- `qwen3:32b` (analyst — profond, analyse éthique 4D complète)

---

## 📋 Phases de livraison

### ✅ Phase 1 — Worker IA (TERMINÉE)
- [x] Structure Python (venv 3.13, requirements minimal, config .env)
- [x] Fetcher RSS multi-sources — **33 sources mondiales** round-robin anti-biais
- [x] Déduplication via SQLite local (UNIQUE constraint + IntegrityError)
- [x] Client Ollama → `qwen3:32b` (Gemma 4 écarté après échec tests)
- [x] Prompt système enrichi — analyse duale éthique + 7 référentiels + cadre 4D
- [x] Parser JSON strict + fallback regex + validation
- [x] Écriture **SQLite local** (Supabase abandonné car 2-projets/org limit)
- [x] Logs structurés (rotation 10 MB × 3)
- [x] Système `last_run.json` pour rattrapage

### ✅ Phase 2 — Déclenchement automatique (TERMINÉE)
- [x] Plist `launchd` : **3×/jour (08:00, 14:00, 20:00 local)** + RunAtLoad
- [x] Script shell `run.sh` (active venv → python main.py → log horodaté)
- [x] Commande bureau cliquable `~/Desktop/CARBON WORLD - Lancer.command`
- [x] `MIN_HOURS_BETWEEN_RUNS=5` protège contre double-runs
- [x] Installation script : `bash install.sh` + `uninstall.sh`
- [x] Service chargé et testé en conditions réelles

### ⏳ Phase 3 — Frontend `carbon-token.xyz` (à démarrer)
- [ ] Stack : Next.js **sur Vercel** (Cyril l'utilise déjà)
- [ ] Source des données : à décider entre :
  - Export JSON depuis SQLite → GitHub → Vercel lit à chaque build
  - Migration SQLite → Turso (cloud) → Next.js fetch au runtime
  - Tunnel Cloudflare depuis le Mac → API locale exposée
- [ ] Page publique : liste des décisions (BURN/MINT) avec détails
- [ ] Section "Pourquoi" : ethical_synthesis, aspects positifs/négatifs, SDGs touchés
- [ ] Graph supply CBWD dans le temps
- [ ] Lien vers chaque tx Solana Explorer (phase 4)
- [ ] Bilingue EN/FR

### ⏳ Phase 4 — Intégration Solana (mint/burn réel)
- [ ] Lib Python `solders` ou `solana-py`
- [ ] Wallet signer (clé privée chiffrée dans `.env`)
- [ ] Exécution BURN → transfert treasury → wallet unique dérivé → burn
- [ ] Exécution MINT → mintTo treasury
- [ ] Écriture `tx_hash` réel dans SQLite + sur Solana Explorer

### ⏳ Phase 5 — Mainnet + VPS
- [ ] Recréation mint sur mainnet
- [ ] Liquidité initiale DEX (Raydium)
- [ ] Migration worker → VPS Hetzner
- [ ] Monitoring (Uptime Kuma ou similaire)
- [ ] Ajout Twitter/X via RSSHub Docker OU X API Basic

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

### Pour reprendre demain
- Tout le contexte est dans `CLAUDE.md` (plan), `MEMORY.md` (journal), `RULES.md` (règles orchestrateur)
- Lire `MEMORY.md` en premier — section "Fait" + "Prochaine étape"
- Le launchd tournera à 08:00 → vérifier `~/CARBON-WORLD/logs/worker.log` au réveil

### Commandes utiles
```bash
# Déclenchement manuel (ignore le MIN_HOURS_BETWEEN_RUNS)
bash ~/CARBON-WORLD/launcher/run.sh --force

# Dry-run (analyse sans écriture DB)
bash ~/CARBON-WORLD/launcher/run.sh --force --dry-run

# Vérifier que launchd est chargé
launchctl list | grep carbonworld

# Voir les dernières décisions dans la DB
sqlite3 ~/CARBON-WORLD/data/carbon.db "SELECT id, decision, amount_crbn, final_score, event_title FROM carbon_events ORDER BY id DESC LIMIT 10;"

# Logs live
tail -f ~/CARBON-WORLD/logs/worker.log

# Désinstaller le launcher (garde le code)
bash ~/CARBON-WORLD/launcher/uninstall.sh
```
