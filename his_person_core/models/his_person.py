# Part of Odoo. See LICENSE file for full copyright and licensing details.
import re
import unicodedata

from odoo import api, fields, models
from odoo.exceptions import ValidationError

MATRICULE_SEQUENCE_CODE = 'his.person.matricule.institutionnel'

# Format documente : HIS-AAAA-NNNNNN-C. La sequence ne produit que
# HIS-AAAA-NNNNNN ; la cle de controle est calculee puis concatenee.
MATRICULE_RE = re.compile(r'^HIS-\d{4}-\d{6}-[0-9X]$')

# Poids mod 11, de droite a gauche, appliques aux 6 chiffres sequentiels.
# Choix confirme avec Endeavor (cf. README, section "Cle de controle").
# Isole ici volontairement : si l'algorithme change, seuls cette constante et
# _compute_matricule_checksum bougent, rien d'autre.
CHECKSUM_WEIGHTS = (2, 3, 4, 5, 6, 7)


def _compute_matricule_checksum(sequential_number):
    """Cle de controle d'un matricule, a partir de sa portion sequentielle.

    `sequential_number` : les 6 chiffres (str ou int). Retourne un caractere.

    Mod 11 pondere 2..7 de droite a gauche ; reste 10 -> 'X' (comme ISBN-10),
    ce qui garde la cle sur un seul caractere.

    Fonction pure : aucun acces ORM, testable isolement du modele et de la
    sequence.
    """
    digits = str(sequential_number).strip()
    if not digits.isdigit():
        raise ValueError("Portion sequentielle non numerique : %r" % (sequential_number,))
    digits = digits.zfill(6)
    if len(digits) != 6:
        raise ValueError("Portion sequentielle attendue sur 6 chiffres : %r" % (sequential_number,))
    total = sum(
        int(digit) * weight
        for digit, weight in zip(reversed(digits), CHECKSUM_WEIGHTS)
    )
    remainder = total % 11
    return 'X' if remainder == 10 else str(remainder)


def normalize_text(value):
    """Forme comparable d'un nom : sans accent, sans ponctuation, minuscule.

    Utilisee par le rapprochement probabiliste (cf. his_person_sync_sheets).
    Placee ici et non dans l'adaptateur : un second adaptateur (Uniflow) doit
    normaliser exactement pareil, sinon les scores ne sont pas comparables.
    """
    if not value:
        return ''
    decomposed = unicodedata.normalize('NFKD', str(value))
    stripped = ''.join(char for char in decomposed if not unicodedata.combining(char))
    return ' '.join(re.sub(r'[^0-9a-z\s]', ' ', stripped.lower()).split())


