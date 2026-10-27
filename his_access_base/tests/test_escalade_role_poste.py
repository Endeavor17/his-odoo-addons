# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Faille S-1 de l'audit : un poste ne doit pas pouvoir conferer l'administration.

Reproduit le scenario confirme : un employe cumulant RH et recrutement se
rendait administrateur en creant un poste, en y mettant le groupe
« Administration / Reglages », puis en se l'attribuant. Ces tests tournent en
`with_user()` (comme un vrai compte, pas en superuser), sinon la contrainte
serait contournee.
"""

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestEscaladeRolePoste(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.admin_group = cls.env.ref("base.group_system")
        cls.annuaire = cls.env.ref("his_access_base.group_annuaire")
        groups = [
            cls.env.ref("base.group_user").id,
            cls.env.ref("hr.group_hr_user").id,
        ]
        rec = cls.env.ref("hr_recruitment.group_hr_recruitment_user", raise_if_not_found=False)
        if rec:
            groups.append(rec.id)
        cls.rh = cls.env["res.users"].create(
            {"name": "RH+Recrutement", "login": "zz_rh_rec", "group_ids": [(6, 0, groups)]}
        )

    def test_un_poste_refuse_le_groupe_administration(self):
        """Le coeur du correctif : RH ne choisit pas les roles d'un poste.

        Seul l'administrateur des droits ecrit `role_ids` ; un role ne peut de
        toute facon pas porter l'administration (TestHisRole).
        """
        admin_role = self.env["his.role"].create({"name": "Ordinary"})
        job = self.env["hr.job"].with_user(self.rh).create({"name": "Charge RH"})
        with self.assertRaises(AccessError):
            job.write({"role_ids": [(4, admin_role.id)]})

    def test_rh_ne_cree_pas_de_role(self):
        """Sinon RH se fabriquerait un role puis le rattacherait a son poste."""
        with self.assertRaises(AccessError):
            self.env["his.role"].with_user(self.rh).create({"name": "ZZ piege"})

    def test_un_role_de_poste_ordinaire_reste_permis(self):
        """Le correctif ne bloque que l'administration, pas les vrais roles."""
        role = self.env["his.role"].create({"name": "Directory", "group_ids": [(6, 0, [self.annuaire.id])]})
        job = self.env["hr.job"].create({"name": "Poste normal", "role_ids": [(6, 0, role.ids)]})
        self.assertEqual(job.role_ids, role)

    def test_la_reconciliation_n_accorde_jamais_l_administration(self):
        """Defense en profondeur : meme un role deja porteur du groupe admin
        (pose en contournant l'ORM) ne doit pas rendre son titulaire admin."""
        role = self.env["his.role"].create({"name": "Role legacy"})
        # Contournement de la contrainte pour simuler une base ancienne : ecriture
        # SQL directe sur la table de relation.
        self.env.cr.execute(
            "INSERT INTO his_role_group_rel (role_id, group_id) VALUES (%s, %s)",
            [role.id, self.admin_group.id],
        )
        role.invalidate_recordset(["group_ids"])
        job = self.env["hr.job"].create({"name": "Poste legacy", "role_ids": [(6, 0, role.ids)]})
        user = self.env["res.users"].create(
            {"name": "Titulaire", "login": "zz_titulaire", "group_ids": [(6, 0, [self.env.ref("base.group_user").id])]}
        )
        self.env["hr.employee"].create({"name": "Titulaire", "user_id": user.id, "job_id": job.id})
        user.invalidate_recordset(["group_ids"])
        self.assertFalse(
            user.has_group("base.group_system"),
            "La reconciliation des roles du poste a accorde l'administration.",
        )
