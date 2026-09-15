# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""La politique de droits du groupe, tenue par des tests.

Ces tests n'inspectent pas une liste ecrite d'avance : ils lisent le registre
REELLEMENT INSTALLE. C'est ce qui les rend generaux — un module livre dans six
mois qui ouvrirait un modele a tout le monde les fera echouer sans que personne
ait eu a penser a les mettre a jour.

Une politique sans controle pourrit : les regles s'ecrivent, puis quelqu'un
livre vite un vendredi, et deux ans plus tard le referentiel des etudiants est
lisible par n'importe quel salarie. C'est exactement ce qui s'etait produit ici.
"""
from odoo.tests import TransactionCase, tagged

# Prefixe de nos modules. Ceux d'Odoo et de l'OCA ne sont pas juges par cette
# politique : on ne les maitrise pas.
NOTRE_PREFIXE = 'his_'

# ============================ REGISTRE DES DEROGATIONS ======================
#
# Un modele ne figure ici que s'il est de la DONNEE DE REFERENCE : non
# nominative, non sensible, et necessaire a tous pour lire un ecran metier.
# Chaque ligne porte son motif. Ajouter une entree est une decision, pas une
# formalite — c'est le sens d'un registre de derogations : assumer l'exception
# plutot que l'oublier.
REFERENCE_PARTAGEE = {
    'his.domaine': "Bareme des domaines : lu pour afficher un score de candidature.",
    'his.specialite': "Catalogue des specialites : lu partout, ne nomme personne.",
    'his.document.type': "Types de pieces : configuration, aucune donnee personnelle.",
    'his.content.deliverable.type': "Types de livrables : configuration de la production.",
    'his.faculty': "Facultes : donnee de reference, lue pour afficher un rattachement, ne nomme personne.",
}

# Paires de roles qui ne se cumulent pas sur un meme compte.
# La branche pose deja qu'un lead n'est gagne qu'a l'encaissement, tenu par une
# contrainte serveur. On l'exprime aussi au niveau des roles, pour que la regle
# ne repose pas sur un garde-fou unique.
SEPARATION_DES_TACHES = [
    (
        'his_admission.group_his_finance',
        'his_crm_pipeline.group_admissions_conseiller',
        "Qui encaisse ne doit pas etre celui qui a vendu : l'encaissement fait "
        "basculer le lead en gagne.",
    ),
]

# Ce qu'un utilisateur interne SANS AUCUN ROLE doit voir, et rien de plus.
#
# « Apps » en a fait partie par erreur. La note precedente affirmait qu'Odoo 19
# livre ce menu sans groupe « y compris sur une base vierge — verifie » : c'est
# faux, et la verification avait ete faite sur une base deja abimee. Une base
# creee avec `-i base` seul porte bien « Role / Administrator » (group_system)
# sur base.menu_management ; le source le declare (base/views/base_menus.xml).
# Ce sont nos bases qui l'avaient perdu, maintenance_university l'ayant remplace
# par un (6, 0, [...]) dont la desinstallation a emporte le dernier groupe.
# socle_menus.xml le repose ; un graphiste ne voit plus la tuile « Apps ».
#
# « Discuss » N'EN FAIT PLUS PARTIE (decision de Mohamed, 2026-09-15 : un
# ouvrier ne garde pas Discuss). maintenance_university retire deja
# `base.group_user` du menu Discuss ; comme un ouvrier de maintenance implique
# `base.group_user`, retirer Discuss du socle est le SEUL moyen de le lui
# retirer, et cela vaut donc pour tout compte sans role. Discuss redevient
# visible pour qui porte un role qui le lui reaccorde. Ce test suppose donc
# maintenance_university installe — c'est le cas en production et en CI.
#
# « Dashboards » est tolere : le menu de `spreadsheet_dashboard` est tire
# transitivement par les modules-pont du POS (spreadsheet_dashboard_pos_*), ne
# porte aucun groupe en natif et n'affiche AUCUNE donnee a un compte sans role.
# Le fermer proprement exigerait une dependance dure vers un module sans rapport
# (spreadsheet_dashboard) sur toutes les bases, POS ou non : cout injustifie
# pour une coquille vide. Exception assumee, au meme titre que REFERENCE_PARTAGEE.
SOCLE_ATTENDU = {'Calendar', 'Dashboards'}


@tagged('post_install', '-at_install')
class TestPolitiqueAcces(TransactionCase):

    def _modules_a_nous(self):
        return self.env['ir.module.module'].search([
            ('state', '=', 'installed'), ('name', '=like', NOTRE_PREFIXE + '%'),
        ]).mapped('name')

    def _acl_a_nous(self):
        """Les ACL declarees PAR nos modules, quel que soit le modele vise."""
        donnees = self.env['ir.model.data'].search([
            ('model', '=', 'ir.model.access'),
            ('module', 'in', self._modules_a_nous()),
        ])
        return self.env['ir.model.access'].browse(donnees.mapped('res_id')).exists()

    # ------------------------------------------------------------------------

    def test_aucun_modele_metier_ouvert_a_tout_le_monde(self):
        """Le defaut d'origine : une ligne d'ACL sur base.group_user suffisait a
        ouvrir le referentiel d'identite du groupe a n'importe quel salarie."""
        interne = self.env.ref('base.group_user')
        fautives = []

        for acl in self._acl_a_nous():
            if acl.group_id != interne:
                continue
            modele = acl.model_id.model
            if modele in REFERENCE_PARTAGEE:
                # Une derogation ne vaut que pour la LECTURE.
                if acl.perm_write or acl.perm_create or acl.perm_unlink:
                    fautives.append(
                        "%s : derogation en lecture seule, or cette ACL accorde "
                        "l'ecriture." % modele
                    )
                continue
            fautives.append(
                "%s est ouvert a tout utilisateur interne (ACL %s). Soit il est "
                "reserve a un role, soit il rejoint REFERENCE_PARTAGEE avec son "
                "motif." % (modele, acl.name)
            )

        self.assertFalse(fautives, "\n".join(fautives))

    def test_le_socle_ne_contient_que_les_outils_communs(self):
        """Attrape un module qui rouvrirait une application a tout le monde.

        Le test le plus large : il ne regarde aucun modele en particulier, il
        regarde ce qu'une personne sans role voit en arrivant.
        """
        nu = self.env['res.users'].create({
            'name': "Sans role", 'login': 'zz_politique_socle',
            'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
        })

        vues = set(self.env['ir.ui.menu'].with_user(nu).search(
            [('parent_id', '=', False)],
        )._filter_visible_menus().mapped('name'))

        self.assertEqual(
            vues, SOCLE_ATTENDU,
            "Le socle a change. En trop : %s. Manquant : %s." % (
                sorted(vues - SOCLE_ATTENDU) or "rien",
                sorted(SOCLE_ATTENDU - vues) or "rien",
            ),
        )

    def test_tout_modele_a_nous_porte_au_moins_une_acl(self):
        """Un modele sans ACL n'est pas « ferme » : il est inutilisable, et le
        defaut ne se voit qu'en production, sur le geste de quelqu'un."""
        nos_modules = self._modules_a_nous()
        sans_droits = []

        for modele in self.env['ir.model'].search([('transient', '=', False)]):
            xmlid = modele.get_external_id().get(modele.id) or ''
            if xmlid.split('.')[0] not in nos_modules:
                continue
            # Les modeles ABSTRAITS n'ont pas de table : his.dashboard ne
            # stocke rien, il repond a des questions. Une ACL sur un tel
            # modele n'aurait aucun sens.
            if self.env[modele.model]._abstract:
                continue
            if not self.env['ir.model.access'].search_count(
                [('model_id', '=', modele.id)],
            ):
                sans_droits.append(modele.model)

        self.assertFalse(
            sans_droits, "Modeles sans aucune ACL : %s" % ", ".join(sans_droits),
        )

    def test_separation_des_taches(self):
        """Deux roles qu'une meme personne ne doit pas cumuler."""
        for xmlid_a, xmlid_b, motif in SEPARATION_DES_TACHES:
            groupe_a = self.env.ref(xmlid_a, raise_if_not_found=False)
            groupe_b = self.env.ref(xmlid_b, raise_if_not_found=False)
            if not groupe_a or not groupe_b:
                continue

            # Ni l'un ni l'autre ne doit impliquer son incompatible par une
            # chaine : le cumul se ferait alors sans que personne l'ait coche.
            self.assertNotIn(
                groupe_b, groupe_a.all_implied_ids,
                "%s implique %s. %s" % (xmlid_a, xmlid_b, motif),
            )
            self.assertNotIn(
                groupe_a, groupe_b.all_implied_ids,
                "%s implique %s. %s" % (xmlid_b, xmlid_a, motif),
            )

            cumulards = self.env['res.users'].search([
                ('group_ids', 'in', groupe_a.id),
                ('group_ids', 'in', groupe_b.id),
                ('active', '=', True),
            ])
            self.assertFalse(
                cumulards,
                "%s cumule(nt) %s et %s. %s" % (
                    cumulards.mapped('login'), xmlid_a, xmlid_b, motif,
                ),
            )
