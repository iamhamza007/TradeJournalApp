from supabase import create_client, Client
import streamlit as st

def get_supabase_client() -> Client:
    url = "https://obzztuakskphspfjouvv.supabase.co"
    key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9ienp0dWFrc2twaHNwZmpvdXZ2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTM2OTIwNjgsImV4cCI6MjA2OTI2ODA2OH0.kFZsRSdyF9aQ26_zOTKRpZCnz3dn5vqw5MqtoJPhwL0"
    supabase = create_client(url, key)
    # Restore session if available
    if "access_token" in st.session_state:
        supabase.auth.set_session(st.session_state.access_token)
    return supabase