-- 芯知 SemiKB 数据库初始化
SET NAMES utf8mb4;

CREATE DATABASE IF NOT EXISTS semi_kb_db
  DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE semi_kb_db;

CREATE TABLE IF NOT EXISTS t_admin (
  id            BIGINT PRIMARY KEY AUTO_INCREMENT,
  username      VARCHAR(64)  NOT NULL UNIQUE,
  password_hash CHAR(64)     NOT NULL,
  salt          VARCHAR(64)  NOT NULL,
  display_name  VARCHAR(64)  NOT NULL DEFAULT '管理员',
  created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS t_session (
  id             BIGINT PRIMARY KEY AUTO_INCREMENT,
  visitor_name   VARCHAR(32) NOT NULL DEFAULT '访客',
  status         ENUM('active','closed') NOT NULL DEFAULT 'active',
  turn_count     INT NOT NULL DEFAULT 0,
  created_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  last_active_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_status_active (status, last_active_at)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS t_message (
  id               BIGINT PRIMARY KEY AUTO_INCREMENT,
  session_id       BIGINT NOT NULL,
  role             ENUM('user','bot') NOT NULL,
  content          MEDIUMTEXT NOT NULL,
  source           ENUM('vectorstore','web_search','fallback','extractive','direct') DEFAULT NULL,
  route            VARCHAR(32) DEFAULT NULL,
  rewrite_count    TINYINT NOT NULL DEFAULT 0,
  regenerate_count TINYINT NOT NULL DEFAULT 0,
  llm_calls        TINYINT NOT NULL DEFAULT 0,
  latency_ms       INT DEFAULT NULL,
  verified         TINYINT NOT NULL DEFAULT 1,
  trace_json       JSON DEFAULT NULL,
  rating           TINYINT DEFAULT NULL,
  created_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_session (session_id, id),
  KEY idx_created (created_at),
  KEY idx_source (source),
  CONSTRAINT fk_msg_session FOREIGN KEY (session_id) REFERENCES t_session(id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS t_citation (
  id          BIGINT PRIMARY KEY AUTO_INCREMENT,
  message_id  BIGINT NOT NULL,
  doc_uid     CHAR(32) DEFAULT NULL,
  chunk_index INT DEFAULT NULL,
  `rank`      TINYINT NOT NULL,
  title       VARCHAR(255) DEFAULT NULL,
  filename    VARCHAR(255) DEFAULT NULL,
  url         VARCHAR(512) DEFAULT NULL,
  snippet     VARCHAR(512) DEFAULT NULL,
  created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_message (message_id),
  KEY idx_doc (doc_uid),
  CONSTRAINT fk_cit_msg FOREIGN KEY (message_id)
    REFERENCES t_message(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS t_document (
  id                BIGINT PRIMARY KEY AUTO_INCREMENT,
  doc_uid           CHAR(32) NOT NULL UNIQUE,
  filename          VARCHAR(255) NOT NULL,
  title             VARCHAR(255) DEFAULT NULL,
  source_path       VARCHAR(512) NOT NULL,
  file_hash         CHAR(64) NOT NULL,
  size_bytes        INT NOT NULL DEFAULT 0,
  chunk_count       INT NOT NULL DEFAULT 0,
  status            ENUM('pending','parsing','indexing','ready','failed','deleted')
                    NOT NULL DEFAULT 'pending',
  milvus_collection VARCHAR(64) NOT NULL DEFAULT 'semi_kb_chunks_v1',
  error_msg         VARCHAR(512) DEFAULT NULL,
  created_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  indexed_at        DATETIME DEFAULT NULL,
  UNIQUE KEY uk_hash (file_hash),
  KEY idx_status (status)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS t_ingest_task (
  id           BIGINT PRIMARY KEY AUTO_INCREMENT,
  task_type    ENUM('upload','reindex','delete','rebuild') NOT NULL,
  doc_uid      CHAR(32) DEFAULT NULL,
  status       ENUM('queued','running','succeeded','failed','cancelled')
               NOT NULL DEFAULT 'queued',
  progress     TINYINT NOT NULL DEFAULT 0,
  total_chunks INT NOT NULL DEFAULT 0,
  done_chunks  INT NOT NULL DEFAULT 0,
  message      VARCHAR(512) DEFAULT NULL,
  created_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  finished_at  DATETIME DEFAULT NULL,
  KEY idx_status_created (status, created_at),
  KEY idx_doc (doc_uid)
) ENGINE=InnoDB;

INSERT INTO t_admin (username, password_hash, salt, display_name)
VALUES ('admin', SHA2(CONCAT('semi-kb', '123456'), 256), 'semi-kb', '知识库管理员')
ON DUPLICATE KEY UPDATE username = username;
