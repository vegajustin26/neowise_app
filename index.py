import streamlit as st

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if st.session_state.logged_in:
    pages = {
        "Quick Start": [
            st.Page("./pages/quickstart.py", title = "Tutorial"),
        ],
        "Review": [
            st.Page("./pages/artifact.py", title = "Artifact"),
            st.Page("./pages/echo.py", title = "Echo"),
            st.Page("./pages/highpm.py", title = "High Proper Motion"),
            st.Page("./pages/reals.py", title = "Reals"),
            st.Page("./pages/stats.py", title = "Classified Stats"),
        ],
        "Classify": [
            st.Page("./pages/hostless.py", title = "Hostless Scan"),
            st.Page("./pages/misclassify.py", title = "Misclassified (Manually Selected)"),
            st.Page("./pages/duplicates.py", title = "Duplicates (across Multiple Classes)"),
        ]
    }

if st.session_state.logged_in:
    if st.session_state.username == "admin":
        pg = st.navigation(pages)    
    else:
        del pages["Review"][-1]
        del pages["Classify"][1:3]
        pg = st.navigation(pages)
else:
    login_page = st.Page("./pages/login.py", title = "Login")
    pg = st.navigation({"Login": [login_page]})

pg.run()