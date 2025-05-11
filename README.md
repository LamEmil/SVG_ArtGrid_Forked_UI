# SVG ArtGrid (PyQt6 Fork)

This is a forked and modified version of an SVG art generation script, originally from [MushroomFleet/SVG_ArtGrid](https://github.com/MushroomFleet/SVG_ArtGrid). This fork introduces a PyQt6 graphical user interface (GUI) and other enhancements for generating customizable SVG grid-based artwork.

## Original Project

Please refer to the original repository for its version and history:
[https://github.com/MushroomFleet/SVG_ArtGrid](https://github.com/MushroomFleet/SVG_ArtGrid)

## Key Changes in This Fork
Added ComfyUI_PNGArtGridGeneratorNode.py, a custom node for comfyui, just drop the python script in to your comfyui custom nodes folder.

This version (`SVG_ArtGrid.py`) has been significantly updated from the original script's base:
added ('SVG_Character_Creator_UI.py') to experiment with animated character generation. UI included in the seperate script.

* **Graphical User Interface (GUI):** Implemented using PyQt6, providing an interactive way to control generation parameters.
* **Enhanced Customization via GUI:**
    * Set grid dimensions (rows, columns) and square size.
    * Load color palettes from local JSON files or use built-in defaults (fetched from a URL if in code, otherwise uses hardcoded defaults).
    * Select a specific palette index from the loaded list.
    * Choose which block styles to include in the generation (from 12 available styles).
    * Enable and configure a "Big Block" feature, which draws a larger pattern over a portion of the grid.
    * Adjust a "Chaos Factor" to control the amount of randomness and variation in the generated art.
    * Input a specific random seed for reproducible artwork generation.
* **Diverse Block Styles:** Includes a variety of generative drawing functions for creating unique patterns within each grid cell, such as circles, crosses, half squares, diagonal squares, quarter circles, dots, letter blocks, concentric circles, stripes, rotated shapes, and wavy lines.
* **Direct SVG Output:** Generates and saves artwork directly as SVG files using the `svgwrite` library.
* **Improved User Experience:** Provides status messages, error dialogs, and file browsing capabilities for a more user-friendly experience.

## Features

* Generate unique, abstract grid-based art.
* Interactive parameter adjustment through a PyQt6 GUI.
* Customizable grid size and cell dimensions.
* Flexible color palette system:
    * Use default palettes.
    * Load palettes from external `.json` files.
    * Palettes can be fetched from an online source (requires `requests`).
* Wide range of selectable block styles for varied visual output.
* "Chaos Factor" for controlling artistic randomness.
* "Big Block" mode for adding a dominant visual element.
* Option to set a random seed for reproducible results.
* Save artwork as scalable SVG files.

## Installation

1.  **Clone the repository (or download the script):**
    ```bash
    git clone https://github.com/LamEmil/SVG_ArtGrid_Forked_UI
    ```
    Or simply download the `SVG_ArtGrid.py` script.

2.  **Ensure Python is installed:**
    Python 3.x is required.

3.  **Install dependencies:**
    This script requires `PyQt6` for the GUI and `svgwrite` for generating SVG files. The `requests` library is optional, required if fetching from a url.

    You can install them using pip:
    ```bash
    pip install PyQt6 svgwrite requests
    ```
    If you prefer not to install `requests`, the script uses a hardcoded set of default palettes and this should not effect functionality. You only need requests if you intend to edit the code to pull palettes from a url.

## Usage

1.  Run the script from your terminal:
    ```bash
    python SVG_ArtGrid.py
    ```
2.  The "Art Grid Generator" window will appear.
3.  Adjust the parameters in the GUI:
    * **Grid & Size Parameters:** Set the number of rows, columns, and the size of each square in pixels.
    * **Color Palette:**
        * Optionally, browse for a local `.json` file containing color palettes. Each palette should be a list of hex color strings (e.g., `["#FF6B6B", "#FFD166", "#06D6A0"]`). The JSON file should contain a list of such palettes.
        * Select the desired palette index using the spin box.
    * **Block Styles:** Check the styles you want to be included in the random generation. At least one must be selected.
    * **Big Block & Chaos:**
        * Enable/disable the "Big Block" feature and choose its size multiplier (2x2 or 3x3 cells).
        * Set the "Chaos Factor" (0.0 for minimal variation, 1.0 for maximum).
        * Enter an integer "Random Seed" for reproducible art, or leave blank for a random seed each time.
4.  Click the "Generate & Save SVG" button (or use Ctrl+S).
5.  A file dialog will prompt you to choose a location and name for your SVG artwork.

## Dependencies

* **Python 3.x**
* **PyQt6:** For the graphical user interface.
* **svgwrite:** For creating and writing SVG files.
* **requests (optional):** For fetching default color palettes from an online source. If not installed, a predefined set of palettes is used.

## Color Palette JSON Format

If you provide a custom palette file, it should be a JSON file containing a list of palettes. Each palette itself is a list of hex color strings.

Example `my_palettes.json`:
```json
[
  ["#1A1A1A", "#2A2A2A", "#3A3A3A", "#4A4A4A", "#5A5A5A"],
  ["#FF0000", "#00FF00", "#0000FF"],
  ["#FAD02C", "#F2A104", "#E87007", "#D53903", "#A01F02"]
]
