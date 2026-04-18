# AGENTS_PROMPT_RULES — Source de vérité des règles de prompt

> Ce fichier documente les règles d'écriture des prompts des agents IA du pipeline CARBON WORLD, les classes de bugs récurrentes, les calibrations d'échelle, et les anti-patterns à éviter. Il est mis à jour à chaque incident documenté et à chaque patch de prompt.

---

## 0. Principes de design

1. **Pas de checklists rigides**. Les "rules of thumb" du type `PUNISHES → BURN` / `APPROVES → MINT` marchent dans 80 % des cas et cassent sur les 20 % nuancés — qui sont précisément ceux que le système doit évaluer. Préférer des exemples qui enseignent un mode de raisonnement, pas un verdict.
2. **Ancrer quantitativement les échelles**. Dire "magnitude 1-10" sans ancrage laisse le LLM remplir à l'intuition → tendance à niveler. Toujours donner des repères chiffrés (voir §1).
3. **Règle des 2+ occurrences avant de patcher**. Ne JAMAIS ajouter une règle pour un cas théorique ou isolé. Attendre d'avoir au moins 2-3 occurrences réelles du même pattern dans le pipeline avant de toucher au prompt. Sinon on code contre un fantôme et on crée de nouveaux modes d'échec.
4. **Séparer confidence et polarité**. Une incertitude sur la pérennité ou la généralisation d'une action est un signal de *confidence* (score 1-10), pas un *negative_aspect* de magnitude élevée.
5. **Le prompt doit enseigner la tension, pas la résoudre**. Quand un event porte des forces contraires (ex : ordre public vs signal moral citoyen), le LLM doit identifier et nommer la tension, puis éventuellement conclure NEUTRAL plutôt que forcer un camp.
6. **Éditorial symétrie ≠ éthique symétrie**. Le réflexe de lister autant de pros que de cons crée des magnitudes nivelées qui faussent le score final. La réalité est asymétrique — le prompt doit le permettre.

---

## 1. Calibration des échelles

### Magnitude (positive_aspects / negative_aspects : 1-10)

| Niveau | Ancrage |
|---|---|
| **9-10** | Massif, irréversible, affecte des millions, frappe plusieurs ODD directement, ou viole un droit fondamental avec effet durable |
| **6-8** | Significatif, échelle nationale ou grande-régionale, impacte clairement 2-3 ODD, chaîne causale établie |
| **3-5** | Modéré, régional ou sectoriel, effet indirect, un seul ODD touché, réversible |
| **1-2** | Mineur, spéculatif, inquiétude de 2e ordre, réserve institutionnelle sans préjudice concret |

**Règle d'application** : si un positif frappe 3+ ODD avec mécanisme prouvé, et le négatif est une réserve spéculative (pérennité, généralisation, cadre), les magnitudes DOIVENT refléter ce différentiel — typiquement 7-8 vs 2-3, pas 6 vs 5.

### Confidence (1-10 entier, étape 6 du prompt analyst)

| Niveau | Signification |
|---|---|
| **9-10** | Données solides, consensus scientifique, historique clair |
| **7-8** | Bonnes données, incertitudes mineures |
| **5-6** | Données partielles, plusieurs hypothèses plausibles |
| **3-4** | Données limitées, forte incertitude |
| **1-2** | Quasi-spéculation, informations critiques manquantes |

### Scores 4D (-10 à +10)

- **SNAPSHOT** (25 %) : impact net actuel, tech et contexte d'aujourd'hui
- **TRAJECTORY** (20 %) : direction de la tendance sous-jacente
- **REVAULATION** (15 %) : ajustement sur 24 mois, triggers de re-jugement
- **PROSPECTIVE** (40 %) : somme pondérée de 3 scénarios 2-30 ans (optimiste/réaliste/pessimiste)

### Décision finale

