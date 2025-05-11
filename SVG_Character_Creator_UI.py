import sys
import os
import json
import random
import colorsys
from math import pi, sin, cos

# --- Pip-installable dependencies ---
try:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QFormLayout, QSpinBox, QDoubleSpinBox, QLineEdit, QPushButton,
        QCheckBox, QComboBox, QFileDialog, QLabel, QScrollArea,
        QGroupBox, QStatusBar, QMessageBox
    )
    from PyQt6.QtGui import QAction
    from PyQt6.QtCore import Qt
except ImportError:
    print("PyQt6 not found. Please install it: pip install PyQt6")
    sys.exit(1)

try:
    import svgwrite
except ImportError:
    print("svgwrite not found. Please install it: pip install svgwrite")
    sys.exit(1)

try:
    import requests # For fetching default color palettes
except ImportError:
    print("requests not found. Please install it: pip install requests (optional, for default palettes)")
    requests = None

# --- Core SVG Art Generation Logic (adapted from previous SVG versions) ---

DEFAULT_PALETTES_DATA = [
    ["#FF6B6B", "#FFD166", "#06D6A0", "#118AB2", "#073B4C"],
    ["#FAD02C", "#F2A104", "#E87007", "#D53903", "#A01F02"],
    ["#22223B", "#4A4E69", "#9A8C98", "#C9ADA7", "#F2E9E4"],
    ["#003049", "#D62828", "#F77F00", "#FCBF49", "#EAE2B7"]
]
DEFAULT_PALETTES_URL = ""

