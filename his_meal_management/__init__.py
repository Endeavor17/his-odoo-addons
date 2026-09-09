from . import models
from . import wizard
from .hooks import post_init_hook

# Ce module n'avait plus ni hook ni reference a his_stock_mdm : un repas etant
# n'importe quel produit portant un meal_credit_cost, toute caisse pouvait en
# servir un sans rien configurer. C'etait juste tant qu'aucune caisse ne
# restreignait son catalogue.
#
# Depuis his_stock_mdm 19.0.1.2.0 les trois caisses ont un perimetre : le
# Restaurant ne sert que des repas, le Copy Center ne vend rien de comestible
# mais encaisse les recharges. Un produit sans pos.category disparait alors de
# toutes les caisses. Il faut donc que quelqu'un dise ou se vendent les
# forfaits et les repas, et ce quelqu'un ne peut etre que ce module : lui seul
# sait lesquels de ses produits sont l'un ou l'autre.
#
# D'ou le couplage assume avec his_stock_mdm. Il existait deja en pratique --
# le module posait available_in_pos sur des caisses definies la-bas -- il est
# desormais declare.
