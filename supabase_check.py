import streamlit as st
from supabase import create_client

st.set_page_config(page_title="Supabase connection check")
st.title("Supabase sign-in check")

try:
    supabase = create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_PUBLISHABLE_KEY"],
    )
except Exception as error:
    st.error(f"Supabase settings error: {error}")
    st.stop()

with st.form("login"):
    email = st.text_input("Test user email")
    password = st.text_input("Test user password", type="password")
    submitted = st.form_submit_button("Sign in and check role")

if submitted:
    try:
        result = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password,
        })

        user = result.user
        if user is None:
            st.error("Sign-in returned no user. Check the email and password.")
            st.stop()

        response = (
            supabase.table("profiles")
            .select("display_name, role")
            .eq("id", user.id)
            .single()
            .execute()
        )

        st.success("Supabase sign-in and profile access worked.")
        st.write("Display name:", response.data["display_name"])
        st.write("Dashboard role:", response.data["role"])

    except Exception as error:
        st.error(f"Sign-in or profile lookup failed: {error}")