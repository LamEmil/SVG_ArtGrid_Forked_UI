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


def create_background_colors(color_palette):
    if not color_palette or len(color_palette) < 2:
        return {"bg_inner": "#EEEEEE", "bg_outer": "#DDDDDD"}
    try:
        # Ensure colors are valid hex strings
        c1 = color_palette[0]
        c2 = color_palette[1]
        if not (isinstance(c1, str) and c1.startswith('#') and len(c1) in [4, 7]) or \
           not (isinstance(c2, str) and c2.startswith('#') and len(c2) in [4, 7]):
            raise ValueError("Invalid color format in palette")

        color1_hex = c1.lstrip('#')
        color2_hex = c2.lstrip('#')
        if len(color1_hex) == 3: color1_hex = "".join([c*2 for c in color1_hex])
        if len(color2_hex) == 3: color2_hex = "".join([c*2 for c in color2_hex])


        r1, g1, b1 = tuple(int(color1_hex[i:i+2], 16) for i in (0, 2, 4))
        r2, g2, b2 = tuple(int(color2_hex[i:i+2], 16) for i in (0, 2, 4))
    except (ValueError, IndexError, TypeError) as e:
        print(f"Warning: Invalid hex color found in palette for background ({e}). Using defaults.")
        return {"bg_inner": "#EEEEEE", "bg_outer": "#DDDDDD"}

    r_mix = (r1 + r2) // 2
    g_mix = (g1 + g2) // 2
    b_mix = (b1 + b2) // 2
    
    h, l, s = colorsys.rgb_to_hls(r_mix/255, g_mix/255, b_mix/255)
    s = max(0, s - 0.1) 
    r_desat, g_desat, b_desat = colorsys.hls_to_rgb(h, l, s)
    r_desat, g_desat, b_desat = int(r_desat*255), int(g_desat*255), int(b_desat*255)
        
    h_l, l_l, s_l = colorsys.rgb_to_hls(r_desat/255, g_desat/255, b_desat/255)
    
    l_light = min(1, l_l + 0.1)
    r_light, g_light, b_light = colorsys.hls_to_rgb(h_l, l_light, s_l)
    bg_inner = f"#{int(r_light*255):02x}{int(g_light*255):02x}{int(b_light*255):02x}"
    
    l_dark = max(0, l_l - 0.1)
    r_dark, g_dark, b_dark = colorsys.hls_to_rgb(h_l, l_dark, s_l)
    bg_outer = f"#{int(r_dark*255):02x}{int(g_dark*255):02x}{int(b_dark*255):02x}"
    
    return {"bg_inner": bg_inner, "bg_outer": bg_outer}

def get_two_colors(color_palette):
    if not color_palette: 
        return {"foreground": "#333333", "background": "#CCCCCC"}
    
    valid_colors = [c for c in color_palette if isinstance(c, str) and c.startswith("#") and len(c.lstrip('#')) in [3,6]]
    if not valid_colors: return {"foreground": "#333333", "background": "#CCCCCC"}
    if len(valid_colors) == 1: return {"foreground": valid_colors[0], "background": "#CCCCCC"}

    background = random.choice(valid_colors)
    remaining_colors = [c for c in valid_colors if c != background]
    
    foreground = random.choice(remaining_colors) if remaining_colors else valid_colors[0]
    return {"foreground": foreground, "background": background}

def get_random_opacity_str(chaos_factor): # For SVG opacity attribute
    if random.random() < chaos_factor * 0.5: 
        return str(round(random.uniform(0.6, 0.95), 2))
    return "1.0"

def get_random_rotation_transform(chaos_factor, cx, cy):
    """
    Returns a rotation transform string for SVG. Defaults to 0 degrees if no rotation is applied.
    """
    angle = random.choice([0, 15, 30, 45, 60, 75, 90, -15, -30, -45, -60, -75]) if random.random() < chaos_factor else 0
    return f"rotate({angle} {cx} {cy})"

# --- SVG Shape Drawing Functions (Using svgwrite) ---

