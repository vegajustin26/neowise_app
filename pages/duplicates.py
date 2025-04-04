import streamlit as st
import astropy
from astropy.io import fits
import numpy as np
import gzip
import io
from io import BytesIO
import pandas as pd
from astropy.stats import sigma_clipped_stats as scs
import matplotlib.pyplot as plt
from streamlit_float import *
from sqlalchemy import create_engine, text, delete, insert, MetaData
from collections import defaultdict


st.set_page_config(page_title="Duplicates", page_icon="❌", layout = "wide")

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

@st.cache_resource
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
        st.toast(incorrect_candids)
    
    images = pd.read_sql_query(f"""
        SELECT c.candid, c.sci_image, c.ref_image, c.diff_image from cutouts c INNER JOIN (SELECT DISTINCT(candid) from candidates) s ON c.candid = s.candid WHERE c.candid IN {incorrect_candids};""", engine)
    st.toast("aas")
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
    record_df = pd.read_csv("log.csv", dtype = str, skipinitialspace=True, header=0)
    dup_df = record_df.loc[record_df["type"] == "duplicate"]
    dup_candids = dup_df["candid"].values
    candids, sci, ref, diff, params = get_images_from_db(dup_candids)
    
except:
    st.write("No duplicates found.")
    st.stop()

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
        page = st.radio("Page", page_list, horizontal = True, on_change = scroll())
        container.float("top: 3.5em; background-color: white; padding: 0.5em; border: 1px solid black;")
    
    with col2:
        st.text("")
        st.button("Clear incorrect", on_click = lambda: st.session_state["incorrect"].clear())

    if page == page_list[-1]:
        st.write(f"Showing: {img_ppage*(page-1)} - {len(candids)}                 Total: {len(candids)}")
    else:
        st.write(f"Showing: {img_ppage*(page-1)} - {(img_ppage*page)-1}                Total: {len(candids)}")


def locate_duplicates(engine):
    
    all_reals = [item for sublist in pd.read_sql_query("SELECT candid FROM reals", engine).values for item in sublist]
    all_artifacts = [item for sublist in pd.read_sql_query("SELECT candid FROM artifact", engine).values.tolist() for item in sublist]
    all_echos = [item for sublist in pd.read_sql_query("SELECT candid FROM echo", engine).values.tolist() for item in sublist]
    all_highpms = [item for sublist in pd.read_sql_query("SELECT candid FROM highpm", engine).values.tolist() for item in sublist]

    list_of_lists = [all_reals, all_artifacts, all_echos, all_highpms]
    sources = ["reals", "artifact", "echo", "highpm"]
    duplicates = defaultdict(set)

    for i, lst in enumerate(list_of_lists, start=1):
        for item in lst:
            duplicates[item].add(f"{sources[i-1]}")

    duplicates = {item: locations for item, locations in duplicates.items() if len(locations) > 1}
    
    strs = [f"{item}, {', '.join(lists)}\n" for item, lists in duplicates.items()]
    
    record_df = pd.read_csv("log.csv", dtype = str, skipinitialspace=True, header=0)

    if len(duplicates) == 0:
        st.write("No duplicates found.")
    
    
    
    
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
        except:
            st.toast(f"Could not locate candidate {candid}.")
            st.stop()
    return source, candid

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
    
    
def remove_class(engine, candid, old_source, new_source, new_label):
    
    # st.toast(str(old_source in new_label))
    # st.toast(str(new_source in new_label))
    
    if old_source == new_label or new_source == new_label: # if the candidate isn't in the chosen class
        # st.toast(type(old_source))
        # st.toast(type(new_source))
        # st.toast(f"Reclassifying candidate {candid} as {new_label}.")
        if old_source == new_label:
            delete_candidate(engine, new_source, candid, write = True) # delete the candidate from the other source only
        elif new_source == new_label:
            delete_candidate(engine, old_source, candid, write = True) # delete the candidate from the other source only
        
    else:
        st.toast(f"Candidate {candid} is not classified as {new_label}. Assigning to {new_label}.")
        delete_candidate(engine, old_source, candid, write = True)
        delete_candidate(engine, new_source, candid, write = False)
        insert_candidate(engine, new_label, candid)
        # with engine.connect() as con:
        #     try:
        #         insert_candidate(engine, new_source, candid)
        #         st.toast(f"Reclassified candidate {candid} as {new_source}.")
        #         record_df.drop(index = (record_df.loc[record_df["candid"] == str(candid)].index), inplace = True)
        #         record_df.to_csv("log.csv", index = False)
        #     except:
        #         st.toast(f"Could not reclassify candidate {candid} as {new_source}.")
        #         st.stop()


