# Monitoring — Uptime Kuma

Uptime Kuma tourne sur le VPS, en privé, bindé sur `127.0.0.1:3001`. Pas d'exposition publique du dashboard de monitoring (sécurité par défaut).

## Accès au dashboard

Via SSH tunnel depuis ton laptop :

```bash
ssh -L 3001:127.0.0.1:3001 carbon@157.90.250.40
```

Laisse la session SSH ouverte, puis dans ton navigateur : **http://localhost:3001**

Raccourci shell (à ajouter dans ton `~/.zshrc`) :

```bash
alias carbon-monitor='ssh -L 3001:127.0.0.1:3001 carbon@157.90.250.40'
```

## Setup initial (1re fois uniquement)

1. Ouvre le tunnel ci-dessus + http://localhost:3001
2. Uptime Kuma te demande de créer un **admin account** — choisis un user/pass robuste (password manager)
3. Clique **Add New Monitor** et crée les 3 moniteurs ci-dessous

### Monitor 1 — Site public HTTPS

| Champ | Valeur |
|---|---|
| Monitor Type | HTTP(s) |
| Friendly Name | `carbon-token.xyz` |
| URL | `https://carbon-token.xyz` |
| Heartbeat Interval | `300` (secondes, = 5 min) |
| Retries | 2 |
| Accepted Status Codes | `200-299` |

### Monitor 2 — API data freshness

| Champ | Valeur |
|---|---|
| Monitor Type | HTTP(s) - Keyword |
| Friendly Name | `api/stats` |
| URL | `https://carbon-token.xyz/api/stats` |
| Keyword | `total_events` |
| Heartbeat Interval | `300` |

### Monitor 3 — Heartbeat du cron pipeline

| Champ | Valeur |
|---|---|
| Monitor Type | Push |
| Friendly Name | `cron-pipeline` |
| Heartbeat Interval | `1200` (20 min — marge pour le cron 15 min) |
| Retries | 0 |

Une fois le monitor Push créé, Uptime Kuma génère un **token**. Exemple d'URL de push :
`http://127.0.0.1:3001/api/push/AbCdEf1234?status=up&msg=OK&ping=`

Copie ce token puis, sur le VPS, ajoute la ligne à la fin de `launcher/run_vps.sh` :

```bash
# Ping Uptime Kuma heartbeat (swallow errors to not break the pipeline)
curl -sSf "http://127.0.0.1:3001/api/push/<TOKEN>?status=up&msg=OK" > /dev/null 2>&1 || true
```

Remplace `<TOKEN>` par le token réel, commit + push.

## Notifications

Dans **Settings → Notifications** d'Uptime Kuma, ajoute au moins une notification :

- **Telegram** (gratuit, recommandé) : crée un bot via [@BotFather](https://t.me/BotFather), récupère le bot token + ton chat ID via [@userinfobot](https://t.me/userinfobot)
- **Email** (SMTP) : Gmail / Infomaniak / autre
- **Discord webhook** si tu préfères

Active la notification sur chaque monitor (édite chaque monitor, onglet Notifications).

## Gérer le container

```bash
ssh carbon@157.90.250.40

# Status
sudo docker ps --filter name=uptime-kuma

# Logs (utile si le dashboard ne répond pas)
sudo docker logs uptime-kuma --tail 50

# Restart
sudo docker restart uptime-kuma

# Stop/start
sudo docker stop uptime-kuma
sudo docker start uptime-kuma

# Données persistées dans /var/lib/uptime-kuma (volume docker)
sudo ls /var/lib/uptime-kuma
```

## Backup

Les données sont dans `/var/lib/uptime-kuma` sur le VPS. Pour un snapshot :

```bash
ssh carbon@157.90.250.40 "sudo tar czf /tmp/uptime-kuma-backup-\$(date +%Y%m%d).tgz /var/lib/uptime-kuma"
scp carbon@157.90.250.40:/tmp/uptime-kuma-backup-*.tgz ./
```

## Mise à niveau

```bash
ssh carbon@157.90.250.40 "sudo docker pull louislam/uptime-kuma:1 && sudo docker stop uptime-kuma && sudo docker rm uptime-kuma && sudo docker run -d --restart=always --name uptime-kuma -p 127.0.0.1:3001:3001 -v /var/lib/uptime-kuma:/app/data louislam/uptime-kuma:1"
```

Les données sont préservées via le volume `/var/lib/uptime-kuma`.

## Pourquoi privé et pas public ?

Exposer un dashboard de monitoring publiquement = surface d'attaque gratuite (panneau admin, info de structure). Le SSH tunnel :
- Aucun port public
- Auth via clé SSH (déjà en place)
- Aucune DNS à modifier

Si plus tard tu veux y accéder depuis ton téléphone sans SSH, on pourra ajouter Caddy + basic auth sur un sous-domaine `status.carbon-token.xyz` — ce sera un commit de 10 lignes le moment venu.