def draw_circle(dwg_group, x, y, square_size, foreground, background, chaos_factor):
    dwg_group.add(svgwrite.shapes.Rect((x, y), (square_size, square_size), fill=background))
    main_circle = svgwrite.shapes.Circle(
        center=(x + square_size/2, y + square_size/2), 
        r=square_size/2 * random.uniform(0.8 - chaos_factor * 0.2, 1.0),
        fill=foreground,
        opacity=get_random_opacity_str(chaos_factor)
    )
    dwg_group.add(main_circle)
    if random.random() < 0.3 + chaos_factor * 0.3:
        inner_r_factor = random.uniform(0.2, 0.5)
        dwg_group.add(svgwrite.shapes.Circle(center=(x + square_size/2, y + square_size/2),
                             r=square_size/2 * inner_r_factor, fill=background,
                             opacity=get_random_opacity_str(chaos_factor)))
        if random.random() < chaos_factor * 0.5:
             dwg_group.add(svgwrite.shapes.Circle(center=(x + square_size/2, y + square_size/2),
                             r=square_size/2 * inner_r_factor * 0.5, fill=foreground,
                             opacity=get_random_opacity_str(chaos_factor)))

def draw_opposite_circles(dwg, x, y, square_size, foreground, background, chaos_factor):
    """
    Draws two opposite circles within a square using a mask.
    """
    dwg.add(svgwrite.shapes.Rect((x, y), (square_size, square_size), fill=background))

    # Add circles directly
    r_factor = random.uniform(0.4, 0.6)
    radius = square_size * r_factor
    offset = square_size / 2

    dwg.add(svgwrite.shapes.Circle(center=(x + offset, y + offset), r=radius, fill=foreground, opacity=get_random_opacity_str(chaos_factor)))
    dwg.add(svgwrite.shapes.Circle(center=(x + square_size - offset, y + square_size - offset), r=radius, fill=foreground, opacity=get_random_opacity_str(chaos_factor)))

def draw_cross(dwg_group, x, y, square_size, foreground, background, chaos_factor):
    dwg_group.add(svgwrite.shapes.Rect((x, y), (square_size, square_size), fill=background))
    is_plus = random.random() < 0.5
    thickness_factor = random.uniform(0.25 - chaos_factor * 0.1, 0.4 + chaos_factor * 0.1)
    thickness = square_size * thickness_factor
    
    transform_str = get_random_rotation_transform(chaos_factor / 2, x + square_size/2, y + square_size/2)
    # svgwrite handles transform=None by omitting the attribute, which is correct.
    cross_elements = dwg_group.add(svgwrite.container.Group(transform=transform_str, opacity=get_random_opacity_str(chaos_factor)))


    if is_plus:
        cross_elements.add(svgwrite.shapes.Rect((x, y + (square_size - thickness)/2), (square_size, thickness), fill=foreground))
        cross_elements.add(svgwrite.shapes.Rect((x + (square_size - thickness)/2, y), (thickness, square_size), fill=foreground))
    else: 
        line_width = thickness * 0.8 
        p1_d1, p2_d1 = (x, y), (x + square_size, y + square_size)
        dx1, dy1 = p2_d1[0] - p1_d1[0], p2_d1[1] - p1_d1[1]
        len1 = (dx1**2 + dy1**2)**0.5
        if len1 == 0: len1 = 1
        nx1, ny1 = -dy1/len1, dx1/len1
        poly1_pts = [
            (p1_d1[0] + nx1*line_width/2, p1_d1[1] + ny1*line_width/2), (p2_d1[0] + nx1*line_width/2, p2_d1[1] + ny1*line_width/2),
            (p2_d1[0] - nx1*line_width/2, p2_d1[1] - ny1*line_width/2), (p1_d1[0] - nx1*line_width/2, p1_d1[1] - ny1*line_width/2)
        ]
        cross_elements.add(svgwrite.shapes.Polygon(poly1_pts, fill=foreground))
        p1_d2, p2_d2 = (x + square_size, y), (x, y + square_size)
        dx2, dy2 = p2_d2[0] - p1_d2[0], p2_d2[1] - p1_d2[1]
        len2 = (dx2**2 + dy2**2)**0.5
        if len2 == 0: len2 = 1
        nx2, ny2 = -dy2/len2, dx2/len2
        poly2_pts = [
            (p1_d2[0] + nx2*line_width/2, p1_d2[1] + ny2*line_width/2), (p2_d2[0] + nx2*line_width/2, p2_d2[1] + ny2*line_width/2),
            (p2_d2[0] - nx2*line_width/2, p2_d2[1] - ny2*line_width/2), (p1_d2[0] - nx2*line_width/2, p1_d2[1] - ny2*line_width/2)
        ]
        cross_elements.add(svgwrite.shapes.Polygon(poly2_pts, fill=foreground))