```
final_score = snap × 0.25 + traj × 0.20 + reval × 0.15 + prosp × 0.40
```
- `≥ 6` → **BURN** (action positive)
- `≤ 4` → **MINT** (action négative)
- Entre → **NEUTRAL** (dropped, pas de tx on-chain)

---

## 2. Classes de bugs récurrentes

Chaque entrée suit le format : **Symptôme → Cause → Fix / à surveiller → Validation → Status**.

### 2.1 Nivellement des magnitudes ✅ FIXÉ (2026-04-18)
- **Identifié** : event #9 Seine-Saint-Denis (MINT 120K CBWD alors que l'action est positive, score 4.10)
- **Symptôme** : pros/cons listés correctement mais magnitudes équivalentes par réflexe d'équilibre rédactionnel → scores s'annulent autour de 4-5 → MINT/NEUTRAL sur une action nettement positive
- **Cause** : le prompt demandait `magnitude (1-10 integer)` sans ancrage chiffré. Le LLM remplissait à l'intuition et restait dans la zone 5-7 pour tout
- **Fix** : rubrique "MAGNITUDE CALIBRATION" ajoutée dans `worker/prompts/analyst_prompt.py` avec échelle ancrée + instruction "éditorial symétrie ≠ éthique symétrie" + règle "réserve institutionnelle = signal de confidence, pas negative_aspect de haute magnitude"
- **Validation** : re-submission Seine-Saint-Denis via Cerebras qwen-3-235b → magnitudes 8/6 vs 4 (vs niveau 5/5 supposé avant), score 4.10 → 5.36, MINT → NEUTRAL, amount 120K → 0
- **Commit** : voir §4 (historique)

### 2.2 Hallucination de risques structurels sur acteurs légitimes — PARTIELLEMENT ABSORBÉ par 2.1
- **Identifié** : event #9 Seine-Saint-Denis (le LLM invoque "non-pérennité", "inégalités territoriales", "manque de cadre institutionnel" alors que le département français agit dans sa compétence sociale légale)
- **Symptôme** : le LLM invente des critiques type "cadre institutionnel manquant" quand l'acteur agit pleinement dans son mandat légal
- **Cause probable** : pression du prompt à "trouver des négatifs partout" + absence de contexte institutionnel (subsidiarité française, compétences territoriales, etc.)
- **Fix ACTUEL** : la calibration magnitude (2.1) absorbe la plupart des cas — la critique reste listée mais avec magnitude appropriée (3-4), pas 6-8. Pas de règle explicite "subsidiarité = pas inégalité" car trop étroite.
- **À surveiller** : si le pattern persiste sur 2-3 cas même après 2.1, envisager d'ajouter une section "identifier le périmètre d'autorité de l'acteur avant de qualifier ses choix d'illégitimes"
- **Status** : observation continue

### 2.4 Dérive linguistique sur articles non-anglais ✅ FIXÉ (2026-04-18)
- **Identifié** : event #10 Seine-Saint-Denis — article source en français (Le Monde), le LLM a produit un `justification` en français ("Impact positif immédiat mais incertitude sur la pérennité...")
- **Symptôme** : les champs texte de sortie (`justification`, `ethical_synthesis`, `description` des aspects, `reason`, scénarios prospectifs) suivent la langue de l'article source au lieu de rester en anglais
- **Règle violée** : CLAUDE.md "Code : anglais uniquement (variables, logs, prompts IA, schémas JSON)". Le code et les sorties LLM doivent rester en anglais, seul le `event_title` est conservé en langue originale pour fidélité de source
- **Cause** : le prompt analyst était en anglais mais ne contenait AUCUNE directive explicite sur la langue de sortie. Le LLM suivait la langue de l'input par défaut
- **Fix** : nouvelle section "LANGUAGE (non-negotiable)" avant "STRICT OUTPUT FORMAT" dans `worker/prompts/analyst_prompt.py`. Énumère explicitement les champs concernés, rappelle que l'anglais est obligatoire même sur des articles FR/ES/PT/ZH/etc., et clarifie que seul `event_title` reste dans sa langue d'origine
- **Validation** : le prochain run du pipeline avec un article non-anglais doit produire tous les champs texte en anglais. Vérifier sur un event FR du prochain batch VPS.
- **Frontend** : `web/src/app/event/[id]/page.tsx` cache désormais la section "AI justification" sur les events reversés — le bandeau orange suffit et évite d'exposer le texte buggy historique

