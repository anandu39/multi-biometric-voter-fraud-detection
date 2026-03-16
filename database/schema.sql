-- =====================================================
-- SQLITE DATABASE SCHEMA
-- Multi Biometric Voter Fraud Detection
-- =====================================================

PRAGMA foreign_keys = ON;


-- =====================================================
-- TABLE 1 : VOTERS
-- =====================================================

CREATE TABLE IF NOT EXISTS voters (

    voter_id INTEGER PRIMARY KEY AUTOINCREMENT,

    name TEXT NOT NULL,
    dob TEXT,
    gender TEXT,
    address TEXT,

    phone TEXT,
    email TEXT,

    status TEXT DEFAULT 'active',

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- =====================================================
-- TABLE 2 : IDENTITY DOCUMENTS
-- =====================================================

CREATE TABLE IF NOT EXISTS identity_documents (

    document_id INTEGER PRIMARY KEY AUTOINCREMENT,

    voter_id INTEGER NOT NULL,

    document_type TEXT NOT NULL,

    document_number TEXT UNIQUE NOT NULL,

    verified INTEGER DEFAULT 0,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (voter_id) REFERENCES voters(voter_id)
);


-- =====================================================
-- TABLE 3 : BIOMETRICS
-- =====================================================

CREATE TABLE IF NOT EXISTS biometrics (

    biometric_id INTEGER PRIMARY KEY AUTOINCREMENT,

    voter_id INTEGER NOT NULL,

    face_embedding TEXT,
    iris_embedding TEXT,
    fingerprint_template TEXT,

    face_image_path TEXT,
    iris_image_path TEXT,
    fingerprint_path TEXT,

    biometric_hash TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (voter_id) REFERENCES voters(voter_id)
);


-- =====================================================
-- TABLE 4 : FRAUD ALERTS
-- =====================================================

CREATE TABLE IF NOT EXISTS fraud_alerts (

    alert_id INTEGER PRIMARY KEY AUTOINCREMENT,

    voter_id INTEGER,
    matched_voter_id INTEGER,

    face_score REAL,
    iris_score REAL,
    fingerprint_score REAL,

    final_score REAL,

    alert_reason TEXT,

    alert_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- =====================================================
-- INDEXES
-- =====================================================

CREATE INDEX IF NOT EXISTS idx_document_number
ON identity_documents(document_number);

CREATE INDEX IF NOT EXISTS idx_biometric_hash
ON biometrics(biometric_hash);