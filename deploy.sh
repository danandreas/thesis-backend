#!/bin/bash
# ============================================================
# Psychoposition Backend — VPS Deploy Script
# Jalankan script ini SEKALI SAJA saat setup awal VPS
# ============================================================
set -e

PROJECT_DIR="/var/www/htm/coba"
SERVICE_NAME="psychoposition"
PYTHON_BIN="python3"

echo ""
echo "========================================================"
echo "  PSYCHOPOSITION — VPS Initial Setup"
echo "========================================================"

# ── 1. Pindah ke direktori project ──
cd "$PROJECT_DIR"
echo "✅ Directory: $PROJECT_DIR"

# ── 2. Buat virtual environment ──
if [ ! -d "venv" ]; then
    echo "📦 Membuat virtual environment..."
    $PYTHON_BIN -m venv venv
fi
echo "✅ Virtualenv ready."

# ── 3. Aktifkan venv & install dependencies ──
source venv/bin/activate
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
echo "✅ Dependencies installed."

# ── 4. Cek file .env ──
if [ ! -f ".env" ]; then
    echo "⚠️  File .env tidak ditemukan. Menyalin dari .env.example..."
    cp .env.example .env
    echo "   ‼️  Edit file .env sesuai konfigurasi production, lalu jalankan script ini lagi."
    exit 1
fi
echo "✅ .env found."

# ── 5. Buat direktori log ──
mkdir -p storage/logs
echo "✅ Log directory ready."

# ── 6. Inisialisasi migrasi (hanya jika belum ada folder migrations) ──
if [ ! -d "migrations" ]; then
    echo "🗄️  Initializing Flask-Migrate..."
    flask db init
    flask db migrate -m "initial migration"
fi
flask db upgrade
echo "✅ Database migrations done."

# ── 7. Install Gunicorn ──
pip install gunicorn --quiet
echo "✅ Gunicorn installed."

# ── 8. Buat systemd service file ──
VENV_PATH="$PROJECT_DIR/venv"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

echo ""
echo "📝 Membuat systemd service: $SERVICE_FILE"
sudo tee "$SERVICE_FILE" > /dev/null << SERVICE
[Unit]
Description=Psychoposition Flask Backend
After=network.target

[Service]
User=$USER
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$VENV_PATH/bin"
EnvironmentFile=$PROJECT_DIR/.env
ExecStart=$VENV_PATH/bin/gunicorn --workers 3 --bind 0.0.0.0:5100 run:app
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
SERVICE

# ── 9. Enable & start service ──
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl start "$SERVICE_NAME"

sleep 2
sudo systemctl is-active --quiet "$SERVICE_NAME" \
    && echo "✅ Service '$SERVICE_NAME' is running!" \
    || (echo "❌ Service gagal start!" && sudo systemctl status "$SERVICE_NAME" && exit 1)

echo ""
echo "========================================================"
echo "  ✅ Setup selesai!"
echo "  API berjalan di: http://$(hostname -I | awk '{print $1}'):5100/api"
echo "========================================================"
