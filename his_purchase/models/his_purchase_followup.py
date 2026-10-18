# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""Relances et escalade : a chaque etape, une personne, une echeance.

Les demandes d'achat s'oublient a HIS (Mohamed, 2026-10-15). Chaque objet suivi
(demande, commande, contrat-cadre) dit, par `_his_step()`, quelle etape attend
qui et pour quand. Ce mixin en tire :

- une activite « Purchase Follow-up » sur le responsable, des que l'etape
  commence, close automatiquement quand elle change ;
- au passage de l'echeance, un rappel au responsable (message + courriel) ;
- puis, a chaque palier de la chaine d'escalade, une activite et un courriel
  a la personne suivante (responsable achats, puis directeur executif).

Delais en jours ouvres algeriens : le week-end est vendredi-samedi.
"""

from datetime import timedelta

from odoo import _, fields, models
from odoo.tools.misc import format_date

ACTIVITY_XMLID = "his_purchase.mail_act_followup"
WEEKEND = (4, 5)  # vendredi, samedi


def add_working_days(day, count):
    """`day` + `count` jours ouvres (dimanche-jeudi)."""
    while count > 0:
        day += timedelta(days=1)
        if day.weekday() not in WEEKEND:
            count -= 1
    return day


class HisPurchaseFollowupMixin(models.AbstractModel):
    _name = "his.purchase.followup.mixin"
    _description = "Purchase follow-up (reminders and escalation)"

    his_step = fields.Char(string="Follow-up Step", copy=False, readonly=True)
    his_step_since = fields.Date(string="Step Since", copy=False, readonly=True)
    his_step_level = fields.Integer(
        string="Reminder Level",
        copy=False,
        readonly=True,
        help="0: on time; 1: owner reminded; 2 and more: escalated.",
    )
    his_reminder_count = fields.Integer(string="Reminders Sent", copy=False, readonly=True)
    his_is_late = fields.Boolean(string="Late", copy=False, readonly=True)

    # ------------------------------------------------------------------
    # A definir par chaque modele suivi
    # ------------------------------------------------------------------

    def _his_step(self):
        """Etape en cours, ou None.

        Renvoie un dict : key (str stable), label (texte de l'activite),
        owner (res.users), due (date), chain (liste de (jours, res.users) :
        delai apres le palier precedent, puis qui reprend la main).
        """
        return None

    # ------------------------------------------------------------------

    def _his_company_people(self, company):
        """Responsable achats et directeur executif de la societe."""
        return company.his_purchase_manager_id, company.his_purchase_director_id

    def _his_by_lang(self, users):
        """[(enregistrement dans la langue du groupe, utilisateurs)] : chacun lit
        ses rappels dans sa langue, meme quand c'est le cron (anglais) qui ecrit."""
        groups = {}
        for user in users:
            groups.setdefault(user.lang or self.env.lang, self.env["res.users"])
            groups[user.lang or self.env.lang] |= user
        return [(self.with_context(lang=lang), group) for lang, group in groups.items()]

    def _his_notify(self, users, message):
        """Message au fil, notifie par courriel. `message` : texte, ou fonction
        (enregistrement dans la langue du destinataire) -> texte."""
        for record, group in self._his_by_lang(users):
            record.message_post(
                body=message(record) if callable(message) else message,
                partner_ids=group.partner_id.ids,
                message_type="comment",
                subtype_xmlid="mail.mt_note",
            )

    def _his_schedule(self, users, label, due, activity=ACTIVITY_XMLID):
        for record, group in self._his_by_lang(users):
            summary = label(record) if callable(label) else label
            for user in group:
                record.activity_schedule(activity, date_deadline=due, summary=summary, user_id=user.id)

    def _his_label(self):
        step = self._his_step()
        return step["label"] if step else ""

    def _his_text_reminder(self):
        step = self._his_step()
        return _("Reminder: “%(step)s” was due on %(due)s.", step=step["label"], due=format_date(self.env, step["due"]))

    def _his_text_escalation(self):
        step = self._his_step()
        return _(
            "Escalation: “%(step)s” was due on %(due)s and is still waiting on %(owner)s.",
            step=step["label"],
            due=format_date(self.env, step["due"]),
            owner=", ".join(step["owner"].mapped("name")) or _("nobody"),
        )

    def _his_text_escalation_label(self):
        return _("Escalated: %(step)s", step=self._his_label())

    def _his_sync_step(self):
        """Aligne l'etape stockee sur l'etape reelle ; nouvelle etape = nouvelle activite."""
        today = fields.Date.context_today(self)
        for record in self:
            step = record._his_step()
            key = step["key"] if step else False
            if key == record.his_step:
                continue
            record.activity_feedback([ACTIVITY_XMLID], feedback=_("Step completed."))
            record.write(
                {"his_step": key, "his_step_since": today if key else False, "his_step_level": 0, "his_is_late": False}
            )
            if step and step["owner"]:
                record._his_schedule(step["owner"], lambda r: r._his_label(), step["due"])

    def _his_run_followup(self):
        """Rappel puis escalade des etapes en retard. Appele chaque jour."""
        today = fields.Date.context_today(self)
        self._his_sync_step()
        for record in self:
            step = record._his_step()
            if not step or today <= step["due"]:
                continue
            if not record.his_is_late:
                record.his_is_late = True
            if record.his_step_level == 0:
                if step["owner"]:
                    record._his_notify(step["owner"], lambda r: r._his_text_reminder())
                record.write({"his_step_level": 1, "his_reminder_count": record.his_reminder_count + 1})
                continue
            # Palier n de la chaine : atteint a due + somme des delais 1..n.
            palier = record.his_step_level - 1
            if palier >= len(step["chain"]):
                continue
            echeance = add_working_days(step["due"], sum(d for d, _u in step["chain"][: palier + 1]))
            if today < echeance:
                continue
            users = step["chain"][palier][1]
            if users:
                record._his_schedule(users, lambda r: r._his_text_escalation_label(), today)
                record._his_notify(users, lambda r: r._his_text_escalation())
            record.write(
                {"his_step_level": record.his_step_level + 1, "his_reminder_count": record.his_reminder_count + 1}
            )
