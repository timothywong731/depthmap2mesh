import trimesh
import numpy as np
from PIL import Image

def depthmap_to_3d_mesh(depthmap_path, stl_path, width, depth, base_thickness, mesh_resolution=None):
    """
    Convert a depthmap image to a 3D mesh suitable for CNC milling.

    Parameters:
    - depthmap_path: str, path to the depthmap image file.
    - stl_path: str, path to save the output STL file.
    - width: float, width of the design in mm.
    - depth: float, maximum carving depth in mm.
    - base_thickness: float, minimum thickness to leave at the base in mm.
    - mesh_resolution: int or tuple, if int, specifies width_res, and height_res is calculated.
      If tuple (width_res, height_res), uses the specified resolutions.
      If None, uses the original image resolution.
    """
    # Read the depthmap image
    img = Image.open(depthmap_path).convert('L')  # Convert to grayscale
    img_array = np.array(img)

    # Normalize the depthmap values to range [0, 1]
    normalized_depthmap = img_array.astype(np.float32) / 255.0

    # If mesh_resolution is specified, resample the depthmap
    if mesh_resolution is not None:
        if isinstance(mesh_resolution, int):
            width_res = mesh_resolution
            # Calculate height_res dynamically to maintain aspect ratio
            aspect_ratio = img_array.shape[0] / img_array.shape[1]
            height_res = int(round(width_res * aspect_ratio))
        elif isinstance(mesh_resolution, tuple):
            width_res, height_res = mesh_resolution
        else:
            raise ValueError("mesh_resolution must be an int or a tuple (width_res, height_res).")
        # Resize the depthmap to the desired resolution using PIL
        img_resized = img.resize((width_res, height_res), resample=Image.BILINEAR)
        normalized_depthmap = np.array(img_resized).astype(np.float32) / 255.0

    # Flip the depthmap vertically to correct the orientation
    normalized_depthmap = np.flipud(normalized_depthmap)

    # Compute heights (z values)
    # White (value 1.0) corresponds to z = 0 (no carving)
    # Black (value 0.0) corresponds to z = -depth (maximum carving depth)
    heights = -depth * (1.0 - normalized_depthmap)  # Shape (H, W)

    # Create grid of x, y coordinates
    height_px, width_px = normalized_depthmap.shape
    # Calculate physical height based on aspect ratio
    height_mm = (height_px / width_px) * width

    x = np.linspace(0, width, num=width_px)
    y = np.linspace(0, height_mm, num=height_px)
    xx, yy = np.meshgrid(x, y)
    zz = heights  # Heights calculated earlier

    # Flatten arrays
    vertices = np.column_stack((xx.ravel(), yy.ravel(), zz.ravel()))

    # Create faces (triangles) for the top surface
    faces = []
    for i in range(height_px - 1):
        for j in range(width_px - 1):
            idx = i * width_px + j
            idx_right = idx + 1
            idx_down = idx + width_px
            idx_down_right = idx_down + 1
            # Two triangles per grid square
            faces.append([idx, idx_down, idx_right])
            faces.append([idx_right, idx_down, idx_down_right])

    # Create side walls and bottom
    # Create vertices for the bottom surface at z = - (depth + base_thickness)
    bottom_z = - (depth + base_thickness)
    bottom_vertices = np.column_stack((xx.ravel(), yy.ravel(), np.full_like(zz.ravel(), bottom_z)))

    # Combine top and bottom vertices
    all_vertices = np.vstack((vertices, bottom_vertices))
    num_vertices = vertices.shape[0]

    # Side walls
    side_faces = []
    # Left and right walls
    for i in range(height_px - 1):
        # Left wall
        idx_top = i * width_px
        idx_bottom = num_vertices + idx_top
        idx_top_next = idx_top + width_px
        idx_bottom_next = idx_bottom + width_px
        side_faces.append([idx_top, idx_bottom, idx_bottom_next])
        side_faces.append([idx_top, idx_bottom_next, idx_top_next])
        # Right wall
        idx_top = i * width_px + (width_px - 1)
        idx_bottom = num_vertices + idx_top
        idx_top_next = idx_top + width_px
        idx_bottom_next = idx_bottom + width_px
        side_faces.append([idx_top, idx_bottom_next, idx_bottom])
        side_faces.append([idx_top, idx_top_next, idx_bottom_next])

    # Front and back walls
    for j in range(width_px - 1):
        # Front wall
        idx_top = j
        idx_bottom = num_vertices + idx_top
        idx_top_next = idx_top + 1
        idx_bottom_next = idx_bottom + 1
        side_faces.append([idx_top, idx_bottom, idx_bottom_next])
        side_faces.append([idx_top, idx_bottom_next, idx_top_next])
        # Back wall
        idx_top = (height_px - 1) * width_px + j
        idx_bottom = num_vertices + idx_top
        idx_top_next = idx_top + 1
        idx_bottom_next = idx_bottom + 1
        side_faces.append([idx_top, idx_bottom_next, idx_bottom])
        side_faces.append([idx_top, idx_top_next, idx_bottom_next])

    # Bottom face
    bottom_faces = []
    for i in range(height_px - 1):
        for j in range(width_px - 1):
            idx = num_vertices + i * width_px + j
            idx_right = idx + 1
            idx_down = idx + width_px
            idx_down_right = idx_down + 1
            bottom_faces.append([idx, idx_down, idx_right])
            bottom_faces.append([idx_right, idx_down, idx_down_right])

    # Combine all faces
    all_faces = np.vstack((faces, side_faces, bottom_faces))

    # Create mesh
    mesh = trimesh.Trimesh(vertices=all_vertices, faces=all_faces)

    # Shift the mesh down by base_thickness to ensure correct total depth
    mesh.vertices[:, 2] -= base_thickness

    # Export to STL
    mesh.export(stl_path)
