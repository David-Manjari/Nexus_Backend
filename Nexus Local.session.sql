
SELECT disbursement_id, reference, payee, amount, currency, status,
       payment_reference, failure_reason, created_at, paid_at
FROM "Disbursements"
ORDER BY created_at DESC
LIMIT 100;