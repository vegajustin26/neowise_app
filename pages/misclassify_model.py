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
plt.rcParams['figure.max_open_warning'] = 101 
import seaborn as sns
from matplotlib import colors
# import pyperclip

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

if "expanded" not in st.session_state:
    st.session_state.expanded = True


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
def get_images_from_db(incorrect_candids, limit = 1000):
    
    if len(incorrect_candids) > 1:
        incorrect_candids = tuple(incorrect_candids)
    else:
        incorrect_candids = f"('{incorrect_candids[0]}')"
    
    images = pd.read_sql_query(f"""
        SELECT c.candid, c.sci_image, c.ref_image, c.diff_image from cutouts c INNER JOIN (SELECT DISTINCT(candid) from candidates) s ON c.candid = s.candid WHERE c.candid IN {incorrect_candids} LIMIT {limit};""", engine)
    
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
        
        sci_cutout = np.array(fits.open(BytesIO(gzip.open(io.BytesIO(sci_image_b), 'rb').read()))[0].data)
        ref_cutout = np.array(fits.open(BytesIO(gzip.open(io.BytesIO(ref_image_b), 'rb').read()))[0].data)
        diff_cutout = np.array(fits.open(BytesIO(gzip.open(io.BytesIO(diff_image_b), 'rb').read()))[0].data)
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

# def submit():
#     st.session_state.submitted = True

# def reset_page():
#     st.session_state.submitted = False
#     cands = []
#     st.toast(f"from button {st.session_state.submitted}")
    # st.rerun()

