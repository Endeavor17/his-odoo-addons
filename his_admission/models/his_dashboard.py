# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Le cockpit des dossiers d'admission.

Il vit ici et non dans his_crm_pipeline parce que his.engagement vit ici :
his_crm_pipeline est en amont et ne connait pas ce modele. Le module qui
apporte un metier apporte aussi ses indicateurs — c'est ce qui permet
d'installer le pipeline sans les dossiers, et de ne pas casser la vue Direction
en le faisant.
"""
from odoo import api, fields, models


class HisDashboard(models.AbstractModel):
    _inherit = 'his.dashboard'

    @api.model
    def get_dossiers(self, date_from, date_to):
        date_from = fields.Date.to_date(date_from)
        date_to = fields.Date.to_date(date_to)
        prec_from, prec_to = self._periode_precedente(date_from, date_to)

        Engagement = self.env['his.engagement']
        periode = self._entre(date_from, date_to)
        encaisses = [('frais_inscription_payes', '=', True)]

        ouverts = Engagement.search_count([])
        complets = Engagement.search_count([('documents_complets', '=', True)])

        tuiles = [
            self._tuile(
                'dossiers_ouverts', "Dossiers ouverts", ouverts,
                action=self._action("Dossiers ouverts", 'his.engagement', []),
            ),
            self._tuile(
                'dossiers_complets', "Dossiers complets",
                round(complets / ouverts * 100, 1) if ouverts else 0, unite='%',
                action=self._action(
                    "Dossiers complets", 'his.engagement',
                    [('documents_complets', '=', True)],
                ),
            ),
            self._tuile(
                'encaissements', "Encaissements de la periode",
                Engagement.search_count(encaisses + periode),
                action=self._action(
                    "Encaissements", 'his.engagement', encaisses + periode,
                ),
                precedent=Engagement.search_count(
                    encaisses + self._entre(prec_from, prec_to),
                ),
            ),
            self._tuile(
                'a_verifier', "Eligibilite a verifier",
                Engagement.search_count([('eligibilite', '=', 'a_verifier')]),
                action=self._action(
                    "Eligibilite a verifier", 'his.engagement',
                    [('eligibilite', '=', 'a_verifier')],
                ),
            ),
        ]

        return {
            'titre': "Cockpit Dossiers",
            'tiles': tuiles,
            'funnel': [],
            'attention': [
                # documents_manquants est deja calcule et stocke. C'est
                # exactement ce que le classeur Excel ne savait pas dire :
                # « pas encore recu » plutot que « pas concerne ».
                self._a_traiter(
                    "Dossiers incomplets", 'his.engagement',
                    [('documents_complets', '=', False)],
                ),
                self._a_traiter(
                    "Lettres d'acceptation non emises", 'his.engagement',
                    [('inscription_initiale', '=', True),
                     ('lettre_acceptation', '=', False)],
                ),
                self._a_traiter(
                    "Cartes recues de l'IT, non remises", 'his.engagement',
                    [('carte_recue_it', '=', True),
                     ('carte_date_remise', '=', False)],
                ),
            ],
            'explore': [
                {'label': "Par cycle et specialite",
                 'action': self._action(
                     "Par cycle et specialite", 'his.engagement', [],
                     views=[[False, 'pivot'], [False, 'list']],
                 )},
            ],
        }

    def _cockpits_direction(self, date_from, date_to):
        cockpits = super()._cockpits_direction(date_from, date_to)
        return cockpits + [self.get_dossiers(date_from, date_to)]
