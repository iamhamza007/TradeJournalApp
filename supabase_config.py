from supabase import create_client, Client
import streamlit as st

def get_supabase_client() -> Client:
    url = "https://obzztuakskphspfjouvv.supabase.co"
    key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9ienp0dWFrc2twaHNwZmpvdXZ2Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1MzY5MjA2OCwiZXhwIjoyMDY5MjY4MDY4fQ.xSKPwny5b6DXxKNBtWSZ1JJQta3aqdNYfnvTI4xQ0p0"
    supabase = create_client(url, key)
    # Restore session if available
    if "access_token" in st.session_state:
        supabase.auth.set_session(st.session_state.access_token)
    return supabase
