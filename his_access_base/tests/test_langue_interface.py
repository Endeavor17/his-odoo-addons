# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""L'interface suit la langue de l'utilisateur, jamais un libelle code en dur.

Regle posee par Mohamed le 2026-10-08, apres un melange francais/anglais dans
les listes deroulantes, les boutons et les tuiles. Odoo ne sait traduire que
DEPUIS l'anglais : pour un utilisateur en_US il rend la source telle quelle.
Une source francaise ne peut donc jamais s'afficher en anglais, et une source
anglaise sans fr.po ne s'affiche jamais en francais. D'ou deux exigences par
module du depot :

1. chaque terme traduisible a sa traduction dans i18n/fr.po ;
2. la source n'est pas du francais (detecte par ses accents : le francais sans
   accents du code passe entre les mailles, la revue humaine reste necessaire).

Le test lit les termes comme `odoo i18n export` les produit. Un echec dit
quel terme manque : relancer l'export du module et completer fr.po.
"""

import os

import polib
from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged
from odoo.tools.translate import TranslationModuleReader

# Tiers OCA vendus avec le depot : leurs traductions viennent d'OCA.
TIERS = {"web_responsive", "helpdesk_mgmt", "helpdesk_mgmt_crm"}
# Du contenu, pas de l'interface : les intitules de matieres s'enseignent dans
# la langue ou ils sont ecrits.
CONTENU = {"campus.subject,name"}
ACCENTS = set("éèêëàâîïôûùçœÉÈÊÀÂÎÔÛÇŒ«»")


@tagged("post_install", "-at_install")
class TestLangueInterface(TransactionCase):
    def _modules_du_depot(self):
        depot = os.path.dirname(get_module_path("his_access_base"))
        installes = self.env["ir.module.module"].search([("state", "=", "installed")]).mapped("name")
        return sorted(
            nom
            for nom in installes
            if nom not in TIERS and (get_module_path(nom, display_warning=False) or "").startswith(depot + os.sep)
        )

    def _termes(self, module):
        """{source: [noms]} tels qu'un export les produirait."""
        termes = {}
        for mod, _type, nom, _res_id, source, _value, _comments in TranslationModuleReader(
            self.env.cr, modules=[module], lang="en_US"
        ):
            if mod == module and source:
                termes.setdefault(source, []).append(nom)
        return termes

    def test_chaque_terme_a_sa_traduction_francaise(self):
        manquants = []
        for module in self._modules_du_depot():
            termes = self._termes(module)
            if not termes:
                continue
            chemin = os.path.join(get_module_path(module), "i18n", "fr.po")
            if not os.path.exists(chemin):
                manquants.append(f"{module}: pas de i18n/fr.po ({len(termes)} termes)")
                continue
            traduits = {e.msgid for e in polib.pofile(chemin) if e.msgstr and not e.obsolete}
            for source in sorted(set(termes) - traduits):
                manquants.append(f"{module}: {source!r}")
        self.assertFalse(
            manquants,
            "Termes sans traduction francaise :\n" + "\n".join(manquants[:60]),
        )

    def test_la_source_est_en_anglais(self):
        francais = []
        for module in self._modules_du_depot():
            for source, noms in self._termes(module).items():
                if all(nom in CONTENU for nom in noms):
                    continue
                if ACCENTS & set(source):
                    francais.append(f"{module}: {source[:90]!r}")
        self.assertFalse(
            francais,
            "Source en francais (la source doit etre anglaise, le francais va dans fr.po) :\n"
            + "\n".join(francais[:60]),
        )
