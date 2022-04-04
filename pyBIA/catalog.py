import numpy as np
import matplotlib.pyplot as plt
import astropy.units as u
from astropy.stats import sigma_clipped_stats

from photutils.detection import DAOStarFinder
from photutils.aperture import aperture_photometry, CircularAperture, CircularAnnulus
from photutils import detect_threshold
from astropy.convolution import Gaussian2DKernel
from astropy.stats import gaussian_fwhm_to_sigma
from photutils import detect_sources
from photutils.segmentation import SourceCatalog

from pyBIA import data_processing

#hdu = fits.open('/Users/daniel/Desktop/NDWFS_Tiles/Bw_FITS/NDWFSJ1426p3236_Bw_03_fix.fits')
#data = hdu[0].data


def create_catalog(data, error=None, morph_params=False, x=None, y=None, aperture=15, annulus_in=20, annulus_out=35, 
    invert=False, path=''):
    """
    Calculates the photometry of the object(s) in the
    given position(s). The parameters x and y should be
    1D arrays containing the pixel location of each source. 
    
    If no positions are input then a catalog is automatically 
    generated by selecting sources brighter than 2 standard 
    deviations than the background.
    
    Example:
        We can use the world coordinate system astropy
        provides to convert our ra and dec to x and y pixels:

        >>> hdu = astropy.io.fits.open(name)
        >>> wcsobj= astropy.wcs.WCS(header = hdu[0].header)
        >>> x_pix, y_pix = wcsobj.all_world2pix(ra, dec, 0) 
        >>> catalog = pyBIA.extract_objects.photometry(data, x_pix, y_pix)

    Args:
        data (array): 2D array.
        error (array, optional): 2D array containing the rms error map.
        morph_params (bool): If True image esegmentation is performed and
            morphological parameters are computed. Defaults to False. 
        x (array, optional): 1D array containing the x pixel position.
            Can contain one position or multiple samples.
        y (array, optional): 1D array containing the y pixel position.
            Can contain one position or multiple samples.
        aperture (int): The radius of the photometric aperture. Defaults to 15.
        annulus_in (int): The inner radius of the cirtular aperture
            that will be used to calculate the background. Defaults to 20.
        annulus_out (int): The outer radius of the cirtular aperture
                that will be used to calculate the background. Defaults to 35.
        path (str): By default the text file containing the photometry will be
            saved to the local directory, unless an absolute path to a desired
            directory is entered here.
    Note:
        As Lyman-alpha nebulae are diffuse sources with
        extended emission features, the default radius of
        the circular photometric aperture is 15 pixels. This 
        large aperture allows us to encapsulate the largest blobs.
    
        The background is calculated as the median pixel value
        within the area of the annulus. Increasing the size of the
        annulus may yield more robust background measurements. This
        is very important when extracting photometry in crowded fields
        where surrounding sources may skew the median background.
                
    Returns:
        array: 1D array containing the photometric flux of the objects, and
            another array containing the photometric error if an rms map is input.
        text file: A text file named "photometric_catalog" containing the 
            photometry of all objects, which will be saved to the local directory, 
            unless a path argument is specified. If x and y positions are input, then 
            the order of the entries in the saved catalog will be in the 
            order of the x and y position arrays.

    """
    
    if error is not None:
        if data.shape != error.shape:
            raise ValueError("The rms error map must be the same shape as the data array.")
    if aperture > annulus_in or annulus_in > annulus_out:
        raise ValueError('The radius of the inner and out annuli must be larger than the aperture radius.')
    if x is not None:
        try: #If position array is a single number it will be converted to a list of unit length
            len(x)
        except TypeError:
            x, y = [x], [y]
        if len(x) != len(y):
            raise ValueError("The two position arrays (x & y) must be the same size.")
        
    if x is None:
        mean, median, std = sigma_clipped_stats(data, sigma=3.0)
        print('Performing source detection -- this will take several minutes.')
        daofind = DAOStarFinder(fwhm=3.0, threshold=2.*std)  
        sources = daofind(data - median)  
        for col in sources.colnames:  
            sources[col].info.format = '%.8g'  # for consistent table output        
        x, y = np.array(sources['xcentroid']), np.array(sources['ycentroid'])

    positions = []
    for it in range(len(x)):
        positions.append((x[it], y[it]))

    apertures = CircularAperture(positions, r=aperture)
    annulus_apertures = CircularAnnulus(positions, r_in=annulus_in, r_out=annulus_out)
    annulus_masks = annulus_apertures.to_mask(method='center')
    annulus_data = annulus_masks[0].multiply(data)
    mask = annulus_masks[0].data
    annulus_data_1d = annulus_data[mask > 0]
    median_bkg = np.median(annulus_data_1d)
        
    if error is None:
        phot_table = aperture_photometry(data, apertures)
        photometry = phot_table['aperture_sum'] - (median_bkg * apertures.area)
        if morph_params == True:
            prop_list = morph_parameters(data, x, y, invert=True)
            return photometry, prop_list
        return photometry
       
    phot_table = aperture_photometry(data, apertures, error=error)
    photometry = phot_table['aperture_sum'] - (median_bkg * apertures.area)
    photometry_err = phot_table['aperture_sum_err']
    if morph_params == True:
        prop_list = morph_parameters(data, x, y, invert=True)
        return photometry, photometry_err, prop_list
    return photometry, photometry_err
        