def draw_half_square(dwg_group, x, y, square_size, foreground, background, chaos_factor):
    dwg_group.add(svgwrite.shapes.Rect((x, y), (square_size, square_size), fill=background))
    shape = dwg_group.add(svgwrite.container.Group(opacity=get_random_opacity_str(chaos_factor)))
    direction = random.choice(['top', 'right', 'bottom', 'left'])
    points = []
    if direction == 'top': points = [(x, y), (x + square_size, y), (x + square_size, y + square_size/2), (x, y + square_size/2)]
    elif direction == 'right': points = [(x + square_size/2, y), (x + square_size, y), (x + square_size, y + square_size), (x + square_size/2, y + square_size)]
    elif direction == 'bottom': points = [(x, y + square_size/2), (x + square_size, y + square_size/2), (x + square_size, y + square_size), (x, y + square_size)]
    else:  points = [(x, y), (x + square_size/2, y), (x + square_size/2, y + square_size), (x, y + square_size)]
    shape.add(svgwrite.shapes.Polygon(points, fill=foreground))

def draw_diagonal_square(dwg_group, x, y, square_size, foreground, background, chaos_factor):
    dwg_group.add(svgwrite.shapes.Rect((x, y), (square_size, square_size), fill=background))
    shape = dwg_group.add(svgwrite.container.Group(opacity=get_random_opacity_str(chaos_factor)))
    is_top_left_to_bottom_right = random.random() < 0.5
    points = []
    if is_top_left_to_bottom_right: points = [(x, y), (x + square_size, y + square_size), (x, y + square_size)]
    else: points = [(x + square_size, y), (x + square_size, y + square_size), (x, y)]
    if random.random() < chaos_factor * 0.5:
        idx_to_move = random.randint(0,2)
        points[idx_to_move] = (points[idx_to_move][0] + (random.random()-0.5) * square_size * 0.1 * chaos_factor,
                                points[idx_to_move][1] + (random.random()-0.5) * square_size * 0.1 * chaos_factor)
    shape.add(svgwrite.shapes.Polygon(points, fill=foreground))

def draw_quarter_circle(dwg_group, x, y, square_size, foreground, background, chaos_factor):
    dwg_group.add(svgwrite.shapes.Rect((x, y), (square_size, square_size), fill=background))
    shape = dwg_group.add(svgwrite.container.Group(opacity=get_random_opacity_str(chaos_factor)))
    corner = random.choice(['top-left', 'top-right', 'bottom-right', 'bottom-left'])
    path = svgwrite.path.Path(fill=foreground)
    r_factor = random.uniform(0.8 - chaos_factor*0.2, 1.2 + chaos_factor*0.2)
    r = square_size * r_factor 
    r = max(square_size*0.1, min(r, square_size*1.5))

    if corner == 'top-left': path.push(f"M {x} {y} L {x+r} {y} A {r} {r} 0 0 0 {x} {y+r} Z")
    elif corner == 'top-right': path.push(f"M {x+square_size} {y} L {x+square_size-r} {y} A {r} {r} 0 0 0 {x+square_size} {y+r} Z")
    elif corner == 'bottom-right': path.push(f"M {x+square_size} {y+square_size} L {x+square_size-r} {y+square_size} A {r} {r} 0 0 0 {x+square_size} {y+square_size-r} Z") # sweep flag was 1, changed to 0
    else: path.push(f"M {x} {y+square_size} L {x+r} {y+square_size} A {r} {r} 0 0 0 {x} {y+square_size-r} Z") # sweep flag was 1, changed to 0
    shape.add(path)