try:
    # record_df = pd.read_csv("log.csv", dtype = str)
    # incorrect_candids = record_df["candid"].tolist()
    
    # dup_candids, source1, source2 = np.loadtxt("duplicates.txt", dtype = str, delimiter=",", unpack = True, ndmin = 1)
        
    # filtered_cands = list(set(incorrect_candids).difference(dup_candids))
    st.markdown("#")
    
    with st.expander("Settings", expanded = st.session_state.expanded):
        with st.form("search_form"):
            st.text("To visualize misclassifications from the model, upload a CSV file with probabilities, candid, and Predicted_Label for testing, or include True_Label for training.")
            uploaded_file = st.file_uploader("Choose a file")
            buttons, sliders = st.columns([0.5, 0.5])
            with buttons:
                source = st.pills("Sources", ['reals', 'highpm', 'echo', 'artifact'], selection_mode="single")
                truth_check = st.checkbox("Include True_Label", value = False, help = "If True_Label is included, the CSV should have columns: candid, True_Label, Predicted_Label. If False, it should have columns: candid, Predicted_Label.")
                limit = st.number_input("Limit number of images to display", max_value=1000, value=500, help="Limit the number of images to display from the uploaded CSV file.")
                binary = st.checkbox("Binary Classification", value = "False", help="If True, the CSV should only contain 'artifact' and 'reals' labels. If False, it can contain 'artifact', 'reals', 'highpm', and 'echo'.")
            with sliders:
                st.write("Probability Thresholds")
                artifact_slider = st.select_slider("Artifact", options = [i/20 for i in range(0, 21, 1)], value = (0.0, 1.0), help="Set the probability threshold for artifacts.")
                reals_slider = st.select_slider("Reals", options = [i/20 for i in range(0, 21, 1)], value = (0.0, 1.0), help="Set the probability threshold for reals.")
                echo_slider = st.select_slider("Echo", options = [i/20 for i in range(0, 21, 1)], value = (0.0, 1.0), help="Set the probability threshold for echoes.")
                highpm_slider = st.select_slider("High PM", options = [i/20 for i in range(0, 21, 1)], value = (0.0, 1.0), help="Set the probability threshold for high proper motion objects.")
                hide_elements = """
            <style>
                div[data-testid="stSliderTickBarMin"],
                div[data-testid="stSliderTickBarMax"] {
                    display: none;
                }
            </style>"""
                st.markdown(hide_elements, unsafe_allow_html=True)
            
            submitted = st.form_submit_button("Submit")
       
    if submitted and (uploaded_file is not None) and artifact_slider is not None:
        # st.session_state.expanded = False
        
        pred_csv = pd.read_csv(uploaded_file)
        st.toast("File uploaded successfully.")
        try:
            if truth_check: # if testing only on labeled data
                if binary:
                    misclassify = pred_csv[(pred_csv['True_Label'] != pred_csv['Predicted_Label'])]
                    
                else:
                    misclassify = pred_csv[(pred_csv['True_Label'] != pred_csv['Predicted_Label']) & (pred_csv["artifact"].between(artifact_slider[0], artifact_slider[1])) & (pred_csv["reals"].between(reals_slider[0], reals_slider[1])) & (pred_csv["echo"].between(echo_slider[0], echo_slider[1])) & (pred_csv["highpm"].between(highpm_slider[0], highpm_slider[1]))]
                    
                cands = misclassify["candid"].values
                pred_labels = misclassify["Predicted_Label"].values
                true_labels = misclassify["True_Label"].values    
            else:
                if source:
                    pred_csv = pred_csv[(pred_csv['Predicted_Label'] == source) & (pred_csv["artifact"].between(artifact_slider[0], artifact_slider[1])) & (pred_csv["reals"].between(reals_slider[0], reals_slider[1])) & (pred_csv["echo"].between(echo_slider[0], echo_slider[1])) & (pred_csv["highpm"].between(highpm_slider[0], highpm_slider[1]))]
                else:
                    pred_csv = pred_csv[(pred_csv["artifact"].between(artifact_slider[0], artifact_slider[1])) & (pred_csv["reals"].between(reals_slider[0], reals_slider[1])) & (pred_csv["echo"].between(echo_slider[0], echo_slider[1])) & (pred_csv["highpm"].between(highpm_slider[0], highpm_slider[1]))]
                    
                cands = pred_csv["candid"].values
                
                pred_labels = pred_csv["Predicted_Label"].values
                
        except:
            st.write("Format of CSV is incorrect. Please upload a CSV with the following columns: candid, True_Label, Predicted_Label.")
            st.stop()
    
    # artifact is 0, reals is 1, highpm is 2, echo is 3
    # true_labels_str = np.where(true_labels == 0, "artifact", np.where(true_labels == 1, "reals", np.where(true_labels == 2, "highpm", np.where(true_labels == 3, "echo", False))))
    # pred_labels_str = np.where(pred_labels == 0, "artifact", np.where(pred_labels == 1, "reals", np.where(pred_labels == 2, "highpm", np.where(pred_labels == 3, "echo", False))))
    if len(cands) == 0:
        st.toast("No images found, try again with different parameters.")
    
    candids, sci, ref, diff, params = get_images_from_db(cands, limit)
    
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
        st.button("Clear form", on_click = lambda: submitted == False)

    if page == page_list[-1]:
        st.write(f"Showing: {img_ppage*(page-1)} - {len(candids)}                 Total: {len(candids)}")
    else:
        st.write(f"Showing: {img_ppage*(page-1)} - {(img_ppage*page)-1}                Total: {len(candids)}")

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
    
    
def change_class(engine, candid, old_source, new_source):
    st.toast("button clicked")
    if old_source == new_source: # if the candidate is already in the new source, then do nothing
        st.toast(f"Candidate {candid} is already classified as {new_source}. Removing from page.")
        record_df.drop(index = record_df.loc[record_df["candid"] == str(candid)].index, inplace = True)
        record_df.to_csv("log.csv", index = False)
    if old_source == None:
        with engine.connect() as con:
            try:
                insert_candidate(engine, new_source, candid)
                st.toast(f"Reclassified candidate {candid} as {new_source}.")
                
            except:
                st.toast(f"Could not reclassify candidate {candid} as {new_source}.")
                st.stop()
    
    
    
    else:
        delete_candidate(engine, old_source, candid) # delete the candidate from the original source
        with engine.connect() as con:
            try:
                insert_candidate(engine, new_source, candid)
                st.toast(f"Reclassified candidate {candid} as {new_source}.")
                record_df.drop(index = (record_df.loc[record_df["candid"] == str(candid)].index), inplace = True)
                record_df.to_csv("log.csv", index = False)
            except:
                st.toast(f"Could not reclassify candidate {candid} as {new_source}.")
                st.stop()

