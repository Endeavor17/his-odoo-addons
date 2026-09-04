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

        tuiles += self._tuiles_revenu()

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

    def _tuiles_revenu(self):
        """Le revenu attendu, DEDUIT et jamais saisi.

        Chez GoHighLevel, 454 opportunites ouvertes sur 505 ne portent aucun
        montant : c'est la consequence directe d'avoir demande a un humain de
        taper un nombre qu'une grille tarifaire connait deja. Ici il se
        calcule, donc il ne peut pas etre vide.

        LA TUILE N'APPARAIT PAS tant qu'aucun tarif n'est saisi. Un chiffre
        d'affaires invente est pire qu'un chiffre absent : il se cite en
        reunion. Tant que la Finance n'a pas fourni le bareme, l'ecran se tait.

        sudo() : un tarif est un chiffre affiche, pas une donnee reservee — le
        meme raisonnement que pour les objectifs. L'ECRITURE reste au groupe
        Finance, c'est la que se joue le controle.
        """
        Tarif = self.env['his.tarif'].sudo()
        if not Tarif.search_count([('frais_inscription', '>', 0)]):
            return []

        equipes = self._equipes_admissions()
        domaine = [
            ('team_id', 'in', equipes.ids),
            ('active', '=', True),
            ('specialite_id', '!=', False),
        ]
        ouverts = self.env['crm.lead'].search(domaine)
        attendu = sum(Tarif._montant_pour(lead.specialite_id) for lead in ouverts)

        return [self._tuile(
            'revenu_attendu', "Revenu attendu", round(attendu, 2), unite="DA",
            action=self._action(
                "Candidatures ouvertes chiffrables", 'crm.lead', domaine,
            ),
        )]

    def _admissions_qualite(self, equipes):
        """Ajoute la lacune que seul ce module peut voir.

        Une specialite sans tarif rend ses candidatures non chiffrables : elles
        disparaissent du revenu attendu sans que rien ne le dise. C'est
        exactement le genre de trou que la file « Qualite des donnees » existe
        pour rendre visible.
        """
        files = super()._admissions_qualite(equipes)
        Tarif = self.env['his.tarif'].sudo()
        sans_tarif = self.env['his.specialite'].search([]).filtered(
            lambda s: not Tarif.search_count([
                ('specialite_id', '=', s.id), ('frais_inscription', '>', 0),
            ])
        )
        if sans_tarif:
            files.append(self._a_traiter(
                "Specialites sans tarif", 'his.specialite',
                [('id', 'in', sans_tarif.ids)],
            ))
        return files

    def _methodes_cockpits(self):
        """Le cockpit des dossiers rejoint la vue Direction.

        Par NOM : c'est l'agregateur qui appelle, et qui entoure l'appel. Un
        role sans droit sur les dossiers ne voit pas ce bloc, au lieu de voir
        la vue d'ensemble entiere tomber.
        """
        return super()._methodes_cockpits() + ['get_dossiers']
