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

try:
    # record_df = pd.read_csv("log.csv", dtype = str)
    # incorrect_candids = record_df["candid"].tolist()
    
    # dup_candids, source1, source2 = np.loadtxt("duplicates.txt", dtype = str, delimiter=",", unpack = True, ndmin = 1)
        
    # filtered_cands = list(set(incorrect_candids).difference(dup_candids))
    st.markdown('#')
    st.markdown('###')
    st.text("Please upload list of candids separated by commas.")
    textbox = st.text_area("candids")
    button = st.button("Submit")
    if button: 
        try:
            textbox_list = json.loads(str(textbox))
            candid_csv = pd.DataFrame(textbox_list, columns = ["candid"])
            cands = candid_csv["candid"]
            
        except:
            st.write("Format of text is incorrect. Please try again.")
            st.stop()
    
    candids, sci, ref, diff, params = get_images_from_db(cands)
    
except:
    st.write("No misclassified images found.")
    st.stop()

keys = ["incorrect"]

for key in keys:
    if key not in st.session_state:
        st.session_state[key] = []

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

float_init()
container = st.container()

with container:
    col1, col2 = st.columns([0.7, 0.3])

    with col1:
        page = st.radio("Page", page_list, horizontal = True)
        container.float("top: 3.5em; background-color: white; padding: 0.5em; border: 1px solid black;")
    
    with col2:
        st.text("")
        st.button("Clear incorrect", on_click = lambda: st.session_state["incorrect"].clear())

    if page == page_list[-1]:
        st.write(f"Showing: {img_ppage*(page-1)} - {len(candids)}                 Total: {len(candids)}")
    else:
        st.write(f"Showing: {img_ppage*(page-1)} - {(img_ppage*page)-1}                Total: {len(candids)}")


def page_load_model_misclass(page):
    if page == page_list[-1]: # if last page, then only load the remaining images
        for i in range(img_ppage*(page-1), len(candids)):
            # st.header(f"{i} - classified as {current_source} (likely {source1[i]} or {source2[i]})")
            fig = plot_triplet(i, candids[i], sci[i], ref[i], diff[i])
            st.pyplot(fig)
            # col1, col2, col3, col4, col5 = st.columns([0.2, 0.2, 0.2, 0.2, 0.2])
            # with col1:
            #     if st.button("Artifact", key = i):
            #         change_class(engine, candids[i], current_source, "artifact")
            #         st.rerun()
            # with col2:
            #     if st.button("Real", key = i+1e5):
            #         change_class(engine, candids[i], current_source, "reals")
            #         st.rerun()
            # with col3:
            #     if st.button("Echo", key = i+2e5):
            #         change_class(engine, candids[i], current_source, "echo")
            #         st.rerun()
            # with col4:
            #     if st.button("High PM", key = i+3e5):
            #         change_class(engine, candids[i], current_source, "highpm")
            #         st.rerun()
            # with col5:
            #     if st.button("Delete", key = i+4e5):
            #         delete_candidate(engine, current_source, candids[i], write = True)
            #         st.rerun() 
            ra, dec = get_ra_dec(candids[i])
            st.write(f"RA: {ra}, DEC: {dec}")
            byworlds = f"http://byw.tools/wiseview#ra={ra}&dec={dec}&size=176&band=2&speed=234.62&minbright=-2.3497&maxbright=963.1413&window=0.09958&diff_window=1&linear=1&color=&zoom=10&border=0&gaia=0&invert=0&maxdyr=0&scandir=0&neowise=0&diff=0&outer_epochs=0&unique_window=1&smooth_scan=0&shift=0&pmra=0&pmdec=0&synth_a=0&synth_a_sub=0&synth_a_ra=&synth_a_dec=&synth_a_w1=&synth_a_w2=&synth_a_pmra=0&synth_a_pmdec=0&synth_a_mjd=&synth_b=0&synth_b_sub=0&synth_b_ra=&synth_b_dec=&synth_b_w1=&synth_b_w2=&synth_b_pmra=0&synth_b_pmdec=0&synth_b_mjd="
            st.link_button("See in BYW", url = byworlds)
    else: # load 100 images per page
        for img in range(img_ppage*(page-1), img_ppage*page):
            pred, true = find_label(candids[img])
            # true = true_labels_str[img]
            st.header(f"{img} - predicted {pred} (true {true})")
            fig = plot_triplet(img, candids[img], sci[img], ref[img], diff[img])
            st.pyplot(fig)
            # col1, col2, col3, col4, col5 = st.columns([0.2, 0.2, 0.2, 0.2, 0.2])
            # with col1:
            #     if st.button("Artifact", key = img):
            #         change_class(engine, candids[img], current_source, "artifact")
            #         st.rerun()
            # with col2:
            #     if st.button("Real", key = img+1e5):
            #         change_class(engine, candids[img], current_source, "reals")
            #         st.rerun()
            # with col3:
            #     if st.button("Echo", key = img+2e5):
            #         change_class(engine, candids[img], current_source, "echo")
            #         st.rerun()
            # with col4:
            #     if st.button("High PM", key = img+3e5):
            #         change_class(engine, candids[img], current_source, "highpm")
            #         st.rerun()
            # with col5:
            #     if st.button("Delete", key = img+4e5):
            #         delete_candidate(engine, current_source, candids[img], write = True)
            #         st.rerun()
            ra, dec = get_ra_dec(candids[img])
            byworlds = f"http://byw.tools/wiseview#ra={ra}&dec={dec}&size=176&band=2&speed=234.62&minbright=-2.3497&maxbright=963.1413&window=0.09958&diff_window=1&linear=1&color=&zoom=10&border=0&gaia=0&invert=0&maxdyr=0&scandir=0&neowise=0&diff=0&outer_epochs=0&unique_window=1&smooth_scan=0&shift=0&pmra=0&pmdec=0&synth_a=0&synth_a_sub=0&synth_a_ra=&synth_a_dec=&synth_a_w1=&synth_a_w2=&synth_a_pmra=0&synth_a_pmdec=0&synth_a_mjd=&synth_b=0&synth_b_sub=0&synth_b_ra=&synth_b_dec=&synth_b_w1=&synth_b_w2=&synth_b_pmra=0&synth_b_pmdec=0&synth_b_mjd="
            st.link_button("See in BYW", url = byworlds)

st.title("Visualization")

page_load_model_misclass(page)

    
