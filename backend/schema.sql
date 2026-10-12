-- Project tracking and sequential approval workflow.
-- The Users table is provisioned by the account setup component.

CREATE TABLE IF NOT EXISTS "Projects" (
	project_id   SERIAL PRIMARY KEY,
	name         VARCHAR(200) NOT NULL,
	description  TEXT,
	status       VARCHAR(24) NOT NULL DEFAULT 'draft'
				 CHECK (status IN (
					 'draft', 'pending_approval', 'approved', 'active',
					 'on_hold', 'completed', 'cancelled', 'rejected'
				 )),
	start_date   DATE,
	end_date     DATE,
	created_by   INTEGER NOT NULL REFERENCES "Users"(user_id),
	created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
	updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
	CHECK (end_date IS NULL OR start_date IS NULL OR end_date >= start_date)
);

CREATE TABLE IF NOT EXISTS "Approval_Requests" (
	approval_id    SERIAL PRIMARY KEY,
	project_id     INTEGER NOT NULL REFERENCES "Projects"(project_id) ON DELETE CASCADE,
	round_number   INTEGER NOT NULL CHECK (round_number > 0),
	step_order     INTEGER NOT NULL CHECK (step_order > 0),
	approver_id    INTEGER NOT NULL REFERENCES "Users"(user_id),
	status         VARCHAR(12) NOT NULL DEFAULT 'waiting'
				   CHECK (status IN ('waiting', 'pending', 'approved', 'rejected', 'skipped')),
	comments       TEXT,
	created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
	decided_at     TIMESTAMPTZ,
	UNIQUE (project_id, round_number, step_order),
	UNIQUE (project_id, round_number, approver_id)
);

CREATE TABLE IF NOT EXISTS "Project_Status_History" (
	history_id   SERIAL PRIMARY KEY,
	project_id   INTEGER NOT NULL REFERENCES "Projects"(project_id) ON DELETE CASCADE,
	from_status  VARCHAR(24),
	to_status    VARCHAR(24) NOT NULL CHECK (to_status IN (
					 'draft', 'pending_approval', 'approved', 'active',
					 'on_hold', 'completed', 'cancelled', 'rejected'
				 )),
	changed_by   INTEGER NOT NULL REFERENCES "Users"(user_id),
	reason       TEXT,
	changed_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
	CHECK (from_status IS NULL OR from_status IN (
		'draft', 'pending_approval', 'approved', 'active',
		'on_hold', 'completed', 'cancelled', 'rejected'
	))
);

CREATE INDEX IF NOT EXISTS projects_status_idx ON "Projects"(status);
CREATE INDEX IF NOT EXISTS projects_created_by_idx ON "Projects"(created_by);
CREATE INDEX IF NOT EXISTS approvals_inbox_idx
	ON "Approval_Requests"(approver_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS approvals_project_round_idx
	ON "Approval_Requests"(project_id, round_number, step_order);
CREATE INDEX IF NOT EXISTS project_status_history_idx
	ON "Project_Status_History"(project_id, changed_at DESC);
