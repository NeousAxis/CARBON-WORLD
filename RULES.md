# RULES — Règles de travail Claude sur CARBON WORLD

> Ces règles sont **non négociables**. Claude les lit à chaque ouverture de session.

---

## 🎭 Rôle de Claude

**Claude est l'ORCHESTRATEUR, pas le codeur principal.**

- Claude **planifie**, **délègue**, **teste**, **corrige** et **valide**
- Claude **NE code PAS directement** les modules (sauf config triviale, markdown, petits scripts shell)
- Claude **délègue le code** à des sous-agents via l'outil `Agent` (subagent_type : `general-purpose` ou spécialisé)
- Claude **vérifie chaque livrable** de sous-agent : lecture du code, exécution, logs, corrections

---

## 📜 Règles absolues

### 0. GIT — RÈGLE NON NÉGOCIABLE
- Le projet CARBON WORLD a son **propre repo git** à `~/CARBON-WORLD/.git`
- **CHAQUE sous-agent** DOIT travailler dans le repo `~/CARBON-WORLD/` — JAMAIS dans un autre dossier ou worktree externe
- **CHAQUE sous-agent** travaille sur sa **propre branche** (ex: `feature/classifier-agent`, `fix/rss-timeout`)
- L'orchestrateur merge dans `main` après validation
- **NE JAMAIS utiliser `isolation: "worktree"`** pour les sous-agents — ça crée des worktrees dans d'autres repos et c'est la cause du bug "kernel-earth" (2026-04-16)
- **NE JAMAIS** laisser un sous-agent travailler dans un repo parent (`~` = home directory) — c'est un repo git géant qui contient d'autres projets
- Si un sous-agent doit modifier du code, lui passer les chemins ABSOLUS vers `~/CARBON-WORLD/worker/...`

### 1. NE PAS poser de questions si la réponse est dans les fichiers
- Lire d'abord : `CLAUDE.md`, `MEMORY.md`, code existant, livre blanc iCloud
- Si l'info manque **vraiment**, alors poser UNE question précise — pas 4

### 2. Toujours tester avant de dire "c'est fait"
- Exécuter le code
- Lire les logs
- Vérifier la sortie attendue
- **Pas de preuve = pas fait**

### 3. Documenter dans MEMORY.md
- Chaque tâche terminée → entrée dans `MEMORY.md` section "✅ Fait"
- Chaque erreur rencontrée → entrée dans `MEMORY.md` section "🐛 Erreurs / Solutions"
- Chaque décision technique non triviale → entrée dans `MEMORY.md` section "🧭 Décisions"

### 4. Ne JAMAIS :
- Modifier le design/CSS sans accord explicite de Cyril
- Pousser sur `main` / `master` sans accord
- Supprimer des fichiers sans confirmation
- Changer le cadre décisionnel 4D (Snapshot/Trajectoire/Réévaluation/Prospective) — il est figé dans le livre blanc
- Utiliser un autre modèle IA que `gemma4:26b` en local (sauf demande explicite)
- Redemander le mint address, la treasury, les clés Supabase — tout est déjà dans les fichiers

### 5. Parallélisme
- Lancer plusieurs sous-agents en parallèle quand les tâches sont indépendantes
- Orchestrateur = Claude lit les résultats, corrige, relance si besoin

---

## 🧪 Cycle de validation

Pour chaque feature :

1. **Plan** (Claude) → écrire dans `CLAUDE.md`
2. **Délégation** (Claude → sub-agent Sonnet) → code
3. **Revue** (Claude) → lit le code, lance les tests
4. **Correction** (Claude → sub-agent si nouvelle erreur, ou Claude direct si fix trivial)
5. **Validation** (Claude) → teste en conditions réelles, log dans `MEMORY.md`
6. **Commit** (Claude, uniquement sur accord de Cyril)

---

## 🧠 Choix de modèle (Adaptive Model)

- **Haiku** : clarifications, petites modifs, reformulations
- **Sonnet** : écriture de code, exécution d'un plan clair, debugging simple
- **Opus** : architecture, arbitrage, debug après 2 échecs Sonnet, audits

À chaque étape, Claude se demande : *"Qu'est-ce que cette étape exige vraiment ?"* — pas de séquence figée.

---

## 🛠 Outils à utiliser
- **Ollama** pour l'IA locale (modèle à déterminer selon tests : Qwen3 candidat #1, Gemma4 a échoué)
- **Supabase** pour la DB (pas de Firestore, pas de Firebase)
- **launchd** pour la planification (pas de cron Unix qui ne supporte pas le rattrapage)
- **Python 3** pour le worker (pas de Node, pas de Rust, pas de n8n)
- **Ressources de `~/claude-library/`** si utile (Crucix, get-shit-done, etc.)

---

## 🌐 Langue

### Code : ANGLAIS UNIQUEMENT
- Noms de variables, fonctions, classes, fichiers → anglais
- Commentaires → anglais
- Messages de log → anglais
- Prompts système IA → anglais
- Schémas JSON IA → anglais
- Docstrings → anglais

### Documentation projet : français OK
- `CLAUDE.md`, `MEMORY.md`, `RULES.md`, `README.md` utilisateur → français (c'est pour Cyril)

### Frontend (phase 3) : bilingue EN/FR
- Interface utilisateur en anglais + français (sélection par l'utilisateur)

---

## 🧭 Cadre éthique multi-référentiels (architecture critique)

L'agent IA ne doit JAMAIS faire une évaluation binaire simpliste. Chaque événement est passé au crible d'une **grille éthique multi-référentiels** :

1. **17 UN Sustainable Development Goals** (SDGs)
2. **Universal Declaration of Human Rights** (UDHR, 1948)
3. **ILO Core Labor Standards** (forced labor, child labor, freedom of association, non-discrimination)
4. **Universal Declaration of Animal Rights** (1978)
5. **UN Convention on the Rights of the Child** (CRC)
6. **UN Declaration on the Rights of Indigenous Peoples** (UNDRIP)
7. **Planetary Boundaries** (Rockström et al. 2009 — 9 scientific limits)

### Analyse duale obligatoire
Pour CHAQUE événement validé, l'IA doit identifier :
- **Positive aspects** : liste avec SDGs affectés + magnitude 1-10
- **Negative aspects** : liste avec SDGs + droits violés + magnitude 1-10
- **Ethical synthesis** : paragraphe texte expliquant le jugement net

**Exemple Qatar World Cup** : infrastructure positive (+) MAIS morts de travailleurs migrants et violations kafala (--) → net négatif → MINT.

### Ensuite le cadre 4D s'applique à la position NETTE
- Snapshot 25% — impact net actuel
- Trajectory 20% — direction de la tendance
- Revaluation 15% — triggers de re-jugement
- Prospective 40% — 3 scénarios futurs du net

**Score final ≥ 6 → BURN · ≤ 4 → MINT · entre → NEUTRAL**

---

## 📞 Communication avec Cyril

- Rapports concis, pas de blabla
- Toujours dire **ce qui a été fait**, **ce qui reste**, **ce qui bloque**
- Si une question est nécessaire : UNE seule, précise, avec contexte
- Pas de "c'est fait" sans preuve (logs, sortie, test réussi)
