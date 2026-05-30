# Psychoposition — Backend API (Flask)

API Backend untuk sistem rekomendasi penempatan kandidat berbasis **Fuzzy-ELECTRE + ML (EWM + PSO)**.

---

## ⚡ Cara Cepat (Mac/Linux)

```bash
cd thesis_flask

# Jika belum ada .env, salin dulu:
cp .env.example .env
# Edit .env: sesuaikan DB_PORT (MAMP=8889, XAMPP=3306), DB_DATABASE=thesis

# Buat database di MySQL/phpMyAdmin:
# CREATE DATABASE thesis CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

# Jalankan semua sekaligus (install deps + seed + run server):
bash start.sh
```

---

## 🔧 Cara Manual Step-by-step

### 1. Buat Database

```sql
-- Di phpMyAdmin / MySQL CLI / TablePlus:
CREATE DATABASE thesis CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 2. Setup Environment

```bash
cd thesis_flask
cp .env.example .env
```

Edit `.env`:
```env
DB_HOST=localhost
DB_PORT=8889        # MAMP=8889 | XAMPP=3306 | MySQL default=3306
DB_DATABASE=thesis
DB_USERNAME=root
DB_PASSWORD=root    # Sesuaikan password MySQL kamu
APP_PORT=5100
```

### 3. Install Dependencies

```bash
python3 -m venv venv
source venv/bin/activate          # Mac/Linux
# venv\Scripts\activate           # Windows

pip install -r requirements.txt
```

### 4. Jalankan Seeder

```bash
python seeder.py
```

Output yang diharapkan:
```
✅ Tables created / verified.
📦 Seeding roles...
  ➕ Role 'admin' created.
  ➕ Role 'candidate' created.
...
✅ SEEDING COMPLETED!
```

### 5. Jalankan Server

```bash
python run.py
```

Output:
```
==================================================
  Psychoposition API Server
  Running on: http://0.0.0.0:5100
  Localhost : http://localhost:5100/api
  Debug mode: True
==================================================
```

Server berjalan di `http://localhost:5100/api`
Dari perangkat lain di jaringan yang sama: `http://<IP-KOMPUTER>:5100/api`

---

## 🔑 Akun Default (setelah seeder)

| Role      | Email                | Password  |
|-----------|----------------------|-----------|
| Admin     | admin@company.com    | password  |
| Admin     | hr@company.com       | password  |
| Kandidat  | budi@email.com       | password  |
| Kandidat  | rina@email.com       | password  |
| ...       | (20 kandidat total)  | password  |

---

## 📋 API Endpoints

### Auth
| Method | URL | Keterangan |
|--------|-----|------------|
| POST | `/api/auth/login` | Login |
| POST | `/api/auth/register` | Register (kandidat) |
| GET  | `/api/auth/me` | Profil sendiri |
| POST | `/api/auth/logout` | Logout |
| POST | `/api/auth/refresh` | Refresh token |

### Master (Admin only)
| Method | URL | Keterangan |
|--------|-----|------------|
| GET/POST | `/api/master/criteria` | CRUD Kriteria |
| GET/POST | `/api/master/requirement-types` | CRUD Jenis Syarat |
| GET/POST | `/api/master/recruitments` | CRUD Rekrutmen |
| POST | `/api/master/recruitments/{id}/publish` | Publish |
| POST | `/api/master/recruitments/{id}/close` | Tutup |
| GET/POST | `/api/master/recruitments/{id}/positions` | CRUD Posisi |
| POST | `/api/master/recruitments/{id}/positions/{pid}/criteria` | Setup Kriteria Posisi |
| GET/POST | `/api/master/position-criteria/{id}/questions` | CRUD Pertanyaan |
| POST | `/api/master/questions/{id}/options` | Tambah Opsi |

### Content (Kandidat)
| Method | URL | Keterangan |
|--------|-----|------------|
| GET | `/api/content/recruitments` | Rekrutmen aktif |
| POST | `/api/content/apply/{position_id}` | Daftar ke posisi |
| GET | `/api/content/applications/{id}/questions` | Ambil soal |
| POST | `/api/content/applications/{id}/submit` | Submit jawaban |
| GET | `/api/content/my-applications` | Lamaran saya |

### Report (Admin only)
| Method | URL | Keterangan |
|--------|-----|------------|
| GET | `/api/report/dashboard` | Ringkasan dashboard |
| POST | `/api/report/generate/{position_id}` | **Generate Ranking** (Fuzzy+EWM+PSO+ELECTRE) |
| GET | `/api/report/ranking/{position_id}` | Lihat ranking (manual vs ML) |
| POST | `/api/report/ranking/{position_id}/choose` | Pilih versi manual/ML |
| POST | `/api/report/ranking/{position_id}/finalize/{app_id}` | Tetapkan accepted/rejected |
| GET | `/api/report/ml-logs/{position_id}` | Log proses ML |

---

## 🐛 Troubleshooting

**`Access denied for user 'root'@'localhost'`**
→ Cek `DB_PASSWORD` di `.env`. MAMP default: `root`.

**`Can't connect to MySQL server on 'localhost' (61)`**
→ Pastikan MAMP/XAMPP/MySQL sudah running.
→ Cek `DB_PORT` di `.env`: MAMP=`8889`, XAMPP/standar=`3306`.

**`Unknown database 'thesis'`**
→ Buat database dulu: `CREATE DATABASE thesis ...`

**`ModuleNotFoundError: No module named 'flask'`**
→ Aktifkan venv dulu: `source venv/bin/activate`

**Port 5100 sudah dipakai**
→ Ganti `APP_PORT=5101` di `.env`

---

## 🏗️ Struktur Project

```
thesis_flask/
├── app/
│   ├── __init__.py          # App factory (Flask + extensions)
│   ├── models/              # SQLAlchemy models
│   ├── controllers/         # Route handlers
│   ├── services/            # Fuzzy, EWM, PSO, ELECTRE, Scoring
│   ├── helpers/             # Response format, validator
│   └── middleware/          # JWT auth middleware
├── routes/
│   └── api.py               # Semua URL rules
├── config/
│   └── settings.py          # Config dari .env
├── .env                     # Konfigurasi (jangan commit!)
├── .env.example             # Template .env
├── requirements.txt         # Dependencies (tanpa versi = latest)
├── seeder.py                # Seed data awal
├── run.py                   # Entry point server
└── start.sh                 # Script all-in-one setup
```
