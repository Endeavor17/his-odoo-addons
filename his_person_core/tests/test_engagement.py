# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""L'engagement est un parcours date, pas une identite : plusieurs par personne."""
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestEngagement(TransactionCase):

    def setUp(self):
        super().setUp()
        self.person = self.env['his.person'].create({
            'name': "Amina Test",
            'type_personne': 'candidat',
            'source_system': 'manual',
        })

    def test_engagement_defaults_to_prospect(self):
        engagement = self.env['his.engagement'].create({'person_id': self.person.id})
        self.assertEqual(engagement.etat, 'prospect')
        self.assertTrue(engagement.date_debut)
        self.assertEqual(self.person.engagement_ids, engagement)

    def test_several_engagements_share_one_identity(self):
        """Repostuler ne cree pas une seconde fiche ni un second matricule."""
        Engagement = self.env['his.engagement']
        Engagement.create({'person_id': self.person.id, 'etat': 'abandonne'})
        Engagement.create({'person_id': self.person.id, 'etat': 'prospect'})
        self.assertEqual(len(self.person.engagement_ids), 2)
        self.assertEqual(
            self.env['his.person'].search_count(
                [('matricule_institutionnel', '=', self.person.matricule_institutionnel)],
            ), 1,
        )

