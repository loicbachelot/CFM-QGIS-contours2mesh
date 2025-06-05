import json
import numpy as np

import sys
sys.path.append("../")

from ccfm.ccfm import (
        make_tri_mesh,
        write_cfm_tri_meshes,
        )

from ccfm.geom import (
    sample_polyline,
    sample_polyline_to_n_pts,
    add_fixed_elev_to_trace,
    haversine_distance,
    _draw_pt_profile,
    get_contours_from_profiles,
    )

def prepare_fault_contours(fault_contours, **kwargs):
    fc_sorted = fault_contours
    trace = fc_sorted[0]
    trace_sampled = sample_polyline(trace['geometry']['coordinates'], **kwargs)
    trace_sampled = add_fixed_elev_to_trace(trace_sampled, trace['properties']['elev'])
    
    contours_out = []
    contours_out.append(trace_sampled)
    
    n_trace_pts = len(trace_sampled)
    for trace in fc_sorted[1:]:
        trace_sampled = sample_polyline_to_n_pts(trace['geometry']['coordinates'], n_trace_pts)
        trace_sampled = add_fixed_elev_to_trace(trace_sampled, trace['properties']['elev'])
        contours_out.append(trace_sampled)
    
    
    return contours_out


def make_mesh_from_prepared_contours(contours, vert_pt_spacing=None, 
                                     down_dip_pt_spacing=None):

    num_contour_sets = len(contours) - 1
    
    all_contours = []
    
    for i_cs in range(num_contour_sets):
        top_contour_elev = contours[i_cs][0][2]
        bottom_contour_elev = contours[i_cs+1][0][2]
        vert_distance = (top_contour_elev - bottom_contour_elev) / 1000.
        
        # get horizontal distance between points
        # using first point
        hor_distance = haversine_distance(contours[i_cs][0][0],
                                          contours[i_cs][0][1],
                                          contours[i_cs+1][0][0],
                                          contours[i_cs+1][0][1],
                                         )
        
        down_dip_distance = np.sqrt(vert_distance**2 + hor_distance**2)
        
        n_pts = int(round( down_dip_distance / down_dip_pt_spacing)) + 1
          
        profiles = [_draw_pt_profile(contours[i_cs][j],
                                     contours[i_cs+1][j],
                                     n_pts)
                    for j in range(len(contours[i_cs]))]
        
        
        if i_cs == 0:
            return_top = True
        else:
            return_top = False
        
        contour_set = get_contours_from_profiles(profiles,
                                                return_top,
                                                )
        all_contours.extend(contour_set)
        
    return all_contours

contour_data = "../misc_data/test_data/test_contours.geojson"

# load contours from file
# data file may contain contours for many faults
with open(contour_data) as f:
    gj = json.load(f)

    contours = {}
    for feature in gj['features']:
        contours[feature['properties']['name']]= feature

# specify contours we want in this fault
fault_contours = [
        contours['top'],
        contours['middle'],
        contours['bottom'],
        ]

# prepare the contours for meshing
prepped_contours = prepare_fault_contours(fault_contours, pt_distance=0.5)

# would add dem elevations to top contour here

# make point mesh (arrays of coordinates, no connections)
mesh = make_mesh_from_prepared_contours(prepped_contours,
                                            down_dip_pt_spacing=0.5)

#make triangular mesh from coordinate arrays
tri_mesh = make_tri_mesh(mesh)

# write to file
write_cfm_tri_meshes(
        "example_3d_fault.geojson",
        [tri_mesh],
        [{'properties': {'name': 'test_fault'}}],
        )
