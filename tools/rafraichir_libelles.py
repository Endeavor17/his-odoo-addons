"""Remet les libelles des enregistrements de donnees dans la langue de la source.

A lancer UNE FOIS sur une base existante, apres la mise a jour qui fait passer
l'interface a « source anglaise + i18n/fr.po » (branche fix/langue-et-police).

Pourquoi un script : la plupart des donnees de nos modules sont en noupdate
(categories de caisse, types d'operation, motifs de rebut, forfaits repas,
barèmes Campus+...). Odoo n'y retouche jamais, ni a `-u` ni avec
--i18n-overwrite : ces enregistrements garderaient leur ancien libelle francais
comme valeur source, donc un utilisateur en anglais verrait du francais, et le
fr.po ne s'y appliquerait pas.

Pour chaque terme `model:` des fr.po du depot, le script pose, sur
l'enregistrement designe par son identifiant XML :
- en_US = la source anglaise du fr.po ;
- fr_FR = sa traduction.
En SQL et non par l'ORM : un barème Campus+ publie refuse toute ecriture, et
ce n'est pas une modification de fond, seulement de libelle.

Seuls les champs traduits « simples » (translate=True) sont touches. Les champs
HTML (corps de courriel) sont decoupes en fragments par Odoo et ne se
reecrivent pas d'un bloc : ils ne changent ici que de police, sans enjeu.

Attention : un libelle de donnees qu'un humain a modifie dans l'interface est
ECRASE (les categories de caisse, par exemple). Le mode a blanc les liste.

    # A blanc : liste ce qui changerait, n'ecrit rien
    docker exec -i <conteneur-odoo> odoo shell -c /etc/odoo/odoo.conf -d <base> \
        --no-http < tools/rafraichir_libelles.py

    # Pour de bon
    docker exec -i -e APPLIQUER=1 <conteneur-odoo> odoo shell -c /etc/odoo/odoo.conf \
        -d <base> --no-http < tools/rafraichir_libelles.py

Ordre en production : sauvegarde, `-u <modules> --i18n-overwrite`, ce script,
redemarrage du conteneur.
"""

import json
import os
import re

import polib
from odoo.modules.module import get_module_path
from odoo.tools import SQL

APPLIQUER = os.environ.get("APPLIQUER") == "1"
TIERS = {"web_responsive", "helpdesk_mgmt", "helpdesk_mgmt_crm"}
OCCURRENCE = re.compile(r"^model:([\w.]+),(\w+):([\w]+)\.(\S+)$")

if "fr_FR" not in [code for code, _nom in env["res.lang"].get_installed()]:
    print("fr_FR n'est pas installe sur cette base : seules les sources anglaises seront posees.")

depot = os.path.dirname(get_module_path("his_access_base"))
installes = env["ir.module.module"].search([("state", "=", "installed")]).mapped("name")
changements = 0
for module in sorted(installes):
    chemin_module = get_module_path(module, display_warning=False) or ""
    if module in TIERS or not chemin_module.startswith(depot + os.sep):
        continue
    chemin_po = os.path.join(chemin_module, "i18n", "fr.po")
    if not os.path.exists(chemin_po):
        continue
    for entree in polib.pofile(chemin_po):
        for occurrence, _ligne in entree.occurrences:
            m = OCCURRENCE.match(occurrence)
            if not m:
                continue
            modele, champ, xml_module, xml_nom = m.groups()
            if modele not in env:
                continue
            field = env[modele]._fields.get(champ)
            if not field or field.translate is not True or not field.store:
                continue
            res_id = env["ir.model.data"]._xmlid_to_res_id(f"{xml_module}.{xml_nom}", raise_if_not_found=False)
            if not res_id:
                continue
            table = env[modele]._table
            env.cr.execute(SQL("SELECT %s FROM %s WHERE id = %s", SQL.identifier(champ), SQL.identifier(table), res_id))
            ligne = env.cr.fetchone()
            actuel = (ligne and ligne[0]) or {}
            voulu = dict(actuel, en_US=entree.msgid)
            if entree.msgstr:
                voulu["fr_FR"] = entree.msgstr
            if voulu == actuel:
                continue
            changements += 1
            print(f"{modele} {xml_module}.{xml_nom} [{champ}] : {actuel.get('en_US')!r} -> {entree.msgid!r}")
            if APPLIQUER:
                env.cr.execute(
                    SQL(
                        "UPDATE %s SET %s = %s::jsonb WHERE id = %s",
                        SQL.identifier(table),
                        SQL.identifier(champ),
                        json.dumps(voulu),
                        res_id,
                    )
                )

if APPLIQUER:
    env.cr.commit()
    env.registry.clear_cache()
    print(f"{changements} libelle(s) reecrit(s).")
else:
    print(f"A blanc : {changements} libelle(s) changeraient. Relancer avec APPLIQUER=1.")
