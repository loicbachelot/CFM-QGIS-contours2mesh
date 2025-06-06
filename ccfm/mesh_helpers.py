from .geom import (
    sample_polyline,
    sample_polyline_to_n_pts,
    add_fixed_elev_to_trace,
    haversine_distance,
    _draw_pt_profile,
    get_contours_from_profiles,
)

def prepare_fault_contours(fault_contours, pt_distance=0.5):
    trace = fault_contours[0]
    trace_sampled = sample_polyline(trace['geometry']['coordinates'], pt_distance=pt_distance)
    trace_sampled = add_fixed_elev_to_trace(trace_sampled, trace['properties']['elev'])
    contours_out = [trace_sampled]

    n_trace_pts = len(trace_sampled)
    for trace in fault_contours[1:]:
        trace_sampled = sample_polyline_to_n_pts(trace['geometry']['coordinates'], n_trace_pts)
        trace_sampled = add_fixed_elev_to_trace(trace_sampled, trace['properties']['elev'])
        contours_out.append(trace_sampled)

    return contours_out

def make_mesh_from_prepared_contours(contours, down_dip_pt_spacing=0.5):
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