def load_color_palettes(palette_file_path=None):
    """Load color palettes from a local file or URL (if requests is available)."""
    if palette_file_path and os.path.exists(palette_file_path):
        try:
            with open(palette_file_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading palette file {palette_file_path}: {e}")
            return DEFAULT_PALETTES_DATA # Basic fallback
    elif requests: # Try fetching from URL if no path or path doesn't exist
        try:
            response = requests.get(DEFAULT_PALETTES_URL, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching default color palettes: {e}. Using hardcoded defaults.")
            return DEFAULT_PALETTES_DATA
    else:
        print("Requests library not available. Using hardcoded default palettes.")
        return DEFAULT_PALETTES_DATA

# --- Humanoid SVG Generation Functions ---

def create_head(dwg_group, x, y, size, colors):
    """Generate a head at the specified position."""
    head_radius = size * 0.4
    # Adjust the y position so the bottom of the head aligns with the top of the neck
    y -= head_radius  # Move the circle up by its radius
    dwg_group.add(svgwrite.shapes.Circle(center=(x, y + head_radius), r=head_radius, fill=colors['skin'], stroke="black", stroke_width=2))
    # Add eyes
    eye_offset = head_radius * 0.4
    eye_radius = head_radius * 0.1
    dwg_group.add(svgwrite.shapes.Circle(center=(x - eye_offset, y - eye_offset * 0.5 + head_radius), r=eye_radius, fill="white"))
    dwg_group.add(svgwrite.shapes.Circle(center=(x + eye_offset, y - eye_offset * 0.5 + head_radius), r=eye_radius, fill="white"))
    # Add pupils
    pupil_radius = eye_radius * 0.5
    dwg_group.add(svgwrite.shapes.Circle(center=(x - eye_offset, y - eye_offset * 0.5 + head_radius), r=pupil_radius, fill="black"))
    dwg_group.add(svgwrite.shapes.Circle(center=(x + eye_offset, y - eye_offset * 0.5 + head_radius), r=pupil_radius, fill="black"))
    # Add mouth
    mouth_width = head_radius * 0.6
    mouth_y = y + head_radius * 0.3 + head_radius
    dwg_group.add(svgwrite.shapes.Rect(insert=(x - mouth_width / 2, mouth_y), size=(mouth_width, head_radius * 0.1), fill="black"))

def create_neck(dwg_group, x, y, width, height, colors):
    """Generate a neck at the specified position."""
    # The neck's top should align with the bottom of the head
    dwg_group.add(svgwrite.shapes.Rect(insert=(x - width / 2, y), size=(width, height), fill=colors['skin'], stroke="black", stroke_width=2))

def create_torso(dwg_group, x, y, width, height, colors):
    """Generate a torso at the specified position."""
    # The torso's top should align with the bottom of the neck
    dwg_group.add(svgwrite.shapes.Rect(insert=(x - width / 2, y), size=(width, height), fill=colors['shirt'], stroke="black", stroke_width=2))

def create_arm(dwg_group, x, y, length, thickness, side, colors):
    """Generate an arm (left or right) at the specified position."""
    offset = -1 if side == 'left' else 1
    x += offset * thickness / 2  # Adjust x position for proper alignment
    arm = svgwrite.shapes.Rect(insert=(x, y), size=(thickness, length), fill=colors['skin'], stroke="black", stroke_width=2)
    dwg_group.add(arm)
    # Return animation details for later appending
    return f'<animateTransform attributeName="transform" type="rotate" from="0 {x} {y}" to="30 {x} {y}" dur="0.5s" repeatCount="indefinite" />'

def create_leg(dwg_group, x, y, length, thickness, side, colors):
    """Generate a leg (left or right) at the specified position."""
    offset = -1 if side == 'left' else 1
    x += offset * thickness / 2  # Adjust x position for proper alignment
    leg = svgwrite.shapes.Rect(insert=(x, y), size=(thickness, length), fill=colors['pants'], stroke="black", stroke_width=2)
    dwg_group.add(leg)
    # Return animation details for later appending
    return f'<animateTransform attributeName="transform" type="rotate" from="0 {x} {y}" to="-30 {x} {y}" dur="0.5s" repeatCount="indefinite" />'

def generate_humanoid_svg(dwg, x, y, size, colors, head_size, arm_length, leg_length, torso_width, torso_height):
    """Generate a humanoid character centered at (x, y) with a breathing idle animation."""
    torso_width = size * torso_width
    torso_height = size * torso_height
    arm_length = size * arm_length
    arm_thickness = size * 0.1
    leg_length = size * leg_length
    leg_thickness = size * 0.15
    neck_width = torso_width * 0.3
    neck_height = size * 0.1

    humanoid_group = dwg.add(dwg.g(id="humanoid"))
    # Calculate positions
    torso_top_y = y
    neck_top_y = torso_top_y - neck_height
    head_center_y = neck_top_y - neck_height

    # Create legs (stationary)
    create_leg(humanoid_group, x - torso_width / 4, torso_top_y + torso_height, leg_length, leg_thickness, 'left', colors)
    create_leg(humanoid_group, x + torso_width / 4 - leg_thickness, torso_top_y + torso_height, leg_length, leg_thickness, 'right', colors)

    # Group upper body elements for animation
    upper_body_group = humanoid_group.add(dwg.g(id="upper_body"))

    # Create torso
    create_torso(upper_body_group, x, torso_top_y, torso_width, torso_height, colors)
    # Create neck
    create_neck(upper_body_group, x, neck_top_y, neck_width, neck_height, colors)
    # Create head
    create_head(upper_body_group, x, head_center_y, size * head_size, colors)
    # Create arms
    create_arm(upper_body_group, x - torso_width / 2, torso_top_y, arm_length, arm_thickness, 'left', colors)
    create_arm(upper_body_group, x + torso_width / 2 - arm_thickness, torso_top_y, arm_length, arm_thickness, 'right', colors)

    # Return the breathing animation as a string for the upper body group
    return f'<animateTransform attributeName="transform" type="translate" from="0,0" to="0,5" dur="1s" repeatCount="indefinite" xlink:href="#upper_body" />'

# --- Main SVG Generation Function ---
def generate_art_svg_string(params):
    """Generates the SVG art as a string based on the provided parameters."""
    # Handle seed: use integer if provided, otherwise random.seed() handles None.
    seed_value = params.get('seed')
    if isinstance(seed_value, str) and seed_value.isdigit():
        random.seed(int(seed_value))
    elif isinstance(seed_value, int):
        random.seed(seed_value)
    else:
        if seed_value is not None and seed_value != '':  # If it's a non-empty, non-digit string
            print(f"Warning: Invalid seed value '{seed_value}'. Using random seed.")
        random.seed()  # Default to random if no seed, empty, or invalid string

    character_size = params['character_size']
    num_humanoids = params['num_humanoids']

    current_palette_list = params['current_palette_list']
    if not current_palette_list:
        print("Error: No color palette data provided for generation.")
        return None
    selected_palette_data = current_palette_list[params['palette_index']]

    # Calculate grid dimensions
    grid_cols = int(num_humanoids**0.5)  # Number of columns in the grid
    grid_rows = (num_humanoids + grid_cols - 1) // grid_cols  # Number of rows in the grid

    # Add padding to ensure no part of the character is cut off
    padding_top = character_size // 2
    padding_sides = character_size // 2
    padding_bottom = character_size  # Extra padding at the bottom for legs

    # Calculate canvas size based on grid dimensions and padding
    svg_width = grid_cols * character_size + 2 * padding_sides
    svg_height = grid_rows * character_size + padding_top + padding_bottom

    dwg = svgwrite.Drawing(filename=None, size=(f"{svg_width}px", f"{svg_height}px"), profile='full')
    dwg.defs.add(dwg.style("svg * { shape-rendering: crispEdges; }"))

    # Collect animations
    all_animations = []

    # Generate humanoid characters in a grid layout
    for idx in range(num_humanoids):
        col = idx % grid_cols
        row = idx // grid_cols
        x = col * character_size + padding_sides + character_size // 2  # Center character in its cell
        y = row * character_size + padding_top + character_size // 2  # Center character in its cell
        colors = {
            'skin': random.choice(["#FAD02C", "#E87007", "#F2E9E4"]),
            'shirt': random.choice(["#118AB2", "#FFD166", "#06D6A0"]),
            'pants': random.choice(["#073B4C", "#4A4E69", "#9A8C98"])
        }
        animation = generate_humanoid_svg(
            dwg, x, y, character_size, colors,
            params['head_size'], params['arm_length'], params['leg_length'],
            params['torso_width'], params['torso_height']
        )
        all_animations.append(animation)

    # Convert SVG to string and append animations
    svg_string = dwg.tostring()
    for animation in all_animations:
        svg_string = svg_string.replace('</svg>', f'{animation}</svg>')

    return svg_string

# --- PyQt6 UI Application ---
class ArtGridWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_palette_list = [] 
        self.current_palette_file_path = "" 
        self.initUI()
        self.load_initial_palettes()

    def initUI(self):
        self.setWindowTitle("Humanoid Character Generator (PyQt6)")
        self.setGeometry(100, 100, 700, 800) 

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        menubar = self.menuBar()
        file_menu = menubar.addMenu("&File")
        
        generate_save_action = QAction("&Generate & Save SVG", self)
        generate_save_action.setShortcut("Ctrl+S")
        generate_save_action.triggered.connect(self.run_generation_and_save)
        file_menu.addAction(generate_save_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("&Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Character Parameters Group
        char_group = QGroupBox("Character Parameters")
        char_layout = QFormLayout()
        self.char_size_spin = QSpinBox()
        self.char_size_spin.setRange(50, 500); self.char_size_spin.setValue(150)
        char_layout.addRow("Character Size (px):", self.char_size_spin)
        self.num_chars_spin = QSpinBox()
        self.num_chars_spin.setRange(1, 10); self.num_chars_spin.setValue(1)
        char_layout.addRow("Number of Characters:", self.num_chars_spin)
        char_group.setLayout(char_layout)
        main_layout.addWidget(char_group)

        # Color Palette Group
        palette_group = QGroupBox("Color Palette")
        palette_layout = QFormLayout()
        palette_file_layout = QHBoxLayout()
        self.palette_file_edit = QLineEdit()
        self.palette_file_edit.setPlaceholderText("Optional: Path to .json (or blank for default)")
        palette_file_layout.addWidget(self.palette_file_edit)
        browse_palette_btn = QPushButton("Browse...")
        browse_palette_btn.clicked.connect(self.browse_palette_file)
        palette_file_layout.addWidget(browse_palette_btn)
        palette_layout.addRow("Palette File:", palette_file_layout)
        
        self.palette_index_spin = QSpinBox()
        self.palette_index_spin.setRange(0, 0) 
        palette_layout.addRow("Palette Index:", self.palette_index_spin)
        palette_group.setLayout(palette_layout)
        main_layout.addWidget(palette_group)

        # Body Part Customization Group
        body_group = QGroupBox("Body Part Customization")
        body_layout = QFormLayout()
        self.head_size_spin = QDoubleSpinBox()
        self.head_size_spin.setRange(0.2, 1.0); self.head_size_spin.setSingleStep(0.1); self.head_size_spin.setValue(0.4)
        body_layout.addRow("Head Size (relative to body):", self.head_size_spin)
        self.arm_length_spin = QDoubleSpinBox()
        self.arm_length_spin.setRange(0.4, 1.0); self.arm_length_spin.setSingleStep(0.1); self.arm_length_spin.setValue(0.6)
        body_layout.addRow("Arm Length (relative to body):", self.arm_length_spin)
        self.leg_length_spin = QDoubleSpinBox()
        self.leg_length_spin.setRange(0.5, 1.0); self.leg_length_spin.setSingleStep(0.1); self.leg_length_spin.setValue(0.7)
        body_layout.addRow("Leg Length (relative to body):", self.leg_length_spin)
        self.torso_width_spin = QDoubleSpinBox()
        self.torso_width_spin.setRange(0.3, 1.0); self.torso_width_spin.setSingleStep(0.1); self.torso_width_spin.setValue(0.5)
        body_layout.addRow("Torso Width (relative to body):", self.torso_width_spin)
        self.torso_height_spin = QDoubleSpinBox()
        self.torso_height_spin.setRange(0.5, 1.0); self.torso_height_spin.setSingleStep(0.1); self.torso_height_spin.setValue(0.8)
        body_layout.addRow("Torso Height (relative to body):", self.torso_height_spin)
        body_group.setLayout(body_layout)
        main_layout.addWidget(body_group)

        # Miscellaneous Options
        misc_group = QGroupBox("Miscellaneous Options")
        misc_layout = QFormLayout()
        self.seed_edit = QLineEdit(); self.seed_edit.setPlaceholderText("Integer or blank for random")
        misc_layout.addRow("Random Seed:", self.seed_edit)
        misc_group.setLayout(misc_layout)
        main_layout.addWidget(misc_group)

        # Generate Button
        self.generate_button = QPushButton("Generate & Save SVG")
        self.generate_button.setFixedHeight(40)
        self.generate_button.setStyleSheet("font-size: 16px; background-color: #4CAF50; color: white; border-radius: 5px; padding: 5px;")
        self.generate_button.clicked.connect(self.run_generation_and_save)
        main_layout.addWidget(self.generate_button)

        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("Ready.")
        self.update_palette_display()

    def load_initial_palettes(self):
        self.current_palette_list = load_color_palettes(None) 
        self.update_palette_display()
        self.palette_file_edit.setPlaceholderText(f"Default: {len(self.current_palette_list)} palettes (URL/Hardcoded)")

    def browse_palette_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open Color Palette File", "", "JSON Files (*.json);;All Files (*)")
        if file_path:
            self.palette_file_edit.setText(file_path)
            self.current_palette_file_path = file_path
            self.current_palette_list = load_color_palettes(file_path)
            self.update_palette_display()
            self.statusBar.showMessage(f"Loaded {len(self.current_palette_list)} palettes from {os.path.basename(file_path)}.")
        elif not self.palette_file_edit.text(): 
            self.load_initial_palettes() 
            self.statusBar.showMessage("Reverted to default palettes.")

    def update_palette_display(self):
        if self.current_palette_list and isinstance(self.current_palette_list, list):
            num_palettes = len(self.current_palette_list)
            self.palette_index_spin.setRange(0, max(0, num_palettes - 1))
            if num_palettes > 0:
                self.palette_index_spin.setEnabled(True)
                current_idx = self.palette_index_spin.value()
                if current_idx >= num_palettes or current_idx < 0 : # if current index is out of new bounds
                    self.palette_index_spin.setValue(random.randint(0, max(0, num_palettes -1)))
            else: # No palettes loaded (e.g. empty JSON)
                self.palette_index_spin.setEnabled(False)
                self.palette_index_spin.setValue(0) # Reset to 0
        else: 
            self.palette_index_spin.setRange(0,0); self.palette_index_spin.setEnabled(False); self.palette_index_spin.setValue(0)
            self.current_palette_list = DEFAULT_PALETTES_DATA 
            self.statusBar.showMessage("Warning: Palette data is invalid or empty. Using fallback.", 5000)
            self.update_palette_display() # Call again to set range for default palettes

    def get_generation_parameters(self):
        """Collect parameters for character generation."""
        if not self.current_palette_list or not isinstance(self.current_palette_list, list) or len(self.current_palette_list) == 0:
            QMessageBox.critical(self, "Palette Error", "No valid color palettes are loaded. Cannot generate.")
            return None
        
        palette_idx = self.palette_index_spin.value()
        if not (0 <= palette_idx < len(self.current_palette_list)):
             QMessageBox.critical(self, "Palette Error", f"Invalid palette index ({palette_idx}). Please check palette loading.")
             return None
        
        seed_text = self.seed_edit.text().strip()
        valid_seed_param = None
        if seed_text:
            try:
                valid_seed_param = int(seed_text)
            except ValueError:
                QMessageBox.warning(self, "Invalid Seed", "Seed must be an integer. Using random seed for this generation.")
                self.seed_edit.clear()

        params = {
            'character_size': self.char_size_spin.value(),
            'num_humanoids': self.num_chars_spin.value(),
            'current_palette_list': self.current_palette_list,
            'palette_index': palette_idx,
            'head_size': self.head_size_spin.value(),
            'arm_length': self.arm_length_spin.value(),
            'leg_length': self.leg_length_spin.value(),
            'torso_width': self.torso_width_spin.value(),
            'torso_height': self.torso_height_spin.value(),
            'seed': valid_seed_param,
        }
        return params

    def run_generation_and_save(self):
        self.statusBar.showMessage("Generating artwork...")
        QApplication.processEvents()

        params = self.get_generation_parameters()
        if not params:
            self.statusBar.showMessage("Generation cancelled due to parameter errors.", 5000)
            return

        output_path, _ = QFileDialog.getSaveFileName(self, "Save Artwork As", "humanoid_art", "SVG Files (*.svg);;All Files (*)")
        if not output_path:
            self.statusBar.showMessage("Save cancelled.", 5000)
            return

        if not output_path.lower().endswith(".svg"):
            output_path += ".svg"

        try:
            svg_data_str = generate_art_svg_string(params)
            if svg_data_str is None:
                QMessageBox.critical(self, "Generation Failed", "SVG generation returned no data.")
                self.statusBar.showMessage("Error during SVG generation.", 5000)
                return

            # Save the SVG file
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(svg_data_str)

            self.statusBar.showMessage(f"SVG artwork saved to {output_path}", 5000)

        except Exception as e:
            QMessageBox.critical(self, "Error", f"An unexpected error occurred: {e}")
            self.statusBar.showMessage(f"Error: {e}", 5000)
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_window = ArtGridWindow()
    main_window.show()
    sys.exit(app.exec())
