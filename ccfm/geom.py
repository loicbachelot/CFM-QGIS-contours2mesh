from copy import deepcopy
from typing import Optional

import numpy as np

from .constants import EARTH_RAD_KM

from osgeo import gdal, osr


def destination_pt_at_bearing_distance(
    start_lon,
    start_lat,
    bearing,
    distance,
    R: float = EARTH_RAD_KM,
    bearing_unit="degrees",
):
    # Equations from http://www.movable-type.co.uk/scripts/latlong.html

    start_lon_rad, start_lat_rad = np.radians(start_lon), np.radians(start_lat)
    angular_distance = distance / R
    if bearing_unit == "degrees":
        bearing = np.radians(bearing)

    end_lat_rad = np.arcsin(
        np.sin(start_lat_rad) * np.cos(angular_distance)
        + np.cos(start_lat_rad) * np.sin(angular_distance) * np.sin(bearing)
    )
    end_lon_rad = start_lon_rad + np.arctan2(
        np.sin(bearing) * np.sin(angular_distance) * np.cos(start_lon_rad),
        np.cos(angular_distance) - np.sin(start_lat_rad * np.sin(end_lat_rad)),
    )

    end_lon, end_lat = np.degrees([end_lon_rad, end_lat_rad])
    return end_lon, end_lat


def mean_azimuth(coords):
    azimuths = [
        azimuth(*coords[i], *coords[i + 1]) for i in range(len(coords) - 1)
    ]

    az_rads = np.radians(azimuths)
    lengths = np.array(
        [
            haversine_distance(*coords[i], *coords[i + 1])
            for i in range(len(coords) - 1)
        ]
    )

    weighted_az_rad = np.arctan2(
        (np.sin(az_rads) * lengths).sum(), (np.cos(az_rads) * lengths).sum()
    )
    mean_az = np.degrees(weighted_az_rad)
    return mean_az


def azimuth(lon_0: float, lat_0: float, lon_1, lat_1):
    r_lon_0, r_lon_1, r_lat_0, r_lat_1 = np.radians(
        (lon_0, lon_1, lat_0, lat_1)
    )

    dlon = r_lon_1 - r_lon_0
    y = np.sin(dlon) * np.cos(r_lat_1)

    # y = np.sin(r_lon_1 - r_lon_0)
    x = np.cos(r_lat_0) * np.sin(r_lat_1) - np.sin(r_lat_0) * np.cos(
        r_lat_1
    ) * np.cos(r_lon_1 - r_lon_0)
    azimuth = np.degrees(np.arctan2(y, x)) % 360.0

    return azimuth


def haversine_distance(
    lon_0: float = None,
    lat_0: float = None,
    lon_1: float = None,
    lat_1: float = None,
    R: float = EARTH_RAD_KM,
) -> float:
    """
    Calculates the great circle distance between two points in lon, lat
    using the haversine formula.
    """
    r_lon_0, r_lon_1, r_lat_0, r_lat_1 = np.radians(
        (lon_0, lon_1, lat_0, lat_1)
    )
    term_1 = np.sin((r_lat_1 - r_lat_0) / 2.0) ** 2
    term_2 = np.cos(r_lat_0) * np.cos(r_lat_1)
    term_3 = np.sin((r_lon_1 - r_lon_0) / 2.0) ** 2

    return 2 * R * np.arcsin(np.sqrt(term_1 + term_2 * term_3))


def terminal_coords_from_bearing_dist(lon1: float, lat1: float, bearing, dist):
    ang_dist = dist / EARTH_RAD_KM
    lat1, lon1, bearing = np.radians([lat1, lon1, bearing])

    lat2 = np.arcsin(
        np.sin(lat1) * np.cos(ang_dist)
        + np.cos(lat1) * np.sin(ang_dist) * np.cos(bearing)
    )
    lon2 = lon1 + np.arctan2(
        np.sin(bearing) * np.sin(ang_dist) * np.cos(lat1),
        np.cos(ang_dist) - np.sin(lat1) * np.sin(lat2),
    )

    return np.degrees(lon2), np.degrees(lat2)


