## Guide to adding datasets to matminer:

_All information current as of 10/24/2018_

In addition to providing tools for retrieving current data from several standard 
materials science databases, matminer also provides a suite of static datasets
pre-formatted as pandas DataFrame objects and stored as compressed JSON files. 
These files are stored on Figshare, a long term academic data storage platform,
and include metadata making each dataset discoverable and clearly linked to the
research and contributors that generated said data. 

This functionality serves two purposes. First as a way for others to quickly 
and easily access data used in research at the Hacking Materials group and 
second to provide the community with a set of standard datasets that can be 
used for benchmarking purposes. As the application of machine learning in 
materials science matures, there is a growing need for a group of benchmark 
datasets that researchers can use as standard training and testing sets for 
comparing model performance against.

To add a dataset to the collection currently supported by matminer there are 
five primary steps:

1.	#### Prepare the dataset for long term hosting
      To work properly with matminer's loading functions it is assumed that 
      all datasets are pandas DataFrame objects stored as JSON files using the 
      MontyEncoder encoding scheme available in the monty Python package. Any 
      datasets added to matminer should ensure this requirement. 
      
      The script `prep_dataset_for_figshare.py` was written to expedite and 
      standardize this process. If the dataset being uploaded needs no 
      modification from the contents stored in the file, one can simply run this 
      script to convert your dataset to the desired format like so: 
      `python prep_dataset_for_figshare.py -fp /path/to/dataset(s) 
      -ct (compression_type: gz or bz2)` This script can take multiple file 
      paths and/or directory names. If given a directory name it will crawl
      the directory and try to process all files within. The prepped files will 
      then be available in `~/dataset_to_json/` along with a .txt file containing 
      some metadata on the files which will be used later on. 
      
      If modification does need to be made to the dataset or if you would 
      like the dataset name to be separate from that of the file being converted,
      users will need to make a small modification to this script prior to 
      running it on their selected datasets.
      
      To update the script to preprocess your dataset:
      - ##### Write a preprocessor for the dataset in prep_dataset_for_figshare.py
        
        The preprocessor should take the dataset path, do any necessary 
        preprocessing to turn it into a usable dataframe, and return a tuple 
        of the form `(string_of_dataset_name, dataframe)`. 
        If the preprocessor produces more than one dataset it should 
        return a tuple of two lists of the form 
        `([dataset_name_1, dataset_name_2, …], [df_1, df_2, …])`
        
        For example:
        ```python
        def _preprocess_heusler_magnetic(file_path):
            df = _read_dataframe_from_file(file_path)

            dropcols = ['gap width', 'stability']
            df = df.drop(dropcols, axis=1)

            return "heusler_magnetic", df
        ```
        Here `_read_dataframe_from_file()` is a simple utility function that
        determines what pandas loading function to use based on the file type
        of the path passed to it. Keyword arguments passed to this function are
        passed on to the underlying pandas loading functions.
        
        An example for preprocessors that return multiple datasets:
        ```python
        def _preprocess_double_perovskites_gap(file_path):
            df = pd.read_excel(file_path, sheet_name='bandgap')

            df = df.rename(columns={'A1_atom': 'a_1', 'B1_atom': 'b_1',
                            'A2_atom': 'a_2', 'B2_atom': 'b_2'})
            lumo = pd.read_excel(file_path, sheet_name='lumo')

            return ["double_perovskites_gap", "double_perovskites_gap_lumo"], [df, lumo]
        ```
        
      - ##### Add the preprocessor function to a dictionary which maps file names to preprocessors in prep_dataset_for_figshare.py
        The prep script identifies datasets by their file name, a dictionary 
        called `_datasets_to_preprocessing_routines` maps these dataset names
        to their preprocessor and should be updated like so:
        ```python
        _datasets_to_preprocessing_routines = {
        "elastic_tensor_2015": _preprocess_elastic_tensor_2015,
        "piezoelectric_tensor": _preprocess_piezoelectric_tensor,
        .
        .
        .
        "wolverton_oxides": _preprocess_wolverton_oxides,
        "m2ax_elastic": _preprocess_m2ax,
        YOUR_DATASET_FILE_NAME: YOUR_PREPROCESSOR,
        ```
        Once this is done the preprocessor is ready to use.