### 2.3 Tension ordre public vs signal moral — À SURVEILLER (pas encore observé en prod)
- **Exemple théorique** (Cyril, 2026-04-18) : militants condamnés pour action directe contre une entreprise anti-biodiversité. Règle naïve `PUNISHES wrongdoing → BURN` → condamnation positive. Réalité : la condamnation étouffe un signal moral citoyen légitime → net incertain/NEUTRAL
- **Cause prédite** : les "rule of thumb" des lignes 11-19 du `analyst_prompt.py` poussent à un verdict binaire au lieu d'une analyse de tension
- **Fix futur possible** : remplacer les rules of thumb par des exemples qui portent une tension réelle, demander au LLM d'identifier et nommer la tension avant de noter
- **NE PAS PATCHER TANT QU'ON N'A PAS** au moins 2-3 cas réels du pipeline qui exhibent cette erreur (règle §0.3)
- **Status** : à surveiller, ne rien faire pour l'instant

---

## 3. Anti-patterns (règles qu'on a été tenté d'ajouter mais rejetées)

### 3.1 "Subsidiarité = pas d'inégalité territoriale"
- **Tentation** : ajouter une règle qui dit "si l'acteur est une collectivité locale agissant dans sa compétence légale, ne pas coder 'inégalité territoriale' comme negative_aspect"
- **Rejeté par Cyril** (2026-04-18) : règle trop étroite, casserait d'autres cas (ex : une loi de répartition budgétaire étatique peut LÉGITIMEMENT créer des inégalités territoriales)
- **Leçon** : ne pas coder contre un cas, coder contre un pattern calibré

### 3.2 "Every event has positives AND negatives" — à assouplir ?
- **Tentation initiale (Claude, 2026-04-18)** : permettre `negative_aspects: []` si aucun n'applique honnêtement
- **Contre-argument (Cyril)** : l'exemple des militants condamnés montre que même un "bon" verdict juridique a un angle négatif légitime (étouffement d'un signal moral). La règle actuelle "EVERY event has both" est plus proche de la réalité qu'une règle qui permet des listes vides
- **Conclusion** : garder l'exigence pros+cons, fixer via magnitude (2.1) et éventuellement via tension (2.3 à venir)

---

## 4. Historique des modifications de prompt

| Date | Fichier | Commit | Classe de bug | Impact mesuré |
|---|---|---|---|---|
| 2026-04-18 | `worker/prompts/analyst_prompt.py` | (voir git log) | 2.1 nivellement magnitudes | Seine-Saint-Denis score 4.10→5.36, MINT→NEUTRAL, 120K CBWD évités |
| 2026-04-18 | `worker/prompts/analyst_prompt.py` | (voir git log) | 2.4 dérive linguistique FR/autres | Directive "LANGUAGE (non-negotiable)" ajoutée, tous champs texte désormais forcés en anglais |

---

## 5. Process pour ajouter une règle

1. Documenter le cas réel ici en §2 (symptôme + cause + event ID)
2. Attendre d'avoir **au moins 2 occurrences** du même pattern
3. Drafter le patch de prompt **avec un test A/B** : re-soumettre le cas connu avant/après pour valider le changement de score/décision
4. Mettre à jour §1 si l'échelle change, §2 avec le fix appliqué, §4 avec le commit
5. **NE JAMAIS** patcher un prompt sans validation quantitative (score avant/après sur au moins un cas réel documenté)
