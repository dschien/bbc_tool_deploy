# Copyright (c) Jupyter Development Team.
# Distributed under the terms of the Modified BSD License.
FROM jupyter/scipy-notebook

MAINTAINER Dan Schien <dschien@gmail.com>

USER root

# libav-tools for matplotlib anim
# RUN apt-get update && \
#     apt-get install -y --no-install-recommends libav-tools && \
#     apt-get clean

USER jovyan


RUN conda install --yes \
    'ipywidgets'   \
    'xray'   \
    'openpyxl'   \
    && conda clean -yt

RUN pip install jupyter_dashboards
RUN jupyter dashboards quick-setup --sys-prefix
#RUN jupyter dashboards install --symlink --overwrite
#RUN jupyter dashboards activate

RUN pip install jupyter_declarativewidgets
RUN jupyter declarativewidgets quick-setup --sys-prefix
#RUN jupyter declarativewidgets install --symlink --overwrite
#RUN jupyter declarativewidgets activate

RUN pip install pypandoc
RUN pip install excel-modelling-helper

RUN pip install jupyter_cms
RUN jupyter cms install --user --symlink --overwrite
RUN jupyter cms activate

USER root

# Install Python 2 kernel spec globally to avoid permission problems when NB_UID
# switching at runtime.
RUN $CONDA_DIR/envs/python2/bin/python \
    $CONDA_DIR/envs/python2/bin/ipython \
    kernelspec install-self

USER jovyan