import streamlit as st
import astropy
from astropy.io import fits
import numpy as np
import gzip
import io
from io import BytesIO
import pandas as pd
from sqlalchemy import create_engine, text, delete, insert, MetaData
from astropy.stats import sigma_clipped_stats as scs
import matplotlib.pyplot as plt
from streamlit_float import *
import json
import streamlit.components.v1 as components

st.set_page_config(page_title="Misclassified", page_icon="❌", layout = "wide")

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
    
if "candid_idx" not in st.session_state:
    st.session_state.candid_idx = 0

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

@st.cache_data
def get_count(incorrect_candids):
    count = len(incorrect_candids)
    return count

@st.cache_data
def get_ra_dec(candid):
    df = pd.read_sql_query(f"""
        SELECT ra, dec from candidates WHERE candid = {candid};""", engine)
    ra = df.ra[0]
    dec = df.dec[0]
    return ra, dec

@st.cache_data
def get_images_from_db(incorrect_candids):
    
    if len(incorrect_candids) > 1:
        incorrect_candids = tuple(incorrect_candids)
    else:
        incorrect_candids = f"('{incorrect_candids[0]}')"
    
    images = pd.read_sql_query(f"""
        SELECT c.candid, c.sci_image, c.ref_image, c.diff_image from cutouts c INNER JOIN (SELECT DISTINCT(candid) from candidates) s ON c.candid = s.candid WHERE c.candid IN {incorrect_candids};""", engine)
    
    sci_images = []
    ref_images = []
    diff_images = []
    candids = []
    
    params_dict = {"sci_vmin": [], "sci_vmax": [], "ref_vmin": [], "ref_vmax": [], "diff_vmin": [], "diff_vmax": []}
    
    for i in range(len(images)):
        sci_image_b = images.sci_image[i]
        ref_image_b = images.ref_image[i]
        diff_image_b = images.diff_image[i]
        candids.append(images.candid[i])
        
        sci_cutout = np.flipud(fits.open(BytesIO(gzip.open(io.BytesIO(sci_image_b), 'rb').read()))[0].data)
        ref_cutout = np.flipud(fits.open(BytesIO(gzip.open(io.BytesIO(ref_image_b), 'rb').read()))[0].data)
        diff_cutout = np.flipud(fits.open(BytesIO(gzip.open(io.BytesIO(diff_image_b), 'rb').read()))[0].data)
        sci_images.append(sci_cutout)
        ref_images.append(ref_cutout)
        diff_images.append(diff_cutout)
    
        sci_mean, sci_median, sci_std = scs(sci_cutout)
        ref_mean, ref_median, ref_std = scs(ref_cutout)
        diff_mean, diff_median, diff_std = scs(diff_cutout)
        
        
        lowp = 1
        highp = 5
        vmin = sci_median - lowp * sci_std
        vmax = sci_median + highp * sci_std
        params_dict["sci_vmin"].append(vmin)
        params_dict["sci_vmax"].append(vmax)
        vmin = ref_median - lowp * ref_std
        vmax = ref_median + highp * ref_std
        params_dict["ref_vmin"].append(vmin)
        params_dict["ref_vmax"].append(vmax)
        vmin = diff_median - lowp * diff_std
        vmax = diff_median + highp * diff_std
        params_dict["diff_vmin"].append(vmin)
        params_dict["diff_vmax"].append(vmax)

    return candids, sci_images, ref_images, diff_images, params_dict
 
def plot_triplet(i, candid, sci, ref, diff):
    fig, ax = plt.subplots(1, 3, figsize = (10, 3))
    ax = ax.flatten()

    ax[0].imshow(sci, cmap='gray', interpolation = 'nearest', aspect = 'equal', vmin = params["sci_vmin"][i], vmax = params["sci_vmax"][i])
    ax[1].imshow(ref, cmap='gray', interpolation = 'nearest', aspect = 'equal', vmin = params["ref_vmin"][i], vmax = params["ref_vmax"][i])
    ax[2].imshow(diff, cmap='gray', interpolation = 'nearest', aspect = 'equal', vmin = params["diff_vmin"][i], vmax = params["diff_vmax"][i])
    # Add a title and axis labels (optional)
    fig.suptitle(f'cand: {candid}', x = 0.5, y = 1.05, fontsize = 16)
    ax[0].set_title('sci', fontsize = 12)
    ax[1].set_title('ref', fontsize = 12)
    ax[2].set_title('diff', fontsize = 12)
    
    for a in ax:
        a.axis('off')
    plt.subplots_adjust(left=None, bottom=None, right=None, top=None, wspace=None, hspace=None)
    
    return fig

# try:
    # record_df = pd.read_csv("log.csv", dtype = str)
    # incorrect_candids = record_df["candid"].tolist()
    
    # dup_candids, source1, source2 = np.loadtxt("duplicates.txt", dtype = str, delimiter=",", unpack = True, ndmin = 1)
        
    # filtered_cands = list(set(incorrect_candids).difference(dup_candids))

