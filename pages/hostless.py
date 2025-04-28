import streamlit as st
import astropy
from astropy.io import fits
import numpy as np
import gzip
import io
from io import BytesIO
import pandas as pd
from sqlalchemy import create_engine, text, insert, MetaData
from astropy.stats import sigma_clipped_stats as scs
import matplotlib.pyplot as plt
from streamlit_float import *


st.set_page_config(page_title="Hostless", page_icon="🌌", layout = "wide")

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



st.write("#")
st.markdown("# Hostless")

# page_load(page)

with st.form("my_form"):
    st.write("Search params:")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        scanep = st.text_input("Epoch ID (0-17)", value = 8, key = "scanep")
    with col2:
        gallimlow = st.text_input("Galactic Latitude (degrees)", value = 0, key = "gallimlow")
    with col3:
        gallimhigh = st.text_input("Galactic Latitude 2", value = 90, key = "gallimhigh", label_visibility="hidden")
    with col4:
        candlim = st.text_input("Candidate limit", value = 100, key = "candlim")
    st.form_submit_button()

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
def get_count(candids):
    count = len(candids)
    return count

@st.cache_data
def get_ra_dec(candid):
    df = pd.read_sql_query(f"""
        SELECT ra, dec from candidates WHERE candid = {candid};""", engine)
    ra = df.ra[0]
    dec = df.dec[0]
    return ra, dec

@st.cache_data
def hostless_candids(scanep, gallimlow, gallimhigh, candlim):
    
    scanep = int(scanep)
    rbscorelow = 0.5
    rbscorehigh = 1.0
    nmatches = 2
    scorrpeak = 10
    gallimlow = float(gallimlow)
    gallimhigh = float(gallimhigh)
    agelowlim = 10.0
    agehighlim = 400.0
    hlwdist = 3 # closest WISE source distance
    brmaglim = 7.0 # reject if WISE source is brighter than this
    brdistlim = 10 # within this many arcseconds
    candlim = int(candlim)
    
    query = f"SELECT candid FROM candidates cand INNER JOIN fields f on f.field = cand.field WHERE abs(f.gallat) >= {gallimlow:.2f} and abs(f.gallat) < {gallimhigh:.2f} AND epochid = {scanep} AND rbscore >= {rbscorelow} AND rbscore <= {rbscorehigh} AND nmatches >= {nmatches} AND scorr_peak >= {scorrpeak} AND ispos = 1 AND mjd - firstdet > {agelowlim} AND mjd - firstdet < {agehighlim} AND wdist1 > {hlwdist} AND wdist2 > {hlwdist} AND wdist3 > {hlwdist} AND distnearbrstar > {brdistlim} AND (wdist1 > {brdistlim} OR w1mag1 > {brmaglim}) AND (wdist2 > {brdistlim} OR w1mag2 > {brmaglim}) AND (wdist3 > {brdistlim} OR w1mag3 > {brmaglim}) ORDER BY rbscore DESC OFFSET 0 LIMIT {candlim};"
    
    with engine.connect() as con:
        try:
            result = con.execute(text(query))
            candids = [i for candid in result.fetchall() for i in candid]
        except:
            st.toast(f"Could not get candidates.")
            st.stop()

    return candids

def get_images_from_db(_candids):
    
    if len(_candids) > 1:
        _candids = tuple(_candids)
    else:
        _candids = f"('{_candids[0]}')"
    
    images = pd.read_sql_query(f"""
        SELECT c.candid, c.sci_image, c.ref_image, c.diff_image from cutouts c INNER JOIN (SELECT DISTINCT(candid) from candidates) s ON c.candid = s.candid WHERE c.candid IN {_candids};""", engine)
    
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

@st.cache_data
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


def insert_candidate(_engine, source, candid):
    
    max_id = get_id(_engine, source)
    correct_col = f"{source}id"
    data = ({correct_col: max_id+1, "candid": str(candid)})
    if st.session_state.username == "visitor":
        st.toast(f"Classified {candid} as {source}.")
    else:    
        if candid in all_classified(_engine):
            st.toast(f"Candidate {candid} is already classified.")
        else:
            with _engine.connect() as con:
                try:
                    table = metadata.tables.get(source)
                    query = insert(table).values(**data) #INSERT INTO reals (realsid, candid) VALUES (%(realsid)s, %(candid)s)
                    # st.toast(str(query.compile(engine, compile_kwargs={"literal_binds": True})))
                    con.execute(query)
                    con.commit()
                    # st.toast(f"Classified {candid} as {source}.")
                    st.toast(f"Classified {candid} as {source}.")
                except:
                    st.toast(f"Could not insert candidate {candid} into {source}.")
                    st.stop()

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

