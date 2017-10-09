from __future__ import print_function

import os
import os.path as osp
from subprocess import call
from submission.log import logger
from numpy import savetxt
import pandas as pd
import nibabel as nb
import numpy as np

# Joel added below
from sympy import Point3D, Line3D
# Joel added above

def brainshift_correct(loc, sub, outfolder, fsfolder, overwrite=False):
    """ Corrects for brain shift using sequential quadratic
    programming optimization in R (package nloptr).
    :param loc: localization structure
    :param sub: subject name
    :param outfolder: where will logs and csv file be saved
    :param fsfolder: fresurfer folder for this subject
    :param overwrite: force processing and overwrite existing files
    """
    here = osp.realpath(osp.dirname(__file__))
    Rcorrection = osp.join(here, "brainshift", "duralDykstra.R")
    # sub = 'R1238N'
    # outfolder = '/data10/RAM/subjects/R1238N/imaging/R1238N'
    # fsfolder = '/data/eeg/freesurfer/subjects/R1238N'
    og_dir = os.getcwd()
    corrfile = os.path.join(outfolder, sub + '_shift_corrected.csv')
    [lhvertex, _, lhname] = nb.freesurfer.io.read_annot(os.path.join(fsfolder, 'label', 'lh.aparc.annot'))
    [rhvertex, _, rhname] = nb.freesurfer.io.read_annot(os.path.join(fsfolder, 'label', 'rh.aparc.annot'))
    
    #Joel added below
    [lhvertex_hcp, _, lhname_hcp] = nb.freesurfer.io.read_annot(os.path.join(fsfolder, 'label', 'lh.HCP-MMP1.annot'))
    [rhvertex_hcp, _, rhname_hcp] = nb.freesurfer.io.read_annot(os.path.join(fsfolder, 'label', 'rh.HCP-MMP1.annot'))
    #Joel added above

    if os.path.isfile(corrfile) and not overwrite:
        print("Corrected csv file already exists for " + sub + ". Use 'overwrite=True' to overwrite results.")
    else:
        ### get data and save them to files that R can read
        elnames = loc.get_contacts()
        coords = loc.get_contact_coordinates('fs', elnames)
        eltypes = loc.get_contact_types(elnames)
        bpairs = loc.get_pairs()
        savetxt(os.path.join(outfolder, sub + '_shift_coords.csv'), coords, delimiter=',')
        savetxt(os.path.join(outfolder, sub + '_shift_eltypes.csv'), eltypes, fmt='%s')
        savetxt(os.path.join(outfolder, sub + '_shift_bpairs.csv'), bpairs, fmt='%s', delimiter=',')
        savetxt(os.path.join(outfolder, sub + '_shift_elnames.csv'), elnames, fmt='%s')
        savetxt(os.path.join(outfolder, sub + '_shift_lhvertex.csv'), lhvertex, fmt='%s')
        savetxt(os.path.join(outfolder, sub + '_shift_lhname.csv'), lhname, fmt='%s')
        savetxt(os.path.join(outfolder, sub + '_shift_rhvertex.csv'), rhvertex, fmt='%s')
        savetxt(os.path.join(outfolder, sub + '_shift_rhname.csv'), rhname, fmt='%s')
        ###

        os.chdir(osp.join(here,'brainshift'))

        ### prepare R command and run

        cmd_args = "'--args sub=\"{sub}\" outfolder=\"{outfolder}\" fsfolder=\"{fsfolder}\"'".format(
            sub=sub,outfolder=outfolder,fsfolder=fsfolder
        )
        logfile = os.path.join(outfolder, sub + '_shiftCorrection.Rlog')
        cmd = ["R", "CMD", "BATCH", "--no-save", "--no-restore", cmd_args,Rcorrection, logfile]
        logger.debug('Executing shell command %s'%str(cmd))
        call(' '.join(cmd),shell=True)
        ###

        os.chdir(og_dir)
    ### load the corrected output
    corrected_data = pd.DataFrame.from_csv(corrfile)
    newnames=corrected_data.index.values


    # put data in loc
    loc.set_contact_coordinates('fs', newnames, corrected_data[['corrx','corry','corrz']].values, coordinate_type='corrected')
    loc.set_contact_infos('displacement', newnames, corrected_data.displaced.values)
    loc.set_contact_infos('closest_vertex_distance', newnames,corrected_data.closestvertexdist.values)
    loc.set_contact_infos('linked_electrodes', newnames, corrected_data.linkedto.values)
    loc.set_contact_infos('link_displaced', newnames, corrected_data.linkdisplaced.values)
    loc.set_contact_infos('group_corrected', newnames, corrected_data['group'].values)
    loc.set_contact_infos('closest_vertex_coordinate', newnames,
                          corrected_data[['closestvertexx','closestvertexy','closestvertexz']].values.tolist())
    # loc.set_contact_labels('dk', newnames, corrected_data.DKT.values)
    # loc.set_contact_coordinates('fsaverage', newnames, corrected_data[['fsavg_x','fsavg_y','fsavg_z']].values.tolist(), coordinate_type='corrected')

    lhcoords = nb.freesurfer.read_geometry(osp.join(fsfolder,'surf','lh.pial'))[0]
    rhcoords = nb.freesurfer.read_geometry(osp.join(fsfolder,'surf','rh.pial'))[0]
    lhname = ['L_'+x for x in lhname]
    rhname = ['R_'+x for x in rhname]
    rhvertex[0] = 0
    lhvertex[0] = 0
    rhvertex+= len(lhname)
    fs_vertices = np.concatenate([lhvertex,rhvertex])
    fs_names = np.concatenate([lhname,rhname])
    
    # Joel added below
    hcp_names = np.concatenate([lhname_hcp,rhname_hcp])
    # Joel added above
    
    coords = np.concatenate([lhcoords,rhcoords])
    
    # Joel added below to get the closest orthogonal to the corrected bipolars
    closest_ortho_pairs = []
    closest_ortho_verts = []
    closest_ortho_distance = []
    vert_radius = 5
    for i in bpairs:
        if loc.get_contact_type(i[0]) in ['G', 'S']:
            c1 = np.array(loc.get_contact_coordinate('fs',i[0],coordinate_type='corrected'))[0]
            c2 = np.array(loc.get_contact_coordinate('fs',i[1],coordinate_type='corrected'))[0]
            b1 = (c1 + c2)/2
            print('Getting closest orthogonal vertex point for', i[0], '-', i[1], 'with bipolar coordinate', b1)
            l1 = Line3D(c1,b1)
            verts_near_bipolar = []
            verts_distances = []
            closest_verts = []
            for v in coords:
                v1 = np.array(list(v))
                vp_dist = np.linalg.norm(b1-v1)
                if vp_dist < vert_radius:
                    verts_near_bipolar.append(v1)
                    verts_distances.append(vp_dist)
            if len(verts_near_bipolar) == 0:
                for v in coords:
                    v1 = np.array(list(v))
                    vp_dist = np.linalg.norm(b1-v1)
                    if vp_dist < 2*vert_radius:
                        verts_near_bipolar.append(v1)
                        verts_distances.append(vp_dist)
            print('Found', len(verts_near_bipolar), 'vertices within radius', vert_radius, 'of bipolar')
            closest_verts = [x for _,x in sorted(zip(verts_distances,verts_near_bipolar))]
            closest_vert = [0, 0, 0]
            for vv1 in closest_verts:
                l2 = Line3D(vv1,b1)
                if abs(l1.angle_between(l2) - 1.5708) < 0.1:
                    closest_vert = vv1
                    break
            print('Found closest orthogonal vertex:', closest_vert)
            closest_ortho_pairs.append(i)
            closest_ortho_verts.append(closest_vert)
    print('Length of closest_ortho_pairs is', len(closest_ortho_pairs))
    print(closest_ortho_pairs)
    print('Length of closest_ortho_verts is',len(closest_ortho_verts))
    print(np.vstack(closest_ortho_verts).tolist())
    loc.set_pair_infos('closest_ortho_vertex_coordinate', closest_ortho_pairs, np.vstack(closest_ortho_verts).tolist())
    # Joel added above

    loc.set_contact_labels('dk',newnames,get_dk_labels(
        loc.get_contact_coordinates('fs',newnames,coordinate_type='corrected'),coords,
        fs_vertices,fs_names))

    loc.set_pair_labels('dk', loc.get_pairs(), get_dk_labels(
        loc.get_pair_coordinates('fs',coordinate_type='corrected'), coords, fs_vertices,
        fs_names))
    
    # Joel added below to add HCP atlas locations to localization.son for corrected bipolars
    loc.set_pair_labels('hcp', loc.get_pairs(), get_dk_labels(
        loc.get_pair_coordinates('fs',coordinate_type='corrected'), coords, fs_vertices,
        hcp_names))
    # Joel added above
    # Joel added below to add closest vertices to localization.json corrected bipolars
    dk_verts, dk_inds, dk_dist = get_dk_vertices(loc.get_pair_coordinates('fs',coordinate_type='corrected'), coords, fs_vertices, fs_names)
    loc.set_pair_infos('closest_vertex_coordinate', loc.get_pairs(), dk_verts)
     # Joel added above
     
    # Joel added below to add fs_average vertices to localization.json corrected bipolars
    print('FSaverage', get_fsavg_vertices(dk_inds))
    print('FSaverage', np.vstack(get_fsavg_vertices(dk_inds)))
    loc.set_pair_infos('fsaverage_vertex_coordinate', loc.get_pairs(), np.vstack(get_fsavg_vertices(dk_inds)).tolist())
     # Joel added above
    
    # Joel added below to get bipolar label file
    #dk_dist = loc.get_pair_infos('closest_vertex_distance',loc.get_pairs())
    lh_offset = len(lhcoords)
    print('Lhcoords length', lh_offset)
    print(len(dk_inds))
    print('lh label file for label2label')
    pairs = loc.get_pairs()
    counter = 0
    for i in xrange(len(dk_inds)):
        if dk_inds[i] <= lh_offset:
            counter = counter + 1
            print(pairs[i], dk_inds[i], dk_verts[i][0], dk_verts[i][1], dk_verts[i][2], '0.000000')
    print(counter)
    counter = 0
    print('rh label file for label2label')
    for i in xrange(len(dk_inds)):
        if dk_inds[i] > lh_offset:
            counter = counter + 1
            print(pairs[i], dk_inds[i]-lh_offset, dk_verts[i][0], dk_verts[i][1], dk_verts[i][2], '0.000000')
    print(counter)
    # Joel added above
    
    return loc

