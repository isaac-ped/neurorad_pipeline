"""
Reads in localization data from the autoloc processing and adds to the electrode database
to coordinates in freesurfer mesh space.
Requires subject ID to find localization data


Run:
    python add_locations.py <subject> <out_file>
"""
import logging

from mri_info import *
from config import paths
import pandas as pd
log = logging.getLogger('submission')
from localization import InvalidContactException,InvalidFieldException

def read_loc(native_loc, localization):
    """
    Reads electrodenames_coordinates_native_and_T1.csv, returning a dictionary of leads
    :param t1_file: path to electrodenames_coordinates_native_and_T1.csv file
    :returns: dictionary of form TODO {lead_name: {contact_name1: contact1, contact_name2:contact2, ...}}
    """

    log.debug('Saved localization for:')
    for line in open(native_loc):
        split_line = line.strip().split(',')

        # Contact name
        contact_name = split_line[0]

        # Contact localization
        contact_autoloc = split_line[1]

        # Split into whole brain/MTL atlas labels
        loc_list = contact_autoloc.strip().split('/')

        # Enter into "leads" dictionary
        try:
            localization.set_contact_label('whole_brain', contact_name, loc_list[0])
            log.debug(contact_name + '(WB)')
            if len(loc_list) > 1:
                localization.set_contact_label('mtl', contact_name, loc_list[1])
                log.debug(contact_name + '(MTL)')
        except InvalidContactException:
            log.warning('Invalid contact %s in file %s'%(contact_name,os.path.basename(native_loc)))

    for (c1,c2) in localization.get_pairs():
        c1_loc = localization.get_contact_label('whole_brain',c1)
        c2_loc = localization.get_contact_label('whole_brain',c2)
        if c1_loc and (c1_loc==c2_loc or not c2_loc):
            localization.set_pair_label('whole_brain',(c1,c2),c1_loc)
        elif c2_loc and not c1_loc:
            localization.set_pair_label('whole_brain',(c1,c2),c2_loc)

        c1_loc = localization.get_contact_label('mtl', c1)
        c2_loc = localization.get_contact_label('mtl', c2)
        if c1_loc and (c1_loc == c2_loc or not c2_loc):
            localization.set_pair_label('mtl', (c1, c2), c1_loc)
        elif c2_loc and not c1_loc:
            localization.set_pair_label('mtl', (c1, c2), c2_loc)



def read_mni(mni_loc, localization):
    """
    Reads electrodenames_coordinates_native_and_T1.csv, returning a dictionary of leads
    :param t1_file: path to electrodenames_coordinates_native_and_T1.csv file
    :returns: dictionary of form TODO {lead_name: {contact_name1: contact1, contact_name2:contact2, ...}}
    """

    log.debug("Saved MNI Coordinate for: ")
    for line in open(mni_loc):
        split_line = line.strip().split(',')

        # Contact name
        contact_name = split_line[0]

        # Contact localization
        contact_mni_x = split_line[1]
        contact_mni_y = split_line[2]
        contact_mni_z = split_line[3]

        # Enter into "leads" dictionary
        localization.set_contact_coordinate('mni', contact_name, [contact_mni_x, contact_mni_y, contact_mni_z])
        log.debug(contact_name)

def read_manual_locations(loc_excel, localization):
    loc_table = pd.read_excel(loc_excel,index_col=0).dropna(subset=['Tag'])
    contacts = [x for x in loc_table.index.values if '-' not in x]
    labels = loc_table['Tag'].values
    localization.set_contact_labels('manual',contacts,labels)


def add_autoloc(files, localization):
    """
    Builds the leads dictionary from VOX_coords_mother and jacksheet
    :param files: dictionary of files including 'vox_mom' and 'jacksheet'
    :returns: dictionary of form {lead_name: {contact_name1: contact1, contact_name2:contact2, ...}}
    """
    read_loc(files['native_loc'], localization)

def add_mni(files, localization):
    """
    Builds the leads dictionary from VOX_coords_mother and jacksheet
    :param files: dictionary of files including 'vox_mom' and 'jacksheet'
    :returns: dictionary of form {lead_name: {contact_name1: contact1, contact_name2:contact2, ...}}
    """
    read_mni(files['mni_loc'], localization)

def add_manual_locations(files,localization):
    read_manual_locations(files['manual_loc'],localization)

def file_locations_loc(subject):
    """
    Creates the default file locations dictionary
    :param subject: Subject name to look for files within
    :returns: Dictionary of {file_name: file_location}
    """
    files = dict(
        native_loc=os.path.join(paths.rhino_root, 'data10', 'RAM', 'subjects', subject, 'imaging', subject, 'electrodenames_coordinates_native.csv'),
        mni_loc=os.path.join(paths.rhino_root, 'data10', 'RAM', 'subjects', subject, 'imaging', subject, 'electrodenames_coordinates_mni.csv'),
    )
    return files


