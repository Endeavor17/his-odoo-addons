from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPartnerPrivacy(TransactionCase):
    """Audit S-6: students' and candidates' contacts are not the whole staff's.

    Every internal user reads res.partner in core, and a his.person delegates to
    a real partner - so a cook read a candidate's email and phone (probe P4).
    Hiding the Contacts menu hid nothing.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Person = cls.env["his.person"].sudo()
        cls.student = Person.create({"name": "Etudiant Prive", "type_personne": "etudiant", "source_system": "manual"})
        cls.candidate = Person.create(
            {"name": "Candidat Prive", "type_personne": "candidat", "source_system": "manual"}
        )
        cls.employee = Person.create({"name": "Employe Public", "type_personne": "employe", "source_system": "manual"})
        cls.supplier = cls.env["res.partner"].create({"name": "Fournisseur Public"})
        cls.staff = cls.env["res.users"].create(
            {
                "name": "Employe Sans Role",
                "login": "sans.role.s6",
                "group_ids": [Command.set(cls.env.ref("base.group_user").ids)],
            }
        )

    def _readable(self, user, partner):
        try:
            partner.with_user(user).read(["email"])
        except AccessError:
            return False
        return True

    def test_a_plain_employee_reads_no_student_or_candidate(self):
        for person in (self.student, self.candidate):
            self.assertFalse(self._readable(self.staff, person.partner_id), person.name)
        found = self.env["res.partner"].with_user(self.staff).search([("name", "like", "Prive")])
        self.assertFalse(found, "search must not list them either")

    def test_the_rest_of_the_address_book_stays_open(self):
        for partner in (self.supplier, self.employee.partner_id, self.staff.partner_id, self.env.company.partner_id):
            self.assertTrue(self._readable(self.staff, partner), partner.name)

    def test_a_person_manager_reads_everyone(self):
        manager = self.env["res.users"].create(
            {
                "name": "Gestionnaire S6",
                "login": "gestionnaire.s6",
                "group_ids": [Command.set(self.env.ref("his_person_core.group_his_person_manager").ids)],
            }
        )
        for person in (self.student, self.candidate):
            self.assertTrue(self._readable(manager, person.partner_id), person.name)
