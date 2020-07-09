from __future__ import division

import itertools
import numpy as np

from matminer.featurizers.utils.grdf import Gaussian, Histogram
from matminer.featurizers.base import BaseFeaturizer


class GaussianSymmFunc(BaseFeaturizer):
    """
    Gaussian symmetry function features suggested by Behler et al.

    The function is based on pair distances and angles, to approximate the
    functional dependence of local energies, originally used in the fitting
    of machine-learning potentials.
    The symmetry functions can be divided to a set of radial functions
    (g2 function), and a set of angular functions (g4 function).
    The number of symmetry functions returned are based on parameters
    of etas_g2, etas_g4, zetas_g4 and gammas_g4.
    See the original papers for more details:
    “Atom-centered symmetry functions for constructing high-dimensional
    neural network potentials”, J Behler, J Chem Phys 134, 074106 (2011).
    The cutoff function is taken as the polynomial form (cosine_cutoff)
    to give a smoothed truncation.
    A Fortran and a different Python version can be found in the code
    Amp: Atomistic Machine-learning Package
    (https://bitbucket.org/andrewpeterson/amp).
    Args:
        etas_g2 (list of floats): etas used in radial functions.
                                  (default: [0.05, 4., 20., 80.])
        etas_g4 (list of floats): etas used in angular functions.
                                  (default: [0.005])
        zetas_g4 (list of floats): zetas used in angular functions.
                                   (default: [1., 4.])
        gammas_g4 (list of floats): gammas used in angular functions.
                                    (default: [+1., -1.])
        cutoff (float): cutoff distance. (default: 6.5)
    """

    def __init__(self, etas_g2=None, etas_g4=None, zetas_g4=None,
                 gammas_g4=None, cutoff=6.5):
        self.etas_g2 = etas_g2 if etas_g2 else [0.05, 4., 20., 80.]
        self.etas_g4 = etas_g4 if etas_g4 else [0.005]
        self.zetas_g4 = zetas_g4 if zetas_g4 else [1., 4.]
        self.gammas_g4 = gammas_g4 if gammas_g4 else [+1., -1.]
        self.cutoff = cutoff

    @staticmethod
    def cosine_cutoff(rs, cutoff):
        """
        Polynomial cutoff function to give a smoothed truncation of the Gaussian
        symmetry functions.
        Args:
            rs (ndarray): distances to elements
            cutoff (float): cutoff distance.
        Returns:
            (ndarray) cutoff function.
        """
        cutoff_fun = 0.5 * (np.cos(np.pi * rs / cutoff) + 1.)
        cutoff_fun[rs > cutoff] = 0
        return cutoff_fun

    @staticmethod
    def g2(eta, rs, cutoff):
        """
        Gaussian radial symmetry function of the center atom,
        given an eta parameter.
        Args:
            eta: radial function parameter.
            rs: distances from the central atom to each neighbor
            cutoff (float): cutoff distance.
        Returns:
            (float) Gaussian radial symmetry function.
        """
        ridge = (np.exp(-eta * (rs ** 2.) / (cutoff ** 2.)) *
                 GaussianSymmFunc.cosine_cutoff(rs, cutoff))
        return ridge.sum()

    @staticmethod
    def g4(etas, zetas, gammas, neigh_dist, neigh_coords, cutoff):
        """
        Gaussian angular symmetry function of the center atom,
        given a set of eta, zeta and gamma parameters.
        Args:
            eta ([float]): angular function parameters.
            zeta ([float]): angular function parameters.
            gamma ([float]): angular function parameters.
            neigh_coords (list of [floats]): coordinates of neighboring atoms, with respect
                to the central atom
            cutoff (float): cutoff parameter.
        Returns:
            (float) Gaussian angular symmetry function for all combinations of eta, zeta, gamma
        """

        output = np.zeros((len(etas)*len(zetas)*len(gammas),))

        # Loop over each neighbor j
        for j, neigh_j in enumerate(neigh_coords):

            # Compute the distance of each neighbor (k) to r
            r_ij = neigh_dist[j]
            d_jk = neigh_coords[(j+1):] - neigh_coords[j]
            r_jk = np.linalg.norm(d_jk, 2, axis=1)
            r_ik = neigh_dist[(j+1):]

            # Compute the cosine term
            cos_theta = np.dot(neigh_coords[(j + 1):], neigh_coords[j]) / r_ij / r_ik

            # Compute the cutoff function (independent of eta/zeta/gamma)
            cutoff_fun = GaussianSymmFunc.cosine_cutoff(np.array([r_ij]), cutoff) * \
                         GaussianSymmFunc.cosine_cutoff(r_ik, cutoff) * \
                         GaussianSymmFunc.cosine_cutoff(r_jk, cutoff)

            # Compute the g4 for each combination of eta/gamma/zeta
            ind = 0
            for eta in etas:
                # Compute the eta term
                eta_term = np.exp(-eta * (r_ij ** 2. + r_ik ** 2. + r_jk ** 2.) /
                                  (cutoff ** 2.)) * cutoff_fun
                for zeta in zetas:
                    for gamma in gammas:
                        term = (1. + gamma * cos_theta) ** zeta * eta_term
                        output[ind] += term.sum() * 2. ** (1. - zeta)
                        ind += 1
        return output

    def featurize(self, struct, idx):
        """
        Get Gaussian symmetry function features of site with given index
        in input structure.
        Args:
            struct (Structure): Pymatgen Structure object.
            idx (int): index of target site in structure.
        Returns:
            (list of floats): Gaussian symmetry function features.
        """
        gaussian_funcs = []

        # Get the neighbors within the cutoff
        neighbors = struct.get_neighbors(struct[idx], self.cutoff)

        # Get coordinates of the neighbors, relative to the central atom
        neigh_coords = np.subtract([neigh[0].coords for neigh in neighbors], struct[idx].coords)

        # Get the distances for later use
        neigh_dists = np.array([neigh[1] for neigh in neighbors])

        # Compute all G2
        for eta_g2 in self.etas_g2:
            gaussian_funcs.append(self.g2(eta_g2, neigh_dists, self.cutoff))

        # Compute all G4s
        gaussian_funcs.extend(GaussianSymmFunc.g4(self.etas_g4, self.zetas_g4, self.gammas_g4,
                                                  neigh_dists, neigh_coords, self.cutoff))
        return gaussian_funcs

    def feature_labels(self):
        return ['G2_{}'.format(eta_g2) for eta_g2 in self.etas_g2] + \
               ['G4_{}_{}_{}'.format(eta_g4, zeta_g4, gamma_g4)
                for eta_g4 in self.etas_g4
                for zeta_g4 in self.zetas_g4
                for gamma_g4 in self.gammas_g4]

    def citations(self):
        gsf_citation = (
            '@Article{Behler2011, author = {Jörg Behler}, '
            'title = {Atom-centered symmetry functions for constructing '
            'high-dimensional neural network potentials}, '
            'journal = {The Journal of Chemical Physics}, year = {2011}, '
            'volume = {134}, number = {7}, pages = {074106}, '
            'doi = {10.1063/1.3553717}}')
        amp_citation = (
            '@Article{Khorshidi2016, '
            'author = {Alireza Khorshidi and Andrew A. Peterson}, '
            'title = {Amp : A modular approach to machine learning in '
            'atomistic simulations}, '
            'journal = {Computer Physics Communications}, year = {2016}, '
            'volume = {207}, pages = {310--324}, '
            'doi = {10.1016/j.cpc.2016.05.010}}')
        return [gsf_citation, amp_citation]

    def implementors(self):
        return ['Qi Wang']