def find_label(candid, pred_csv = pred_csv):
    # st.toast(type(candid))
    
    cand_row = pred_csv[pred_csv["candid"] == candid]
    pred = cand_row["Predicted_Label"].values[0]
    
    if binary:
        probs = cand_row[pred_csv.columns[:2]]
    else:
        probs = cand_row[pred_csv.columns[:4]]
    if truth_check:
        true = cand_row["True_Label"].values[0]
    else:
        true = None
    return(pred, true, probs)


def confusion_matrix(binary):
    # Create a confusion matrix
    
    col1, plot, col2 = st.columns([1, 2, 1])
    
    with plot:
        cm = pd.crosstab(pred_csv['True_Label'].values, pred_csv['Predicted_Label'].values, rownames=['Actual'], colnames=['Predicted'], margins=False)
        
        
        if binary:
            classes = pred_csv.columns[:2]
        else:
            classes = pred_csv.columns[:4]
        
        cm = cm.reindex(index=classes, columns=classes)
        
            
        fig, ax = plt.subplots(figsize=(8, 6))
        sns.heatmap(cm, annot=True, fmt="d", cmap=plt.cm.Blues, cbar=False,
                    annot_kws={"size": 12})
            
        cm = cm.values
        cm_norm = cm/cm.sum(axis = 1)
        cmap = plt.cm.Blues
        norm = colors.Normalize(vmin=np.amin(cm), vmax=np.amax(cm))
        for i in range(cm.shape[0]):
            for j in range(cm.shape[1]):
                cell_val = cm[i, j]
                cell_color = cmap(norm(cell_val))
                # Compute brightness from the RGB values (ignore alpha)
                brightness = np.mean(cell_color[:3])
                text_color = "white" if brightness < 0.5 else "black"
                ax.text(j + 0.5, i + 0.6, f"\n({cm_norm[i,j]*100:.1f}%)", 
                        ha="center", va="center", color=text_color, fontsize=10)

        ax.set_title("Confusion Matrix")
        ax.set_xlabel("Predicted Label")
        ax.set_ylabel("True Label")
        ax.xaxis.set_ticklabels(classes)
        ax.yaxis.set_ticklabels(classes)
        
        st.pyplot(fig)
    
    # Display the confusion matrix
    # st.write("Confusion Matrix:")
    # st.dataframe(cm)