def draw_dots(dwg_group, x, y, square_size, foreground, background, chaos_factor):
    dwg_group.add(svgwrite.shapes.Rect((x, y), (square_size, square_size), fill=background))
    num_dots_choices = [4, 9, 16, 25 if chaos_factor > 0.5 else 16]
    num_dots_sqrt = int(random.choice(num_dots_choices)**0.5)
    rows, cols = num_dots_sqrt, num_dots_sqrt
    cell_size = square_size / rows
    for i in range(rows):
        for j in range(cols):
            if random.random() < chaos_factor * 0.2: continue
            dot_radius = cell_size * random.uniform(0.2, 0.4 + chaos_factor * 0.1)
            center_x = x + (i + 0.5) * cell_size + (random.random() - 0.5) * cell_size * 0.2 * chaos_factor
            center_y = y + (j + 0.5) * cell_size + (random.random() - 0.5) * cell_size * 0.2 * chaos_factor
            dwg_group.add(svgwrite.shapes.Circle(center=(center_x, center_y), r=max(1, dot_radius), fill=foreground, opacity=get_random_opacity_str(chaos_factor)))

def draw_letter_block(dwg_group, x, y, square_size, foreground, background, chaos_factor):
    dwg_group.add(svgwrite.shapes.Rect((x, y), (square_size, square_size), fill=background))
    characters = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 
                 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z',
                 '0', '1', '2', '3', '4', '5', '6', '7', '8', '9',
                 '+', '-', '*', '/', '=', '#', '@', '&', '%', '$', '!', '?']
    character = random.choice(characters)
    font_size_factor = random.uniform(0.6 - chaos_factor * 0.1, 0.9 + chaos_factor * 0.1)
    font_size = max(10, square_size * font_size_factor)
    
    # Calculate center for rotation more accurately for text
    text_center_x = x + square_size / 2
    text_center_y = y + square_size / 2 # dominant-baseline="central" will handle vertical alignment from this point

    transform_str = get_random_rotation_transform(chaos_factor * 0.8, text_center_x, text_center_y)
    
    text_element = svgwrite.text.Text(
        character, 
        insert=(text_center_x, text_center_y), 
        font_family="monospace, Courier, 'Courier New'", 
        font_size=f"{font_size}px", 
        font_weight="bold", 
        fill=foreground,
        text_anchor="middle", 
        dominant_baseline="central",
        opacity=get_random_opacity_str(chaos_factor),
        transform=transform_str  # Always valid due to updated get_random_rotation_transform
    )
    dwg_group.add(text_element)

def draw_concentric_circles(dwg_group, x, y, square_size, foreground, background, chaos_factor):
    dwg_group.add(svgwrite.shapes.Rect((x, y), (square_size, square_size), fill=background))
    center_x, center_y = x + square_size / 2, y + square_size / 2
    num_circles = random.randint(2 + int(chaos_factor*2), 5 + int(chaos_factor*3))
    max_radius = square_size / 2 * random.uniform(0.85, 1.0)
    current_color_is_fg = True
    for i in range(num_circles, 0, -1):
        radius = max_radius * (i / num_circles)
        if radius < 1: continue 
        color = foreground if current_color_is_fg else background
        offset_x_val = (random.random() - 0.5) * square_size * 0.05 * chaos_factor
        offset_y_val = (random.random() - 0.5) * square_size * 0.05 * chaos_factor
        dwg_group.add(svgwrite.shapes.Circle(center=(center_x + offset_x_val, center_y + offset_y_val), r=radius, fill=color, opacity=get_random_opacity_str(chaos_factor)))
        current_color_is_fg = not current_color_is_fg