def morph_parameters(data, x, y, invert=False):
    """
    Applies image segmentation on each object to calculate morphological 
    parameters. These parameters can be used to train a machine learning classifier.
    
    Args:
        data (array): 2D array.
        x (array): 1D array containing the x pixel position.
            Can contain one position or multiple samples.
        y (array): 1D array containing the y pixel position.
            Can contain one position or multiple samples.
        invert (bool): If True the x & y coordinates will be
            switched when cropping out the object, see Note below.
            Defaults to False.

    Note:
        This procedure requires x & y positions as each source 
        is isolated before the segmentation is performed. If your
        image array is less than 100x100 pixels, the procedure will fail.

        IMPORTANT: When loading data from a .fits file please note the pixel convention
        is switched. The (x, y) = (0, 0) position is on the top left corner of the .fits
        image. The standard convention is for the (x, y) = (0, 0) to be at the bottom left
        corner of the data. We strongly recommend you double-check your data coordinate
        convention. We made use of .fits data with the (x, y) = (0, 0) position at the top
        left of the image, for this reason we switched x and y when cropping out individual
        objects. The parameter invert=True performs the coordinate switch for us. This is only
        required when running this function as the image must be cropped before segmentation.

    
    Return:
        A catalog of morphological parameters.
        
    """
    try: #If position array is a single number it will be converted to a list of unit length
        len(x)
    except TypeError:
        x, y = [x], [y]
    if invert == True:
        x, y = y, x

    prop_list=[]
    for i in range(len(x)):
        new_data = data_processing.crop_image(data, int(x[i]), int(y[i]), 100)
        threshold = detect_threshold(new_data, nsigma=1.)

        sigma = 3.0 * gaussian_fwhm_to_sigma   
        kernel = Gaussian2DKernel(sigma, x_size=3, y_size=3)
        kernel.normalize()
        segm = detect_sources(new_data, threshold, npixels=5, kernel=kernel)
        props = SourceCatalog(new_data, segm, kernel=kernel)
   
        sep_list=[]
        for xx in range(len(props)):
            xcen = float(props[xx].centroid[0])
            ycen = float(props[xx].centroid[1])
        
            sep = np.sqrt((xcen-50)**2 + (ycen-50)**2)
            sep_list.append(sep)
    
        inx = np.where(sep_list == np.min(sep_list))[0]
        if len(inx) > 1:
            inx = inx[0]
            props = props[int(inx)]
        prop_list.append(props)

    return prop_list

def save_catalog(photometry, photometry_err, prop_list):
    """
    """
    return photometry

def plot(data, cmap='gray'):
    """
    Plots 2D array using a robust colorbar range to
    ensure proper visibility.
    
    Args:
        data (array): 2D array for single image, or 
        3D array with stacked channels.
        cmap (str): Colormap to use when generating the image.
    Returns:
        Image
        
    """
    
    index = np.where(np.isfinite(data))
    std = np.median(np.abs(data[index]-np.median(data[index])))
    vmin = np.median(data[index]) - 3*std
    vmax = np.median(data[index]) + 10*std
    
    plt.imshow(data, vmin=vmin, vmax=vmax, cmap=cmap)
    plt.show()
