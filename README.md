# Clash Royale Crawler

Bot crawler Python async pour construire une base de donnees massive de joueurs Clash Royale,
classes par activite, avec stockage compact dans **Turso** (libSQL) et raw JSON compresse dans **Cloudflare R2**.

---

## Pourquoi pas un endpoint /friends ?

L'API officielle Clash Royale **ne fournit pas d'endpoint pour recuperer les amis d'un joueur**.  
Le crawler decouvre donc les joueurs de proche en proche via :

1. Le joueur seed (`#GUUR8QP0`)
2. Son battlelog -> tous les adversaires et coequipiers visibles
3. Son clan -> tous les membres
4. Les battlelogs des membres -> nouveaux joueurs
5. Les clans des joueurs decouverts -> leurs membres
6. Et ainsi de suite jusqu'a `CRAWL_MAX_DEPTH` / `CRAWL_MAX_PLAYERS`

---

## Prerequis

- Python 3.11+
- Compte [Clash Royale Developer](https://developer.clashroyale.com/)
- Compte [Turso](https://turso.tech/)
- Compte [Cloudflare R2](https://developers.cloudflare.com/r2/)

---

## 1. Token Clash Royale API

1. Aller sur https://developer.clashroyale.com/
2. Creer un compte, se connecter
3. "My Account" > "Keys" > "Create New Key"
4. **Important** : entrer l'IP publique de votre machine (le token est lie a une IP)
5. Copier le token -> `CLASH_API_TOKEN` dans `.env`

---

## 2. Creer une base Turso

```bash
# Installer la CLI Turso
curl -sSfL https://get.tur.so/install.sh | bash

# Se connecter
turso auth login

# Creer la base
turso db create clash-royale-crawler

# Recuperer URL et token
turso db show clash-royale-crawler          # -> TURSO_DATABASE_URL
turso db tokens create clash-royale-crawler # -> TURSO_AUTH_TOKEN
```

---

## 3. Creer un bucket Cloudflare R2

1. Se connecter a https://dash.cloudflare.com/
2. R2 > "Create bucket" > nom : `clash-royale-raw`
3. "Manage R2 API tokens" > "Create API token" (Object Read & Write)
4. Noter `Access Key ID`, `Secret Access Key` et l'endpoint `https://<ACCOUNT_ID>.r2.cloudflarestorage.com`

---

## 4. Configurer .env

```bash
cp .env.example .env
# Editer .env avec vos vraies valeurs
```

---

## 5. Installation et lancement

```bash
# Installer les dependances
pip install -r requirements.txt

# Initialiser le schema
python main.py init-db

# Lancer le crawler
python main.py crawl

# Voir les statistiques
python main.py stats
```

---

## Structure du projet

```
clash-royale-crawler/
├── .env.example           Variables d environnement (modele)
├── requirements.txt       Dependances Python
├── README.md              Ce fichier
├── schema.sql             Schema SQL complet
├── main.py                CLI (init-db / crawl / stats)
└── src/
    ├── __init__.py
    ├── config.py          Chargement et validation .env
    ├── clash_api.py       Client HTTP async Clash Royale
    ├── db.py              Acces Turso / libSQL
    ├── r2_storage.py      Upload gzip vers Cloudflare R2
    ├── crawler.py         Moteur du crawler
    ├── classifier.py      Calcul activite joueur
    ├── normalize.py       Normalisation tags, temps, hashes
    ├── rate_limiter.py    Rate limiter async token bucket
    └── utils.py           Utilitaires
```

---

## Niveaux d activite

| Status  | Score  | Prochain scan |
|---------|--------|---------------|
| hot     | >= 100 | 30 minutes    |
| active  | >= 60  | 3 heures      |
| warm    | >= 25  | 24 heures     |
| cold    | > 0    | 7 jours       |
| unknown | 0      | 24 heures     |

---

## Reprise apres interruption

Le crawler peut etre **stoppe (Ctrl+C) et relance** sans perte de donnees.  
Les queues `player_queue` et `clan_queue` sont persistees dans Turso.  
Les upserts sont idempotents - aucune donnee n est perdue ni dupliquee.

---

## Endpoints utilises

| Endpoint | Usage |
|---|---|
| `GET /players/{tag}` | Profil complet joueur |
| `GET /players/{tag}/battlelog` | Historique batailles |
| `GET /clans/{tag}` | Infos clan |
| `GET /clans/{tag}/members` | Liste membres clan |

Les tags doivent etre URL-encodes : `#GUUR8QP0` -> `%23GUUR8QP0`.