def draw_stripes(dwg_group, x, y, square_size, foreground, background, chaos_factor):
    dwg_group.add(svgwrite.shapes.Rect((x, y), (square_size, square_size), fill=background))
    num_stripes = random.randint(3 + int(chaos_factor*2), 7 + int(chaos_factor*4))
    is_horizontal = random.choice([True, False])
    stripe_elements = dwg_group.add(svgwrite.container.Group(opacity=get_random_opacity_str(chaos_factor)))
    for i in range(num_stripes):
        stripe_color = foreground if (i % 2 == 0 or random.random() < chaos_factor * 0.3) else background
        if stripe_color == background and random.random() < chaos_factor * 0.6: continue
        
        base_thickness = square_size / num_stripes
        thickness_variation = base_thickness * random.uniform(0.7 - chaos_factor * 0.2, 1.3 + chaos_factor * 0.2)
        stripe_thickness = max(1, thickness_variation) 

        if is_horizontal:
            y_pos = y + i * base_thickness 
            stripe_elements.add(svgwrite.shapes.Rect((x, y_pos), (square_size, stripe_thickness), fill=stripe_color))
        else: 
            x_pos = x + i * base_thickness
            stripe_elements.add(svgwrite.shapes.Rect((x_pos, y), (stripe_thickness, square_size), fill=stripe_color))

def draw_rotated_shape(dwg_group, x, y, square_size, foreground, background, chaos_factor):
    dwg_group.add(svgwrite.shapes.Rect((x, y), (square_size, square_size), fill=background))
    shape_type = random.choice(['rect', 'circle', 'ellipse'])
    inner_size_factor = random.uniform(0.5 - chaos_factor * 0.1, 0.8 + chaos_factor * 0.1)
    inner_size = square_size * inner_size_factor
    center_x, center_y = x + square_size / 2, y + square_size / 2
    
    transform_str = get_random_rotation_transform(chaos_factor * 1.5, center_x, center_y)
    shape_element_group = dwg_group.add(svgwrite.container.Group(
        transform=transform_str,
        opacity=get_random_opacity_str(chaos_factor)
    ))

    if shape_type == 'rect':
        rect_w = inner_size * random.uniform(0.7, 1.3)
        rect_h = inner_size * random.uniform(0.7, 1.3)
        rect_w = max(1, min(rect_w, square_size * 0.9))
        rect_h = max(1, min(rect_h, square_size * 0.9))
        shape_element_group.add(svgwrite.shapes.Rect(
            insert=(center_x - rect_w / 2, center_y - rect_h / 2),
            size=(rect_w, rect_h), fill=foreground
        ))
    elif shape_type == 'circle':
        shape_element_group.add(svgwrite.shapes.Circle(
            center=(center_x, center_y), r=max(1, inner_size / 2), fill=foreground
        ))
    elif shape_type == 'ellipse':
        rx_val = inner_size / 2 * random.uniform(0.7, 1.3)
        ry_val = inner_size / 2 * random.uniform(0.7, 1.3)
        shape_element_group.add(svgwrite.shapes.Ellipse(
            center=(center_x, center_y), r=(max(1, rx_val), max(1, ry_val)), fill=foreground
        ))

