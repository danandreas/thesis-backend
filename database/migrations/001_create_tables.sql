-- Migration: Create Initial Tables
-- Database: dan_flask
-- Run this if not using Flask-Migrate

CREATE DATABASE IF NOT EXISTS `dan_flask` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE `dan_flask`;

-- Roles Table
CREATE TABLE IF NOT EXISTS `roles` (
    `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
    `code` VARCHAR(50) NOT NULL UNIQUE,
    `name` VARCHAR(100) NOT NULL,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    INDEX `idx_roles_code` (`code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Users Table
CREATE TABLE IF NOT EXISTS `users` (
    `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
    `role_id` INT UNSIGNED NOT NULL,
    `name` VARCHAR(150) NOT NULL,
    `email` VARCHAR(200) NOT NULL UNIQUE,
    `password` VARCHAR(255) NOT NULL,
    `phone` VARCHAR(20) DEFAULT NULL,
    `address` TEXT DEFAULT NULL,
    `force_logout_at` DATETIME DEFAULT NULL COMMENT 'Semua token sebelum waktu ini dianggap invalid (logout semua device)',
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uniq_users_email` (`email`),
    INDEX `idx_users_role_id` (`role_id`),
    CONSTRAINT `fk_users_role_id` FOREIGN KEY (`role_id`) REFERENCES `roles` (`id`) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Token Blacklist Table
-- Menyimpan token yang sudah di-logout sebelum expired
CREATE TABLE IF NOT EXISTS `token_blacklist` (
    `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
    `jti` VARCHAR(36) NOT NULL UNIQUE COMMENT 'JWT ID — identifier unik tiap token',
    `token_type` VARCHAR(20) NOT NULL DEFAULT 'access' COMMENT 'access atau refresh',
    `user_id` INT UNSIGNED NOT NULL,
    `expires_at` DATETIME NOT NULL COMMENT 'Kapan token ini expired, untuk cleanup',
    `revoked_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT 'Kapan token di-revoke',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uniq_blacklist_jti` (`jti`),
    INDEX `idx_blacklist_user_id` (`user_id`),
    INDEX `idx_blacklist_expires_at` (`expires_at`),
    CONSTRAINT `fk_blacklist_user_id` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Default Data
INSERT IGNORE INTO `roles` (`code`, `name`) VALUES
    ('admin', 'Administrator'),
    ('user', 'User');

-- Default admin user (password: password)
INSERT IGNORE INTO `users` (`role_id`, `name`, `email`, `password`, `phone`, `address`)
SELECT r.id, 'Super Admin', 'admin@example.com',
    '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW',
    '08123456789', 'Jakarta, Indonesia'
FROM `roles` r WHERE r.code = 'admin' LIMIT 1;
