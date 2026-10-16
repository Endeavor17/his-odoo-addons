"""Quels modules installes ont change depuis leur dernier -u ?

Empreinte = sha256 du contenu de chaque module de /opt/his-addons, hors
static/ et tests/ (servis ou lus sans -u). Les empreintes du dernier -u
reussi vivent dans ir_config_parameter, cle his.module_hashes.

    modules_modifies.py liste             -> modules installes a mettre a jour, separes par des virgules
    modules_modifies.py enregistrer a,b   -> note l'empreinte actuelle de a et b (apres un -u reussi)

Connexion : odoo.conf ($ODOO_RC) d'abord, puis HOST/PORT/USER/PASSWORD,
comme /entrypoint.sh de l'image officielle.
"""

import configparser
import hashlib
import json
import os
import sys
from pathlib import Path

import psycopg2

ADDONS = Path("/opt/his-addons")
CLE = "his.module_hashes"
IGNORES = {"static", "tests", "__pycache__"}


def empreinte(module):
    h = hashlib.sha256()
    racine = ADDONS / module
    for chemin in sorted(racine.rglob("*")):
        rel = chemin.relative_to(racine)
        if not chemin.is_file() or IGNORES & set(rel.parts) or chemin.suffix == ".pyc":
            continue
        h.update(rel.as_posix().encode() + b"\0" + chemin.read_bytes() + b"\0")
    return h.hexdigest()


def connexion():
    conf = configparser.ConfigParser(interpolation=None)
    conf.read(os.environ.get("ODOO_RC", "/etc/odoo/odoo.conf"))
    opt = conf["options"] if conf.has_section("options") else {}
    dbname = opt.get("db_name")
    if not dbname or dbname == "False":
        sys.exit("modules_modifies : db_name absent de odoo.conf, base inconnue")
    return psycopg2.connect(
        dbname=dbname,
        host=opt.get("db_host") or os.environ.get("HOST", "db"),
        port=opt.get("db_port") or os.environ.get("PORT", "5432"),
        user=opt.get("db_user") or os.environ.get("USER", "odoo"),
        password=opt.get("db_password") or os.environ.get("PASSWORD", "odoo"),
    )


def lire(cr):
    cr.execute("SELECT value FROM ir_config_parameter WHERE key = %s", [CLE])
    row = cr.fetchone()
    return json.loads(row[0]) if row else {}


def main():
    commande = sys.argv[1]
    with connexion() as conn, conn.cursor() as cr:
        connues = lire(cr)
        if commande == "liste":
            cr.execute("SELECT name FROM ir_module_module WHERE state IN ('installed', 'to upgrade')")
            installes = sorted(n for (n,) in cr.fetchall() if (ADDONS / n / "__manifest__.py").is_file())
            print(",".join(m for m in installes if connues.get(m) != empreinte(m)))
        elif commande == "enregistrer":
            for m in sys.argv[2].split(","):
                if (ADDONS / m / "__manifest__.py").is_file():
                    connues[m] = empreinte(m)
            cr.execute(
                "INSERT INTO ir_config_parameter (key, value, create_date, write_date)"
                " VALUES (%s, %s, now() at time zone 'UTC', now() at time zone 'UTC')"
                " ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, write_date = EXCLUDED.write_date",
                [CLE, json.dumps(connues, sort_keys=True)],
            )


if __name__ == "__main__":
    main()
