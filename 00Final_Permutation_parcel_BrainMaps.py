# The code was generated by Jie Song, at UNIGE, 2023
# The code was used to do parcel damage-based SVR-LSM analysis, 
# the aim is to save the brain maps of beta values for each behavior.
import numpy as np
import os
import pandas as pd
from sklearn.svm import SVR
from sklearn.linear_model import LinearRegression
import matplotlib.pyplot as plt
import seaborn as sns
import glob
import scipy.io as scio
import nibabel as nib
from tqdm import tqdm
from statsmodels.stats.multitest import multipletests
from statsmodels.stats.multitest import fdrcorrection
from nilearn import plotting
from nilearn.image import new_img_like
import copy

# Set random seed for reproducibility
np.random.seed(0)
def linear_model(x, m, c):
    return m * x + c

# Function to approximate back-projection for SVR with RBF kernel
def approximate_back_projection(model, support_vectors, gamma):
    dual_coef = model.dual_coef_[0]
    beta_star = sum(dual_coef[i] * support_vectors[i] for i in range(len(dual_coef))) / gamma
    return np.squeeze(beta_star)  # Convert to one-dimensional array

output_dir = 'S:\\GVuilleumier\\jies\\20230201_acute_chronic_Neglect_proj\\2_LesionQuantification\\G_Acute'
mat_names = glob.glob('S:\\GVuilleumier\\jies\\20230201_acute_chronic_Neglect_proj\\2_LesionQuantification\\G_Acute\\FCS_*_A\\Parcel_Damage\\Reshape_FCS_*_A_hcp__percent_damage.mat')
num_subjects = len(mat_names)
COV_file = 'S:\\GVuilleumier\\jies\\20230201_acute_chronic_Neglect_proj\\2_LesionQuantification\\behaviors\\COV\\Acute_COV.csv'
vector_length = 426
figure_path = 'S:\\GVuilleumier\\jies\\20230201_acute_chronic_Neglect_proj\\2_LesionQuantification\\Figures'
atlas_img = nib.load('C:\\Software\\Lesion_Quantification_Toolkit\\Lesion_Quantification_Toolkit\\Support_Tools\\Parcellations\\HCPex\\Reslice_HCPex.nii')
tem_img = nib.load('S:\\GVuilleumier\\jies\\20230201_acute_chronic_Neglect_proj\\3_SVR-LSM\\ch2better.nii.gz')
# Read the x and Y.
all_Y_paths = [
    'S:\\GVuilleumier\\jies\\20230201_acute_chronic_Neglect_proj\\2_LesionQuantification\\Behaviors\\Acute_F1.csv',
    'S:\\GVuilleumier\\jies\\20230201_acute_chronic_Neglect_proj\\2_LesionQuantification\\Behaviors\\Acute_F2.csv',
    'S:\\GVuilleumier\\jies\\20230201_acute_chronic_Neglect_proj\\2_LesionQuantification\\Behaviors\\Acute_F3.csv'
]

all_Y_list = [pd.read_csv(path) for path in all_Y_paths]
# Combine all Y dataframes into a single dataframe
all_Y = pd.concat(all_Y_list, axis=1)

data_X = np.zeros((num_subjects, vector_length))
COV_df = pd.read_csv(COV_file)
data_x_COV = COV_df.values  # Only covariates, not concatenating with data_X

num = 0
for mat_name in mat_names:
    file_path = os.path.join(mat_name)
    data_x = scio.loadmat(file_path)
    data_X[num] = data_x['pcd_vect'][:, 0]
    num += 1

label_file = 'S:\\GVuilleumier\\jies\\20230201_acute_chronic_Neglect_proj\\2_LesionQuantification\\HCPex_parcel_name.mat'
label_data = scio.loadmat(label_file)
regression_model = LinearRegression().fit(data_x_COV, data_X)
residuals = data_X - regression_model.predict(data_x_COV)

# Filter parcels as needed (remove left hemisphere parcels)
parcel_names = [item[0] for item in label_data['Parcel_name'][:, 0]]
mask = ~np.char.startswith(parcel_names, 'L_')
data_X = data_X[:, mask]
parcel_names_R = [item for item in parcel_names if not item.startswith('L_')]

# Apply the mask to label_data as well
label_data['Parcel_name'] = label_data['Parcel_name'][mask, :]

