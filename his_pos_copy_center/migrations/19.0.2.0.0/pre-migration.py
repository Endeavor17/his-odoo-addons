"""Le format (A4/A3) cede la place au papier.

Aucun produit reel ne porte copy_format sur le staging ni en prod (0 produit
copie, cf. recette P-16) ; seules d'eventuelles fiches de demo sont concernees.
Un A4 devient du papier normal ; un A3 n'a pas d'equivalent dans la grille et
garde un papier vide, ce qui le rend invisible au dialogue plutot que faux.
L'ORM supprime ensuite la colonne copy_format, qui n'est plus declaree.
"""


def migrate(cr, version):
    cr.execute("ALTER TABLE product_template ADD COLUMN IF NOT EXISTS copy_paper varchar")
    cr.execute(
        """
        SELECT 1 FROM information_schema.columns
         WHERE table_name = 'product_template' AND column_name = 'copy_format'
        """
    )
    if cr.fetchone():
        cr.execute("UPDATE product_template SET copy_paper = 'normal' WHERE copy_format = 'a4'")
