This is a web app that I built to visualize and classify transients (astronomical sources that vary in brightness over time) in the neoWISE survey! All of the data is being queried from a PostGreSQL database in real-time, where each set of images has a unique candidate id associated with it. There are something like 50 million images in the database in total. Below is the quickstart that you'll see [on the website](https://neowise-classify.streamlit.app/):

![](website.gif)

## Classifying Transients from neoWISE

Welcome! This is an ongoing project by Justin Vega to classify transients from the [neoWISE survey](https://neowise.ipac.caltech.edu).

The goal is to identify and classify various types of transients, including:
- **Artifacts**: These can range from spurious reflections, to diffraction spikes, to errors in the image subtraction process.
- **Echoes**: Transients that are likely to be echoes (reflected or emitted light from the dust of supernovae).
- **High Proper Motion Stars**: Stars with significant (apparent) motion across the sky. Characterized by a strong sharp residual (think black and white cookie).
- **Real Transients**: Genuine transients that are not artifacts or echoes. These will often appear to brighten over time, and are point-source like in nature.

## Helpful Tips:

### Plots:
Each triplet plot shows three images:
- **Science**: The image of scientific interest.
- **Reference**: The same field of view as the science, but from some time in the past.
- **Difference**: The difference "subtracted" image of the two.

### Sections:
- **Review** lets you review the transients that have already been classified. If you see one that looks like it should have a different label, hit the "incorrect" button! It should then populate in the **Misclassified** section.
- The ***Hostless Scan*** scans the database for images that haven't been classified yet, given the following search parameters:
    - Epochs are the different periods of time when neoWISE was observing (from 0-17)
    - Galactic latitude is the *absolute* angle of the object in the sky, with 0 degrees being the galactic plane and 90 degrees being the north galactic pole.

## Classifying Transients:
To gain an intuition for what things look like, I'd recommend starting with reviewing what's already been classified. Under each set of plots is a button to access the Backyard Worlds visualization tool for that particular image, which shows you all the data neoWISE has on that object. Seeing the images stitched together into a "movie" can help you distinguish between echos, highpm stars, and real artifacts.

Happy classifying!
