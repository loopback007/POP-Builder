# POP-Builder

Containerized **Network PoP (Point of Presence) Builder** for Network Engineers.

This app helps you:
- Model current PoP infrastructure (site/chassis/slots/line cards).
- Input sales forecast demand and traffic dispersion.
- Apply design strategy (`Run Hot` or `N+1`).
- Generate a Bill of Materials (BOM) for capacity upgrades.
- Export BOM summary as CSV.

---

## Tech Stack
- **Backend:** Python 3.11+, Flask, Gunicorn
- **Database:** PostgreSQL
- **Cache/Queue:** Redis + RQ worker
- **Web server:** Nginx (reverse proxy)
- **Orchestration:** Docker Compose

---

## Step-by-Step Setup on Ubuntu 22.04

### 1) Update system packages
```bash
sudo apt update
sudo apt upgrade -y
```

### 2) Install prerequisites
```bash
sudo apt install -y ca-certificates curl gnupg lsb-release git
```

### 3) Install Docker Engine + Compose plugin
```bash
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo \"$VERSION_CODENAME\") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

### 4) (Optional) Run Docker without sudo
```bash
sudo usermod -aG docker $USER
newgrp docker
```
> If group changes don’t apply immediately, log out and log back in.

### 5) Clone the repository
```bash
git clone <YOUR_REPO_URL> POP-Builder
cd POP-Builder
```

### 6) Create environment file
Create a `.env` in the project root:

```bash
cat > .env << 'ENV_EOF'
POSTGRES_USER=popuser
POSTGRES_PASSWORD=poppass
POSTGRES_DB=popbuilder
FLASK_ENV=development
REDIS_HOST=redis
REDIS_PORT=6379
ENV_EOF
```

### 7) Build and start the stack
```bash
docker compose up -d --build
```

### 8) Verify containers are healthy/running
```bash
docker compose ps
```
You should see services similar to:
- `db`
- `redis`
- `web`
- `worker`
- `nginx`

### 9) Open the app
Visit:
- **http://localhost:8080**

Nginx listens on port `8080` and proxies the Flask/Gunicorn app.

### 10) Check logs (if needed)
```bash
docker compose logs -f web
docker compose logs -f nginx
docker compose logs -f db
docker compose logs -f worker
```

### 11) Stop the stack
```bash
docker compose down
```

To stop and remove volumes too (DB/cache data reset):
```bash
docker compose down -v
```

---

## Usage Notes
1. Open the UI and provide:
   - Sales Forecast (Gbps)
   - Intl Traffic Split (%)
   - Design Strategy (`Run Hot` / `N+1`)
   - Port speed + count requirement and role (`Intl` or `Dom`)
2. Click **Run Solver**.
3. Review:
   - Current vs required vs post-upgrade capacity
   - Generated BOM and total cost
   - Post-upgrade slot occupancy
4. Click **Export CSV** to download the BOM summary.

---

## Troubleshooting
- **Port 8080 already in use**
  - Change `8080:80` in `docker-compose.yml` to another host port (e.g. `8090:80`).
- **Containers fail to start**
  - Inspect logs with `docker compose logs -f <service>`.
- **Database reset needed**
  - `docker compose down -v && docker compose up -d --build`.

---

## Project Files
- `docker-compose.yml` — service orchestration
- `Dockerfile` — app image build
- `nginx.conf` — reverse proxy config
- `app.py` — Flask routes + CSV export
- `logic.py` — capacity solver and BOM engine
- `models.py` — SQLAlchemy models
- `templates/index.html` — UI
- `static/styles.css` — styling
