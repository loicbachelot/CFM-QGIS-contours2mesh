from .geom import (
    sample_polyline,
    sample_polyline_to_n_pts,
    add_fixed_elev_to_trace,
    haversine_distance,
    _draw_pt_profile,
    get_contours_from_profiles,
    get_values_at_coordinates,
    polyline_length,
    get_values_at_coordinates_gdal
)

def get_invalid_contour_messages(features, min_points=4):
    """
    Checks contour features for valid LineString geometry with at least `min_points` vertices.

    Parameters:
        features (list[QgsFeature]): The contour features to check.
        min_points (int): Minimum number of vertices required.

    Returns:
        list[str]: List of error message strings for each invalid feature.
    """
    errors = []

    for i, feature in enumerate(features):
        geom = feature.geometry()
        name = feature["name"] if "name" in feature.fields().names() else f"Feature {i}"

        if geom is None or geom.isEmpty():
            errors.append(f"{name} (empty geometry)")
            continue

        coords = geom.asPolyline()
        if len(coords) < min_points:
            errors.append(f"{name} ({len(coords)} points)")

    return errors


def prepare_fault_contours(fault_contours, pt_distance=0.5, elevation_path=None):
    MAX_POINTS = 1_000

    # Resample the top contour using spacing
    trace = fault_contours[0]
    coords = trace['geometry']['coordinates']
    total_length = polyline_length(coords)
    n_estimated = int(total_length / pt_distance) + 1

    if n_estimated > MAX_POINTS:
        raise ValueError(
            f"Resampling would produce {n_estimated:,} points (limit is {MAX_POINTS}). "
            f"Please increase the spacing."
        )

    trace_sampled = sample_polyline(coords, pt_distance=pt_distance)
    if len(trace_sampled[0]) == 2:
        trace_sampled = add_fixed_elev_to_trace(trace_sampled, trace['properties']['elev'])
    contours_out = [trace_sampled]

    # Resample other contours to match point count
    n_trace_pts = len(trace_sampled)
    print(f"Number of points: {n_trace_pts} (prepare contours)")
    for contour in fault_contours[1:]:
        contour_sampled = sample_polyline_to_n_pts(contour['geometry']['coordinates'], n_trace_pts)
        if len(contour_sampled[0]) == 2:
            contour_sampled = add_fixed_elev_to_trace(contour_sampled, contour['properties']['elev'])
        contours_out.append(contour_sampled)

    # Optional raster elevation logic for top only
    if elevation_path:
        try:
            coords_2d = [pt[:2] for pt in contours_out[0]]
            elevs = get_values_at_coordinates_gdal(elevation_path, coords_2d)
            for j, elev in enumerate(elevs):
                contours_out[0][j][2] = elev
            print("Interpolated elevation applied to top contour.")
        except Exception as e:
            from qgis.PyQt.QtWidgets import QMessageBox
            QMessageBox.critical(None, "Elevation Error",
                                 f"Failed to sample elevation data:\n{str(e)}")

    return contours_out

def make_mesh_from_prepared_contours(contours, down_dip_pt_spacing=0.5):
    """
    Generate a triangular fault mesh by interpolating between stacked contours.

    Parameters:
    -----------
    contours : list of list of list of float
        A list of sampled contour traces, ordered from top to bottom.
        Each contour is a list of points, and each point is a list [x, y, z].
        All contours must have the same number of points, aligned along strike.

    down_dip_pt_spacing : float, optional
        Target spacing (in kilometers) between points in the vertical (down-dip) direction.
        Controls how finely the fault is meshed between adjacent contours.

    Returns:
    --------
    list
        A list of interpolated profiles forming a triangular mesh between the contours.
        Each profile corresponds to a vertical slice between matching points on adjacent contours.

    Notes:
    ------
    - The spacing parameter only affects vertical (down-dip) resolution.
      The horizontal spacing between points along strike must be pre-sampled in the input `contours`.
    - This function assumes that the input contours are ordered top to bottom
      and that each contour has the same number of corresponding points.
    """
    num_contour_sets = len(contours) - 1
    all_contours = []

    for i_cs in range(num_contour_sets):
        top_z = contours[i_cs][0][2]
        bottom_z = contours[i_cs+1][0][2]
        vert_distance = (top_z - bottom_z) / 1000.0

        hor_distance = haversine_distance(
            contours[i_cs][0][0], contours[i_cs][0][1],
            contours[i_cs+1][0][0], contours[i_cs+1][0][1],
        )

        down_dip_distance = (vert_distance**2 + hor_distance**2) ** 0.5
        n_pts = int(round(down_dip_distance / down_dip_pt_spacing)) + 1

        profiles = [
            _draw_pt_profile(contours[i_cs][j], contours[i_cs+1][j], n_pts)
            for j in range(len(contours[i_cs]))
        ]

        contour_set = get_contours_from_profiles(profiles, return_top=(i_cs == 0))
        all_contours.extend(contour_set)

    return all_contours


def estimate_triangle_count(prepped_contours, spacing_km):
    """
    Estimate the number of triangles in the fault mesh based on spacing.

    Parameters:
    - prepped_contours: list of contours (each a list of [x, y, z] points), ordered top to bottom
    - spacing_km: horizontal and vertical spacing in kilometers

    Returns:
    - Estimated number of triangles (int)
    """
    if len(prepped_contours) < 2:
        return 0

    n_profile_pts = len(prepped_contours[0])
    total_triangles = 0

    for i in range(len(prepped_contours) - 1):
        for j in range(n_profile_pts - 1):
            pt_top = prepped_contours[i][j]
            pt_next = prepped_contours[i + 1][j]

            horiz_km = haversine_distance(pt_top[0], pt_top[1], pt_next[0], pt_next[1])
            vert_km = abs(pt_top[2] - pt_next[2]) / 1000.0
            down_dip_dist = (horiz_km ** 2 + vert_km ** 2) ** 0.5

            n_down = int(down_dip_dist / spacing_km) + 1
            total_triangles += (n_down - 1) * 2

    return total_triangles