class HisPerson(models.Model):
    _name = 'his.person'
    _description = "Personne (Groupe HIS-HTC-IRA)"
    _inherit = ['mail.thread']
    _order = 'matricule_institutionnel'
    _rec_name = 'nom_latin'

    # readonly=True au niveau ORM : le matricule est emis a la creation et
    # jamais reemis. Le rendre editable, meme par un administrateur, casserait
    # l'identifiant sur lequel s'appuieront la carte RFID et le portefeuille.
    matricule_institutionnel = fields.Char(
        string="Matricule institutionnel",
        copy=False,
        readonly=True,
        index=True,
        tracking=True,
    )
    nom_latin = fields.Char(string="Nom (latin)", required=True, tracking=True)
    nom_arabe = fields.Char(string="Nom (arabe)", tracking=True)
    email_institutionnel = fields.Char(string="Email institutionnel", tracking=True)
    email_personnel = fields.Char(string="Email personnel")
    telephone = fields.Char(string="Telephone")

    # Selection et non un jeu de booleens : la liste des types s'allongera
    # (alumni, prestataire...) et doit pouvoir grandir sans migration de
    # schema. Ce champ reflete le statut courant, il ne definit pas
    # l'identite : un candidat devenu etudiant puis employe garde la meme
    # fiche et le meme matricule.
    type_personne = fields.Selection(
        selection=[
            ('employe', "Employe"),
            ('enseignant', "Enseignant"),
            ('etudiant', "Etudiant"),
            ('candidat', "Candidat"),
        ],
        string="Type de personne",
        required=True,
        tracking=True,
    )
    active = fields.Boolean(string="Actif", default=True)

    source_system = fields.Selection(
        selection=[
            ('odoo_hr', "Odoo RH"),
            ('google_sheets', "Google Sheets"),
            ('uniflow', "Uniflow"),
            ('manual', "Saisie manuelle"),
        ],
        string="Systeme source",
        required=True,
        tracking=True,
    )
    external_ref = fields.Char(
        string="Reference source",
        help="Identifiant de la fiche dans son systeme source (ligne de la feuille, "
             "cle Uniflow...). Sert a remonter a l'origine de la donnee.",
    )

    match_method = fields.Selection(
        selection=[
            ('deterministic', "Deterministe"),
            ('probabilistic', "Probabiliste (confirme)"),
            ('new', "Creation"),
        ],
        string="Methode de rapprochement",
        readonly=True,
        tracking=True,
    )
    matched_by = fields.Many2one(
        'res.users', string="Rapprochement confirme par", readonly=True, tracking=True,
    )
    matched_on = fields.Datetime(string="Date de confirmation", readonly=True, tracking=True)

    _matricule_institutionnel_unique = models.Constraint(
        'unique(matricule_institutionnel)',
        "Ce matricule institutionnel est deja attribue a une autre personne.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        sequence = self.env['ir.sequence'].sudo()
        for vals in vals_list:
            # Cle de service, jamais un champ : elle ne sert qu'a choisir la
            # plage annuelle de la sequence (embauche antidatee ou future).
            sequence_date = vals.pop('matricule_sequence_date', None)
            if vals.get('matricule_institutionnel'):
                # Valeur pre-existante (reprise RH, import Sheets). On ne la
                # reformate pas et on ne recalcule pas sa cle : une valeur
                # anterieure a ce module peut ne pas en avoir. Elle est
                # stockee telle quelle ; seule la contrainte d'unicite
                # s'applique. C'est a l'import de signaler ce qui est malforme.
                continue
            sequence_date = fields.Date.to_date(sequence_date) or fields.Date.context_today(self)
            base = sequence.next_by_code(MATRICULE_SEQUENCE_CODE, sequence_date=sequence_date)
            vals['matricule_institutionnel'] = '%s-%s' % (
                base, _compute_matricule_checksum(base[-6:]),
            )
        return super().create(vals_list)

    def write(self, vals):
        # readonly=True bloque l'UI mais pas un write() serveur ni un import.
        # La regle « un matricule n'est jamais reemis » doit tenir cote
        # serveur, sinon ce n'est pas une regle.
        if 'matricule_institutionnel' in vals:
            for person in self:
                if person.matricule_institutionnel \
                        and vals['matricule_institutionnel'] != person.matricule_institutionnel:
                    raise ValidationError(
                        "Le matricule institutionnel de %s ne peut pas etre modifie."
                        % person.display_name
                    )
        return super().write(vals)

    # --- Rapprochement (matching) -------------------------------------------
    #
    # Volontairement porte par his.person et non par l'adaptateur Google
    # Sheets : un second adaptateur (Uniflow) doit appeler exactement le meme
    # algorithme sans dependre du premier. Un algorithme duplique derive, et
    # deux fiches pour la meme personne, c'est deux portefeuilles.

    # Poids du score probabiliste. Somme = 1.0.
    MATCH_WEIGHTS = {'nom': 0.40, 'email': 0.35, 'telephone': 0.25}
    # Au-dessus : candidat propose a un humain. Jamais de lien automatique.
    MATCH_THRESHOLD = 0.75

    @api.model
    def _score_candidate(self, candidate_vals, person):
        """Score de similarite [0.0, 1.0] entre une ligne source et une fiche."""
        scores = {}

        left = normalize_text(candidate_vals.get('nom_latin'))
        right = normalize_text(person.nom_latin)
        if left and right and left == right:
            scores['nom'] = 1.0
        elif left and right:
            # Recouvrement de tokens : « Ali Ben Salah » vs « Ben Salah Ali »
            # est la meme personne dans une source qui inverse nom et prenom.
            left_tokens, right_tokens = set(left.split()), set(right.split())
            union = left_tokens | right_tokens
            scores['nom'] = len(left_tokens & right_tokens) / len(union) if union else 0.0
        else:
            scores['nom'] = 0.0
        # Le nom arabe, quand les deux cotes l'ont, ne peut que confirmer.
        arabe_left = (candidate_vals.get('nom_arabe') or '').strip()
        if arabe_left and person.nom_arabe and arabe_left == person.nom_arabe.strip():
            scores['nom'] = 1.0

        candidate_emails = {
            (candidate_vals.get(field) or '').strip().lower()
            for field in ('email_institutionnel', 'email_personnel')
        } - {''}
        person_emails = {
            (value or '').strip().lower()
            for value in (person.email_institutionnel, person.email_personnel)
        } - {''}
        scores['email'] = 1.0 if candidate_emails & person_emails else 0.0

        # Comparaison sur les 8 derniers chiffres : indicatif pays et
        # espaces varient d'une source a l'autre pour le meme numero.
        candidate_phone = re.sub(r'\D', '', candidate_vals.get('telephone') or '')[-8:]
        person_phone = re.sub(r'\D', '', person.telephone or '')[-8:]
        scores['telephone'] = 1.0 if candidate_phone and candidate_phone == person_phone else 0.0

        return sum(scores[key] * weight for key, weight in self.MATCH_WEIGHTS.items())

    @api.model
    def _find_or_flag_match(self, candidate_vals, types=('etudiant', 'candidat')):
        """Rapproche une ligne source d'une fiche existante, sans jamais fusionner.

        Retourne un dict :
          - `person`  : la fiche trouvee, ou None
          - `method`  : 'deterministic' | 'probabilistic' | 'new'
          - `score`   : 0.0 a 1.0
          - `conflict`: message bloquant, ou False

        'probabilistic' ne signifie PAS « rapproche » : cela signifie « a faire
        confirmer par un humain ». L'appelant ne doit rien lier tant que la
        confirmation n'est pas explicite.
        """
        matricule = (candidate_vals.get('matricule_institutionnel') or '').strip()
        if matricule:
            existing = self.with_context(active_test=False).search(
                [('matricule_institutionnel', '=', matricule)], limit=1,
            )
            # Chercher dans his.person suffit a couvrir aussi les employes :
            # his_hr_base miroite tout matricule d'employe dans une fiche
            # his.person. Il n'y a pas de matricule vivant hors de cette table.
            if not existing:
                return {'person': None, 'method': 'deterministic', 'score': 1.0, 'conflict': False}
            if types and existing.type_personne not in types:
                return {
                    'person': existing, 'method': 'deterministic', 'score': 1.0,
                    'conflict': (
                        "Le matricule %s existe deja et appartient a une personne de type "
                        "« %s », incompatible avec cette source. Ligne rejetee : a arbitrer "
                        "manuellement, aucune fusion automatique." % (
                            matricule, existing.type_personne,
                        )
                    ),
                }
            return {'person': existing, 'method': 'deterministic', 'score': 1.0, 'conflict': False}

        # Second cle deterministe : la reference source. Rejouer un import a
        # l'identique doit retomber sur la meme fiche, pas en proposer un
        # rapprochement. Generique a tout adaptateur, d'ou sa place ici.
        external_ref = (candidate_vals.get('external_ref') or '').strip()
        source_system = candidate_vals.get('source_system')
        if external_ref and source_system:
            existing = self.with_context(active_test=False).search([
                ('external_ref', '=', external_ref),
                ('source_system', '=', source_system),
            ], limit=1)
            if existing:
                return {
                    'person': existing, 'method': 'deterministic', 'score': 1.0,
                    'conflict': False,
                }

        domain = [('type_personne', 'in', list(types))] if types else []
        best, best_score = None, 0.0
        for person in self.with_context(active_test=False).search(domain):
            score = self._score_candidate(candidate_vals, person)
            if score > best_score:
                best, best_score = person, score
        if best is not None and best_score >= self.MATCH_THRESHOLD:
            return {
                'person': best, 'method': 'probabilistic', 'score': best_score, 'conflict': False,
            }
        return {'person': None, 'method': 'new', 'score': best_score, 'conflict': False}

    def action_confirm_probabilistic_match(self):
        """Trace qui a confirme un rapprochement probabiliste, et quand."""
        for person in self:
            person.sudo().write({
                'match_method': 'probabilistic',
                'matched_by': self.env.user.id,
                'matched_on': fields.Datetime.now(),
            })
            person.message_post(
                body="Rapprochement probabiliste confirme par %s." % self.env.user.display_name,
            )