def polyline_seg_lengths(polyline):
    seg_lengths = np.array(
        [
            haversine_distance(*polyline[i], *polyline[i + 1])
            for i in range(len(polyline) - 1)
        ]
    )
    return seg_lengths


def polyline_length(polyline):
    return np.sum(polyline_seg_lengths(polyline))


# TODO clean up if not needed
# def sample_polyline(polyline, dists, last_pt=False):
#    seg_lengths = polyline_seg_lengths(polyline)
#    cum_lengths = np.insert(np.cumsum(seg_lengths), 0, 0.0)
#    new_pts = []
#
#    # for dist in filter(lambda d: d > 0, dists):
#    for dist in dists:
#        last_smaller_idx = np.searchsorted(cum_lengths, dist, side="right") - 1
#        if last_smaller_idx < len(seg_lengths):
#            start_lon, start_lat = polyline[last_smaller_idx]
#            end_lon, end_lat = polyline[last_smaller_idx + 1]
#            seg_az = azimuth(start_lon, start_lat, end_lon, end_lat)
#            remain_dist = dist - cum_lengths[last_smaller_idx]
#
#            new_lon, new_lat = terminal_coords_from_bearing_dist(
#                start_lon, start_lat, seg_az, remain_dist
#            )
#            new_pts.append([new_lon, new_lat])
#    # if last_pt:
#    #    new_pts.append(polyline[-1])
#
#    return np.array(new_pts)


def _resample_polyline(polyline, interval_km):
    """
    Resamples a polyline at regular intervals specified in kilometers.

    Parameters:
    -----------
    polyline : list of [x, y] or [x, y, z]
        The original polyline to resample.
    interval_km : float
        Target spacing between points in kilometers.

    Returns:
    --------
    new_polyline : list of [x, y] or [x, y, z]
        The resampled polyline.
    """
    print(f"interpolating polyline at {interval_km} kilometers (_resample_polyline)")
    if len(polyline) < 2:
        return polyline

    is_3d = len(polyline[0]) == 3

    total_length = polyline_length(polyline)
    if total_length < interval_km:
        interval_km = np.mean(polyline_seg_lengths(polyline))

    new_polyline = [polyline[0]]
    remaining_distance = interval_km

    for i in range(len(polyline) - 1):
        start = polyline[i]
        end = polyline[i + 1]
        segment_distance = haversine_distance(start[0], start[1], end[0], end[1])

        while segment_distance >= remaining_distance:
            bearing = azimuth(start[0], start[1], end[0], end[1])
            new_xy = terminal_coords_from_bearing_dist(start[0], start[1], bearing, remaining_distance)

            if is_3d:
                z_interp = start[2] + (end[2] - start[2]) * (remaining_distance / segment_distance)
                new_point = [new_xy[0], new_xy[1], z_interp]
            else:
                new_point = [new_xy[0], new_xy[1]]

            new_polyline.append(new_point)
            start = new_point
            segment_distance -= remaining_distance
            remaining_distance = interval_km

        remaining_distance -= segment_distance

    # If last point is not close enough to the end, append the real end point
    last = new_polyline[-1]
    end = polyline[-1]
    end_dist = haversine_distance(last[0], last[1], end[0], end[1])
    if end_dist > 0.25 * interval_km:
        new_polyline.append(end)

    return new_polyline



def adjust_sampling_distance(poly_length, pt_distance):
    num_segments = poly_length / pt_distance
    num_segs_rounded = round(num_segments)
    new_pt_distance = poly_length / num_segs_rounded
    return new_pt_distance