class AngularFourierSeries(BaseFeaturizer):
    """
    Compute the angular Fourier series (AFS), including both angular and radial info

    The AFS is the product of pairwise distance function (g_n, g_n') between two pairs
    of atoms (sharing the common central site) and the cosine of the angle
    between the two pairs. The AFS is a 2-dimensional feature (the axes are g_n,
    g_n').

    Examples of distance functionals are square functions, Gaussian, trig
    functions, and Bessel functions. An example for Gaussian:
        lambda d: exp( -(d - d_n)**2 ), where d_n is the coefficient for g_n

    See :func:`~matminer.featurizers.utils.grdf` for a full list of available binning functions.

    There are two preset conditions:
        gaussian: bin functions are gaussians
        histogram: bin functions are rectangular functions

    Features:
        AFS ([gn], [gn']) - Angular Fourier Series between binning functions (g1 and g2)

    Args:
        bins:   ([AbstractPairwise]) a list of binning functions that
                implement the AbstractPairwise base class
        cutoff: (float) maximum distance to look for neighbors. The
                 featurizer will run slowly for large distance cutoffs
                 because of the number of neighbor pairs scales as
                 the square of the number of neighbors
    """

    def __init__(self, bins, cutoff=10.0):
        self.bins = bins
        self.cutoff = cutoff

    def featurize(self, struct, idx):
        """
        Get AFS of the input structure.
        Args:
            struct (Structure): Pymatgen Structure object.
            idx (int): index of target site in structure struct.

        Returns:
            Flattened list of AFS values. the list order is:
                g_n g_n'
        """

        if not struct.is_ordered:
            raise ValueError("Disordered structure support not built yet")

        # Generate list of neighbor position vectors (relative to central
        # atom) and distances from each central site as tuples
        sites = struct._sites
        central_site = sites[idx]
        neighbors_lst = struct.get_neighbors(central_site, self.cutoff)
        neighbor_collection = [
            (neighbor[0].coords - central_site.coords, neighbor[1])
            for neighbor in neighbors_lst]

        # Generate exhaustive permutations of neighbor pairs around each
        # central site (order matters). Does not allow repeat elements (i.e.
        # there are two distinct sites in every permutation)
        neighbor_tuples = itertools.permutations(neighbor_collection, 2)

        # Generate cos(theta) between neighbor pairs for each central site.
        # Also, retain data on neighbor distances for each pair
        # process with matrix algebra, we really need the speed here
        data = np.array(list(neighbor_tuples))
        v1, v2 = np.vstack(data[:, 0, 0]), np.vstack(data[:, 1, 0])
        distances = data[:, :, 1]
        neighbor_pairs = np.concatenate([
            np.clip(np.einsum('ij,ij->i', v1, v2) /
                    np.linalg.norm(v1, axis=1) /
                    np.linalg.norm(v2, axis=1), -1.0, 1.0).reshape(-1, 1),
            distances], axis=1)

        # Generate distance functional matrix (g_n, g_n')
        bin_combos = list(itertools.product(self.bins, repeat=2))

        # Compute AFS values for each element of the bin matrix
        # need to cast arrays as floats to use np.exp
        cos_angles, dist1, dist2 = neighbor_pairs[:, 0].astype(float),\
            neighbor_pairs[:, 1].astype(float),\
            neighbor_pairs[:, 2].astype(float)
        features = [sum(combo[0](dist1) * combo[1](dist2) *
                        cos_angles) for combo in bin_combos]

        return features

    def feature_labels(self):
        bin_combos = list(itertools.product(self.bins, repeat=2))
        return ['AFS ({}, {})'.format(combo[0].name(), combo[1].name())
                for combo in bin_combos]

    @staticmethod
    def from_preset(preset, width=0.5, spacing=0.5, cutoff=10):
        """
        Preset bin functions for this featurizer. Example use:
            >>> AFS = AngularFourierSeries.from_preset('gaussian')
            >>> AFS.featurize(struct, idx)

        Args:
            preset (str): shape of bin (either 'gaussian' or 'histogram')
            width (float): bin width. std dev for gaussian, width for histogram
            spacing (float): the spacing between bin centers
            cutoff (float): maximum distance to look for neighbors
        """

        # Generate bin functions
        if preset == "gaussian":
            bins = []
            for center in np.arange(0., cutoff, spacing):
                bins.append(Gaussian(width, center))
        elif preset == "histogram":
            bins = []
            for start in np.arange(0, cutoff, spacing):
                bins.append(Histogram(start, width))
        else:
            raise ValueError('Not a valid preset condition.')
        return AngularFourierSeries(bins, cutoff=cutoff)

    def citations(self):
        return ['@article{PhysRevB.95.144110, title = {Representation of compo'
                'unds for machine-learning prediction of physical properties},'
                ' author = {Seko, Atsuto and Hayashi, Hiroyuki and Nakayama, '
                'Keita and Takahashi, Akira and Tanaka, Isao},'
                'journal = {Phys. Rev. B}, volume = {95}, issue = {14}, '
                'pages = {144110}, year = {2017}, publisher = {American Physic'
                'al Society}, doi = {10.1103/PhysRevB.95.144110}}']

    def implementors(self):
        return ["Maxwell Dylla", "Logan Williams"]