def get_dk_labels(electrode_coords,vertex_coords,vertex_inds,labels):
    electrode_labels = []
    for coord in electrode_coords:
        closest_vertex_index = np.argmin(np.linalg.norm(vertex_coords-np.squeeze(coord),axis=1))
        label = labels[vertex_inds[closest_vertex_index]]
        electrode_labels.append(label)
    return electrode_labels

    # Joel added below to get the closest vertex locations for each of the corrected bipolar pairs
def get_dk_vertices(electrode_coords,vertex_coords,vertex_inds,labels):
    electrode_vertices = []
    electrode_vertices_indices = []
    electrode_vertex_distances = []
    for coord in electrode_coords:
        closest_vertex_index = np.argmin(np.linalg.norm(vertex_coords-np.squeeze(coord),axis=1))
        closest_vertex = vertex_coords[closest_vertex_index]
        closest_distances = np.linalg.norm(closest_vertex-coord)
        electrode_vertices.append(closest_vertex.tolist())
        electrode_vertices_indices.append(closest_vertex_index)
        electrode_vertex_distances.append(closest_distances)
    return electrode_vertices, electrode_vertices_indices, electrode_vertex_distances
    # Joel added above
    
    # Joel added below to get fsaverage vertex coords
def get_fsavg_vertices(vertex_inds):
    electrode_vertices = []
    lhcoords_avg = nb.freesurfer.read_geometry('/data/eeg/freesurfer/subjects/fsaverage/surf/lh.pial')[0]
    rhcoords_avg = nb.freesurfer.read_geometry('/data/eeg/freesurfer/subjects/fsaverage/surf/rh.pial')[0]
    coords_avg = np.concatenate([lhcoords_avg,rhcoords_avg])
    for index in vertex_inds:
        electrode_vertices.append(coords_avg[index])
    return electrode_vertices
    # Joel added above
    