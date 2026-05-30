#!/bin/bash
# ============================================================
# Psychoposition Backend — Setup & Run Script
# ============================================================
set -e

echo ""
echo "======================================================"
echo "  PSYCHOPOSITION — Flask Backend Setup"
echo "======================================================"

# Masuk ke direktori project
cd "$(dirname "$0")"

# 1. Cek Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 tidak ditemukan. Install Python 3.10+ terlebih dahulu."
    exit 1
fi
echo "✅ Python: $(python3 --version)"

# 2. Buat virtual environment jika belum ada
if [ ! -d "venv" ]; then
    echo "📦 Membuat virtual environment..."
    python3 -m venv venv
fi
echo "✅ Virtualenv ready."

# 3. Aktifkan venv
source venv/bin/activate
echo "✅ Virtualenv activated."

# 4. Upgrade pip
pip install --upgrade pip --quiet

# 5. Install dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt --quiet
echo "✅ Dependencies installed."

# 6. Cek .env
if [ ! -f ".env" ]; then
    echo "⚠️  File .env tidak ditemukan. Menyalin dari .env.example..."
    cp .env.example .env
    echo "   ‼️  Edit file .env dan sesuaikan DB_HOST, DB_PORT, DB_DATABASE, dll."
    echo "   ‼️  Lalu jalankan script ini lagi."
    exit 1
fi
echo "✅ .env found."

# 7. Buat direktori log
mkdir -p storage/logs

# 8. Jalankan seeder (buat tabel + data awal)
echo ""
echo "📦 Running seeder (create tables + seed data)..."
python seeder.py

# 9. Jalankan server
echo ""
echo "🚀 Starting server..."
echo "   Akses: http://localhost:5100/api"
echo "   Atau  : http://$(hostname -I | awk '{print $1}'):5100/api"
echo ""
python run.py