def sample_polyline(polyline, pt_distance, return_distance=False):
    """
    Resample a polyline at uniform spacing (in kilometers) using arc-length interpolation.

    Parameters:
    -----------
    polyline : list of [x, y] or [x, y, z]
        Input polyline to resample.
    pt_distance : float
        Desired spacing between consecutive points (in km).
    return_distance : bool
        If True, also return the actual spacing used.

    Returns:
    --------
    resampled : list of [x, y] or [x, y, z]
        Resampled polyline with approximately uniform spacing.
    pt_distance : float (optional)
        Returned only if return_distance=True.
    """
    if len(polyline) < 2:
        return (polyline, pt_distance) if return_distance else polyline

    is_3d = len(polyline[0]) == 3

    # Compute cumulative arc lengths
    arc_lengths = [0.0]
    for i in range(1, len(polyline)):
        d = haversine_distance(
            polyline[i - 1][0], polyline[i - 1][1],
            polyline[i][0], polyline[i][1]
        )
        arc_lengths.append(arc_lengths[-1] + d)

    total_length = arc_lengths[-1]
    if total_length < pt_distance:
        return (polyline, pt_distance) if return_distance else polyline

    n_points = max(2, int(total_length / pt_distance) + 1)
    target_distances = np.linspace(0, total_length, n_points)
    print(f"n_points: {n_points} (sample polyline)")
    resampled = []
    j = 0
    for d in target_distances:
        while j < len(arc_lengths) - 2 and arc_lengths[j + 1] < d:
            j += 1
        t = (d - arc_lengths[j]) / (arc_lengths[j + 1] - arc_lengths[j])

        x1, y1 = polyline[j][:2]
        x2, y2 = polyline[j + 1][:2]
        x = x1 + t * (x2 - x1)
        y = y1 + t * (y2 - y1)

        if is_3d:
            z1 = polyline[j][2]
            z2 = polyline[j + 1][2]
            z = z1 + t * (z2 - z1)
            resampled.append([x, y, z])
        else:
            resampled.append([x, y])

    return (resampled, pt_distance) if return_distance else resampled


def sample_polyline_to_n_pts(polyline, n_pts):
    """
    Resample a polyline to exactly n_pts using arc-length interpolation.

    Parameters:
    -----------
    polyline : list of [x, y] or [x, y, z]
        Input polyline to resample.
    n_pts : int
        Desired number of points (must be >= 2).

    Returns:
    --------
    list of [x, y] or [x, y, z]
        Resampled polyline with exactly n_pts.
    """
    if len(polyline) < 2 or n_pts < 2:
        return polyline

    is_3d = len(polyline[0]) == 3

    # Compute cumulative arc lengths
    arc_lengths = [0.0]
    for i in range(1, len(polyline)):
        d = haversine_distance(
            polyline[i-1][0], polyline[i-1][1],
            polyline[i][0], polyline[i][1]
        )
        arc_lengths.append(arc_lengths[-1] + d)

    total_length = arc_lengths[-1]
    target_distances = np.linspace(0, total_length, n_pts)

    resampled = []
    j = 0
    for d in target_distances:
        while j < len(arc_lengths) - 2 and arc_lengths[j+1] < d:
            j += 1
        t = (d - arc_lengths[j]) / (arc_lengths[j+1] - arc_lengths[j])

        x1, y1 = polyline[j][:2]
        x2, y2 = polyline[j+1][:2]
        x = x1 + t * (x2 - x1)
        y = y1 + t * (y2 - y1)

        if is_3d:
            z1 = polyline[j][2]
            z2 = polyline[j+1][2]
            z = z1 + t * (z2 - z1)
            resampled.append([x, y, z])
        else:
            resampled.append([x, y])

    return resampled


def shift_fault_trace(trace, shift_azimuth, shift_distance):
    new_trace = []
    for pt in trace:
        new_pt = terminal_coords_from_bearing_dist(
            pt[0], pt[1], shift_azimuth, shift_distance
        )
        new_trace.append(new_pt)
    return new_trace


cardinal_directions = {
    "N": (337.5, 22.5),  # North
    "NE": (22.5, 67.5),  # Northeast
    "E": (67.5, 112.5),  # East
    "SE": (112.5, 157.5),  # Southeast
    "S": (157.5, 202.5),  # South
    "SW": (202.5, 247.5),  # Southwest
    "W": (247.5, 292.5),  # West
    "NW": (292.5, 337.5),  # Northwest
}


def is_correct_direction(
    azimuth, direction, cardinal_directions=cardinal_directions
):
    """
    Checks if the given azimuth corresponds to the given direction according to
    the cardinal directions dictionary.

    Parameters:
    - azimuth: A float representing the azimuth in degrees.
    - direction: A string representing the cardinal or intercardinal direction.
    - cardinal_directions: A dictionary mapping direction abbreviations to
      their azimuth ranges.

    Returns:
    - A boolean indicating whether the azimuth corresponds to the direction.
    """
    if direction == "vertical":
        return True

    if direction not in cardinal_directions:
        raise ValueError("Invalid direction string provided.")

    min_az, max_az = cardinal_directions[direction]

    # Handling the discontinuity for North
    if direction == "N":
        return azimuth >= min_az or azimuth <= max_az
    else:
        return min_az <= azimuth <= max_az

