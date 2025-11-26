# Market Rotation Strategy Webapp - Deployment Guide

This guide provides step-by-step instructions for deploying the Market Rotation Strategy Webapp in a **Proxmox LXC (Linux Container)** environment.

## Prerequisites

- **Proxmox VE** server up and running.
- Basic familiarity with the Linux command line.
- Internet access for the container to fetch stock data.

---

## Step 1: Create a Proxmox LXC Container

1.  **Log in** to your Proxmox web interface.
2.  Click **"Create CT"** (top right).
3.  **General**:
    -   **Hostname**: `market-rotation-app` (or your preferred name)
    -   **Password**: Set a strong root password.
    -   **Unprivileged container**: Checked (recommended for security).
4.  **Template**:
    -   Select a **Debian 12 (Bookworm)** or **Ubuntu 22.04/24.04** template.
5.  **Disks**:
    -   **Storage**: Local-lvm (or your preferred storage).
    -   **Disk size**: `8GB` is sufficient.
6.  **CPU**:
    -   **Cores**: `1` or `2` cores.
7.  **Memory**:
    -   **Memory**: `1024 MB` (1GB) is usually enough.
    -   **Swap**: `512 MB`.
8.  **Network**:
    -   **Bridge**: `vmbr0` (default).
    -   **IPv4**: `DHCP` (or set a Static IP if you prefer).
9.  **Confirm** and **Start** the container.

---

## Step 2: System Setup

Open the **Console** of your new container or SSH into it.

1.  **Update the system**:
    ```bash
    apt update && apt upgrade -y
    ```

2.  **Install system dependencies**:
    We need Python, pip, git, and virtualenv support.
    ```bash
    apt install -y python3 python3-pip python3-venv git curl
    ```

---

## Step 3: Application Setup

We will set up the application in the `/opt` directory, which is a common convention for add-on software.

1.  **Clone the repository**:
    *(Replace `<YOUR_REPO_URL>` with the actual URL of this repository)*
    ```bash
    cd /opt
    git clone <YOUR_REPO_URL> market-rotation-app
    cd market-rotation-app
    ```
    *If you don't have a git URL yet, you can copy the files manually using SCP or FileZilla.*

2.  **Create a Virtual Environment**:
    This keeps the application dependencies isolated from the system Python.
    ```bash
    python3 -m venv venv
    ```

3.  **Activate the Virtual Environment**:
    ```bash
    source venv/bin/activate
    ```

4.  **Install Python Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

---

## Step 4: Running the Application

### Option A: Manual Test Run
To verify everything is working:
```bash
streamlit run app.py
```
You should see output indicating the server is running on `http://0.0.0.0:8501`.
Press `Ctrl+C` to stop it.

### Option B: Systemd Service (Recommended for Production)
We will create a system service so the app starts automatically on boot and restarts if it crashes.

1.  **Create a service user** (optional but recommended for security):
    ```bash
    useradd -r -s /bin/false marketapp
    chown -R marketapp:marketapp /opt/market-rotation-app
    ```

2.  **Create the service file**:
    ```bash
    nano /etc/systemd/system/market-rotation.service
    ```

3.  **Paste the following configuration**:
    *Adjust the paths if you installed somewhere other than `/opt/market-rotation-app`.*

    ```ini
    [Unit]
    Description=Market Rotation Streamlit App
    After=network.target

    [Service]
    User=marketapp
    Group=marketapp
    WorkingDirectory=/opt/market-rotation-app
    Environment="PATH=/opt/market-rotation-app/venv/bin:/usr/local/bin:/usr/bin:/bin"
    ExecStart=/opt/market-rotation-app/venv/bin/streamlit run app.py --server.port 8501 --server.address 0.0.0.0
    Restart=always
    RestartSec=5

    [Install]
    WantedBy=multi-user.target
    ```

4.  **Save and Exit**:
    Press `Ctrl+O`, `Enter`, then `Ctrl+X`.

5.  **Enable and Start the Service**:
    ```bash
    systemctl daemon-reload
    systemctl enable market-rotation
    systemctl start market-rotation
    ```

6.  **Check Status**:
    ```bash
    systemctl status market-rotation
    ```
    You should see `Active: active (running)`.

---

## Step 5: Accessing the Application

1.  Find the **IP address** of your LXC container:
    ```bash
    ip a
    ```
    Look for the IP address under `eth0` (e.g., `192.168.1.105`).

2.  Open your web browser and navigate to:
    ```
    http://<YOUR_LXC_IP>:8501
    ```

---

## Maintenance

-   **View Logs**:
    ```bash
    journalctl -u market-rotation -f
    ```

-   **Update Application**:
    ```bash
    cd /opt/market-rotation-app
    git pull
    source venv/bin/activate
    pip install -r requirements.txt
    systemctl restart market-rotation
    ```