if st.session_state.get("candids") is None: # if form is not submitted
    st.markdown('#')
    st.markdown('###')
    c1 = st.container()
    with c1:
        st.markdown("Please upload list of candids (with brackets) separated by commas.")
        textbox = st.text_area("candids")
        submit_button = st.button("Submit")
    if submit_button: 
        try:
            textbox_list = json.loads(str(textbox))
            candid_csv = pd.DataFrame(textbox_list, columns = ["candid"])
            cands = candid_csv["candid"]
            st.session_state["candids"] = cands
            candids, sci, ref, diff, params = get_images_from_db(cands)
            st.session_state["candid_idx"] = 0
        except:
            st.write("Format of text is incorrect. Please try again.")
            st.stop()
    else:
        st.write("No misclassified images found.")
        st.stop()
else:
    candids = st.session_state["candids"]
    candids, sci, ref, diff, params = get_images_from_db(candids)
    st.session_state["len_candids"] = len(candids)
# except:
#     st.write("No misclassified images found.")
#     st.stop()

# keys = ["incorrect"]

# for key in keys:
#     if key not in st.session_state:
#         st.session_state[key] = []

if 'scroll_to_top' not in st.session_state:
    st.session_state.scroll_to_top = False

if st.session_state.scroll_to_top:
    scroll_to_here(10, key='top')  # Scroll to the top of the page, 0 means instantly, but you can add a delay (im milliseconds)
    st.session_state.scroll_to_top = False  # Reset the state after scrolling

def scroll():
    st.session_state.scroll_to_top = True
    
img_ppage = 50
page_num = len(candids) // img_ppage

page_list = np.arange(1, page_num+2)


container = st.container()

with container:
    col1, col2 = st.columns([0.7, 0.3])
    
    with col1:
        st.text(f"Showing {st.session_state.candid_idx+1}/{len(candids)}")
    
    with col2:
        st.text("")
        st.button("Clear candids", on_click = lambda: st.session_state.pop("candids"))


def button_click(candid):
    if candid not in st.session_state["incorrect"]:
        st.session_state["incorrect"].append(candid)
        record_df.loc[len(record_df)] = [candid, "incorrect"]
        record_df.to_csv("log.csv", index = False)


def delete_candidate(engine, source, candid, write = False):
    with engine.connect() as con:
        try:
            table = metadata.tables.get(source)
            query = delete(table).where(table.c.candid == str(candid))
            
            con.execute(query)
            con.commit()
            st.toast(f"Deleted candidate {candid} from {source}.")
        except:
            st.toast(f"Could not delete candidate {candid} from {source}.")
            st.stop()
    if write:
        record_df.drop(index = record_df.loc[record_df["candid"] == str(candid)].index, inplace = True)
        record_df.to_csv("log.csv", index = False)
    
def insert_candidate(engine, source, candid):
    
    max_id = get_id(engine, source)
    correct_col = f"{source}id"
    data = ({correct_col: max_id+1, "candid": str(candid)})
    
    with engine.connect() as con:
        try:
            table = metadata.tables.get(source)
            query = insert(table).values(**data) #INSERT INTO reals (realsid, candid) VALUES (%(realsid)s, %(candid)s)
            # st.toast(str(query.compile(engine, compile_kwargs={"literal_binds": True})))
            con.execute(query)
            con.commit()
        except:
            st.toast(f"Could not insert candidate {candid} into {source}.")
            st.stop()


def locate_candidate(engine, candid):
    with engine.connect() as con:
        try:
            query = f"(SELECT 'reals' AS table_name, * FROM reals WHERE candid = {candid}) UNION (SELECT 'artifact' AS table_name, * from artifact WHERE candid = {candid}) UNION (SELECT 'echo' AS table_name, * from echo WHERE candid = {candid}) UNION (SELECT 'highpm' AS table_name, * from highpm WHERE candid = {candid})"
            result = con.execute(text(query))
            row = result.fetchall()
            source = row[0][0]
            candid = row[0][2]
            return source, candid
        except:
            # st.toast(f"Could not locate candidate {candid}.")
            # st.stop()
            return [None]
    

def get_id(engine, source):
    with engine.connect() as con:
        try:
            query = f"SELECT MAX({source}id) FROM {source}"
            result = con.execute(text(query))
            id = result.fetchone()[0]
        except:
            st.toast(f"Could not get ID for {source}.")
            st.stop()
    return(id)
    
    
