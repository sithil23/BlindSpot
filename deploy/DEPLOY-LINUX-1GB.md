# Deploy BLINDSPOT to sbmc.space on a small Linux VPS

This guide assumes Ubuntu/Debian, SSH sudo access, the domain is yours, and no existing website should be overwritten. **Use a subdomain such as `blindspot.sbmc.space` if `sbmc.space` hosts another site**; change the Nginx `server_name` and Certbot command accordingly. No live deployment has been performed by this package.

## 1. DNS and server sizing

Point an `A` record for `sbmc.space` (or your chosen subdomain) at the server's public IPv4 address. DNS updates may take time. Ensure ports 80 and 443 are open in the provider's firewall. A 1 GB VPS can be tight; running other apps may cause out-of-memory termination. This build avoids camera inference on the server and keeps telemetry in memory per browser session. Use a 1–2 GB swap file only if needed; swap is not extra RAM and may be slow. Monitor actual memory before increasing load.

## 2. Install base packages

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip nginx certbot python3-certbot-nginx
```

Check `python3 --version` (Python >=3.10). Use the full Python interpreter and a dedicated venv. Copy the **server ZIP** from your computer to the server and extract its `BLINDSPOT` directory into `/opt/blindspot`. Example:

```bash
sudo useradd --system --home /opt/blindspot --shell /usr/sbin/nologin blindspot || true
sudo mkdir -p /opt/blindspot
sudo chown -R "$USER":"$USER" /opt/blindspot
# Transfer the server ZIP with scp/SFTP, unpack it on the server, and copy the BLINDSPOT/* contents into /opt/blindspot.
cd /opt/blindspot
python3 -m venv .venv
.venv/bin/python -m pip install --no-cache-dir -e .
sudo chown -R blindspot:blindspot /opt/blindspot
```

No webcam extras (`.[camera]`) are required on the VPS. Do not copy your Windows `.venv`; a Linux virtual environment must be created on Linux.

## 3. Install and start service

```bash
sudo cp /opt/blindspot/deploy/blindspot.service /etc/systemd/system/blindspot.service
sudo systemctl daemon-reload
sudo systemctl enable --now blindspot
sudo systemctl status blindspot --no-pager
curl -I http://127.0.0.1:8501/
```

Service binds to localhost, not a public port. `BLINDSPOT_PUBLIC=1` hides local webcam and history and disables saving. Browser-session simulation uses randomly chosen or user-selected replay seeds; no account information is needed.

## 4. Reverse proxy and HTTPS

Only do this if `sbmc.space` is not currently served by another Nginx configuration. If it is, use a separate subdomain and match `server_name` to that subdomain.

```bash
sudo cp /opt/blindspot/deploy/blindspot.nginx.conf /etc/nginx/sites-available/blindspot
sudo ln -s /etc/nginx/sites-available/blindspot /etc/nginx/sites-enabled/blindspot
sudo nginx -t
sudo systemctl reload nginx
sudo certbot --nginx -d sbmc.space
```

Certbot should install HTTPS and configure certificate renewal. Test `https://sbmc.space/` and confirm that interactions still work (Streamlit requires WebSocket proxy headers). Consider rate limiting at Nginx or Cloudflare and keeping Ubuntu packages patched.

## 5. Verify and troubleshoot

```bash
sudo journalctl -u blindspot -n 100 --no-pager
free -h
systemctl show blindspot -p MemoryCurrent -p MemoryPeak
sudo nginx -t
```

Do **not** claim medical or flight safety validation. This publicly accessible prototype has no authentication; it intentionally excludes private sessions and real webcam processing. Streamlit can still create browser sessions and memory use for each connected visitor. On 1 GB RAM, monitor load and limit visitors as needed. Do not add visitor-upload or database-writing features without reviewing security and privacy first.

For local Windows use, leave `BLINDSPOT_PUBLIC` unset and run `python -m streamlit run app.py` in your existing virtual environment.
