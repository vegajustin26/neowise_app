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
            st.Page("./pages/viz.py", title = "Visualization"),
        ],
        "Classify": [
            st.Page("./pages/hostless.py", title = "Hostless Scan"),
            st.Page("./pages/misclassify.py", title = "Misclassified (Manual Input)"),
            st.Page("./pages/misclassify_model.py", title = "Misclassified (Model)"),
            st.Page("./pages/duplicates.py", title = "Duplicates (across Multiple Classes)"),
            st.Page("./pages/single_search.py", title = "Single Search"),
        ]
    }

if st.session_state.logged_in:
    if st.session_state.username == "admin":
        pg = st.navigation(pages)
    elif st.session_state.username == "guest":
        del pages["Review"][-1]   
        del pages["Classify"][0:4]
        pg = st.navigation(pages)
    elif st.session_state.username == "visitor":
        del pages["Review"][-1]
        del pages["Classify"][1:4]
        pg = st.navigation(pages)
else:
    login_page = st.Page("./pages/login.py", title = "Login")
    pg = st.navigation({"Login": [login_page]})

pg.run()