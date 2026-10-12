-- Asset tables for Member 3. Give this to Member 1 to merge into schema.sql.
-- ASSUMPTION: "Users".user_id is an integer primary key.
-- project_id and request_id have no foreign keys yet: add them once
-- the Projects and Requests tables exist.

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

CREATE TABLE IF NOT EXISTS "Asset_Assignments" (
    assignment_id    SERIAL PRIMARY KEY,
    asset_id         INTEGER NOT NULL REFERENCES "Assets"(asset_id),
    user_id          INTEGER NOT NULL REFERENCES "Users"(user_id),
    project_id       INTEGER,
    request_id       INTEGER,
    assigned_by      INTEGER REFERENCES "Users"(user_id),
    assigned_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    due_back         DATE,
    returned_at      TIMESTAMPTZ,
    return_condition VARCHAR(50)
);

-- An asset can have only one open (not yet returned) assignment.
CREATE UNIQUE INDEX IF NOT EXISTS one_open_assignment_per_asset
    ON "Asset_Assignments"(asset_id) WHERE returned_at IS NULL;

CREATE INDEX IF NOT EXISTS assets_status_idx ON "Assets"(status);
CREATE INDEX IF NOT EXISTS assets_type_idx   ON "Assets"(asset_type);