def draw_wavy_lines(dwg_group, x, y, square_size, foreground, background, chaos_factor):
    dwg_group.add(svgwrite.shapes.Rect((x, y), (square_size, square_size), fill=background))
    num_lines = random.randint(2 + int(chaos_factor*2), 5 + int(chaos_factor*3))
    is_horizontal = random.choice([True, False])
    stroke_w = max(1, square_size * random.uniform(0.02, 0.05 + chaos_factor * 0.05))
    for i in range(num_lines):
        path = svgwrite.path.Path(stroke=foreground, fill='none', stroke_width=stroke_w, opacity=get_random_opacity_str(chaos_factor))
        amplitude = square_size * random.uniform(0.05, 0.2 + chaos_factor * 0.1)
        frequency = random.uniform(0.5, 2.0 + chaos_factor)
        num_segments = random.randint(3, 7)
        if is_horizontal:
            start_y_line = y + (square_size / (num_lines + 1)) * (i + 1)
            path.push('M', x, start_y_line)
            for j_seg in range(num_segments):
                cx1 = x + (square_size / num_segments) * j_seg + random.uniform(-10,10) * chaos_factor * (square_size/100)
                cy1 = start_y_line + amplitude * sin(j_seg * pi * frequency / num_segments + random.random()*chaos_factor) + random.uniform(-5,5) * chaos_factor * (square_size/100)
                cx2 = x + (square_size / num_segments) * (j_seg + 0.5) + random.uniform(-10,10) * chaos_factor* (square_size/100)
                cy2 = start_y_line - amplitude * sin((j_seg + 0.5) * pi * frequency / num_segments + random.random()*chaos_factor) + random.uniform(-5,5) * chaos_factor* (square_size/100)
                ex = x + (square_size / num_segments) * (j_seg + 1)
                ey = start_y_line 
                if j_seg < num_segments -1 :
                     ey = start_y_line + amplitude * sin((j_seg+1) * pi * frequency / num_segments + random.random()*chaos_factor)
                path.push('C', round(cx1,1), round(cy1,1), round(cx2,1), round(cy2,1), round(ex,1), round(ey,1))
        else: 
            start_x_line = x + (square_size / (num_lines + 1)) * (i + 1)
            path.push('M', start_x_line, y)
            for j_seg in range(num_segments):
                cy1 = y + (square_size / num_segments) * j_seg + random.uniform(-10,10) * chaos_factor* (square_size/100)
                cx1 = start_x_line + amplitude * sin(j_seg * pi * frequency / num_segments + random.random()*chaos_factor) + random.uniform(-5,5) * chaos_factor* (square_size/100)
                cy2 = y + (square_size / num_segments) * (j_seg + 0.5) + random.uniform(-10,10) * chaos_factor* (square_size/100)
                cx2 = start_x_line - amplitude * sin((j_seg + 0.5) * pi * frequency / num_segments + random.random()*chaos_factor) + random.uniform(-5,5) * chaos_factor* (square_size/100)
                ey = y + (square_size / num_segments) * (j_seg + 1)
                ex = start_x_line
                if j_seg < num_segments -1 :
                    ex = start_x_line + amplitude * sin((j_seg+1) * pi * frequency / num_segments + random.random()*chaos_factor)
                path.push('C', round(cx1,1), round(cy1,1), round(cx2,1), round(cy2,1), round(ex,1), round(ey,1))
        dwg_group.add(path)

