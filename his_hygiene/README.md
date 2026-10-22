# Hygiène — planning de l'équipe de nettoyage

Spec : `docs/superpowers/specs/2026-10-22-hygiene-team-design.md`.

La responsable de l'équipe d'hygiène planifie chaque mois qui nettoie quelle zone, jour par jour, sans règle imposée : son jugement fait la rotation. Les agentes qui savent se servir de leur téléphone pointent et cochent elles-mêmes ; pour les autres, la responsable fait tout depuis le même écran.

## Écrans

| Menu | Qui | Quoi |
|---|---|---|
| **Ma journée** | toutes | Gros bouton de pointage (début, pause, reprise, fin), zones du jour avec **Fait**, **Signaler un problème** (panne ou salissure, photo), onglet **Mon mois**. La responsable choisit l'agente en haut de l'écran. |
| **Planning** | responsable | Matrice zones × jours du mois. Choisir une agente dans la palette (le « pinceau »), cliquer les cases pour l'ajouter ou la retirer ; Maj+clic plus loin sur la ligne répète la dernière case (jours de repos sautés). Ligne **Absences** en bas : un clic marque l'agente absente, ses zones apparaissent **non couvertes** (bord rouge) tant que personne n'est ajouté. **Copier le mois précédent** : jour N → jour N. |
| **Signalements** | responsable | Les salissures à attribuer (un clic en fait du travail en plus, avec l'équipe déjà sur la zone ce jour-là) et les pannes envoyées à la maintenance. |
| **Récapitulatif mensuel** | responsable | Par agente : jours travaillés, absences, heures pointées, jours non pointés, zones faites, signalements. Par zone : jours planifiés, nettoyés, non couverts. Grille d'équité : jours passés par chaque agente dans chaque zone. |
| **Journées de travail** | responsable | Corriger une heure oubliée ; l'heure d'origine et l'auteur de la correction restent visibles. |

## Règles à connaître

- **Un jour planifié et non marqué absent compte comme travaillé**, pointé ou non. Les heures ne viennent que des jours pointés ; le récapitulatif montre à part les jours non pointés.
- **Une absence est une journée entière.** Une agente qui part à 11 h n'est pas absente : la responsable ajoute quelqu'un sur les zones restantes.
- **Pointage** : c'est la journée de `maintenance_university`, partagée. La responsable hygiène peut pointer pour son équipe ; le responsable maintenance, lui, ne pointe jamais pour quelqu'un, et chaque responsable ne voit que les journées de son équipe.
- **Panne** → un constat de maintenance soumis, bâtiment et salle remplis, catégorie « Reported by hygiene » (le chef maintenance reclasse puis convertit). **Salissure** → revient à la responsable hygiène.
- Les jours de repos sont le vendredi et le samedi : paramètre système `his_hygiene.off_weekdays` (numéros Python, lundi = 0), valeur `4,5`.
- Interface en anglais, traduite en **français** et en **arabe**.

## Mise en place

1. Installer le module (il dépend de `his_patrimoine` et de `maintenance_university`).
2. Mettre les rôles sur les postes (RH ▸ Postes ▸ rôles Odoo) : **Hygiene / Manager** sur le poste de la responsable, **Hygiene / Worker** sur celui des agentes. Une agente sans compte n'a besoin d'aucun rôle.
3. Créer les lieux dans **Inventaire ▸ Patrimoine**, sous leur bâtiment : salles, couloirs, escaliers, sanitaires, étages. Les espaces extérieurs (cour, parking) vont sous un bâtiment **Campus**.
4. **Hygiène ▸ Configuration ▸ Zones** : choisir les lieux que l'équipe couvre, dans l'ordre voulu.
5. **Hygiène ▸ Configuration ▸ Membres de l'équipe** : ajouter les agentes depuis l'annuaire des employés, avec leur couleur.

## Côté maintenance

Ce travail a aussi ajouté une **salle** (facultative) aux demandes et constats de maintenance, prise sous l'emplacement Patrimoine du bâtiment ; elle se vide si le bâtiment change et suit la conversion d'un constat en demande (`his_patrimoine`).