def change_class(engine, candid, old_source, new_source):
    
    # if old_source == new_source: # if the candidate is already in the new source, then do nothing
    #     st.toast(f"Candidate {candid} is already classified as {new_source}. Removing from page.")
    #     record_df.drop(index = record_df.loc[record_df["candid"] == str(candid)].index, inplace = True)
    #     record_df.to_csv("log.csv", index = False)
    # else:
    if old_source:
        delete_candidate(engine, old_source, candid) # delete the candidate from the original source
    
    with engine.connect() as con:
        try:
            insert_candidate(engine, new_source, candid)
            st.toast(f"Reclassified candidate {candid} as {new_source}.")
            # record_df.drop(index = (record_df.loc[record_df["candid"] == str(candid)].index), inplace = True)
            # record_df.to_csv("log.csv", index = False)
        except:
            st.toast(f"Could not reclassify candidate {candid} as {new_source}.")
            st.stop()

# def find_label(candid, pred_csv = pred_csv):
#     # st.toast(type(candid))
#     cand_row = pred_csv[pred_csv["candid"] == candid]
#     pred = cand_row["Predicted_Label"].values[0]
#     true = cand_row["True_Label"].values[0]
#     classes = ["artifact", "reals", "highpm", "echo"]
    
#     return(classes[pred], classes[true])



def page_load(i, candids):
     
    current_source = locate_candidate(engine, candids)[0]
    
    if current_source:
        st.header(f"{candids} - classified as {current_source}")
    else:
        st.header(f"{candids} - not classified")
    
    fig, ax = plt.subplots(1, 3, figsize = (10, 3))
    ax = ax.flatten()

    ax[0].imshow(sci[i], cmap='gray', interpolation = 'nearest', aspect = 'equal', vmin = params["sci_vmin"][i], vmax = params["sci_vmax"][i])
    ax[1].imshow(ref[i], cmap='gray', interpolation = 'nearest', aspect = 'equal', vmin = params["ref_vmin"][i], vmax = params["ref_vmax"][i])
    ax[2].imshow(diff[i], cmap='gray', interpolation = 'nearest', aspect = 'equal', vmin = params["diff_vmin"][i], vmax = params["diff_vmax"][i])
    # Add a title and axis labels (optional)
    fig.suptitle(f'cand: {candids}', x = 0.5, y = 1.05, fontsize = 16)
    ax[0].set_title('sci', fontsize = 12)
    ax[1].set_title('ref', fontsize = 12)
    ax[2].set_title('diff', fontsize = 12)
    
    for a in ax:
        a.axis('off')
    plt.subplots_adjust(left=None, bottom=None, right=None, top=None, wspace=None, hspace=None)
    
    st.pyplot(fig)
    col1, col2, col3, col4, col5 = st.columns([0.2, 0.2, 0.2, 0.2, 0.2])
    with col1:
        if st.button("Artifact", key = i+1):
            # st.toast("artifact button")
            change_class(engine, candids, current_source, "artifact")
            # st.rerun()
    with col2:
        if st.button("Real", key = i+1e5):
            change_class(engine, candids, current_source, "reals")
    with col3:
        if st.button("Echo", key = i+2e5):
            change_class(engine, candids, current_source, "echo")
    with col4:
        if st.button("High PM", key = i+3e5):
            change_class(engine, candids, current_source, "highpm")
    with col5:
        if st.button("Delete", key = i+4e5):
            delete_candidate(engine, current_source, candids, write = False)
    ra, dec = get_ra_dec(candids)
    byworlds = f"http://byw.tools/wiseview#ra={ra}&dec={dec}&size=176&band=2&speed=234.62&minbright=-2.3497&maxbright=963.1413&window=0.09958&diff_window=1&linear=1&color=&zoom=10&border=0&gaia=0&invert=0&maxdyr=0&scandir=0&neowise=0&diff=0&outer_epochs=0&unique_window=1&smooth_scan=0&shift=0&pmra=0&pmdec=0&synth_a=0&synth_a_sub=0&synth_a_ra=&synth_a_dec=&synth_a_w1=&synth_a_w2=&synth_a_pmra=0&synth_a_pmdec=0&synth_a_mjd=&synth_b=0&synth_b_sub=0&synth_b_ra=&synth_b_dec=&synth_b_w1=&synth_b_w2=&synth_b_pmra=0&synth_b_pmdec=0&synth_b_mjd="
    st.link_button("See in BYW", url = byworlds)
    st.markdown("### Backyard Worlds")
    components.iframe(byworlds, width = 1000, height=700)


st.title("Misclassified")

def next_plot():
    st.session_state["candid_idx"] = min(st.session_state["candid_idx"] + 1, len(candids))
    
def previous_plot():
    st.session_state["candid_idx"] = max(0, st.session_state["candid_idx"] - 1)
    
if candids:
    prev, nxt = st.columns([0.5, 0.5])
    with prev:
        previous_page = st.button("Previous", key = "previous_page", use_container_width=True, on_click = previous_plot)
    with nxt:
        next_page = st.button("Next", key = "next_page", use_container_width=True, on_click = next_plot)

    page_load(st.session_state["candid_idx"], candids[st.session_state["candid_idx"]])
    
