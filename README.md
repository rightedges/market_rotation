# Portfolio Manager

A multi-user stock portfolio management web application built with Python and Flask. This app allows users to track their investments, view real-time prices via Twelve Data, and calculate rebalancing actions to maintain their desired asset allocation.

## Features

-   **Multi-User Support**: Secure registration and login for multiple users.
-   **Multiple Portfolios**: Manage separate portfolios (e.g., RRSP, TFSA, Non-Registered).
-   **Real-Time Data**: Fetches live stock prices using Yahoo Finance.
-   **Portfolio Visualization**: Interactive doughnut charts showing current allocation.
-   **Smart Rebalancing**: Calculate exact buy/sell units based on target percentages and available cash.
    -   **Market Rotation Analysis**: Analyze your portfolio with a momentum-based rotation strategy.
        -   **Trend Filter**: Adjust weights based on 50-day Moving Average (Customizable weight).
        -   **Relative Strength**: Adjust weights based on 3-month performance vs benchmark (Customizable weight).
        -   **Backtesting**: View historical performance of the strategy vs benchmark.
-   **Premium UI**: Modern, responsive design with a clean interface.

## Prerequisites

-   Python 3.8+


## Installation

### Local Development

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd portfolio-manager
    ```

2.  **Create a virtual environment:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Set up environment variables:**
    Create a `.env` file in the root directory (optional, or set them in your shell):
    ```bash
    export FLASK_APP=run.py
    export SECRET_KEY=your-secret-key
    # Database defaults to local sqlite:///portfolio.db
    ```

5.  **Initialize the database:**
    The app will automatically create the SQLite database tables on the first run.

6.  **Run the application:**
    ```bash
    python run.py
    ```
    Access the app at `http://localhost:8000`.

### Proxmox LXC Deployment

1.  **Create a Python LXC container** (e.g., Ubuntu or Debian).

2.  **Install System Dependencies:**
    Update the package list and install Python, Pip, Virtualenv, and Git:
    ```bash
    apt update && apt install -y python3 python3-pip python3-venv git
    ```

3.  **Clone the Repository:**
    ```bash
    git clone <repository-url>
    cd portfolio-manager
    ```

4.  **Set up the Environment:**
    Create and activate a virtual environment:
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

5.  **Install Python Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

6.  **Configure Environment Variables:**
    Create a `.env` file or export variables directly:
    ```bash
    export FLASK_APP=run.py
    export SECRET_KEY=your-secret-key
    # Database defaults to local sqlite:///portfolio.db
    ```

7.  **Run with Gunicorn (Production):**
    Install Gunicorn and start the server:
    ```bash
    pip install gunicorn
    gunicorn -w 4 -b 0.0.0.0:8000 run:app
    ```

8.  **Access the Application:**
    Open your browser and navigate to `http://<container-ip>:8000`.

9.  **Configure Systemd Service (Optional):**
    To ensure the app starts automatically on boot, create a systemd service file.

    Create the file `/etc/systemd/system/portfolio.service`:
    ```ini
    [Unit]
    Description=Portfolio Manager Gunicorn Service
    After=network.target

    [Service]
    User=root
    WorkingDirectory=/root/portfolio-manager
    Environment="PATH=/root/portfolio-manager/venv/bin"
    Environment="FLASK_APP=run.py"
    Environment="SECRET_KEY=your-secret-key"
    ExecStart=/root/portfolio-manager/venv/bin/gunicorn -w 4 -b 0.0.0.0:8000 run:app

    [Install]
    WantedBy=multi-user.target
    ```
    *Note: Adjust `WorkingDirectory` and `ExecStart` if you cloned the repo elsewhere.*

    Reload systemd, enable the service, and start it:
    ```bash
    systemctl daemon-reload
    systemctl enable portfolio
    systemctl start portfolio
    ```

## Upgrading

To upgrade the application to the latest version without losing your data:

1.  **Pull the latest changes:**
    ```bash
    git pull origin main
    ```

2.  **Update dependencies:**
    ```bash
    source venv/bin/activate
    pip install -r requirements.txt
    ```

3.  **Migrate the database:**
    If new features require database changes (like the benchmark weight persistence), run the migration script:
    ```bash
    python migrate_db.py
    python migrate_weights.py
    ```
    *Note: This script checks for missing columns and adds them safely.*

4.  **Restart the application:**
    ```bash
    # If running locally
    python run.py

    # If running as a service
    systemctl restart portfolio
    ```

## Usage

1.  **Register** a new account.

3.  **Create a Portfolio**:
    -   Click **Create New Portfolio** to start from scratch.
    -   Or click **Create Example Portfolio** to generate a test portfolio with pre-populated holdings (VOO, QQQ, BRK-B, SPMO) to explore the features instantly.
4.  **Add Stocks**: Enter the symbol (e.g., AAPL) and number of units.
5.  **Rebalance**:
    -   Go to the portfolio view.
    -   Click "Rebalance".
    -   Enter your available cash to invest.
    -   Set your target allocation ratios (e.g., 0.6 for 60%).
    -   View the recommended Buy/Sell orders.

## Tech Stack

-   **Backend**: Flask, SQLAlchemy (SQLite)
-   **Frontend**: HTML5, Vanilla CSS, Chart.js
-   **API**: Yahoo Finance
