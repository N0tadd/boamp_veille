"""
Veille BOAMP — Notifications Discord
By N0tad
"""

import requests
import sys
import json
import os
import gc
import schedule
import time
from datetime import date

# ─── CONFIG ───────────────────────────────────────────────────────────────────

LOG_FILE         = os.path.join(os.path.dirname(os.path.abspath(__file__)), "boamp_log.txt")
DISCORD_WEBHOOK_URL = "mettre le lien de son webhook discord ici"
FICHIER_VUS      = os.path.join(os.path.dirname(os.path.abspath(__file__)), "boamp_vus.json")
API_URL          = "https://www.boamp.fr/api/explore/v2.1/catalog/datasets/boamp/records"

# ─── LOGS ─────────────────────────────────────────────────────────────────────

class Logger:
    def __init__(self, filepath):
        self.terminal = sys.stdout
        self.log = open(filepath, "a", encoding="utf-8")

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)
        self.log.flush()

    def flush(self):
        self.terminal.flush()
        self.log.flush()

sys.stdout = Logger(LOG_FILE)

# ─── REQUÊTE API ──────────────────────────────────────────────────────────────

def construire_where():
    aujourd_hui = date.today().isoformat()
    return (
        '(dc in ("63","169","222"))'
        ' AND (code_departement in ("35","37","44","49","53","56","72","79","85"))' # à personnaliser
        f' AND ((datelimitereponse is not null AND datelimitereponse>=\'{aujourd_hui}\')' # à personnaliser
        f' OR (datelimitereponse is null AND datefindiffusion>=\'{aujourd_hui}\'))' # à personnaliser
    )

def recuperer_avis():
    params = {
        "where":    construire_where(),
        "limit":    100,
        "select":   "idweb,objet,nomacheteur,dateparution,datelimitereponse,code_departement,url_avis",
        "order_by": "dateparution DESC",
    }
    try:
        r = requests.get(API_URL, params=params, timeout=15)
        r.raise_for_status()
        data = r.json().get("results", [])
        return data
    except Exception as e:
        print(f"[ERREUR] Appel API : {e}")
        return []

# ─── STOCKAGE ─────────────────────────────────────────────────────────────────

def charger_vus() -> set:
    if not os.path.exists(FICHIER_VUS):
        return set()
    try:
        with open(FICHIER_VUS, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except (json.JSONDecodeError, ValueError):
        print("[WARN] boamp_vus.json corrompu, réinitialisation")
        return set()

def sauvegarder_vus(vus: set):
    with open(FICHIER_VUS, "w", encoding="utf-8") as f:
        json.dump(list(vus), f, indent=2)

# ─── DISCORD ──────────────────────────────────────────────────────────────────

def envoyer_discord(avis: dict):
    idweb         = avis.get("idweb", "")
    objet         = avis.get("objet", "Sans titre")
    acheteur      = avis.get("nomacheteur", "Inconnu")
    date_parution = avis.get("dateparution", "")[:10]
    date_limite   = avis.get("datelimitereponse", "")
    date_limite   = date_limite[:10] if date_limite else "Non précisée"
    departement   = avis.get("code_departement", "")
    url           = avis.get("url_avis", "")

    message = {
        "embeds": [{
            "title":       f"📢 Nouvel avis BOAMP — Dept {departement}",
            "description": f"**{objet}**",
            "color":       0x1D6FA5,
            "fields": [
                {"name": "🏢 Acheteur",   "value": acheteur,      "inline": True},
                {"name": "📅 Publié le",   "value": date_parution, "inline": True},
                {"name": "⏳ Date limite", "value": date_limite,   "inline": True},
            ],
            "url":    url,
            "footer": {"text": f"ID : {idweb}"},
        }]
    }

    try:
        r = requests.post(DISCORD_WEBHOOK_URL, json=message, timeout=10)
        r.raise_for_status()
        print(f"[DISCORD] Envoyé : {idweb}")
    except Exception as e:
        print(f"[ERREUR] Discord ({idweb}) : {e}")

# ─── BOUCLE PRINCIPALE ────────────────────────────────────────────────────────

def verifier():
    try:
        print(f"[CHECK] {time.strftime('%H:%M:%S')} — Vérification en cours...")

        vus      = charger_vus()
        avis_api = recuperer_avis()
        nouveaux = [a for a in avis_api if a.get("idweb") not in vus]

        if not nouveaux:
            print("[CHECK] Aucun nouvel avis.")
            return

        print(f"[CHECK] {len(nouveaux)} nouvel(s) avis trouvé(s) !")
        for avis in nouveaux:
            envoyer_discord(avis)
            vus.add(avis.get("idweb"))
            time.sleep(1)

        sauvegarder_vus(vus)

    except Exception as e:
        print(f"[ERREUR CRITIQUE] verifier() : {e}")
        import traceback; traceback.print_exc()
    finally:
        gc.collect()

# ─── LANCEMENT ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("🚀 Veille BOAMP démarrée — vérification toutes les 15 minutes")
    print(f"   Webhook : {DISCORD_WEBHOOK_URL[:50]}...")
    print()

    verifier()

    schedule.every(15).minutes.do(verifier)

    while True:
        try:
            schedule.run_pending()
        except Exception as e:
            print(f"[ERREUR] Boucle principale : {e}")
        time.sleep(30)
