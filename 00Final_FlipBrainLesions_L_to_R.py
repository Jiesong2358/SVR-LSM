#function:flip the nifti image
from dataclasses import dataclass
from importlib.resources import path
import os
from matplotlib import image
from matplotlib.pyplot import new_figure_manager
import nibabel as nib
import numpy as np
import math

#1.read data, set input and output path
input_folder='C:\\Jie_Documents\\stroke_data\\Lesion_map\\lesions_rawData\\Samoto_tobeflipped'
output_folder='C:\\Jie_Documents\\stroke_data\\Lesion_map\\lesions_rawData\\SAMATO_filpped'
#file_name = 'FCS_{:0>2d}_A_lesion_111_fnirt_111MNI.nii'
file_name = 'S1P0{:0>2d}.nii'

#2.Batch read, flip and save the nii data
img_n=34
for i in range(img_n):
    # TALECON
    # if i==26 or i==28 or i==31:
    #SAMATO
    if i == 4 or i == 9 or i == 30:
        continue
    input_file=os.path.join(input_folder,file_name.format(i+1))
    #flipping the data
    img=nib.load(input_file)
    nii_data=img.get_data()
    nii_data=(np.array(nii_data)).astype('uint8')
    flipped_data=np.flipud(nii_data)
    new_img=nib.Nifti1Image(flipped_data, img.affine, header=img.header)
    nib.save(new_img, os.path.join(output_folder, file_name.format(i+1)))