# Tableau de bord « Cash Control » (Metabase)

Le module `his_pos_finance` déclare le tableau `cash` (menu Comptabilité > Cash Indicators,
réservé à la Finance). Le tableau lui-même se construit dans Metabase avec les quatre
questions ci-dessous, puis son numéro se saisit dans Odoo (Paramètres > Tableaux de bord),
comme les autres tableaux de `his_metabase`.

## 1. Écarts par caissier et par mois (§6.6)

```sql
SELECT date_trunc('month', d.date) AS mois,
       COALESCE(e.name, p.name)      AS caissier,
       j.code                        AS caisse,
       count(*)                      AS nombre,
       sum(d.amount)                 AS cumul,
       sum(abs(d.amount))            AS cumul_absolu
FROM his_cash_discrepancy d
JOIN account_journal j ON j.id = d.journal_id
LEFT JOIN hr_employee e ON e.id = d.holder_employee_id
LEFT JOIN res_users u ON u.id = d.holder_id
LEFT JOIN res_partner p ON p.id = u.partner_id
GROUP BY 1, 2, 3
ORDER BY 1 DESC, 5;
```

## 2. Fiches ouvertes par ancienneté et statut

```sql
SELECT d.name, j.code AS caisse, d.state, d.tier, d.amount,
       current_date - d.date::date AS jours
FROM his_cash_discrepancy d
JOIN account_journal j ON j.id = d.journal_id
WHERE d.state <> 'closed'
ORDER BY jours DESC;
```

## 3. Versements non reçus

```sql
SELECT t.name, f.code AS de, tj.code AS vers, t.amount_sent, t.sent_at,
       now() - t.sent_at AS attente
FROM his_cash_transfer t
JOIN account_journal f ON f.id = t.from_journal_id
JOIN account_journal tj ON tj.id = t.to_journal_id
WHERE t.state = 'sent'
ORDER BY t.sent_at;
```

## 4. Autorisations du responsable par caissier

```sql
SELECT date_trunc('month', o.date_order) AS mois,
       ce.name                           AS caissier,
       ae.name                           AS autorise_par,
       l.his_authorization_kind          AS geste,
       count(*)                          AS nombre
FROM pos_order_line l
JOIN pos_order o ON o.id = l.order_id
LEFT JOIN hr_employee ce ON ce.id = o.employee_id
LEFT JOIN hr_employee ae ON ae.id = l.his_authorized_by_id
WHERE l.his_authorization_kind IS NOT NULL
GROUP BY 1, 2, 3, 4
ORDER BY 1 DESC, 5 DESC;
```