2.	#### Upload the dataset to long term hosting
      Once the dataset file is ready, it should be hosted on Figshare
      or a comparable open access academic data hosting service. For the Hacking
      Materials group:
      - Details for getting access to the group Figshare account is available in
      the group handbook.
      - Add the dataset compressed json file as well as the original file as an 
      entry in the matminer datasets figshare project
      - Fill out **_ALL_** metadata carefully, see existing entries for 
      examples of expected quality of citations and descriptions. If the dataset
      originally came from a source outside the group they should be 
      thoroughly cited.

3.	#### Update the matminer dataset metadata file
      Matminer stores a file called `dataset_metadata.json` which contains 
      information on all datasets available in the package. This file is 
      automatically checked by CircleCI for propper formatting and the 
      available datasets are regularly checked to ensure they match the 
      descriptors contained in this metadata. While the appropriate metadata
      can be added manually, it is preferable to run the helper script
      `modify_dataset_metadata.py` to do the bulk of interfacing with this file
      to prevent missing data or formatting mistakes.
      - Run the `modify_dataset_metadata.py` file and add the appropriate 
      metadata, see existing metadata as a guideline for new datasets. 
      The url attribute should be filled with a figshare download link for 
      the individual file on figshare. Other items will be dataset specific 
      or included in the .txt file produced in step 1.
      - Replace the metadata file in matminer/datasets with the 
      newly generated file (should be done automatically)
      - Look over the modified `dataset_metadata.json` file and 
      fix mistakes if necessary.

4.	#### Update the dataset tests and loading code
      Dataset testing uses unit tests to ensure dataset metadata and dataset content
      is formatted properly and available. When adding a new datasets these tests 
      need updated. In addition matminer provides a set of convenience functions that
      explicitly load a single dataset as opposed to the keyword based generic loader.
      These convenience functions provide additional post processing options for
      filtering or modifying data in the dataset after it has been loaded. A 
      convenience function should be added alongside dataset tests.

      - Update dataset names saved in `matminer/datasets/tests/base.py`
        ```python
        class DataSetTest(unittest.TestCase):
          def setUp(self):
              self.dataset_names = [
                'flla',
                'elastic_tensor_2015',
                'piezoelectric_tensor',
                .
                .
                .
                YOUR DATSET NAME HERE
              ]
        ```
      - Write a test for loading the dataset in test_datasets.py. 
      
        These tests ensure that the dataset is downloadable and that its data matches what
        is described in the file metadata. See prior datasets for examples and 
        the .txt file from step 1 for column type info. A typical test consists of
        a call to a universal test function that only needs specifiers of what 
        dataframe columns should be of what type, followed by dataset specific type tests
        if necessary.
        
        Example:
        ```python
        def test_dielectric_constant(self):
            # Universal Tests
            object_headers = ['material_id', 'formula', 'structure',
                              'e_electronic', 'e_total', 'cif', 'meta',
                              'poscar']
    
            numeric_headers = ['nsites', 'space_group', 'volume', 'band_gap',
                               'n', 'poly_electronic', 'poly_total']
    
            bool_headers = ['pot_ferroelectric']
    
            self.universal_dataset_check(
                "dielectric_constant", object_headers, numeric_headers,
                bool_headers=bool_headers,
            )
    
            # Unique tests
            df = load_dataset("dielectric_constant")
            self.assertEqual(type(df['structure'][0]), Structure)
        ```
      - Write a convenience function for the dataset in `convenience_loaders.py`
        This can be as simple as just returning the results of load_dataset 
        or provide the user with extra options to return only subsets 
        of the dataset with certain properties.
        
        Example:
        ```python
        def load_elastic_tensor(version="2015", include_metadata=False, data_home=None,
                    download_if_missing=True):
            """
            Convenience function for loading the elastic_tensor dataset.
        
            Args:
                version (str): Version of the elastic_tensor dataset to load
                    (defaults to 2015)
        
                include_metadata (bool): Whether or not to include the cif, meta,
                    and poscar dataset columns. False by default.
        
                data_home (str, None): Where to loom for and store the loaded dataset
        
                download_if_missing (bool): Whether or not to download the dataset if
                    it isn't on disk
        
            Returns: (pd.DataFrame)
            """
            df = load_dataset("elastic_tensor" + "_" + version, data_home,
                              download_if_missing)
        
            if not include_metadata:
                df = df.drop(['cif', 'kpoint_density', 'poscar'], axis=1)
        
            return df
        ```
      - Write a test for the added convenience function
        These tests can be simple and will depend on the options provided in the
        convenience function. See existing tests for examples.

5.	#### Update GitHub repository
      - Make a commit describing the added dataset
      - Make a pull request from your fork to the primary repository