def page_load(page):
    if page == page_list[-1]: # if last page, then only load the remaining images
        for i in range(img_ppage*(page-1), len(candids)):
            # st.toast(len(dup_df))
            
            source1 = dup_df.loc[dup_df["candid"] == str(candids[i]), "source1"].values[0]
            source2 = dup_df.loc[dup_df["candid"] == str(candids[i]), "source2"].values[0]
            
            
            st.header(f"{i} - classified as {source1} and {source2}")
            
            fig = plot_triplet(i, candids[i], sci[i], ref[i], diff[i])
            st.pyplot(fig)
            
            col1, col2, col3, col4, col5 = st.columns([0.2, 0.2, 0.2, 0.2, 0.2])
            with col1:
                if st.button("Artifact", key = i):
                    remove_class(engine, candids[i], source1, source2, "artifact")
                    st.rerun()
            with col2:
                if st.button("Real", key = i+1e5):
                    remove_class(engine, candids[i], source1, source2, "reals")
                    st.rerun()
            with col3:
                if st.button("Echo", key = i+2e5):
                    remove_class(engine, candids[i], source1, source2, "echo")
                    st.rerun()
            with col4:
                if st.button("High PM", key = i+3e5):
                    remove_class(engine, candids[i], source1, source2, "highpm")
                    st.rerun()
            with col5:
                if st.button("Delete", key = i+4e5):
                    delete_candidate(engine, source1, candids[i], write = True)
                    delete_candidate(engine, source2, candids[i], write = False)
                    st.rerun() 
    else: # load 100 images per page
        for img in range(img_ppage*(page-1), img_ppage*page):
            
            source1 = dup_df.loc[dup_df["candid"] == str(candids[i]), "source1"].values[0]
            source2 = dup_df.loc[dup_df["candid"] == str(candids[i]), "source2"].values[0]
            st.header(f"{i} - classified as {source1} and {source2}")
            
            fig = plot_triplet(img, candids[img], sci[img], ref[img], diff[img])
            st.pyplot(fig)
            
            col1, col2, col3, col4, col5 = st.columns([0.2, 0.2, 0.2, 0.2, 0.2])
            with col1:
                if st.button("Artifact", key = img):
                    remove_class(engine, candids[img], source1, source2, "artifact")
                    st.rerun()
            with col2:
                if st.button("Real", key = img+1e5):
                    remove_class(engine, candids[img], source1, source2, "reals")
                    st.rerun()
            with col3:
                if st.button("Echo", key = img+2e5):
                    remove_class(engine, candids[img], source1, source2, "echo")
                    st.rerun()
            with col4:
                if st.button("High PM", key = img+3e5):
                    remove_class(engine, candids[img], source1, source2, "highpm")
                    st.rerun()
            with col5:
                if st.button("Delete", key = img+4e5):
                    delete_candidate(engine, source1, candids[img], write = True)
                    delete_candidate(engine, source2, candids[img], write = False)
                    st.rerun()

st.write("#")
st.write("###")
st.title("Duplicates")

page_load(page)


# locate_duplicates(engine)
# page_load(page)

    
