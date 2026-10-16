"""Attache a chaque article du catalogue sa photo de tools/seed/images/.
Run via `odoo shell -d <base>` ; A BLANC par defaut, APPLIQUER=1 pour ecrire.

Le fichier porte le nom exact de l'article, aux caracteres interdits par
Windows pres : « ∕ » pour « / », « ∗ » pour « * », « ʺ » pour « " », et « _ »
pour tout autre caractere (« % », « ' »). Une photo qui ne designe pas
exactement UN article est signalee, jamais devinee. Un article qui a deja une
image n'est pas touche : rejouable sans ecraser une photo changee a la main.

Sur staging/prod, tools/ n'est pas dans l'image (.dockerignore) : copier
tools/seed/images et ce script dans le conteneur (docker cp) et passer
IMAGES_DIR vers la copie.
"""

import base64
import os
import re

IMAGES_DIR = os.environ.get("IMAGES_DIR", "/mnt/extra-addons/tools/seed/images")
APPLIQUER = os.environ.get("APPLIQUER") == "1"
WINDOWS = str.maketrans({"∕": "/", "∗": "*", "ʺ": '"'})

templates = env["product.template"].search([])
by_name = {}
for t in templates:
    by_name.setdefault(t.name.strip().lower(), []).append(t)

poses, deja, orphelines, ambigues = [], [], [], []
for fichier in sorted(os.listdir(IMAGES_DIR)):
    stem, ext = os.path.splitext(fichier)
    if ext.lower() not in (".jpg", ".jpeg", ".png"):
        continue
    motif = re.compile(re.escape(stem.translate(WINDOWS).strip().lower()).replace("_", ".") + "$")
    cibles = [t for name, ts in by_name.items() if motif.match(name) for t in ts]
    if not cibles:
        orphelines.append(fichier)
    elif len(cibles) > 1:
        ambigues.append((fichier, [t.name for t in cibles]))
    elif cibles[0].image_1920:
        deja.append(fichier)
    else:
        if APPLIQUER:
            with open(os.path.join(IMAGES_DIR, fichier), "rb") as f:
                cibles[0].image_1920 = base64.b64encode(f.read())
        poses.append(fichier)

print(
    "%s : %d photos posees, %d articles avaient deja une image"
    % ("APPLIQUE" if APPLIQUER else "A BLANC", len(poses), len(deja))
)
print("%d photos sans article :" % len(orphelines))
for f in orphelines:
    print("   ", f)
print("%d photos designant plusieurs articles :" % len(ambigues))
for f, noms in ambigues:
    print("   ", f, "->", noms)

if APPLIQUER:
    env.cr.commit()
    print("%d articles restent sans photo" % env["product.template"].search_count([("image_1920", "=", False)]))
