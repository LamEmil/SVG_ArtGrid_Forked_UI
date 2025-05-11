import os
import sys
import json
import random
import colorsys
from math import pi, sin, cos, atan2, degrees
import io

import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont

# --- Core Art Generation Logic using Pillow ---

DEFAULT_PALETTES_DATA = [
    ["#FF6B6B", "#FFD166", "#06D6A0", "#118AB2", "#073B4C"],
    ["#FAD02C", "#F2A104", "#E87007", "#D53903", "#A01F02"],
    ["#22223B", "#4A4E69", "#9A8C98", "#C9ADA7", "#F2E9E4"],
    ["#003049", "#D62828", "#F77F00", "#FCBF49", "#EAE2B7"]
]

# Generate all possible triadic color palettes
def generate_triadic_palettes():
    triadic_palettes = []
    for r in range(0, 256, 64):
        for g in range(0, 256, 64):
            for b in range(0, 256, 64):
                base_color = (r, g, b)
                triadic1 = ((g + 128) % 256, (b + 128) % 256, (r + 128) % 256)
                triadic2 = ((b + 128) % 256, (r + 128) % 256, (g + 128) % 256)
                triadic_palettes.append([
                    f"#{r:02X}{g:02X}{b:02X}",
                    f"#{triadic1[0]:02X}{triadic1[1]:02X}{triadic1[2]:02X}",
                    f"#{triadic2[0]:02X}{triadic2[1]:02X}{triadic2[2]:02X}"
                ])
    return triadic_palettes

DEFAULT_PALETTES_DATA.extend(generate_triadic_palettes())

ALL_POSSIBLE_STYLE_NAMES = [
    'circle', 'opposite_circles', 'cross', 'half_square',
    'diagonal_square', 'quarter_circle', 'dots', 'letter_block',
    'concentric_circles', 'stripes', 'rotated_shape', 'wavy_lines'
]

# --- Pillow Drawing Helper Functions ---
def hex_to_rgba(hex_color, alpha=255):
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 3:
        hex_color = "".join([c*2 for c in hex_color])
    if len(hex_color) != 6:
        # Fallback for invalid hex
        return (0,0,0, alpha)
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return (r, g, b, alpha)

def get_random_alpha(chaos_factor):
    if random.random() < chaos_factor * 0.5:
        return random.randint(150, 240) # Alpha between ~60% and ~95%
    return 255 # Full opacity

def get_random_rotation_angle(chaos_factor):
    if random.random() < chaos_factor:
        return random.choice([0, 15, 30, 45, 60, 75, 90, -15, -30, -45, -60, -75])
    return 0

def draw_rotated_image(target_image, shape_image, x, y, angle, pivot=None):
    """Pastes a rotated image onto the target image."""
    if angle == 0:
        target_image.paste(shape_image, (int(x), int(y)), shape_image) # Use shape_image as mask for transparency
        return

    rotated_shape = shape_image.rotate(angle, expand=True, resample=Image.BICUBIC)
    
    # Calculate new position for the rotated image to keep it centered around the original pivot
    # By default, pivot is the center of the shape_image
    if pivot is None:
        pivot_x_shape, pivot_y_shape = shape_image.width / 2, shape_image.height / 2
    else:
        pivot_x_shape, pivot_y_shape = pivot

    # Center of the expanded rotated_shape
    rotated_center_x, rotated_center_y = rotated_shape.width / 2, rotated_shape.height / 2
    
    # Original top-left of shape_image was (x,y) on target_image
    # We want the original pivot point on shape_image to remain at (x+pivot_x_shape, y+pivot_y_shape) on target
    
    paste_x = x + pivot_x_shape - rotated_center_x
    paste_y = y + pivot_y_shape - rotated_center_y
    
    target_image.paste(rotated_shape, (int(paste_x), int(paste_y)), rotated_shape)


# --- Pillow Shape Drawing Functions ---

