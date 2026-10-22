"""Le petit monde commun aux tests : un batiment, deux zones, une responsable,
une salariee avec compte (Fatima) et une sans compte (Karima)."""

from odoo.tests import TransactionCase


class HygieneCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.group_manager = cls.env.ref("his_hygiene.group_hygiene_manager")
        cls.group_worker = cls.env.ref("his_hygiene.group_hygiene_worker")
        cls.bloc = cls.env["maintenance.building"].create({"name": "Bloc H", "code": "H"})
        Location = cls.env["stock.location"]
        cls.loc_rdc = Location.create({"name": "RDC", "location_id": cls.bloc.his_location_id.id})
        cls.loc_amphi = Location.create({"name": "Amphi 1", "location_id": cls.bloc.his_location_id.id})

        Users = cls.env["res.users"].with_context(no_reset_password=True)
        cls.manager_user = Users.create(
            {"name": "Samira", "login": "samira.hyg@his.test", "group_ids": [(6, 0, [cls.group_manager.id])]}
        )
        cls.fatima_user = Users.create(
            {"name": "Fatima Zahra", "login": "fatima.hyg@his.test", "group_ids": [(6, 0, [cls.group_worker.id])]}
        )
        Employee = cls.env["hr.employee"]
        cls.manager_emp = Employee.create({"name": "Samira", "user_id": cls.manager_user.id})
        cls.fatima = Employee.create({"name": "Fatima Zahra", "user_id": cls.fatima_user.id})
        cls.karima = Employee.create({"name": "Karima Saidi"})

        Member = cls.env["his.hygiene.member"]
        cls.m_fatima = Member.create({"employee_id": cls.fatima.id})
        cls.m_karima = Member.create({"employee_id": cls.karima.id})
        Area = cls.env["his.hygiene.area"]
        cls.area_rdc = Area.create({"location_id": cls.loc_rdc.id})
        cls.area_amphi = Area.create({"location_id": cls.loc_amphi.id})