# Count the number of subjects with values greater than 0 for each feature
num_subjects_positive = np.sum(data_X > 0, axis=0)
# Identify features where at least 4 subjects have values greater than 0
features_to_include = np.where(num_subjects_positive >= 4)[0]
# Apply the same mask to parcel_names
selected_parcel_names = np.array(parcel_names_R)[features_to_include]

# Filter data_X and residuals to include only selected features
data_X_filtered = data_X[:, features_to_include]
residuals_filtered = residuals[:, features_to_include]

# Perform linear regression to regress out the covariates on filtered data
regression_model_filtered = LinearRegression().fit(data_x_COV, data_X_filtered)
residuals_filtered = data_X_filtered - regression_model_filtered.predict(data_x_COV)

num_permutations = 5000
# Initialize dictionaries to store p-values and significant parcels
p_values_dict = {}
significant_parcels_dict = {}
beta_list = []
p_values = []

# Iterate over each behavior
for behavior, Y_data in all_Y.items():
    data_Y = Y_data.values.ravel()  # Flatten Y data
    # Create and fit the SVR model with RBF kernel and specified parameters
    model = SVR(kernel='rbf', C=30.0, epsilon=0.1, max_iter=10000,
                tol=0.001, verbose=True, cache_size=1000, shrinking=True, gamma=5)
    model.fit(residuals_filtered, data_Y)
    # Calculate beta map using the approximate back-projection method
    support_vectors = model.support_vectors_
    gamma = model._gamma
    beta = approximate_back_projection(model, support_vectors, gamma)
    beta_list.append(beta) 
    
    # Perform permutations
    for _ in tqdm(range(num_permutations), desc=f"Permutations for {behavior}"):
        np.random.shuffle(data_Y)
        model.fit(residuals_filtered, data_Y)
        support_vectors = model.support_vectors_
        gamma = model._gamma
        permuted_beta = approximate_back_projection(model, support_vectors, gamma)
        # Calculate p-values for each parcel
        p_values.append([np.mean(permuted_beta[i] >= beta[i]) for i in range(len(beta))])
    # Calculate average p-values across permutations
    avg_p_values = np.mean(p_values, axis=0)
    significance_threshold = 0.05
    # Filter significant parcels based on threshold
    significant_parcels = [parcel for parcel, p_value in zip(selected_parcel_names, avg_p_values) if p_value < significance_threshold]
    
    # Store results in dictionaries
    p_values_dict[behavior] = avg_p_values
    # Save parcels and p-values to a text file
    output_file_path = os.path.join(output_dir, f'parcels_{behavior}.csv')
    with open(output_file_path, 'w') as file:
        file.write("Parcel Name, p-value\n")
        for parcel, p_value in zip(selected_parcel_names, avg_p_values):
            file.write(f"{parcel}, {p_value:.10f}\n")
    # save significant parcels to a text file (p<0.05)
    output_file_path = os.path.join(output_dir, f'significant_parcels_{behavior}.csv')
    with open(output_file_path, 'w') as file:
        file.write("Parcel Name, p-value\n")
        for parcel, p_value in zip(selected_parcel_names, avg_p_values):
            if p_value < significance_threshold:
                file.write(f"{parcel}, {p_value:.10f}\n")
    
    # Perform FWE correction on p-values
    rejected_null, corrected_p_values, _, _ = multipletests(avg_p_values, method='holm')
    # Save significant parcels and FWE-corrected p-values to the same text file
    output_file_path = os.path.join(output_dir, f'FWE-significant_parcels_{behavior}.csv')
    with open(output_file_path, 'w') as file:
        file.write("Parcel Name, p-value (Uncorrected), p-value (Corrected)\n")
        for parcel, uncorrected_p_value, corrected_p_value, rejected in zip(selected_parcel_names, avg_p_values, corrected_p_values, rejected_null):
            file.write(f"{parcel}, {uncorrected_p_value:.10f}, {corrected_p_value:.10f}, {rejected}\n")
    # do FDR correction
    corrected_p_values = fdrcorrection(avg_p_values, alpha=0.05, method='indep')[1]
    with open(output_file_path, 'a') as file:
        file.write("Corrected p-value\n")
        for p_value in corrected_p_values:
            file.write(f"{p_value:.10f}\n")
    # Save significant parcels and FDR-corrected p-values to the same text file
    output_file_path = os.path.join(output_dir, f'FDR-significant_parcels_{behavior}.csv')
    with open(output_file_path, 'w') as file:
        file.write("Parcel Name, p-value (Uncorrected), p-value (Corrected)\n")
        for parcel, uncorrected_p_value, corrected_p_value in zip(selected_parcel_names, avg_p_values, corrected_p_values):
            file.write(f"{parcel}, {uncorrected_p_value:.10f}, {corrected_p_value:.10f}\n")
  
