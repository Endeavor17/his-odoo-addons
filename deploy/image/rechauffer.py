"""Rechauffe Odoo juste apres son demarrage, avant le premier vrai visiteur.

Sans ca, le premier a ouvrir l'appli paie le chargement du registre dans
chaque worker et la generation des bundles JS/CSS (plusieurs secondes pour
web.assets_web) : c'est la page blanche d'apres deploiement. Une fois genere,
un bundle est stocke en base et servi a tous.

Lance en arriere-plan par his-entrypoint.sh ; n'echoue jamais bruyamment.
"""

import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

BASE = "http://127.0.0.1:8069"
# /web/assets/1/<bundle> redirige vers la version courante et la genere.
BUNDLES = [
    "web.assets_frontend_minimal.min.js",
    "web.assets_frontend_lazy.min.js",
    "web.assets_frontend.min.css",
    "web.assets_web.min.js",
    "web.assets_web.min.css",
    "point_of_sale.assets_prod.min.js",
    "point_of_sale.assets_prod.min.css",
]


def get(chemin):
    debut = time.monotonic()
    try:
        with urllib.request.urlopen(BASE + chemin, timeout=120) as r:  # noqa: S310 -- URL locale fixe
            taille = len(r.read())
        return f"{chemin} {r.status} {taille} o {time.monotonic() - debut:.1f} s"
    except Exception as e:  # rechauffage : on note et on continue
        return f"{chemin} ECHEC {e}"


def main():
    for _ in range(300):  # Odoo pret en moins de 5 min, sinon on renonce
        try:
            urllib.request.urlopen(BASE + "/web/health", timeout=5)  # noqa: S310
            break
        except Exception:
            time.sleep(1)
    else:
        print("rechauffer : Odoo ne repond pas, abandon", flush=True)
        return
    debut = time.monotonic()
    # Plusieurs /web/login en parallele : chaque worker charge son registre.
    with ThreadPoolExecutor(4) as pool:
        for ligne in pool.map(get, ["/web/login"] * 4):
            print("rechauffer :", ligne, flush=True)
    for b in BUNDLES:
        print("rechauffer :", get(f"/web/assets/1/{b}"), flush=True)
    print(f"rechauffer : termine en {time.monotonic() - debut:.1f} s", flush=True)


if __name__ == "__main__":
    main()