# --- SVG Generation Function ---
def generate_art_svg_string(params):
    """Generates the SVG art as a string based on the provided parameters."""
    # Handle seed: use integer if provided, otherwise random.seed() handles None.
    seed_value = params.get('seed')
    if isinstance(seed_value, str) and seed_value.isdigit():
        random.seed(int(seed_value))
    elif isinstance(seed_value, int):
        random.seed(seed_value)
    else:
        if seed_value is not None and seed_value != '': # If it's a non-empty, non-digit string
            print(f"Warning: Invalid seed value '{seed_value}'. Using random seed.")
        random.seed() # Default to random if no seed, empty, or invalid string

    num_cols = params['cols']
    num_rows = params['rows']
    square_size = params['square_size']
    
    current_palette_list = params['current_palette_list']
    if not current_palette_list:
        print("Error: No color palette data provided for generation.")
        return None 
    selected_palette_data = current_palette_list[params['palette_index']]

    block_styles_names = params['block_styles'] 
    chaos_factor = params['chaos_factor']
        
    svg_width = num_cols * square_size
    svg_height = num_rows * square_size
    
    dwg = svgwrite.Drawing(filename=None, size=(f"{svg_width}px", f"{svg_height}px"), profile='full')
    dwg.defs.add(dwg.style("svg * { shape-rendering: crispEdges; }")) 
    
    bg_colors = create_background_colors(selected_palette_data)
    gradient_id = f"bg_grad_{random.randint(1000,9999)}"
    gradient = dwg.defs.add(dwg.radialGradient(id=gradient_id, cx="50%", cy="50%", r="75%", fx="50%", fy="50%"))
    gradient.add_stop_color(0, bg_colors["bg_inner"])
    gradient.add_stop_color(1, bg_colors["bg_outer"])
    dwg.add(svgwrite.shapes.Rect((0, 0), (svg_width, svg_height), fill=f"url(#{gradient_id})"))
    
    style_function_map = {
        'circle': draw_circle, 'opposite_circles': draw_opposite_circles, 'cross': draw_cross,
        'half_square': draw_half_square, 'diagonal_square': draw_diagonal_square,
        'quarter_circle': draw_quarter_circle, 'dots': draw_dots, 'letter_block': draw_letter_block,
        'concentric_circles': draw_concentric_circles, 'stripes': draw_stripes,
        'rotated_shape': draw_rotated_shape, 'wavy_lines': draw_wavy_lines,
    }
    
    active_style_funcs = [style_function_map[name] for name in block_styles_names if name in style_function_map]
    if not active_style_funcs: active_style_funcs = list(style_function_map.values())

    grid_group = dwg.add(dwg.g(id="grid_elements")) 

    for r_idx in range(num_rows):
        for c_idx in range(num_cols):
            colors = get_two_colors(selected_palette_data)
            draw_func = random.choice(active_style_funcs)
            cell_group = grid_group.add(dwg.g(id=f"cell_{c_idx}_{r_idx}"))
            draw_func(cell_group, c_idx * square_size, r_idx * square_size, square_size, 
                      colors["foreground"], colors["background"], chaos_factor)
    
    if params['big_block_enabled']:
        multiplier = params['big_block_size']
        if num_rows >= multiplier and num_cols >= multiplier:
            bb_col_idx = random.randint(0, num_cols - multiplier) 
            bb_row_idx = random.randint(0, num_rows - multiplier) 
            bb_svg_x = bb_col_idx * square_size
            bb_svg_y = bb_row_idx * square_size
            big_square_actual_size = multiplier * square_size
            
            colors = get_two_colors(selected_palette_data)
            draw_func_big = random.choice(active_style_funcs) 
            
            big_block_group = dwg.add(dwg.g(id="big_block_element")) 
            draw_func_big(big_block_group, bb_svg_x, bb_svg_y, big_square_actual_size, 
                          colors["foreground"], colors["background"], chaos_factor)
        else:
            print(f"Skipping big block: Grid size ({num_rows}x{num_cols}) too small for multiplier {multiplier}.")
            
    return dwg.tostring()


