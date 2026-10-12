CREATE TABLE IF NOT EXISTS "Users" (
    user_id        SERIAL PRIMARY KEY,
    username       VARCHAR(64)  NOT NULL UNIQUE,
    email          VARCHAR(254) NOT NULL UNIQUE,
    password_hash  TEXT         NOT NULL,
    role           VARCHAR(20)  NOT NULL
                   CHECK (role IN ('admin', 'manager', 'store_manager', 'staff')),
    is_active      BOOLEAN      NOT NULL DEFAULT TRUE,
    last_login_at  TIMESTAMPTZ,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS "Projects" (
    project_id   SERIAL PRIMARY KEY,
    name         VARCHAR(200) NOT NULL,
    description  TEXT,
    status       VARCHAR(20)  NOT NULL DEFAULT 'planned'
                 CHECK (status IN ('planned', 'active', 'on_hold', 'completed')),
    manager_id   INTEGER NOT NULL REFERENCES "Users"(user_id),
    start_date   DATE,
    due_date     DATE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS "Tasks" (
    task_id      SERIAL PRIMARY KEY,
    project_id   INTEGER NOT NULL REFERENCES "Projects"(project_id) ON DELETE CASCADE,
    assignee_id  INTEGER REFERENCES "Users"(user_id),
    title        VARCHAR(200) NOT NULL,
    status       VARCHAR(20)  NOT NULL DEFAULT 'todo'
                 CHECK (status IN ('todo', 'in_progress', 'done')),
    due_date     DATE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS "Assets" (
    asset_id    SERIAL PRIMARY KEY,
    asset_type  VARCHAR(10)  NOT NULL CHECK (asset_type IN ('tool', 'device', 'vehicle')),
    name        VARCHAR(150) NOT NULL,
    category    VARCHAR(100),
    brand       VARCHAR(100),
    serial_no   VARCHAR(100) UNIQUE,
    condition   VARCHAR(50)  NOT NULL DEFAULT 'good',
    status      VARCHAR(20)  NOT NULL DEFAULT 'available'
                CHECK (status IN ('available', 'assigned', 'maintenance', 'retired')),
    image_path  VARCHAR(255),
    added_by    INTEGER REFERENCES "Users"(user_id),
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS "Vehicle_Details" (
    asset_id  INTEGER PRIMARY KEY REFERENCES "Assets"(asset_id) ON DELETE CASCADE,
    plate_no  VARCHAR(20) NOT NULL UNIQUE,
    make      VARCHAR(100),
    model     VARCHAR(100),
    mileage   INTEGER NOT NULL DEFAULT 0 CHECK (mileage >= 0)
);

CREATE TABLE IF NOT EXISTS "Requests" (
    request_id    SERIAL PRIMARY KEY,
    requester_id  INTEGER NOT NULL REFERENCES "Users"(user_id),
    asset_id      INTEGER REFERENCES "Assets"(asset_id),
    project_id    INTEGER REFERENCES "Projects"(project_id),
    item_name     VARCHAR(200),
    reason        TEXT,
    status        VARCHAR(20) NOT NULL DEFAULT 'pending'
                  CHECK (status IN ('pending', 'approved', 'rejected', 'fulfilled', 'cancelled')),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (asset_id IS NOT NULL OR item_name IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS "Asset_Assignments" (
    assignment_id    SERIAL PRIMARY KEY,
    asset_id         INTEGER NOT NULL REFERENCES "Assets"(asset_id),
    user_id          INTEGER NOT NULL REFERENCES "Users"(user_id),
    project_id       INTEGER REFERENCES "Projects"(project_id),
    request_id       INTEGER REFERENCES "Requests"(request_id),
    assigned_by      INTEGER REFERENCES "Users"(user_id),
    assigned_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    due_back         DATE,
    returned_at      TIMESTAMPTZ,
    return_condition VARCHAR(50)
);

CREATE UNIQUE INDEX IF NOT EXISTS one_open_assignment_per_asset
    ON "Asset_Assignments"(asset_id) WHERE returned_at IS NULL;
CREATE INDEX IF NOT EXISTS assets_status_idx ON "Assets"(status);
CREATE INDEX IF NOT EXISTS assets_type_idx   ON "Assets"(asset_type);

CREATE TABLE IF NOT EXISTS "Procurements" (
    procurement_id  SERIAL PRIMARY KEY,
    request_id      INTEGER UNIQUE REFERENCES "Requests"(request_id) ON DELETE SET NULL,
    requested_by    INTEGER NOT NULL REFERENCES "Users"(user_id),
    item_name       VARCHAR(200) NOT NULL,
    quantity        INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),
    estimated_cost  NUMERIC(12, 2) NOT NULL CHECK (estimated_cost >= 0),
    supplier        VARCHAR(200),
    status          VARCHAR(20) NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'level_1', 'level_2', 'approved', 'rejected')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS "Approvals" (
    approval_id     SERIAL PRIMARY KEY,
    procurement_id  INTEGER NOT NULL REFERENCES "Procurements"(procurement_id) ON DELETE CASCADE,
    level           SMALLINT NOT NULL CHECK (level IN (1, 2)),
    approver_id     INTEGER REFERENCES "Users"(user_id),
    decision        VARCHAR(10) NOT NULL DEFAULT 'pending'
                    CHECK (decision IN ('pending', 'approved', 'rejected')),
    comment         TEXT,
    decided_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (procurement_id, level)
);

CREATE TABLE IF NOT EXISTS "Disbursements" (
    disbursement_id  SERIAL PRIMARY KEY,
    procurement_id   INTEGER NOT NULL UNIQUE REFERENCES "Procurements"(procurement_id),
    amount           NUMERIC(12, 2) NOT NULL CHECK (amount >= 0),
    status           VARCHAR(12) NOT NULL DEFAULT 'pending'
                     CHECK (status IN ('pending', 'processing', 'success', 'failed')),
    paid_by          INTEGER REFERENCES "Users"(user_id),
    paid_at          TIMESTAMPTZ,
    receipt_ref      VARCHAR(100),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS "Notifications" (
    notification_id  SERIAL PRIMARY KEY,
    user_id          INTEGER NOT NULL REFERENCES "Users"(user_id) ON DELETE CASCADE,
    message          VARCHAR(500) NOT NULL,
    notif_type       VARCHAR(30)  NOT NULL DEFAULT 'info',
    is_read          BOOLEAN NOT NULL DEFAULT FALSE,
    email_sent       BOOLEAN NOT NULL DEFAULT FALSE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS notifications_user_unread_idx
    ON "Notifications"(user_id, is_read);

CREATE TABLE IF NOT EXISTS "Audit_Log" (
    audit_id     SERIAL PRIMARY KEY,
    user_id      INTEGER REFERENCES "Users"(user_id) ON DELETE SET NULL,
    action       VARCHAR(100) NOT NULL,
    entity_type  VARCHAR(50),
    entity_id    INTEGER,
    details      JSONB,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS audit_log_created_idx ON "Audit_Log"(created_at);