# TODO remove if validating using the gdal version
def get_values_at_coordinates(geotiff_path, coordinates, low_memory=False,
                              out_of_bounds_val=-9999):
    """
    Extract values from a GeoTIFF at given coordinates.
    
    Args:
        geotiff_path (str): Path to the GeoTIFF file
        coordinates (list): List of (longitude, latitude) tuples
    
    Returns:
        list: Values at the specified coordinates
    """
    with rasterio.open(geotiff_path) as src:
        # Transform geographic coordinates to pixel coordinates
        pixel_coords = [src.index(lon, lat) for lon, lat in coordinates]
        
        if low_memory:
            # Read values at pixel coordinates
            #values = [src.read(1)[row, col] for row, col in pixel_coords]
            values = []
            for row, col in pixel_coords:
                try:
                    values.append(src.read(1)[row, col])
                except IndexError:
                    values.append(out_of_bounds_val)
        else:
            data = src.read(1)
            #values = [data[row, col] for row, col in pixel_coords]
            values = []
            for row, col in pixel_coords:
                try:
                    values.append(data[row, col])
                except IndexError:
                    values.append(out_of_bounds_val)
        
    return values


def get_values_at_coordinates_gdal(geotiff_path, coordinates, out_of_bounds_val=-9999):
    """
    Extract values from a GeoTIFF at given coordinates using GDAL (no rasterio).

    Args:
        geotiff_path (str): Path to the GeoTIFF file
        coordinates (list): List of (longitude, latitude) tuples
        out_of_bounds_val (float): Value to return for coordinates outside the raster bounds

    Returns:
        list: Values at the specified coordinates
    """
    dataset = gdal.Open(geotiff_path)
    band = dataset.GetRasterBand(1)
    transform = dataset.GetGeoTransform()

    # Inverse transform: world to pixel
    inv_transform = gdal.InvGeoTransform(transform)
    if inv_transform is None:
        raise RuntimeError("Failed to invert geotransform")

    values = []
    for lon, lat in coordinates:
        px, py = gdal.ApplyGeoTransform(inv_transform, lon, lat)
        px, py = int(px), int(py)
        if 0 <= px < dataset.RasterXSize and 0 <= py < dataset.RasterYSize:
            try:
                structval = band.ReadAsArray(px, py, 1, 1)
                values.append(float(structval[0][0]))
            except Exception:
                values.append(out_of_bounds_val)
        else:
            values.append(out_of_bounds_val)

    return values


def get_resampled_trace_elevations(
    resampled_trace,
    trace,
    method='nearest',
    elev_grid: Optional[np.ndarray] = None,
    low_memory: bool= False,
):
    if method == 'nearest':
        for pt in resampled_trace:
            dists = np.array(
                [haversine_distance(*pt[:2], *trace_pt[:2]) for trace_pt in trace]
            )
            min_dist_idx = np.argmin(dists)
            if len(pt) > 2:
                del pt[2:]
            pt.append(float(trace[min_dist_idx][2]))

    elif method == 'sample':
        elevs = get_values_at_coordinates(elev_grid, resampled_trace,
                                          low_memory=low_memory)
        resampled_trace = [cc.append(float(elevs[i])) 
                           for i, cc in enumerate(resampled_trace)]    
    
    else:
        raise NotImplementedError(
            "Only nearest neighbor interpolation and DEM sampling are" +
             " currently supported."
        )
    return resampled_trace


def add_fixed_elev_to_trace(trace, elev):
    for pt in trace:
        pt.append(elev)
    return trace