# --- PyQt6 UI Application ---
class ArtGridWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_palette_list = [] 
        self.current_palette_file_path = "" 
        self.initUI()
        self.load_initial_palettes()

    def initUI(self):
        self.setWindowTitle("Art Grid Generator (PyQt6)")
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

        grid_group = QGroupBox("Grid & Size Parameters")
        grid_layout = QFormLayout()
        self.rows_spin = QSpinBox()
        self.rows_spin.setRange(1, 100); self.rows_spin.setValue(random.randint(4,8))
        grid_layout.addRow("Number of Rows:", self.rows_spin)
        self.cols_spin = QSpinBox()
        self.cols_spin.setRange(1, 100); self.cols_spin.setValue(random.randint(4,8))
        grid_layout.addRow("Number of Columns:", self.cols_spin)
        self.square_size_spin = QSpinBox()
        self.square_size_spin.setRange(10, 500); self.square_size_spin.setValue(100); self.square_size_spin.setSingleStep(10)
        grid_layout.addRow("Square Size (px):", self.square_size_spin)
        grid_group.setLayout(grid_layout)
        main_layout.addWidget(grid_group)

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

        styles_group = QGroupBox("Block Styles (select one or more)")
        styles_scroll_area = QScrollArea()
        styles_scroll_area.setWidgetResizable(True)
        styles_widget_container = QWidget() 
        self.styles_layout = QVBoxLayout(styles_widget_container) 
        
        self.all_possible_style_names = [ 
            'circle', 'opposite_circles', 'cross', 'half_square', 
            'diagonal_square', 'quarter_circle', 'dots', 'letter_block',
            'concentric_circles', 'stripes', 'rotated_shape', 'wavy_lines'
        ]
        self.style_checkboxes = {}
        for style_name in self.all_possible_style_names:
            cb = QCheckBox(style_name.replace("_", " ").title())
            cb.setChecked(True) 
            self.styles_layout.addWidget(cb)
            self.style_checkboxes[style_name] = cb
        
        styles_scroll_area.setWidget(styles_widget_container)
        styles_group_layout_wrapper = QVBoxLayout() 
        styles_group_layout_wrapper.addWidget(styles_scroll_area)
        styles_group.setLayout(styles_group_layout_wrapper)
        main_layout.addWidget(styles_group)
        styles_scroll_area.setMinimumHeight(150)

        misc_group = QGroupBox("Big Block & Chaos")
        misc_layout = QFormLayout()
        self.big_block_check = QCheckBox("Enable Big Block"); self.big_block_check.setChecked(True)
        misc_layout.addRow(self.big_block_check)
        self.big_block_size_combo = QComboBox(); self.big_block_size_combo.addItems(["2", "3"]) 
        misc_layout.addRow("Big Block Size Multiplier:", self.big_block_size_combo)
        
        self.chaos_factor_spin = QDoubleSpinBox()
        self.chaos_factor_spin.setRange(0.0, 1.0); self.chaos_factor_spin.setSingleStep(0.05); self.chaos_factor_spin.setValue(0.3)
        misc_layout.addRow("Chaos Factor:", self.chaos_factor_spin)

        self.seed_edit = QLineEdit(); self.seed_edit.setPlaceholderText("Integer or blank for random")
        misc_layout.addRow("Random Seed:", self.seed_edit)
        misc_group.setLayout(misc_layout)
        main_layout.addWidget(misc_group)

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
        selected_styles = [name for name, cb in self.style_checkboxes.items() if cb.isChecked()]
        if not selected_styles:
            QMessageBox.warning(self, "No Styles Selected", "At least one block style must be selected. Defaulting to all styles.")
            selected_styles = self.all_possible_style_names
            for cb in self.style_checkboxes.values(): cb.setChecked(True)

        if not self.current_palette_list or not isinstance(self.current_palette_list, list) or len(self.current_palette_list) == 0:
            QMessageBox.critical(self, "Palette Error", "No valid color palettes are loaded. Cannot generate.")
            return None
        
        palette_idx = self.palette_index_spin.value()
        if not (0 <= palette_idx < len(self.current_palette_list)):
             QMessageBox.critical(self, "Palette Error", f"Invalid palette index ({palette_idx}). Please check palette loading.")
             return None
        
        seed_text = self.seed_edit.text().strip()
        valid_seed_param = None # Use this to pass to generate_art_svg_string
        if seed_text:
            try:
                valid_seed_param = int(seed_text)
            except ValueError:
                QMessageBox.warning(self, "Invalid Seed", "Seed must be an integer. Using random seed for this generation.")
                self.seed_edit.clear() 
                # valid_seed_param remains None, so generate_art_svg_string will use random.seed()

        params = {
            'rows': self.rows_spin.value(), 'cols': self.cols_spin.value(),
            'square_size': self.square_size_spin.value(),
            'current_palette_list': self.current_palette_list,
            'palette_index': palette_idx, 'block_styles': selected_styles,
            'big_block_enabled': self.big_block_check.isChecked(),
            'big_block_size': int(self.big_block_size_combo.currentText()), 
            'chaos_factor': self.chaos_factor_spin.value(),
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

        output_path, _ = QFileDialog.getSaveFileName(self, "Save Artwork As", "art_grid", "SVG Files (*.svg);;All Files (*)")
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
