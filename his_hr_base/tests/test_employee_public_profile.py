# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Ce qu'un utilisateur sans droits RH peut lire d'un employe.

Le coeur d'Odoo pose une regle en tete de hr/models/hr_employee.py : un champ
present sur hr.employee et absent de hr.employee.public porte
groups="hr.group_hr_user". Sinon le prefetch le charge pour un utilisateur sans
acces au modele, _check_private_fields refuse la lecture ENTIERE, et le moindre
acces a un employe echoue.

Trois champs de nos modules l'enfreignaient (person_id, matricule_institutionnel,
date_start_working). Symptome vecu le 2026-09-21 : avec pos_hr installe, la
caisse restait blanche pour tout caissier non RH (« Could not load model
pos.config »). Le cas se reproduit sans pos_hr - lire le NOM d'un employe
suffit - et c'est ce que ces tests posent.
"""

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class TestEmployeePublicProfile(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee = cls.env["hr.employee"].create({"name": "Profil Public"})
        # Un simple utilisateur interne : aucun droit RH, lecture par le profil
        # public, exactement comme un caissier.
        cls.internal = new_test_user(cls.env, login="his_profil_interne", groups="base.group_user")

    def test_a_plain_user_can_read_an_employee(self):
        """Le symptome lui-meme : lire le nom declenchait le refus du prefetch."""
        employee = self.employee.with_user(self.internal)
        self.assertEqual(employee.name, "Profil Public")
        # Et via read(), le chemin du chargement de la caisse.
        self.assertEqual(employee.read(["name"])[0]["name"], "Profil Public")

    def test_the_matricule_is_public(self):
        """Imprime sur le badge : lisible par tout utilisateur interne (decision du 2026-09-21)."""
        self.assertTrue(self.employee.matricule_institutionnel)
        self.assertEqual(
            self.employee.with_user(self.internal).matricule_institutionnel,
            self.employee.matricule_institutionnel,
        )

    def test_the_person_link_stays_hr_only(self):
        with self.assertRaises(AccessError):
            self.employee.with_user(self.internal).read(["person_id"])

    def test_every_stored_employee_field_is_public_or_guarded(self):
        """La regle du coeur, verifiee pour TOUS les modules installes.

        C'est ce qui attrape le prochain module qui ajoute un champ a
        hr.employee sans y penser : le test le nomme, au lieu d'une caisse
        blanche en production.
        """
        public = self.env["hr.employee.public"]._fields
        # current_version_id : le coeur l'ecarte lui-meme, par son nom, de la
        # lecture par le profil public (hr.employee.fetch). Meme exception ici.
        exempt = {"current_version_id"}
        offenders = sorted(
            name
            for name, field in self.env["hr.employee"]._fields.items()
            if field.store and field.column_type and not field.groups and name not in public and name not in exempt
        )
        self.assertFalse(
            offenders,
            "Champs stockes de hr.employee ni publics ni proteges : %s. Ajoutez-les a "
            'hr.employee.public, ou posez groups="hr.group_hr_user" (cf. la tete de '
            "hr/models/hr_employee.py)." % ", ".join(offenders),
        )
