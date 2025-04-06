import streamlit as st
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader
import numpy as np

with open('./credentials.yaml') as file:
    config = yaml.load(file, Loader=SafeLoader)

authenticator = stauth.Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days']
)

st.session_state['authenticator'] = authenticator

# Display login form
authenticator.login()
index_pg = st.Page("./index.py", title = "Tutorial")

if st.session_state.authentication_status is True:
    name = st.session_state.name
    st.success(f"Welcome {name}!")
    st.session_state.logged_in = True
    st.session_state.logout = False
    st.switch_page(index_pg)
    authenticator.logout("Logout", "main")
elif st.session_state.authentication_status is False:
    st.error("Incorrect username or password")
else:
    text = """
    To demo the app, use 'visitor' as both the username and password.\n
    If you want to take part in classifying images, contact me (Justin) for an account.
    """
    st.info(text)
