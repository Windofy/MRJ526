# i_Windofy — Mr. Jealousy Interior Intelligence Tool

AI-powered interior visualization tool that lets customers see how blinds look in their own space before ordering.

## Architecture

```
i_Windofy/
├── app.py              ← Flask entrypoint (routes: /, /analyze, /render, /preview)
├── core.py             ← Business logic, product catalog, system constants
├── backend/            ← AI service modules
│   ├── analyse_claude.py    ← Claude vision analysis pipeline
│   ├── render_gemini.py     ← Gemini image generation
│   ├── render_blind.py      ← Procedural blind renderer
│   ├── sam2_segment.py      ← SAM2 window segmentation
│   ├── warp_blind.py        ← Perspective warp + compositing
│   ├── utils.py             ← Upload helpers (Supabase + local)
│   └── refs.py              ← Reference image generator
├── frontend/           ← Static UI served by Flask
│   ├── index.html
│   ├── script.js
│   ├── style.css
│   └── assets/
│       ├── fonts/      ← MrGintoNord + Poppins (.woff2)
│       ├── images/     ← UI images (logo, icons)
│       ├── icons/      ← Social media icons
│       └── ref/        ← Generated reference images (auto-created)
├── data/
│   ├── catalogus.json  ← Product catalog (colors, materials, sample URLs)
│   └── uploads/        ← Runtime user uploads (gitignored)
├── models/             ← SAM2 model checkpoint (~898 MB, gitignored)
├── design/             ← Figma design references (18 PNG exports)
├── scripts/            ← Development & setup scripts
│   ├── setup_sam2.py   ← SAM2 model installer
│   ├── test_keys.py    ← API key validator
│   ├── start.bat       ← Windows quick-start
│   └── start.sh        ← Unix quick-start
└── Dockerfile          ← Cloud Run deployment
```

## Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Python 3.12, Flask, Gunicorn |
| **AI Vision** | Claude (Anthropic) — window analysis |
| **AI Render** | Gemini (Google) — interior visualization |
| **Segmentation** | SAM2 (Meta) — window detection |
| **Frontend** | Vanilla HTML/CSS/JS, MrGintoNord + Poppins fonts |
| **Storage** | Supabase (remote), local filesystem (fallback) |
| **Deployment** | Docker, Google Cloud Run |

## Quick Start

### Prerequisites
- Python 3.10+
- API keys: `ANTHROPIC_API_KEY`, `GEMINI_API_KEY` (in `.env`)

### Setup
```bash
# Clone and enter project
cd i_Windofy

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt

# Setup SAM2 model (~2.5 GB download)
python scripts/setup_sam2.py

# Validate API keys
python scripts/test_keys.py

# Run the app
python app.py
```

Open http://localhost:5000 in your browser.

## Environment Variables

| Variable | Description |
|---|---|
| `ANTHROPIC_API_KEY` | Claude API key for vision analysis |
| `GEMINI_API_KEY` | Gemini API key for image generation |
| `SUPABASE_URL` | Supabase project URL (optional) |
| `SUPABASE_KEY` | Supabase anon key (optional) |

## Deployment

The app deploys to Google Cloud Run:

```bash
gcloud run deploy i-windofy \
  --source . \
  --region europe-west1 \
  --allow-unauthenticated
```

## License

Proprietary — Mr. Jealousy B.V.
