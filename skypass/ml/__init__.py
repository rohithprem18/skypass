"""Optional learned components of SkyPass.

Two models replace hand-built approximations in the pipeline:

* :mod:`skypass.ml.brightness` predicts a satellite's apparent magnitude from the
  pass geometry, trained on measured magnitudes (IAU CPS SCORE). It replaces
  the diffuse-sphere photometry, which the paper treats only as an ordering.
* :mod:`skypass.ml.cloudcam` segments cloud in whole-sky camera images and
  returns a sky-cloud nowcast, the sub-hourly signal a forecast cannot give.

Both need the optional ``[ml]`` dependencies (numpy, scikit-learn; PyTorch for
the cloud U-Net). The core planner never imports this package, so SkyPass keeps
``sgp4`` as its only runtime dependency.
"""

from ..paths import ML_DATA_DIR, MODEL_DIR

__all__ = ["MODEL_DIR", "ML_DATA_DIR"]
