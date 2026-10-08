#!/usr/bin/env python
# coding: utf-8

# # unsupervised_contour_clustering_HDBSCAN.ipynb
# 
# This notebook uses functions stored in tree_shape_tools.py
# 
# After running this notebook you can:
# - run view_tree_shape_classes.ipynb to see tree shape samples from each cluster
# - have a look at some of the views set up in the database
# 
# ### Convert to python script using:
# ```
# jupyter nbconvert --no-prompt --to script unsupervised_contour_clustering_HDBSCAN.ipynb
# ```
# 
# 
# ## References
# - [Gemini reference](https://share.gemini.google/OH0lJw2upRny)
# - [Tuning DBSCAN parameters](https://share.gemini.google/vN3GhPCw2g3x)
# - [Gemini reference for standard hdbscan module](https://share.google/aimode/EBb5xLhfQzgcLtEMP)

import tomllib
from contextlib import contextmanager
from datetime import datetime
from icecream import ic
from tree_shape_tools import run_train_model_pipeline, run_tree_shape_classifier_pipeline
import fire


# # FUNCTIONS

def timestamp():
    """ 
    use for ic formatting 
    """
    return f"{datetime.now().isoformat(sep='T', timespec='seconds')} "

#########################################################################


@contextmanager
def ic_red():
    """ 
    displays ic message in red while within the context 
    """
    RED, RESET = "\033[31m", "\033[0m"
    ic.configureOutput(outputFunction=lambda s: print(f"{RED}{s}{RESET}"))
    try:
        yield
    finally:
        # Automatically revert back to normal
        ic.configureOutput(outputFunction=print)

# # Usage Example:
# ic("Normal color")
# with ic_red():
#     ic("Temporary red message 1")
#     ic("Temporary red message 2")
# ic("Normal color again")

#########################################################################

def run_task(task: str):
    """  
    Task can be TRAIN MODEL or 'CLASSIFY TREE SHAPES'
    """

    ic.configureOutput(prefix=timestamp, includeContext=True)

    ic('starting')

    ic('getting parameters from config.toml')
    # with open("config.toml", "rb") as f:
    #     config = tomllib.load(f)  
    config = dict_from_toml('config.toml')
    ic(config['database'])
    ic(config['trees'])  

    if task =='TRAIN MODEL':
        ic(task)
        run_train_model_pipeline(
            db_path=config['database']['db_path'], 
            db_backup_dir=config['database']['db_backup_dir'], 
            model_path=config['trees']['model_path'], 
            images_per_cluster=config['trees']['images_per_cluster'], 
            gallery_dir=config['trees']['gallery_dir'], 
            min_prob=config['trees']['min_prob']) 

        WARNING = f'IMPORTANT: Please have look at images in the tree cluster gallery ({config['trees']['gallery_dir']}) and update {config['trees']['csv_path']} before proceeding with the CLASSIFY TREE SHAPES task'
        with ic_red():
            ic(WARNING) 

    if task == 'CLASSIFY TREE SHAPES':
        ic(task)
        run_tree_shape_classifier_pipeline(
            db_path=config['database']['db_path'], 
            csv_path=config['trees']['csv_path']
            )

    ic('finished');


# # MAIN

if __name__ == '__main__':
  fire.Fire()