def page_load_model_misclass(page):
    
    if page == page_list[-1]: # if last page, then only load the remaining images
        for i in range(img_ppage*(page-1), len(candids)):
            pred, true, probs = find_label(candids[i])
            if truth_check:
                st.header(f"{i} - predicted {pred} for {candids[i]} (true {true})")
            else:
                st.header(f"{i} - predicted {pred} for {candids[i]}")
            st.write(probs)
            fig = plot_triplet(i, candids[i], sci[i], ref[i], diff[i])
            st.pyplot(fig)
            col1, col2, col3, col4, col5 = st.columns([0.2, 0.2, 0.2, 0.2, 0.2])
            with col1:
                if st.button("Artifact", key = i):
                    change_class(engine, candids[i], None, "artifact")
                    st.rerun()
            with col2:
                if st.button("Real", key = i+1e5):
                    change_class(engine, candids[i], None, "reals")
                    st.rerun()
            with col3:
                if st.button("Echo", key = i+2e5):
                    change_class(engine, candids[i], None, "echo")
                    st.rerun()
            with col4:
                if st.button("High PM", key = i+3e5):
                    change_class(engine, candids[i], None, "highpm")
                    st.rerun()
            # with col5:
            #     if st.button("Delete", key = i+4e5):
            #         delete_candidate(engine, current_source, candids[i], write = True)
                    # st.rerun() 
            ra, dec = get_ra_dec(candids[i])
            byworlds = f"http://byw.tools/wiseview#ra={ra}&dec={dec}&size=176&band=2&speed=234.62&minbright=-2.3497&maxbright=963.1413&window=0.09958&diff_window=1&linear=1&color=&zoom=10&border=0&gaia=0&invert=0&maxdyr=0&scandir=0&neowise=0&diff=0&outer_epochs=0&unique_window=1&smooth_scan=0&shift=0&pmra=0&pmdec=0&synth_a=0&synth_a_sub=0&synth_a_ra=&synth_a_dec=&synth_a_w1=&synth_a_w2=&synth_a_pmra=0&synth_a_pmdec=0&synth_a_mjd=&synth_b=0&synth_b_sub=0&synth_b_ra=&synth_b_dec=&synth_b_w1=&synth_b_w2=&synth_b_pmra=0&synth_b_pmdec=0&synth_b_mjd="
            st.link_button("See in BYW", url = byworlds)
    else: # load 100 images per page
        for img in range(img_ppage*(page-1), img_ppage*page):
            pred, true, probs = find_label(candids[img])
            if truth_check:
                st.header(f"{img} - predicted {pred} for {candids[img]} (true {true})")
            else:
                st.header(f"{img} - predicted {pred} for {candids[img]}")
            st.write(probs)
            fig = plot_triplet(img, candids[img], sci[img], ref[img], diff[img])
            st.pyplot(fig)
            col1, col2, col3, col4, col5 = st.columns([0.2, 0.2, 0.2, 0.2, 0.2])
            with col1:
                if st.button("Artifact", key = img):
                    st.toast("test test")
                    change_class(engine, candids[img], None, "artifact")
                    # st.rerun()
            with col2:
                if st.button("Real", key = img+1e5):
                    change_class(engine, candids[img], None, "reals")
                    # st.rerun()
            with col3:
                if st.button("Echo", key = img+2e5):
                    change_class(engine, candids[img], None, "echo")
                    # st.rerun()
            with col4:
                if st.button("High PM", key = img+3e5):
                    change_class(engine, candids[img], None, "highpm")
                    # st.rerun()
            # with col5:
            #     if st.button("Delete", key = img+4e5):
            #         delete_candidate(engine, current_source, candids[img], write = True)
                    # st.rerun()
            ra, dec = get_ra_dec(candids[img])
            byworlds = f"http://byw.tools/wiseview#ra={ra}&dec={dec}&size=176&band=2&speed=234.62&minbright=-2.3497&maxbright=963.1413&window=0.09958&diff_window=1&linear=1&color=&zoom=10&border=0&gaia=0&invert=0&maxdyr=0&scandir=0&neowise=0&diff=0&outer_epochs=0&unique_window=1&smooth_scan=0&shift=0&pmra=0&pmdec=0&synth_a=0&synth_a_sub=0&synth_a_ra=&synth_a_dec=&synth_a_w1=&synth_a_w2=&synth_a_pmra=0&synth_a_pmdec=0&synth_a_mjd=&synth_b=0&synth_b_sub=0&synth_b_ra=&synth_b_dec=&synth_b_w1=&synth_b_w2=&synth_b_pmra=0&synth_b_pmdec=0&synth_b_mjd="
            st.link_button("See in BYW", url = byworlds)

st.title("Misclassified")
if truth_check:
    confusion_matrix(binary)

if submitted and (uploaded_file is not None) and artifact_slider is not None:
    st.write(pred_csv["Predicted_Label"].value_counts())
    # pyperclip.copy(pred_csv["candid"].values.tolist())
    # st.toast("Candids copied to clipboard")
    

page_load_model_misclass(page)

    
