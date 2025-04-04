import streamlit as st
import astropy
from astropy.io import fits
import pandas as pd
from sqlalchemy import create_engine, delete, MetaData, text
import matplotlib.pyplot as plt
import numpy as np

st.set_page_config(page_title="Stats", page_icon="📊", layout = "wide")

## Check if the user is logged in
login_page = st.Page("./pages/login.py", title = "Login")
authenticator = st.session_state.authenticator

st.sidebar.markdown(f"**Logged in as:** {st.session_state.username}")
authenticator.logout("Logout", "sidebar")

if st.session_state.get('authentication_status'):
    st.session_state.logged_in = True

if st.session_state.get('logout'):
    st.session_state.logged_in = False
    st.session_state.logout = True
    st.session_state.authentication_status = None
    st.switch_page(login_page)


@st.cache_resource
def init_connection():
    db_user = st.secrets.wise_db.username
    db_password = st.secrets.wise_db.password
    db_host = st.secrets.wise_db.host
    db_port = st.secrets.wise_db.port
    db_name = st.secrets.wise_db.database

    # Create SQLAlchemy engine
    engine = create_engine(f'postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}')

    return engine


engine = init_connection()
metadata = MetaData()
metadata.reflect(bind=engine)

def get_total_counts():
    with engine.connect() as conn:
        query = """
            SELECT (SELECT COUNT(DISTINCT(candid)) FROM reals) AS count1, (SELECT COUNT(DISTINCT(candid)) FROM highpm) AS count2, (SELECT COUNT(DISTINCT(candid)) FROM echo) AS count3, (SELECT COUNT(DISTINCT(candid)) FROM artifact) AS count4;"""
        result = conn.execute(text(query))
        record = result.fetchone()
        num_artifacts = record[3]
        num_reals = record[0]
        num_highpm = record[1]
        num_echo = record[2]
        total = num_artifacts + num_reals + num_highpm + num_echo
    
    counts = {"artifact": num_artifacts, "reals": num_reals, "highpm": num_highpm, "echo": num_echo}
    return counts

def get_dup_counts(table):
    with engine.connect() as conn:
        query = """
            SELECT (SELECT COUNT(candid) FROM reals) AS count1, (SELECT COUNT(candid) FROM highpm) AS count2, (SELECT COUNT(candid) FROM echo) AS count3, (SELECT COUNT(candid) FROM artifact) AS count4;"""
        result = conn.execute(text(query))
        record = result.fetchone()
        
        unique_counts = get_total_counts()
        num_artifacts = record[3] - unique_counts["artifact"]
        num_reals = record[0] - unique_counts["reals"]
        num_highpm = record[1] - unique_counts["highpm"]
        num_echo = record[2] - unique_counts["echo"]
        
        dup_counts = {"artifact": num_artifacts, "reals": num_reals, "highpm": num_highpm, "echo": num_echo}
    return dup_counts


st.write("# Stats")
st.write("## Total Counts")
counts = get_total_counts()
counts["total"] = sum(counts.values())
df = pd.DataFrame.from_dict(counts, orient='index', columns=['count'])
df['percentage'] = [f"{(count / counts['total']) * 100:.2f}%" for count in counts.values()]
st.dataframe(df, width = 400)

st.write("## Duplicate Counts (in each class)")
dup_counts = get_dup_counts("artifact")
dup_df = pd.DataFrame.from_dict(dup_counts, orient='index', columns=['count'])
st.dataframe(dup_df, width = 200)

def delete_duplicates(table):
    with engine.connect() as conn:
        delete_query = f"""DELETE FROM {table}
            WHERE candid IN (
                SELECT candid
                FROM {table}
                GROUP BY candid
                HAVING COUNT(*) > 1
            ) AND {table}id NOT IN (
                SELECT MIN({table}id)
                FROM {table}
                GROUP BY candid
                HAVING COUNT(*) > 1
            );"""
        conn.execute(text(delete_query))
        conn.commit()
        st.success(f"Duplicates deleted from {table}")

def back_up_tables_pandas(table):
    with engine.connect() as conn:
        query = f"SELECT * FROM {table};"
        df = pd.read_sql(query, conn)
        df.to_csv(f"{table}_backup.csv", index=False)
        st.success(f"Backed up {table} to {table}_backup.csv")

if st.button(f"Back Up DB"):
    for table in ["artifact", "reals", "highpm", "echo"]:
        back_up_tables_pandas(table)

if st.button("Delete Duplicates"):
    st.toast("Duplicates deleted")
    delete_duplicates("artifact")
    delete_duplicates("reals")
    delete_duplicates("highpm")
    delete_duplicates("echo")