bool_mask = np.zeros(len(parcel_names_R), dtype=bool)
bool_mask[features_to_include] = True
         
beta = np.array(beta_list)
weights_2d = np.zeros((beta.shape[0],
                       len(parcel_names_R)))
weights_2d[:, ~bool_mask] = np.nan 
weights_2d[:, bool_mask] = beta
#save the beta values from weights_2d of all behaviors to a .csv file
output_file_path = os.path.join(output_dir, 'parcel_beta_values.csv')
with open(output_file_path, 'w') as file:
    file.write("Behavior,")
    file.write(", ".join(selected_parcel_names))
    file.write("\n")
    for i, behavior in enumerate(all_Y.keys()):
        file.write(f"{behavior},")
        file.write(", ".join([f"{beta_value:.10f}" for beta_value in beta[i]]))
        file.write("\n")

# Plot heatmap for beta values
plt.figure(figsize=(36, 9))
sns.heatmap(weights_2d, cmap='jet', xticklabels=False,
            yticklabels=False, annot=False, fmt=".2f", cbar=False, mask=np.isnan(weights_2d))
plt.xticks(rotation=45)
plt.tight_layout()
plt.savefig(os.path.join(output_dir, 'A-beta.png'))
plt.show()

# Save beta volumes to NIfTI files and plot the brain maps
img_array = np.asarray(atlas_img.get_fdata())
weights_2d_all = np.zeros((beta.shape[0], 426))
mask_idx = np.where(mask)[0]
second_mask_idx = mask_idx[features_to_include]
# Initialize weights_2d_all with NaN values
weights_2d_all = np.full((beta.shape[0], len(parcel_names)), np.nan)
# Use the final_mask to assign values to weights_2d_all
weights_2d_all[:, second_mask_idx] = beta
for behavior in range(3):
    new_array = copy.deepcopy(img_array)
    for i in range(weights_2d_all.shape[1]):
        new_array[img_array == i + 1] = weights_2d_all[behavior, i]
    new_image = nib.Nifti1Image(new_array, atlas_img.affine, header=atlas_img.header)
    nib.save(new_image, os.path.join(output_dir, f'beta_map_{behavior + 1}.nii'))

    # Save beta volumes to NIfTI files
for behavior in range(3):
    new_array = copy.deepcopy(img_array)
    for i in range(weights_2d_all.shape[1]):
        new_array[img_array == i + 1] = weights_2d_all[behavior, i]
    new_image = nib.Nifti1Image(new_array, atlas_img.affine, header=atlas_img.header)
    nib.save(new_image, os.path.join(output_dir, f'beta_map_{behavior + 1}.nii'))

    # plot the beta map
    # display = plotting.plot_stat_map(new_image, cut_coords=range(-10, 41, 10), draw_cross=False,
    #                                     threshold=0.01, colorbar=False,
    #                                     vmax=150, display_mode='z', bg_img=tem_img,
    #                                     black_bg=True, annotate=False, cmap='jet')

    # Define your custom vmax and vmin asymmetrically, !! This step need changes on nilearn function
    vmax = 124
    vmin = -27

    # Plot the image using plot_stat_map
    display = plotting.plot_stat_map(new_image,
                                    cut_coords=range(-10, 61, 10),  # Slices along the z-axis
                                    draw_cross=False,
                                    threshold=0.01, 
                                    colorbar=True,
                                    vmax=vmax, 
                                    display_mode='z', 
                                    bg_img=tem_img,  # Background template image
                                    black_bg=True,
                                    annotate=False,
                                    cmap='jet')
    cbar = display._cbar

    # Set the colorbar ticks at vmin, vmax, and 0
    vmin = -vmax  # Define vmin as the negative of vmax or set manually
    cbar.set_ticks([vmin, 0, vmax])
    # Optionally, add custom tick labels if needed
    cbar.set_ticklabels([f'{vmin:.2f}', '0', f'{vmax:.2f}'])

    # Save the figure
    # figure_name = f'new_beta_map_{behavior + 1}.png'
    figure_name = f'colorbar_{behavior + 1}.png'
    plt.savefig(os.path.join(output_dir, figure_name), dpi=300)
    # Show the plot
    plt.show()