@st.fragment    
def artifact_button(i, candid):
    if st.button("Artifact", key = i):
        insert_candidate(engine, "artifact", candid)
        st.rerun()

@st.fragment
def reals_button(i, candid):
    if st.button("Real", key = i+1e5):
        insert_candidate(engine, "reals", candid)
        st.rerun()

@st.fragment
def echo_button(i, candid):
    if st.button("Echo", key = i+2e5):
        insert_candidate(engine, "echo", candid)
        st.rerun()

@st.fragment        
def highpm_button(i, candid):
    if st.button("High PM", key = i+3e5):
        insert_candidate(engine, "highpm", candid)
        st.rerun()

def page_load(page):
    if page == page_list[-1]: # if last page, then only load the remaining images
        for i in range(img_ppage*(page-1), len(candids)):
            st.header(f"{i}")
            fig = plot_triplet(i, candids[i], sci[i], ref[i], diff[i])
            st.pyplot(fig)
            col1, col2, col3, col4, col5 = st.columns([0.2, 0.2, 0.2, 0.2, 0.2])
            with col1:
                artifact_button(i, candids[i])
            with col2:
                reals_button(i, candids[i])
            with col3:
                echo_button(i, candids[i])
            with col4:
                highpm_button(i, candids[i])
            ra, dec = get_ra_dec(candids[i])
            byworlds = f"http://byw.tools/wiseview#ra={ra}&dec={dec}&size=176&band=2&speed=234.62&minbright=-2.3497&maxbright=963.1413&window=0.09958&diff_window=1&linear=1&color=&zoom=10&border=0&gaia=0&invert=0&maxdyr=0&scandir=0&neowise=0&diff=0&outer_epochs=0&unique_window=1&smooth_scan=0&shift=0&pmra=0&pmdec=0&synth_a=0&synth_a_sub=0&synth_a_ra=&synth_a_dec=&synth_a_w1=&synth_a_w2=&synth_a_pmra=0&synth_a_pmdec=0&synth_a_mjd=&synth_b=0&synth_b_sub=0&synth_b_ra=&synth_b_dec=&synth_b_w1=&synth_b_w2=&synth_b_pmra=0&synth_b_pmdec=0&synth_b_mjd="
            st.link_button("See in BYW", url = byworlds)
    else: # load 100 images per page
        for img in range(img_ppage*(page-1), img_ppage*page):
            st.header(f"{img}")
            fig = plot_triplet(img, candids[img], sci[img], ref[img], diff[img])
            st.pyplot(fig)
            col1, col2, col3, col4, col5 = st.columns([0.2, 0.2, 0.2, 0.2, 0.2])
            with col1:
                artifact_button(img, candids[img])
            with col2:
                reals_button(img, candids[img])
            with col3:
                echo_button(img, candids[img])
            with col4:
                highpm_button(img, candids[img])
            ra, dec = get_ra_dec(candids[img])
            byworlds = f"http://byw.tools/wiseview#ra={ra}&dec={dec}&size=176&band=2&speed=234.62&minbright=-2.3497&maxbright=963.1413&window=0.09958&diff_window=1&linear=1&color=&zoom=10&border=0&gaia=0&invert=0&maxdyr=0&scandir=0&neowise=0&diff=0&outer_epochs=0&unique_window=1&smooth_scan=0&shift=0&pmra=0&pmdec=0&synth_a=0&synth_a_sub=0&synth_a_ra=&synth_a_dec=&synth_a_w1=&synth_a_w2=&synth_a_pmra=0&synth_a_pmdec=0&synth_a_mjd=&synth_b=0&synth_b_sub=0&synth_b_ra=&synth_b_dec=&synth_b_w1=&synth_b_w2=&synth_b_pmra=0&synth_b_pmdec=0&synth_b_mjd="
            st.link_button("See in BYW", url = byworlds)