def pil_create_background_colors(color_palette): # Simplified from SVG version for Pillow
    if not color_palette or len(color_palette) < 2:
        return {"bg_inner": hex_to_rgba("#EEEEEE"), "bg_outer": hex_to_rgba("#DDDDDD")}
    try:
        c1_hex = color_palette[0]
        c2_hex = color_palette[1]

        r1, g1, b1, _ = hex_to_rgba(c1_hex)
        r2, g2, b2, _ = hex_to_rgba(c2_hex)
    except Exception as e:
        print(f"Warning: Invalid hex color in palette for background ({e}). Using defaults.")
        return {"bg_inner": hex_to_rgba("#EEEEEE"), "bg_outer": hex_to_rgba("#DDDDDD")}

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
    bg_inner = (int(r_light*255), int(g_light*255), int(b_light*255), 255)

    l_dark = max(0, l_l - 0.1)
    r_dark, g_dark, b_dark = colorsys.hls_to_rgb(h_l, l_dark, s_l)
    bg_outer = (int(r_dark*255), int(g_dark*255), int(b_dark*255), 255)

    return {"bg_inner": bg_inner, "bg_outer": bg_outer}


def pil_get_two_colors(color_palette, chaos_factor):
    alpha = get_random_alpha(chaos_factor)
    if not color_palette:
        return {"foreground": (51,51,51, alpha), "background": (204,204,204, 255)} # Pillow uses RGBA

    valid_colors_hex = [c for c in color_palette if isinstance(c, str) and c.startswith("#") and len(c.lstrip('#')) in [3,6]]
    if not valid_colors_hex:
        return {"foreground": (51,51,51, alpha), "background": (204,204,204, 255)}
    
    bg_hex = random.choice(valid_colors_hex)
    background_rgba = hex_to_rgba(bg_hex, 255) # Background usually full opacity

    remaining_colors_hex = [c for c in valid_colors_hex if c != bg_hex]
    fg_hex = random.choice(remaining_colors_hex) if remaining_colors_hex else valid_colors_hex[0]
    foreground_rgba = hex_to_rgba(fg_hex, alpha)
    
    return {"foreground": foreground_rgba, "background": background_rgba}


def draw_pil_circle(draw, x, y, square_size, foreground_rgba, background_rgba, chaos_factor):
    draw.rectangle([x, y, x + square_size, y + square_size], fill=background_rgba)
    radius_factor = random.uniform(0.8 - chaos_factor * 0.2, 1.0)
    r = (square_size / 2) * radius_factor
    cx, cy = x + square_size / 2, y + square_size / 2
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=foreground_rgba)

    if random.random() < 0.3 + chaos_factor * 0.3:
        inner_r_factor = random.uniform(0.2, 0.5)
        inner_r = (square_size / 2) * inner_r_factor
        # Draw inner circle with background color (partially transparent if fg was)
        inner_bg_alpha = foreground_rgba[3] if len(foreground_rgba) == 4 else 255
        inner_bg_color = (background_rgba[0], background_rgba[1], background_rgba[2], inner_bg_alpha)

        draw.ellipse([cx - inner_r, cy - inner_r, cx + inner_r, cy + inner_r], fill=inner_bg_color)
        if random.random() < chaos_factor * 0.5:
            tiny_r = inner_r * 0.5
            draw.ellipse([cx - tiny_r, cy - tiny_r, cx + tiny_r, cy + tiny_r], fill=foreground_rgba)


def draw_pil_opposite_circles(draw, x, y, square_size, foreground_rgba, background_rgba, chaos_factor):
    draw.rectangle([x, y, x + square_size, y + square_size], fill=background_rgba)
    r_factor = random.uniform(0.4, 0.6)
    radius = square_size * r_factor
    offset = square_size / 2 
    

    
    cx1, cy1 = x + radius, y + radius
    cx2, cy2 = x + square_size - radius, y + square_size - radius
    
    center_offset = square_size / 2 
    cx_main = x + center_offset
    cy_main = y + center_offset

    q_ss = square_size / 4
    q_radius = q_ss * random.uniform(0.8, 1.2)
    draw.ellipse([x + q_ss - q_radius, y + q_ss - q_radius, x + q_ss + q_radius, y + q_ss + q_radius], fill=foreground_rgba)
    draw.ellipse([x + 3*q_ss - q_radius, y + 3*q_ss - q_radius, x + 3*q_ss + q_radius, y + 3*q_ss + q_radius], fill=foreground_rgba)


