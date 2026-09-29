# Deployment Guide (ai-sop)

Deployed to Scaleway as `ai-sop`.

## 1. Prerequisites & Environment Setup

The application runs with Python 3.11+ (recommended conda environment: `dcr`).

```bash
# Clone and enter directory
cd /path/to/DCR.AI

# Activate environment
conda activate dcr

# Install dependencies
pip install -r requirements.txt
pip install -r faq_search/requirements.txt
# Requires: flask waitress requests sentence-transformers numpy torch transformers
```

## 2. Environment Variables (`.env`)

Configure the following variables in `.env`:
```ini
# DCR Portal API Credentials
API_KEY=your_dcr_api_key
TOKEN=your_dcr_token
ROOT_URL=https://api.dcr.design

# Local Semantic Search
USE_LOCAL_RETRIEVER=1
FAQ_MATCH_MODEL=Qwen/Qwen3-Embedding-0.6B

# Optional OpenAI fallback / form interpretation
OPENAI_API_KEY=your_openai_key
```

## 3. Pre-Deployment Data & Embedding Build

Ensure the knowledge base and vectors are pre-computed before starting the service:
```bash
# 1. Build authoritative Q&A records (43 records reconciled from Vejledning nr 9577)
python faq_search/build_faq_data.py

# 2. Compute 1024-dim sentence embeddings (saved to faq_search/data/faq_embeddings.npy)
python faq_search/embed_faq_data.py
```

## 4. Graph Deployment in DCR Portal

1. Import `xml graphs/SU_handicaptillaeg_FAQ_Application_Lean.xml` into your DCR Portal organization as a new graph.
2. Note the generated Graph ID (e.g. `2012794` or similar).
3. If using dynamic effects with external REST endpoints:
   - Configure the REST endpoint in DCR Portal **Effect Admin** (Organization Registry).
   - Do NOT commit sensitive URLs or API keys into XML files.

## 5. Verification & Test Suite

Before starting the server, run the full test suite:
```bash
python -m unittest discover -s tests
```
All 82 tests must pass (`OK`).

## 6. Running the Production Server

Start the Waitress server via `app.py`:
```bash
python app.py
```
- Server listens on port `8080`.
- The root route `/` automatically redirects visitors to `/demo`.