def make_3d_fault_mesh(
    fault,
    lower_depth: Optional[float] = None,
    pt_distance: float = 2.0,
    lower_depth_default: float = 16.0,
    check_dip_dir: bool = False,
    decimals: Optional[float] = 3,
):
    # TODO: deal with variable/non-zero trace elevation
    if lower_depth is None:
        lower_depth = fault['properties'].get(
            'lower_depth', lower_depth_default
        )

    trace = fault['geometry']['coordinates']
    if len(trace[0]) == 2:
        trace_3d = [[pt[0], pt[1], 0.0] for pt in trace]
        elev_flag = False
    else:
        trace_3d = deepcopy(trace)
        trace = [[pt[0], pt[1]] for pt in trace_3d]
        elev_flag = True

    mean_az = mean_azimuth(trace)
    proj_dir = (mean_az + 90.0) % 360.0  # need to check for RHR

    if check_dip_dir:
        assert is_correct_direction(
            proj_dir, fault['properties']['dip_dir']
        ), (
            f"The projection direction ({proj_dir})is not consistent with the "
            + f"dip direction ({fault['properties']['dip_dir']})."
        )

    res_trace, pt_distance = sample_polyline(
        trace, pt_distance, return_distance=True
    )

    for pt in res_trace:
        pt.append(0.0)

    vert_distance = pt_distance * np.sin(
        np.radians(fault['properties']['dip'])
    )
    hor_distance = pt_distance * np.cos(np.radians(fault['properties']['dip']))
    depths = np.arange(0.0, lower_depth, vert_distance)
    depths[depths > 0.0] = -1.0 * depths[depths > 0.0]

    mesh = []

    for i, depth in enumerate(depths):
        if fault["properties"]["dip"] != 90.0:
            shifted_trace = shift_fault_trace(
                res_trace, proj_dir, hor_distance * i
            )
        else:
            shifted_trace = res_trace
        new_trace = [
            [pt[0], pt[1], (depth * 1000) + res_trace[i][2]]
            for i, pt in enumerate(shifted_trace)
        ]
        mesh.append(new_trace)

    if elev_flag:
        resampled_3d_trace = get_resampled_trace_elevations(res_trace, 
                                                            trace_3d,
                                                            method='nearest')
        mesh[0] = resampled_3d_trace

    if decimals is not None:
        mesh = np.round(mesh, decimals=decimals).tolist()

    return mesh


def make_tri_mesh(mesh_3d):

    tris = []

    for row in range(len(mesh_3d) - 1):
        for col in range(len(mesh_3d[0]) - 1):
            tris.append(
                [
                    mesh_3d[row][col],
                    mesh_3d[row + 1][col],
                    mesh_3d[row + 1][col + 1],
                    mesh_3d[row][col],
                ]
            )
            tris.append(
                [
                    mesh_3d[row][col + 1],
                    mesh_3d[row][col],
                    mesh_3d[row + 1][col + 1],
                    mesh_3d[row][col + 1],
                ]
            )
    return tris


def _straight_profile_n_pts(p1, p2, n_pts):
    hor_distance = haversine_distance(p1[0], p1[1], p2[0], p2[1])
    pt_distance = hor_distance / (n_pts - 1)
    profile_az = azimuth(p1[0], p1[1], p2[0], p2[1])
    out_pts = [p1[:2]]
    for n in range(1, n_pts - 1):
        dist = n * pt_distance
        new_pt = terminal_coords_from_bearing_dist(p1[0], p1[1], profile_az,
                                                   dist)
        out_pts.append(list(new_pt))
    
    out_pts.append(p2[:2])

    return out_pts


def _draw_pt_profile(p1, p2, n_pts):
    if n_pts < 3:
        return [p1, p2]

    profile_pts = _straight_profile_n_pts(p1, p2, n_pts)
    elevs = np.linspace(p1[2], p2[2], n_pts)
    for i, pt in enumerate(profile_pts):
        pt.append(elevs[i])

    return profile_pts


def get_contours_from_profiles(profiles, return_top=True, return_bottom=True):
    n_contours = len(profiles[0])
    contours = []

    contour_inds = list(range(n_contours))
    if not return_top:
        contour_inds = contour_inds[1:]
    if not return_bottom:
        contour_inds = contour_inds[:-1]

    for i in contour_inds:
        contour = [profile[i] for profile in profiles]
        contours.append(contour)

    return contours
