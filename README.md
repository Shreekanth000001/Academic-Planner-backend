# Academic Planner - Core API & AI Engine ⚙️

> **Presentation Layer:** The Next.js web client for this system can be found [here]([Insert Frontend Repo Link Here]).

This repository houses the backend compute engine, vector retrieval system, and asynchronous AI pipeline for the Academic Planner platform. It is designed as a decoupled, zero-trust REST API that handles heavy LLM workloads out-of-band while maintaining eventual consistency with the frontend client.

![System Architecture]([Insert Your Architecture Image URL Here])

## 🛠 Tech Stack

*   **Framework:** FastAPI (Python 3.12)
*   **Database:** PostgreSQL (Supabase) + `pgvector` + SQLAlchemy 2.0 (Async)
*   **Background Compute:** Redis + ARQ (Async Python Queue)
*   **AI/LLM:** Azure OpenAI (`gpt-4o-mini`), `text-embedding-3-small`, PyMuPDF (`fitz`)
*   **Auth & FinOps:** Clerk (Identity), Stripe (Billing), PyJWT
*   **DevOps:** Bare-Metal Azure Ubuntu VM, Nginx (Reverse Proxy), Systemd, GitHub Actions (CI/CD)

---

## 🏛 Core Architecture & System Design

This system was built to handle long-running LLM tasks without blocking the main HTTP thread, ensuring a highly responsive user experience and strict multi-tenant data isolation.

### 1. Asynchronous AI Pipeline & State Hydration
PDF parsing and LLM data extraction routinely take 30-45 seconds. To prevent UI blocking and gateway timeouts, the ingestion pipeline is completely decoupled.
*   **Eventual Consistency:** `POST /upload` calculates an SHA-256 hash for deduplication, drops the file into a Supabase S3 bucket, queues an ARQ task via Redis, and instantly returns a `202 Accepted`.
*   **State Machine:** The background worker explicitly broadcasts state transitions (`PENDING` -> `PROCESSING` -> `COMPLETED`/`FAILED`) to the PostgreSQL database, which the Next.js client polls to safely hydrate its UI state.

### 2. Vector Retrieval & Conversational RAG
The platform features a fully conversational Retrieval-Augmented Generation (RAG) chat system.
*   **Ingestion:** Syllabi are chunked and embedded using `text-embedding-3-small`, then stored in Postgres using the `pgvector` extension.
*   **Retrieval:** When a user queries the document, the system utilizes a **Routing LLM** to rewrite the chat history into a standalone contextual question. It then performs a mathematical Cosine-Similarity search (`<=>`) via `asyncpg` to inject the most relevant text chunks into the final prompt.

### 3. Distributed Ledger & FinOps
Billing and Authentication are handled via a decoupled, event-driven webhook architecture.
*   **Zero-Trust API:** FastAPI acts as a Resource Server, performing local CPU-bound cryptographic verification of Clerk JWTs on every request to extract the user's identity without expensive database lookups.
*   **Asynchronous Billing:** Stripe Checkouts are tracked via metadata injection (`client_reference_id`). Upon successful payment, Stripe fires a cryptographically signed webhook to the backend, which updates the local PostgreSQL ledger. 
*   **Integer Scaling:** To avoid IEEE 754 floating-point precision errors, all billing logic uses integer scaling (e.g., 1000 credits = $5.00), protected by strict FastAPI middleware guardrails.

### 4. Bare-Metal DevOps & CI/CD
This backend operates on a bare-metal Linux environment to ensure unrestricted access to compute resources for Python-heavy C++ dependencies (like PyMuPDF).
*   **Infrastructure:** Deployed on an Azure Ubuntu VM (x64) utilizing custom Swap File partitioning to prevent OOM panics during deployment.
*   **Ingress & Daemons:** Traffic is caught by Nginx on Port 80/443, secured via Let's Encrypt (Certbot) TLS termination, and reverse-proxied to Uvicorn running via `systemd` daemons.
*   **Automation:** A GitHub Actions CI/CD pipeline securely SSHs into the server, updates dependencies, and restarts the daemons on every push to the `main` branch. A daily Linux `cron` job purges stale PDF files from the S3 bucket to minimize cloud storage bloat.

---

## 💻 Local Development Setup

### 1. Prerequisites
* Python 3.12+
* A local Redis server running on Port `6379` (`brew install redis` or `sudo apt install redis-server`)

### 2. Environment Variables
Create a `.env` file in the root directory of the backend:

```env
SUPABASE_URL="https://your-url.supabase.co"
SUPABASE_SERVICE_KEY="eyJ..."
STRIPE_SECRET_KEY="sk_test_..."
STRIPE_PRICE_ID="price_..."
STRIPE_WEBHOOK_SECRET="whsec_..."
CLERK_WEBHOOK_SECRET="whsec_..."
GITHUB_PAT_TOKEN="ghp_..."
```

### 3. Installation
Set up your Python virtual environment and install the dependencies.

```bash
# 1. Create and activate the virtual environment
python3 -m venv venv
source venv/bin/activate

# 2. Install required packages
pip install -r requirements.txt
```

### 4. Running the Services
Because the AI worker and the HTTP server are decoupled, you must run them in two separate terminal windows. Make sure your virtual environment is activated in both!

**Terminal 1: The API Server**
```bash
uvicorn main:app --reload --port 8000
```

**Terminal 2: The ARQ Background Worker**
```bash
arq worker.WorkerSettings
```

Once running, the interactive Swagger API documentation will be available at `http://127.0.0.1:8000/docs`.