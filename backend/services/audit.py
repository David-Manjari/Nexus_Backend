"""Audit dashboard queries whose backing schemas are available."""

from ..admin_accounts import connect_database


class AuditSchemaNotConfigured(RuntimeError):
	"""Raised when an audit dashboard's backing tables are not provisioned."""


def get_project_audit():
	with connect_database() as connection:
		rows = connection.execute(
			'''SELECT status, COUNT(*) AS project_count
			   FROM "Projects"
			   GROUP BY status
			   ORDER BY status'''
		).fetchall()
	return [dict(row) for row in rows]


def get_account_activity(user_id):
	raise AuditSchemaNotConfigured("Account activity schema is not configured.")


def get_disbursement_audit():
	raise AuditSchemaNotConfigured("Disbursement audit schema is not configured.")


def get_procurement_audit():
	raise AuditSchemaNotConfigured("Procurement audit schema is not configured.")
