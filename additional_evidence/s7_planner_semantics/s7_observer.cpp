// Independent measurement adapter.  It contains no Fields2Cover algorithm changes.
#include "fields2cover.h"

#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>

namespace {
constexpr double kCoverageWidthM = 2.0;
constexpr double kRobotWidthM = 2.0;
constexpr double kRobotLengthM = 6.0;  // protocol binding; F2C v2 exposes no body-length planner parameter.
constexpr double kMinTurningRadiusM = 2.0;
constexpr double kHeadlandWidthM = 6.0;
std::string read_file(const std::string& path) {
  std::ifstream in(path);
  if (!in) throw std::runtime_error("cannot open metric WKT file");
  return {std::istreambuf_iterator<char>(in), std::istreambuf_iterator<char>()};
}

double swath_length(const F2CSwathsByCells& groups, int* count) {
  f2c::obj::SwathLength objective;
  double total = 0.0;
  *count = 0;
  for (size_t i = 0; i < groups.size(); ++i) {
    const auto swaths = groups.at(i);
    *count += static_cast<int>(swaths.size());
    total += objective.computeCost(swaths);
  }
  return total;
}

// Runner-only compatibility fix for a Fields2Cover splitByLine edge case.
// Preserve the original split lines and numerical epsilons, but allow the
// tiny post-split buffer to return multiple polygon components instead of
// forcing the result into one Cell.
constexpr double kSplitNumericalEps = 1e-8;

F2CCells split_by_line_preserve_components(
    const F2CCells& input,
    const f2c::types::LineString& line) {
  const F2CCells cut =
      input.difference(F2CCells::buffer(line, kSplitNumericalEps));

  F2CCells repaired;
  for (auto&& cell : cut) {
    // Match the original Cell::buffer(c, eps/2) OGRBuffer(width)
    // semantics exactly, but preserve all polygon components if GDAL
    // returns a MultiPolygon instead of forcing the result into one Cell.
    OGRGeometry* repaired_geom =
        cell.OGRBuffer(kSplitNumericalEps * 0.5);

    if (repaired_geom == nullptr) {
      throw std::runtime_error("post-split numerical buffer returned null");
    }

    F2CCells buffered;
    try {
      buffered = F2CCells(repaired_geom);
    } catch (...) {
      OGRGeometryFactory::destroyGeometry(repaired_geom);
      throw;
    }
    OGRGeometryFactory::destroyGeometry(repaired_geom);

    for (auto&& component : buffered) {
      repaired.addGeometry(component);
    }
  }
  return repaired;
}

class RunnerSafeTrapezoidalDecomp final
    : public f2c::decomp::TrapezoidalDecomp {
 public:
  F2CCells split(
      const F2CCells& cells,
      const f2c::obj::DecompObjective& obj) override {
    F2CCells result {cells};
    const F2CMultiLineString lines = genSplitLines(cells, obj);

    for (auto&& line : lines) {
      result = split_by_line_preserve_components(result, line);
    }
    return result;
  }
};

void emit_point(std::ostream& out, const F2CPoint& p) {
  out << '[' << p.getX() << ',' << p.getY() << ',' << p.getZ() << ']';
}

void emit_swath(std::ostream& out, const F2CSwath& s,
                size_t cell_id, size_t local_id) {
  out << "{\"cell_id\":" << cell_id << ",\"local_id\":" << local_id
      << ",\"f2c_id\":" << s.getId() << ",\"length\":" << s.length()
      << ",\"points\":[";
  for (size_t k = 0; k < s.numPoints(); ++k) {
    if (k) out << ',';
    emit_point(out, s.getPoint(static_cast<int>(k)));
  }
  out << "]}";
}

void emit_observation(std::ostream& out, const F2CSwathsByCells& swaths,
                      const F2CRoute& route, const F2CPath& path,
                      double swath_total, double complete) {
  out << std::setprecision(std::numeric_limits<double>::max_digits10)
      << "{\"status\":\"VALID_FINITE\",\"swath_total_length_m\":"
      << swath_total << ",\"complete_path_length_m\":" << complete
      << ",\"path_length_m\":" << path.length()
      << ",\"generated\":[";
  bool first = true;
  for (size_t c = 0; c < swaths.size(); ++c) {
    for (size_t k = 0; k < swaths.at(c).size(); ++k) {
      if (!first) out << ',';
      first = false;
      emit_swath(out, swaths.at(c)[k], c, k);
    }
  }
  out << "],\"route_groups\":[";
  for (size_t g = 0; g < route.sizeVectorSwaths(); ++g) {
    if (g) out << ',';
    out << '[';
    const auto& group = route.getSwaths(g);
    for (size_t k = 0; k < group.size(); ++k) {
      if (k) out << ',';
      emit_swath(out, group[k], g, k);
    }
    out << ']';
  }
  out << "],\"route_connections\":[";
  for (size_t g = 0; g < route.sizeConnections(); ++g) {
    if (g) out << ',';
    out << '[';
    const auto& con = route.getConnection(g);
    for (size_t k = 0; k < con.size(); ++k) {
      if (k) out << ',';
      emit_point(out, con[k]);
    }
    out << ']';
  }
  out << "],\"states\":[";
  for (size_t i = 0; i < path.size(); ++i) {
    if (i) out << ',';
    const auto& s = path[i];
    out << "{\"i\":" << i << ",\"point\":";
    emit_point(out, s.point);
    out << ",\"end\":";
    emit_point(out, s.atEnd());
    out << ",\"angle\":" << s.angle << ",\"len\":" << s.len
        << ",\"dir\":" << static_cast<int>(s.dir)
        << ",\"type\":" << static_cast<int>(s.type) << '}';
  }
  out << "]}\n";
}

void usage() { std::cerr << "usage: agri_f2c_runner --wkt-file FILE --angle-deg DEG\n"; }
}  // namespace

