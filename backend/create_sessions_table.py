"""
create_sessions_table.py  —  run once to create the sessions table in Supabase.
Usage:  python create_sessions_table.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

from supabase import create_client

url  = os.environ['SUPABASE_URL']
key  = os.environ['SUPABASE_SERVICE_KEY']
c    = create_client(url, key)

# We use PostgREST RPC to run raw SQL via a helper function.
# Since Supabase doesn't expose a raw SQL endpoint via the REST API,
# we create the table by upserting with all required columns — this fails
# gracefully if the table already exists.
# Instead, we use the Supabase Python SDK's `storage` feature to probe,
# then fall back to manual SQL via the Supabase Management REST API.

import httpx, json

PROJECT_REF = url.replace("https://", "").split(".")[0]
MGMT_URL    = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query"

# The management API needs a Supabase personal access token (PAT), not the service key.
# We'll use the service_role JWT directly against the pg-meta endpoint instead.
PGMETA_URL = f"https://{PROJECT_REF}.supabase.co/pg/v1/query"

SQL = """
CREATE TABLE IF NOT EXISTS public.sessions (
    id                 TEXT PRIMARY KEY,
    status             TEXT DEFAULT 'uploading',
    phase              INTEGER DEFAULT 1,
    step               INTEGER DEFAULT 0,
    image_url          TEXT,
    render_url         TEXT,
    analysis           JSONB,
    render_instruction JSONB,
    error              TEXT,
    render_count       INTEGER DEFAULT 0,
    image_local        TEXT,
    created_at         TIMESTAMPTZ DEFAULT now(),
    updated_at         TIMESTAMPTZ DEFAULT now()
);
ALTER TABLE public.sessions ENABLE ROW LEVEL SECURITY;
CREATE POLICY IF NOT EXISTS sessions_all ON public.sessions USING (true) WITH CHECK (true);
"""

print("Attempting to create sessions table via pg-meta...")
r = httpx.post(
    PGMETA_URL,
    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    json={"query": SQL},
    timeout=20,
)
print(f"  pg-meta status: {r.status_code}")
if r.status_code == 200:
    print("  ✅ Table created successfully!")
    sys.exit(0)

print(f"  pg-meta failed: {r.text[:200]}")

# Fallback: test if the table already exists by attempting an insert + select
print("\nFallback: testing if sessions table exists via upsert probe...")
try:
    test_id = "__probe_delete_me__"
    c.table("sessions").upsert({"id": test_id, "status": "probe"}).execute()
    c.table("sessions").delete().eq("id", test_id).execute()
    print("  ✅ Table already exists and is accessible!")
    sys.exit(0)
except Exception as e:
    print(f"  ❌ Table does not exist: {e}")
    print()
    print("  ⚠️  Please create the table manually in the Supabase SQL Editor:")
    print("     https://supabase.com/dashboard/project/mqxlclxcqujpymylbqdy/sql")
    print()
    print("  SQL to run:")
    print(SQL)
    sys.exit(1)
