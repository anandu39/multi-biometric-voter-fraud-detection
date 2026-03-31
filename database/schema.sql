-- EVRS Schema v3 (Phase 2)
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS officers (
    officer_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL, emp_id TEXT UNIQUE NOT NULL,
    mobile TEXT UNIQUE NOT NULL, district TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'registration_officer',
    password_hash TEXT NOT NULL, is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS voters (
    voter_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL, dob TEXT, gender TEXT,
    parent_name TEXT, occupation TEXT, phone TEXT, email TEXT,
    street TEXT, ward_number TEXT, panchayat TEXT, taluk TEXT,
    district TEXT, state TEXT, pincode TEXT, constituency TEXT,
    address TEXT, status TEXT DEFAULT 'active', officer_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (officer_id) REFERENCES officers(officer_id)
);

CREATE TABLE IF NOT EXISTS identity_documents (
    document_id INTEGER PRIMARY KEY AUTOINCREMENT,
    voter_id INTEGER NOT NULL, document_type TEXT NOT NULL,
    document_number TEXT UNIQUE NOT NULL, verified INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (voter_id) REFERENCES voters(voter_id)
);

CREATE TABLE IF NOT EXISTS biometrics (
    biometric_id INTEGER PRIMARY KEY AUTOINCREMENT,
    voter_id INTEGER NOT NULL UNIQUE,
    face_embedding TEXT, iris_embedding TEXT, fingerprint_template TEXT,
    face_image_path TEXT, iris_image_path TEXT, fingerprint_path TEXT,
    biometric_hash TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (voter_id) REFERENCES voters(voter_id)
);

CREATE TABLE IF NOT EXISTS fraud_alerts (
    alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
    voter_id INTEGER, matched_voter_id INTEGER,
    face_score REAL DEFAULT 0, iris_score REAL DEFAULT 0,
    fingerprint_score REAL DEFAULT 0, final_score REAL DEFAULT 0,
    alert_reason TEXT, alert_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS otp_store (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mobile TEXT NOT NULL, otp TEXT NOT NULL,
    purpose TEXT DEFAULT 'verification',
    expires_at INTEGER NOT NULL, used INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS voting_log (
    vote_id INTEGER PRIMARY KEY AUTOINCREMENT,
    voter_id INTEGER NOT NULL, officer_id INTEGER,
    booth_name TEXT, ward_number TEXT, override_reason TEXT,
    voted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (voter_id) REFERENCES voters(voter_id),
    FOREIGN KEY (officer_id) REFERENCES officers(officer_id)
);

CREATE INDEX IF NOT EXISTS idx_document_number  ON identity_documents(document_number);
CREATE INDEX IF NOT EXISTS idx_biometric_hash   ON biometrics(biometric_hash);
CREATE INDEX IF NOT EXISTS idx_voter_ward       ON voters(ward_number);
CREATE INDEX IF NOT EXISTS idx_voter_district   ON voters(district);
CREATE INDEX IF NOT EXISTS idx_otp_mobile       ON otp_store(mobile, expires_at);
CREATE INDEX IF NOT EXISTS idx_voting_log_voter ON voting_log(voter_id, voted_at);
CREATE INDEX IF NOT EXISTS idx_voting_log_ward  ON voting_log(ward_number, voted_at);