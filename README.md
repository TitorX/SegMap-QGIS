# SegMap

<div align="center">
  <img src="icons/logo.svg" alt="SegMap Logo">
</div>

## Introduction

**What is SegMap?**  

SegMap is a **QGIS plugin** that leverages deep learning (DL) models to enable fast map digitization. Unlike traditional methods requiring labor-intensive polygon editing, SegMap allows users to extract objects of interest from aerial imagery with just a few clicks. This streamlined approach makes it significantly faster and more efficient for generating precise vector outputs.  

**Traditional vector editing vs. SegMap**  

- Old Workflow: Manual digitization of aerial features often demands **hundreds** of clicks to adjust polygon vertices.  
- SegMap Advantage: Achieves accurate results in **seconds with 1-5 clicks**, reducing effort by over 90%.  

**Key Features**  

- **Rapid Interactive Vectorization**: Extract objects to vector polygons using foreground/background clicks, guided by DL models.  
- **QGIS Integration**: Functions seamlessly within the QGIS environment, combining AI power with geospatial tools.  

By merging AI efficiency with user-friendly interaction, SegMap revolutionizes tasks like land cover mapping, infrastructure monitoring, and environmental analysis.

## Installation

To install SegMap as a QGIS plugin, follow these steps:

1. Download the latest release from the [releases page](https://github.com/your-repo/segmap/releases).

2. Open QGIS and navigate to `Plugins > Manage and Install Plugins...`.

3. In the Plugin Manager, click on the `Install from ZIP` tab.

4. Click the `...` button to browse and select the downloaded ZIP file.

5. Click `Install Plugin` to complete the installation.

<div align="center">
  <img src="imgs/1. install.gif" alt="Installation Guide">
</div>

You are now ready to use SegMap as a QGIS plugin for your segmentation tasks!

## Usage

### Step 1: Prepare and Setup Everything

a. Click the **SegMap: Settings** button to configure the server and token. Use the demo server `https://segmap.nodes.studio` and token `demo` for quick setup. Note: The demo service is available for use, but its availability and speed are not guaranteed.

b. Click the **SegMap: Start** button to open the tool panel.

c. Choose the **Model**, **Raster**, and **Output**, and edit the **Class** list as needed.

<div align="center">
  <img src="imgs/2. setup.gif" alt="Prepare and Setup">
</div>

### Step 2: Start Using SegMap

a. Click the **Start** button to begin.

b. Use the mouse middle button or scroll to pan/zoom the image and locate the object in the center of the canvas.

c. Left-click on the desired object and right-click on unwanted areas to refine the selection.

d. When the result is satisfactory, click **Confirm** to save it to the selected vector layer.

e. Once finished, click the **End** button to exit the tool usage.

<div align="center">
  <img src="imgs/3. usage.gif" alt="Usage Guide">
</div>

## Self-Hosted API Server

If you prefer to deploy the API server on your own device, please refer to the [server/README.md](server/README.md) for detailed instructions.
