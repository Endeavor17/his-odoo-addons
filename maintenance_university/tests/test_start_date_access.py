"""Who may read an employee's start date, now that it carries a `groups=`.

`date_start_working` decides the year of the institutional ID, so it is HR data.
It used to carry no `groups=` at all, which broke Odoo's rule for hr.employee
fields that are not on the public profile: every user without HR rights had
their whole read of an employee refused (a till with pos_hr stayed blank). It
is now kept to HR and to maintenance managers, who set it when creating workers.

These run as real users rather than as the test's admin, who is an HR user and
would see everything whatever the rule said.
"""

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class TestStartDateAccess(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee = cls.env["hr.employee"].create({"name": "Date Start Probe"})
        cls.manager = new_test_user(
            cls.env,
            login="maint_manager_no_hr",
            groups="maintenance_university.group_maintenance_manager",
        )
        # A worker can read hr.employee directly (this module's ACL), so it is
        # the field's own groups= that has to keep the date from them.
        cls.worker = new_test_user(
            cls.env,
            login="maint_worker_no_hr",
            groups="maintenance_university.group_maintenance_worker",
        )
        hr_user = cls.env.ref("hr.group_hr_user")
        assert hr_user not in cls.manager.all_group_ids, "the manager fixture must not be an HR user"

    def test_a_maintenance_manager_reads_the_start_date(self):
        self.assertEqual(
            self.employee.with_user(self.manager).date_start_working,
            self.employee.date_start_working,
        )

    def test_a_worker_does_not(self):
        with self.assertRaises(AccessError):
            self.employee.with_user(self.worker).read(["date_start_working"])

    def test_a_worker_still_reads_the_rest_of_an_employee(self):
        """The date is refused, not the employee: the prefetch no longer drags it in."""
        self.assertEqual(self.employee.with_user(self.worker).name, "Date Start Probe")

    def test_a_manager_without_hr_rights_still_creates_a_worker(self):
        """The wizard sets the start date and mints the matricule through sudo()."""
        wizard = (
            self.env["maintenance.university.worker.create"]
            .with_user(self.manager)
            .create(
                {
                    "line_ids": [
                        (
                            0,
                            0,
                            {
                                "name": "Recrue Sans RH",
                                "login": "recrue.sans.rh@his.test",
                                "date_start_working": "2025-09-01",
                            },
                        )
                    ],
                }
            )
        )
        wizard.action_create_workers()

        employee = wizard.line_ids.employee_id.sudo()
        self.assertTrue(employee, "no employee was created")
        self.assertEqual(str(employee.date_start_working), "2025-09-01")
        # The matricule's year comes from the start date, not from today.
        self.assertRegex(employee.matricule_institutionnel, r"^HIS-2025-\d{6}-[0-9X]$")
