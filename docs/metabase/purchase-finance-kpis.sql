-- Les 6 indicateurs mensuels de la procedure Achats (PROC-ACH, etape 10),
-- a poser sur le tableau de bord Metabase « Purchasing ».
-- Spec : docs/superpowers/specs/2026-11-22-purchase-finance-controls-design.md §6.11.
-- Une requete par carte ; chacune rend une ligne par mois.

-- 1. Demandes autorisees avant engagement : commandes confirmees dont toutes
--    les demandes etaient approuvees avant l'approbation de la commande
--    (une commande sur contrat-cadre compte comme autorisee).
WITH po_req AS (
    SELECT pol.order_id AS po_id, r.approved_on
    FROM purchase_order_line pol
    JOIN his_purchase_request_line rl ON rl.id = pol.his_request_line_id
    JOIN his_purchase_request r ON r.id = rl.request_id
    UNION
    SELECT po.id, r.approved_on
    FROM purchase_order po
    JOIN his_purchase_request r ON r.id = po.his_request_id
)
SELECT date_trunc('month', po.date_approve)::date AS month,
       count(*) AS orders_confirmed,
       round(100.0 * count(*) FILTER (
           WHERE po.requisition_id IS NOT NULL
              OR (EXISTS (SELECT 1 FROM po_req WHERE po_id = po.id)
                  AND NOT EXISTS (SELECT 1 FROM po_req
                                  WHERE po_id = po.id
                                    AND (approved_on IS NULL OR approved_on > po.date_approve)))
       ) / count(*), 1) AS pct_authorised
FROM purchase_order po
WHERE po.state IN ('purchase', 'done') AND po.date_approve IS NOT NULL
GROUP BY 1 ORDER BY 1;

-- 2. Dossiers fournisseurs conformes avant commande : 100 % par construction
--    (la confirmation est refusee sinon) ; affiche pour memoire.
SELECT date_trunc('month', po.date_approve)::date AS month,
       count(*) AS orders_confirmed,
       round(100.0 * count(*) FILTER (WHERE cp.his_supplier_status = 'validated') / count(*), 1) AS pct_supplier_validated
FROM purchase_order po
JOIN res_partner p ON p.id = po.partner_id
JOIN res_partner cp ON cp.id = p.commercial_partner_id
WHERE po.state IN ('purchase', 'done') AND po.date_approve IS NOT NULL
GROUP BY 1 ORDER BY 1;

-- 3. Factures conformes au premier controle.
SELECT date_trunc('month', m.date)::date AS month,
       count(*) AS bills_checked,
       round(100.0 * count(*) FILTER (WHERE m.his_first_check_clean) / count(*), 1) AS pct_clean_first_time
FROM account_move m
WHERE m.move_type = 'in_invoice' AND m.his_first_check_done
GROUP BY 1 ORDER BY 1;

-- 4. Delai moyen de traitement d'une demande : jours entre sa creation et sa
--    premiere commande confirmee.
WITH first_po AS (
    SELECT r.id, r.create_date, min(po.date_approve) AS first_approve
    FROM his_purchase_request r
    JOIN his_purchase_request_line rl ON rl.request_id = r.id
    JOIN purchase_order_line pol ON pol.his_request_line_id = rl.id
    JOIN purchase_order po ON po.id = pol.order_id AND po.state IN ('purchase', 'done')
    GROUP BY r.id, r.create_date
)
SELECT date_trunc('month', first_approve)::date AS month,
       count(*) AS requests,
       round(avg(extract(epoch FROM first_approve - create_date) / 86400)::numeric, 1) AS avg_days
FROM first_po
GROUP BY 1 ORDER BY 1;

-- 5. Receptions conformes : receptions faites sans reliquat ni retour.
SELECT date_trunc('month', sp.date_done)::date AS month,
       count(*) AS receipts,
       round(100.0 * count(*) FILTER (
           WHERE NOT EXISTS (SELECT 1 FROM stock_picking b WHERE b.backorder_id = sp.id)
             AND NOT EXISTS (SELECT 1 FROM stock_picking r WHERE r.return_id = sp.id)
       ) / count(*), 1) AS pct_compliant
FROM stock_picking sp
JOIN stock_picking_type t ON t.id = sp.picking_type_id
WHERE t.code = 'incoming' AND sp.state = 'done' AND sp.return_id IS NULL
GROUP BY 1 ORDER BY 1;

-- 6. Paiements a l'echeance : factures soldees dont le dernier lettrage est
--    au plus tard a l'echeance.
WITH paid AS (
    SELECT m.id, m.invoice_date_due, max(apr.max_date) AS paid_on
    FROM account_move m
    JOIN account_move_line l ON l.move_id = m.id
    JOIN account_account a ON a.id = l.account_id AND a.account_type = 'liability_payable'
    JOIN account_partial_reconcile apr ON apr.credit_move_id = l.id OR apr.debit_move_id = l.id
    WHERE m.move_type = 'in_invoice' AND m.payment_state IN ('paid', 'in_payment')
    GROUP BY m.id, m.invoice_date_due
)
SELECT date_trunc('month', paid_on)::date AS month,
       count(*) AS bills_paid,
       round(100.0 * count(*) FILTER (WHERE paid_on <= invoice_date_due) / count(*), 1) AS pct_on_time
FROM paid
GROUP BY 1 ORDER BY 1;