def draw_pil_cross(main_draw, x, y, square_size, foreground_rgba, background_rgba, chaos_factor):
    # Draw background for the cell on the main image
    main_draw.rectangle([x, y, x + square_size, y + square_size], fill=background_rgba)

    # Create a temporary transparent image for the cross
    cross_img = Image.new('RGBA', (square_size, square_size), (0,0,0,0))
    draw_temp = ImageDraw.Draw(cross_img)

    is_plus = random.random() < 0.5
    thickness_factor = random.uniform(0.25 - chaos_factor * 0.1, 0.4 + chaos_factor * 0.1)
    thickness = int(square_size * thickness_factor)

    if is_plus:
        draw_temp.rectangle([0, (square_size - thickness) // 2, square_size, (square_size + thickness) // 2], fill=foreground_rgba)
        draw_temp.rectangle([(square_size - thickness) // 2, 0, (square_size + thickness) // 2, square_size], fill=foreground_rgba)
    else: # X shape
        line_width = int(thickness * 0.8)
        if line_width < 1: line_width = 1
        draw_temp.line([0, 0, square_size, square_size], fill=foreground_rgba, width=line_width)
        draw_temp.line([square_size, 0, 0, square_size], fill=foreground_rgba, width=line_width)
    
    angle = get_random_rotation_angle(chaos_factor / 2)
    # Paste the rotated cross onto the main image
    draw_rotated_image(main_draw._image, cross_img, x, y, angle)


def draw_pil_half_square(draw, x, y, square_size, foreground_rgba, background_rgba, chaos_factor):
    draw.rectangle([x, y, x + square_size, y + square_size], fill=background_rgba)
    direction = random.choice(['top', 'right', 'bottom', 'left'])
    if direction == 'top':
        draw.rectangle([x, y, x + square_size, y + square_size / 2], fill=foreground_rgba)
    elif direction == 'right':
        draw.rectangle([x + square_size / 2, y, x + square_size, y + square_size], fill=foreground_rgba)
    elif direction == 'bottom':
        draw.rectangle([x, y + square_size / 2, x + square_size, y + square_size], fill=foreground_rgba)
    else:  # left
        draw.rectangle([x, y, x + square_size / 2, y + square_size], fill=foreground_rgba)


def draw_pil_diagonal_square(draw, x, y, square_size, foreground_rgba, background_rgba, chaos_factor):
    draw.rectangle([x, y, x + square_size, y + square_size], fill=background_rgba)
    is_top_left_to_bottom_right = random.random() < 0.5
    points = []
    if is_top_left_to_bottom_right:
        points = [(x, y), (x + square_size, y + square_size), (x, y + square_size)]
    else:
        points = [(x + square_size, y), (x + square_size, y + square_size), (x, y)]
    
    if random.random() < chaos_factor * 0.5: # Slight jitter
        idx_to_move = random.randint(0,2)
        jitter_x = (random.random()-0.5) * square_size * 0.1 * chaos_factor
        jitter_y = (random.random()-0.5) * square_size * 0.1 * chaos_factor
        points[idx_to_move] = (points[idx_to_move][0] + jitter_x, points[idx_to_move][1] + jitter_y)
    draw.polygon(points, fill=foreground_rgba)


def draw_pil_quarter_circle(draw, x, y, square_size, foreground_rgba, background_rgba, chaos_factor):
    draw.rectangle([x, y, x + square_size, y + square_size], fill=background_rgba)
    corner = random.choice(['top-left', 'top-right', 'bottom-right', 'bottom-left'])
    # Pieslice can make quarter circles
    bbox = [x, y, x + square_size, y + square_size]
    if corner == 'top-left':
        draw.pieslice(bbox, start=180, end=270, fill=foreground_rgba)
    elif corner == 'top-right':
        draw.pieslice(bbox, start=270, end=360, fill=foreground_rgba)
    elif corner == 'bottom-right':
        draw.pieslice(bbox, start=0, end=90, fill=foreground_rgba)
    else:  # bottom-left
        draw.pieslice(bbox, start=90, end=180, fill=foreground_rgba)


def draw_pil_dots(draw, x, y, square_size, foreground_rgba, background_rgba, chaos_factor):
    draw.rectangle([x, y, x + square_size, y + square_size], fill=background_rgba)
    num_dots_choices = [4, 9, 16, 25 if chaos_factor > 0.5 else 16]
    num_dots_sqrt = int(random.choice(num_dots_choices)**0.5)
    rows_dots, cols_dots = num_dots_sqrt, num_dots_sqrt
    cell_s = square_size / rows_dots
    for i in range(rows_dots):
        for j_inner in range(cols_dots):
            if random.random() < chaos_factor * 0.2: continue
            dot_r = cell_s * random.uniform(0.2, 0.4 + chaos_factor * 0.1) / 2 # Pillow uses radius for ellipse
            center_x = x + (i + 0.5) * cell_s + (random.random() - 0.5) * cell_s * 0.2 * chaos_factor
            center_y = y + (j_inner + 0.5) * cell_s + (random.random() - 0.5) * cell_s * 0.2 * chaos_factor
            if dot_r < 1: dot_r = 1
            draw.ellipse([center_x - dot_r, center_y - dot_r, center_x + dot_r, center_y + dot_r], fill=foreground_rgba)


def draw_pil_letter_block(main_draw, x, y, square_size, foreground_rgba, background_rgba, chaos_factor):
    main_draw.rectangle([x, y, x + square_size, y + square_size], fill=background_rgba)
    
    characters = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M',
                  'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z',
                  '0', '1', '2', '3', '4', '5', '6', '7', '8', '9',
                  '+', '-', '*', '/', '=', '#', '@', '&', '%', '$', '!', '?']
    character = random.choice(characters)
    font_size_factor = random.uniform(0.6 - chaos_factor * 0.1, 0.9 + chaos_factor * 0.1)
    font_size = max(10, int(square_size * font_size_factor))

    try:
        font = ImageFont.truetype("cour.ttf", font_size) # Courier New
    except IOError:
        try:
            font = ImageFont.truetype("arial.ttf", font_size) # Arial as fallback
        except IOError:
            font = ImageFont.load_default() # Default fallback

    # Create a temporary image for the text
    text_img = Image.new('RGBA', (square_size, square_size), (0,0,0,0))
    draw_temp = ImageDraw.Draw(text_img)
    
    # Get text size using textbbox for Pillow 9.2.0+ or textsize for older
    try:
        bbox = draw_temp.textbbox((0,0), character, font=font, anchor="lt") # Pillow 9.2.0+
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        # For anchor="mm", text_x/y is the center.
        text_x = square_size / 2
        text_y = square_size / 2
        draw_temp.text((text_x, text_y), character, font=font, fill=foreground_rgba, anchor="mm")

    except AttributeError: # Fallback for older Pillow versions
        text_width, text_height = draw_temp.textsize(character, font=font)
        text_x = (square_size - text_width) / 2
        text_y = (square_size - text_height) / 2
        draw_temp.text((text_x, text_y), character, font=font, fill=foreground_rgba)

    angle = get_random_rotation_angle(chaos_factor * 0.8)
    draw_rotated_image(main_draw._image, text_img, x, y, angle)


def draw_pil_concentric_circles(draw, x, y, square_size, foreground_rgba, background_rgba, chaos_factor):
    draw.rectangle([x, y, x + square_size, y + square_size], fill=background_rgba)
    center_x, center_y = x + square_size / 2, y + square_size / 2
    num_circles = random.randint(2 + int(chaos_factor*2), 5 + int(chaos_factor*3))
    max_r = square_size / 2 * random.uniform(0.85, 1.0)
    current_color_is_fg = True

    for i in range(num_circles, 0, -1):
        radius = max_r * (i / num_circles)
        if radius < 1: continue
        
        # Apply chaos to alpha of the chosen color
        base_color = foreground_rgba if current_color_is_fg else background_rgba
        current_alpha = base_color[3] if len(base_color) == 4 else 255
        chaotic_alpha = get_random_alpha(chaos_factor)
        final_alpha = min(current_alpha, chaotic_alpha) # Don't exceed original alpha for bg
        color = (base_color[0], base_color[1], base_color[2], final_alpha)

        offset_x_val = (random.random() - 0.5) * square_size * 0.05 * chaos_factor
        offset_y_val = (random.random() - 0.5) * square_size * 0.05 * chaos_factor
        cx, cy = center_x + offset_x_val, center_y + offset_y_val
        draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=color)
        current_color_is_fg = not current_color_is_fg


def draw_pil_stripes(draw, x, y, square_size, foreground_rgba, background_rgba, chaos_factor):
    draw.rectangle([x, y, x + square_size, y + square_size], fill=background_rgba)
    num_stripes = random.randint(3 + int(chaos_factor*2), 7 + int(chaos_factor*4))
    is_horizontal = random.choice([True, False])

    for i in range(num_stripes):
        # Apply chaos to alpha for stripes
        base_stripe_color = foreground_rgba if (i % 2 == 0 or random.random() < chaos_factor * 0.3) else background_rgba
        current_alpha = base_stripe_color[3] if len(base_stripe_color) == 4 else 255
        chaotic_alpha = get_random_alpha(chaos_factor)
        final_alpha = min(current_alpha, chaotic_alpha)
        stripe_color = (base_stripe_color[0], base_stripe_color[1], base_stripe_color[2], final_alpha)

        if stripe_color == background_rgba and random.random() < chaos_factor * 0.6: continue

        base_thickness_exact = square_size / num_stripes
        thickness_variation = base_thickness_exact * random.uniform(0.7 - chaos_factor * 0.2, 1.3 + chaos_factor * 0.2)
        stripe_thickness = int(max(1, thickness_variation))

        if is_horizontal:
            y_pos = int(y + i * base_thickness_exact)
            draw.rectangle([x, y_pos, x + square_size, y_pos + stripe_thickness], fill=stripe_color)
        else:
            x_pos = int(x + i * base_thickness_exact)
            draw.rectangle([x_pos, y, x_pos + stripe_thickness, y + square_size], fill=stripe_color)


def draw_pil_rotated_shape(main_draw, x, y, square_size, foreground_rgba, background_rgba, chaos_factor):
    main_draw.rectangle([x, y, x + square_size, y + square_size], fill=background_rgba)
    
    shape_img = Image.new('RGBA', (square_size, square_size), (0,0,0,0))
    draw_temp = ImageDraw.Draw(shape_img)

    shape_type = random.choice(['rect', 'circle', 'ellipse']) # Ellipse used for circle too
    inner_size_factor = random.uniform(0.5 - chaos_factor * 0.1, 0.8 + chaos_factor * 0.1)
    inner_size = square_size * inner_size_factor
    
    shape_center_x, shape_center_y = square_size / 2, square_size / 2

    if shape_type == 'rect':
        rect_w = inner_size * random.uniform(0.7, 1.3)
        rect_h = inner_size * random.uniform(0.7, 1.3)
        rect_w = max(1, min(rect_w, square_size * 0.9))
        rect_h = max(1, min(rect_h, square_size * 0.9))
        draw_temp.rectangle([shape_center_x - rect_w/2, shape_center_y - rect_h/2, 
                             shape_center_x + rect_w/2, shape_center_y + rect_h/2], fill=foreground_rgba)
    elif shape_type == 'circle' or shape_type == 'ellipse': # Treat circle as ellipse
        rx_val = inner_size / 2 * random.uniform(0.7, 1.3 if shape_type == 'ellipse' else 1.0)
        ry_val = inner_size / 2 * random.uniform(0.7, 1.3 if shape_type == 'ellipse' else 1.0)
        rx_val = max(1, rx_val)
        ry_val = max(1, ry_val)
        draw_temp.ellipse([shape_center_x - rx_val, shape_center_y - ry_val, 
                           shape_center_x + rx_val, shape_center_y + ry_val], fill=foreground_rgba)

    angle = get_random_rotation_angle(chaos_factor * 1.5)
    draw_rotated_image(main_draw._image, shape_img, x, y, angle)


def draw_pil_wavy_lines(draw, x, y, square_size, foreground_rgba, background_rgba, chaos_factor):
    draw.rectangle([x, y, x + square_size, y + square_size], fill=background_rgba)
    num_lines = random.randint(2 + int(chaos_factor*2), 5 + int(chaos_factor*3))
    is_horizontal = random.choice([True, False])
    stroke_w = int(max(1, square_size * random.uniform(0.02, 0.05 + chaos_factor * 0.05)))

    for i in range(num_lines):
        amplitude = square_size * random.uniform(0.05, 0.2 + chaos_factor * 0.1)
        frequency = random.uniform(0.5, 2.0 + chaos_factor)
        num_segments = random.randint(10, 20) # More segments for smoother lines with Pillow
        
        points = []
        if is_horizontal:
            start_y_line = y + (square_size / (num_lines + 1)) * (i + 1)
            for j_seg in range(num_segments + 1):
                px = x + (square_size / num_segments) * j_seg
                py = start_y_line + amplitude * sin(j_seg * pi * frequency / num_segments + random.random()*chaos_factor)
                # Add minor jitter
                px += (random.random() - 0.5) * square_size * 0.01 * chaos_factor
                py += (random.random() - 0.5) * square_size * 0.01 * chaos_factor
                points.append((int(px), int(py)))
        else:
            start_x_line = x + (square_size / (num_lines + 1)) * (i + 1)
            for j_seg in range(num_segments + 1):
                py = y + (square_size / num_segments) * j_seg
                px = start_x_line + amplitude * sin(j_seg * pi * frequency / num_segments + random.random()*chaos_factor)
                px += (random.random() - 0.5) * square_size * 0.01 * chaos_factor
                py += (random.random() - 0.5) * square_size * 0.01 * chaos_factor
                points.append((int(px), int(py)))
        
        if len(points) > 1:
            draw.line(points, fill=foreground_rgba, width=stroke_w, joint="curve")


# --- Main Pillow Art Generation Function ---
def generate_art_image_pil(num_rows, num_cols, square_size,
                           palette_index, block_styles_str,
                           big_block_enabled, big_block_size_multiplier,
                           num_big_blocks, chaos_factor, seed_value):
    if seed_value is None or seed_value < 0:
        random.seed()
    else:
        random.seed(int(seed_value))

    if not (0 <= palette_index < len(DEFAULT_PALETTES_DATA)):
        palette_index = 0
    selected_palette_data = DEFAULT_PALETTES_DATA[palette_index]

    block_style_names_list = []
    if block_styles_str and block_styles_str.strip():
        block_style_names_list = [name.strip() for name in block_styles_str.split(',') if name.strip() in ALL_POSSIBLE_STYLE_NAMES]
    if not block_style_names_list:
        block_style_names_list = ALL_POSSIBLE_STYLE_NAMES

    img_width = num_cols * square_size
    img_height = num_rows * square_size
    
    # Create main image with RGBA to handle transparency of shapes
    final_image = Image.new('RGBA', (img_width, img_height), (255, 255, 255, 255)) # White opaque background
    main_draw = ImageDraw.Draw(final_image)

    bg_colors = pil_create_background_colors(selected_palette_data)
    main_draw.rectangle([0, 0, img_width, img_height], fill=bg_colors["bg_outer"])
    inset = max(10, int(min(img_width, img_height) * 0.1)) # Inset for inner color
    if img_width > 2*inset and img_height > 2*inset:
        main_draw.rectangle([inset, inset, img_width - inset, img_height - inset], fill=bg_colors["bg_inner"])


    style_function_map_pil = {
        'circle': draw_pil_circle, 'opposite_circles': draw_pil_opposite_circles, 'cross': draw_pil_cross,
        'half_square': draw_pil_half_square, 'diagonal_square': draw_pil_diagonal_square,
        'quarter_circle': draw_pil_quarter_circle, 'dots': draw_pil_dots, 'letter_block': draw_pil_letter_block,
        'concentric_circles': draw_pil_concentric_circles, 'stripes': draw_pil_stripes,
        'rotated_shape': draw_pil_rotated_shape, 'wavy_lines': draw_pil_wavy_lines,
    }
    active_style_funcs = [style_function_map_pil[name] for name in block_style_names_list if name in style_function_map_pil]
    if not active_style_funcs:
        active_style_funcs = list(style_function_map_pil.values())

    for r_idx in range(num_rows):
        for c_idx in range(num_cols):
            colors = pil_get_two_colors(selected_palette_data, chaos_factor)
            draw_func = random.choice(active_style_funcs)
            
            # Some functions need main_draw (for rotation) others just draw
            if draw_func in [draw_pil_cross, draw_pil_letter_block, draw_pil_rotated_shape]:
                 draw_func(main_draw, c_idx * square_size, r_idx * square_size, square_size,
                      colors["foreground"], colors["background"], chaos_factor)
            else:
                draw_func(main_draw, c_idx * square_size, r_idx * square_size, square_size,
                        colors["foreground"], colors["background"], chaos_factor)


    if big_block_enabled:
        multiplier = big_block_size_multiplier
        for _ in range(num_big_blocks):
            if num_rows >= multiplier and num_cols >= multiplier:
                bb_col_idx = random.randint(0, num_cols - multiplier)
                bb_row_idx = random.randint(0, num_rows - multiplier)
                bb_x = bb_col_idx * square_size
                bb_y = bb_row_idx * square_size
                big_s_size = multiplier * square_size
                
                colors = pil_get_two_colors(selected_palette_data, chaos_factor)
                draw_func_big = random.choice(active_style_funcs)
                
                if draw_func_big in [draw_pil_cross, draw_pil_letter_block, draw_pil_rotated_shape]:
                    draw_func_big(main_draw, bb_x, bb_y, big_s_size,
                                  colors["foreground"], colors["background"], chaos_factor)
                else:
                    draw_func_big(main_draw, bb_x, bb_y, big_s_size,
                                  colors["foreground"], colors["background"], chaos_factor)
            else:
                print(f"Skipping big block: Grid size ({num_rows}x{num_cols}) too small for multiplier {multiplier}.")
    
    return final_image.convert("RGB") # Convert to RGB before sending to ComfyUI tensor


class ArtGridPNGGenerator: # Renamed class
    CATEGORY = "generate"

    @classmethod
    def INPUT_TYPES(s):
        palette_names = [f"Palette {i+1}" for i in range(len(DEFAULT_PALETTES_DATA))]
        all_styles_string = ",".join(ALL_POSSIBLE_STYLE_NAMES)

        return {
            "required": {
                "rows": ("INT", {"default": 6, "min": 1, "max": 100, "step": 1}),
                "cols": ("INT", {"default": 6, "min": 1, "max": 100, "step": 1}),
                "square_size": ("INT", {"default": 100, "min": 10, "max": 500, "step": 10}),
                "palette": (palette_names, ),
                "block_styles": ("STRING", {"default": all_styles_string, "multiline": True}),
                "chaos_factor": ("FLOAT", {"default": 0.3, "min": 0.0, "max": 1.0, "step": 0.05}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
                "big_block_enabled": ("BOOLEAN", {"default": True}),
                "big_block_size": ("INT", {"default": 2, "min": 2, "max": 10, "step": 1}), # Increased max size
                "num_big_blocks": ("INT", {"default": 1, "min": 1, "max": 10, "step": 1}), # New input
            }
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "generate_art_pil"

    def generate_art_pil(self, rows, cols, square_size, palette, block_styles,
                         chaos_factor, seed, big_block_enabled, big_block_size, num_big_blocks):
        palette_names = [f"Palette {i+1}" for i in range(len(DEFAULT_PALETTES_DATA))]
        try:
            palette_index = palette_names.index(palette)
        except ValueError:
            palette_index = 0
        
        pil_image = generate_art_image_pil(
            num_rows=rows, num_cols=cols, square_size=square_size,
            palette_index=palette_index, block_styles_str=block_styles,
            big_block_enabled=big_block_enabled, big_block_size_multiplier=big_block_size,
            num_big_blocks=num_big_blocks, chaos_factor=chaos_factor, seed_value=seed
        )

        if pil_image is None:
            error_img = Image.new('RGB', (square_size, square_size), color = 'black')
            img_np = np.array(error_img).astype(np.float32) / 255.0
            img_tensor = torch.from_numpy(img_np).unsqueeze(0)
            return (img_tensor,)

        try:
            img_np = np.array(pil_image).astype(np.float32) / 255.0
            img_tensor = torch.from_numpy(img_np).unsqueeze(0)
            return (img_tensor,)
        except Exception as e:
            print(f"ArtGridPNGGenerator: Error converting PIL to Tensor: {e}")
            error_img = Image.new('RGB', (square_size, square_size), color = 'red')
            img_np = np.array(error_img).astype(np.float32) / 255.0
            img_tensor = torch.from_numpy(img_np).unsqueeze(0)
            return (img_tensor,)

NODE_CLASS_MAPPINGS = {
    "ArtGridPNGGenerator": ArtGridPNGGenerator
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "ArtGridPNGGenerator": "Art Grid PNG Generator"
}

if __name__ == "__main__":
    # Basic test
    print("Art Grid PNG Generator (Pillow version) - Test Mode")
    img = generate_art_image_pil(4, 4, 80, 0, "circle,cross,dots,stripes", True, 2, 1, 0.2, 42)
    if img:
        img.save("test_artgrid_pillow.png")
        print("Generated test_artgrid_pillow.png")