def all_classified(_engine, save = False):
    
    all_reals = [item for sublist in pd.read_sql_query("SELECT candid FROM reals", _engine).values for item in sublist]
    all_artifacts = [item for sublist in pd.read_sql_query("SELECT candid FROM artifact", _engine).values.tolist() for item in sublist]
    all_echos = [item for sublist in pd.read_sql_query("SELECT candid FROM echo", _engine).values.tolist() for item in sublist]
    all_highpms = [item for sublist in pd.read_sql_query("SELECT candid FROM highpm", _engine).values.tolist() for item in sublist]

    if save:
        np.savez_compressed("all_classified.npz", reals = all_reals, artifacts = all_artifacts, echos = all_echos, highpms = all_highpms)

    return np.concatenate((all_reals, all_artifacts, all_echos, all_highpms), axis = 0)

filtered_cands = hostless_candids(scanep, gallimlow, gallimhigh, candlim)
all_class_cands = all_classified(engine)
filtered_cands1 = np.setdiff1d(filtered_cands, all_class_cands)

# np.savez_compressed("filtered_cands.npz", candid = filtered_cands1)


candids, sci, ref, diff, params = get_images_from_db(filtered_cands1)
# keys = ["incorrect"]

# for key in keys:
#     if key not in st.session_state:
#         st.session_state[key] = []

# if 'scroll_to_top' not in st.session_state:
#     st.session_state.scroll_to_top = False

# if st.session_state.scroll_to_top:
#     scroll_to_here(10, key='top')  # Scroll to the top of the page, 0 means instantly, but you can add a delay (im milliseconds)
#     st.session_state.scroll_to_top = False  # Reset the state after scrolling

# def scroll():
#     st.session_state.scroll_to_top = True
    
img_ppage = 50
page_num = len(candids) // img_ppage

page_list = np.arange(1, page_num+2)

float_init()
container = st.container()

with container:
    col1, col2 = st.columns([0.7, 0.3])

    with col1:
        page = st.radio("Page", page_list, horizontal = True)
        container.float("top: 3.5em; background-color: white; padding: 0.5em; border: 1px solid black;")
        
    with col2:
        st.text("")
        st.markdown('[Back to Top](#hostless)')

    if page == page_list[-1]:
        st.write(f"Showing: {img_ppage*(page-1)} - {len(candids)}                 Total: {len(candids)}")
    else:
        st.write(f"Showing: {img_ppage*(page-1)} - {(img_ppage*page)-1}                Total: {len(candids)}")

page_load(page)

# def button_click(candid):
#     if candid not in st.session_state["incorrect"]:
#         st.session_state["incorrect"].append(candid)
#         record_df.loc[len(record_df)] = [candid, "incorrect"]
#         record_df.to_csv("log.csv", index = False)


# def delete_candidate(engine, source, candid, write = False):
#     with engine.connect() as con:
#         try:
#             table = metadata.tables.get(source)
#             query = delete(table).where(table.c.candid == str(candid))
        
#             con.execute(query)
#             con.commit()
#             st.toast(f"Deleted candidate {candid} from {source}.")
#         except:
#             st.toast(f"Could not delete candidate {candid} from {source}.")
#             st.stop()
#     if write:
#         record_df.drop(index = record_df.loc[record_df["candid"] == str(candid)].index, inplace = True)
#         record_df.to_csv("log.csv", index = False)




# def change_class(engine, candid, old_source, new_source):

#     if old_source == new_source: # if the candidate is already in the new source, then do nothing
#         st.toast(f"Candidate {candid} is already classified as {new_source}. Removing from page.")
#         record_df.drop(index = record_df.loc[record_df["candid"] == str(candid)].index, inplace = True)
#         record_df.to_csv("log.csv", index = False)
#     else:
#         delete_candidate(engine, old_source, candid) # delete the candidate from the original source
#         with engine.connect() as con:
#             try:
#                 insert_candidate(engine, new_source, candid)
#                 st.toast(f"Reclassified candidate {candid} as {new_source}.")
#                 record_df.drop(index = (record_df.loc[record_df["candid"] == str(candid)].index), inplace = True)
#                 record_df.to_csv("log.csv", index = False)
#             except:
#                 st.toast(f"Could not reclassify candidate {candid} as {new_source}.")
#                 st.stop()


