# Konfigurasi sudoers untuk deployment tanpa password

Jalankan perintah ini di VPS agar GitHub Actions bisa restart service tanpa diminta password:

```bash
# Ganti "ubuntu" dengan username VPS Anda (sesuai VPS_USER secret)
echo "ubuntu ALL=(ALL) NOPASSWD: /bin/systemctl restart psychoposition.service, /bin/systemctl status psychoposition.service, /bin/systemctl is-active psychoposition.service" | sudo tee /etc/sudoers.d/psychoposition
sudo chmod 440 /etc/sudoers.d/psychoposition
```

