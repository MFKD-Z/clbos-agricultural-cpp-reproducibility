# Environment

Level A numeric reproduction uses Python 3.10+ and the standard library. Matplotlib is optional and needed only for `scripts/reproduce_figures.py`.

Level B was recorded on Ubuntu under WSL; exact versions are in `system_snapshot.txt`. Build Fields2Cover at the pinned commit with a C++17 compiler and CMake. Fields2Cover's official Linux dependencies include Eigen, GDAL, GEOS, TBB, TinyXML2, and nlohmann-json. The acquisition/preprocessing helpers additionally use Shapely and pyproj.

The snapshot is provenance, not a promise that timing will match on other hardware. Do not compare wall-clock timing across materially different systems as a deterministic reproducibility check.

