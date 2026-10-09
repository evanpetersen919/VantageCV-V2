### [RESOLVED] `scipy.spatial.qhull.QhullError` import path is deprecated
`from scipy.spatial.qhull import QhullError` (used in some scipy example
code and easy to reach for) emits a `DeprecationWarning` on scipy 1.11.4 —
confirmed by direct import test. Used `from scipy.spatial import
QhullError` instead (the supported public path).