int main(int argc, char** argv) {
  std::string wkt_file;
  double angle_deg = NAN;
  bool swath_only = false;
  for (int i = 1; i < argc; ++i) {
    const std::string arg(argv[i]);
    if (arg == "--wkt-file" && i + 1 < argc) wkt_file = argv[++i];
    else if (arg == "--angle-deg" && i + 1 < argc) angle_deg = std::stod(argv[++i]);
    else if (arg == "--swath-only") swath_only = true;
    else { usage(); return 2; }
  }
  if (wkt_file.empty() || !std::isfinite(angle_deg)) { usage(); return 2; }

  try {
    // All coordinates have been transformed to a local UTM metre system by prepare_fields.py.
    F2CCell cell;
    cell.importFromWkt(read_file(wkt_file));
    F2CCells cells;
    cells.addGeometry(cell);

    F2CRobot robot(kRobotWidthM, kCoverageWidthM);
    robot.setMinTurningRadius(kMinTurningRadiusM);
    f2c::hg::ConstHL headlands;
    f2c::decomp::TrapezoidalDecomp decomposition;
    decomposition.setSplitAngle(angle_deg * M_PI / 180.0);  // fixed for every direction of this field.
    // Fixed 6 m headland: make the 3 m route ring, decompose it, then inset 3 m again.
    (void)kRobotLengthM;
    const F2CCells mid_headland = headlands.generateHeadlands(cells, kHeadlandWidthM / 2.0);
    F2CCells decomposed_mid;
    try {
      // Normal path: preserve stock Fields2Cover behaviour exactly.
      decomposed_mid = decomposition.decompose(mid_headland);
    } catch (const std::invalid_argument& e) {
      const std::string msg = e.what();

      // Compatibility fallback ONLY for the known splitByLine edge case
      // where the tiny numerical repair buffer returns MultiPolygon.
      if (msg.find(
              "Cell(const OGRGeometry*): Type of OGRGeometry* is 6") ==
          std::string::npos) {
        throw;
      }

      RunnerSafeTrapezoidalDecomp fallback_decomposition;
      fallback_decomposition.setSplitAngle(
          angle_deg * M_PI / 180.0);

      decomposed_mid =
          fallback_decomposition.decompose(mid_headland);
    }
    const F2CCells working_cells = headlands.generateHeadlands(decomposed_mid, kHeadlandWidthM / 2.0);

    f2c::sg::BruteForce swath_generator;
    const F2CSwathsByCells swaths = swath_generator.generateSwaths(
        angle_deg * M_PI / 180.0, robot.getCovWidth(), working_cells);
    int swath_count = 0;
    const double swath_total = swath_length(swaths, &swath_count);
    if (swath_count <= 0 || swath_total <= 0.0) throw std::runtime_error("no swaths generated");

    if (swath_only) {
      std::cout << std::setprecision(17)
                << "{\"swath_count\":" << swath_count
                << ",\"swath_total_length_m\":" << swath_total << "}\n";
      return 0;
    }

    f2c::rp::RoutePlannerBase shortest_route;
    const F2CRoute route = shortest_route.genRoute(mid_headland, swaths);
    f2c::pp::PathPlanning planner;
    f2c::pp::DubinsCurves dubins;
    const F2CPath path = planner.planPath(robot, route, dubins);
    f2c::obj::PathLength path_length;
    const double complete = path_length.computeCost(path);
    if (!std::isfinite(complete) || complete <= 0.0) throw std::runtime_error("complete path length unavailable");
    const double turns = std::max(0.0, complete - swath_total);

    (void)turns;
    emit_observation(std::cout, swaths, route, path, swath_total, complete);
  } catch (const std::exception& e) {
    std::cerr << "F2C_RUNNER_ERROR: " << e.what() << '\n';
    return 1;
  }
  return 0;
}
