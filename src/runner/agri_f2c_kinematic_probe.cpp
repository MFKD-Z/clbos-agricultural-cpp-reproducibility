// Independent measurement adapter.  It contains no Fields2Cover algorithm changes.
#include <array>
#include <algorithm>
#include <cmath>
#include <limits>
#include <vector>
#include <steering_functions/dubins_state_space/dubins_state_space.hpp>
#include "fields2cover.h"
#include <vector>
#include <limits>
#include <chrono>
#include <algorithm>

#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
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


using MstClock = std::chrono::steady_clock;

double mst_seconds(MstClock::time_point a, MstClock::time_point b) {
  return std::chrono::duration<double>(b - a).count();
}

double mst_endpoint_distance(const F2CSwath& a, const F2CSwath& b) {
  const F2CPoint a0 = a.startPoint();
  const F2CPoint a1 = a.endPoint();
  const F2CPoint b0 = b.startPoint();
  const F2CPoint b1 = b.endPoint();
  return std::min({
      a0.distance(b0), a0.distance(b1),
      a1.distance(b0), a1.distance(b1)});
}

double mst_connection_bound(const F2CSwathsByCells& groups, int expected_count) {
  std::vector<F2CSwath> flat;
  flat.reserve(static_cast<size_t>(std::max(0, expected_count)));
  for (size_t i = 0; i < groups.size(); ++i) {
    const auto swaths = groups.at(i);
    for (const auto& swath : swaths) flat.push_back(swath);
  }
  if (flat.size() <= 1) return 0.0;

  const size_t n = flat.size();
  std::vector<double> best(n, std::numeric_limits<double>::infinity());
  std::vector<unsigned char> used(n, 0);
  best[0] = 0.0;
  double total = 0.0;

  for (size_t it = 0; it < n; ++it) {
    size_t u = n;
    double bu = std::numeric_limits<double>::infinity();
    for (size_t i = 0; i < n; ++i) {
      if (!used[i] && best[i] < bu) {
        bu = best[i];
        u = i;
      }
    }
    if (u == n || !std::isfinite(bu)) {
      throw std::runtime_error("MST endpoint graph disconnected");
    }
    used[u] = 1;
    total += bu;
    for (size_t v = 0; v < n; ++v) {
      if (used[v]) continue;
      const double w = mst_endpoint_distance(flat[u], flat[v]);
      if (w < best[v]) best[v] = w;
    }
  }
  return total;
}

void usage() { std::cerr << "usage: agri_f2c_runner --wkt-file FILE --angle-deg DEG\n"; }
}  // namespace


double kinematic_path_length(const F2CPath& path) {
  f2c::obj::PathLength obj;
  return obj.computeCost(path);
}

double point_distance(const F2CPoint& a, const F2CPoint& b) {
  return a.distance(b);
}

double uncached_dubins_pose_distance(
    const F2CRobot& robot,
    const F2CPoint& p1, double a1,
    const F2CPoint& p2, double a2) {
  const double eu = point_distance(p1, p2);
  if (eu <= 1e-12 &&
      std::abs(std::remainder(a1 - a2, 2.0 * M_PI)) <= 1e-12) {
    return 0.0;
  }

  steer::State start_state, end_state;
  start_state.x = p1.getX();
  start_state.y = p1.getY();
  start_state.theta = a1;
  start_state.kappa = 0.0;
  start_state.d = 0;

  end_state.x = p2.getX();
  end_state.y = p2.getY();
  end_state.theta = a2;
  end_state.kappa = 0.0;
  end_state.d = 0;

  Dubins_State_Space ss(
      robot.getMaxCurv(),
      0.1,
      true);
  const double d = ss.get_distance(start_state, end_state);

  if (!std::isfinite(d) || d < 0.0) return eu;
  return std::max(eu, d);
}

struct TraversalState {
  F2CPoint in_p;
  double in_a;
  F2CPoint out_p;
  double out_a;
};

std::array<TraversalState, 2> traversal_states(const F2CSwath& s) {
  F2CSwath fwd = s;
  F2CSwath rev = s;
  rev.reverse();
  return {{
    {fwd.startPoint(), fwd.getInAngle(), fwd.endPoint(), fwd.getOutAngle()},
    {rev.startPoint(), rev.getInAngle(), rev.endPoint(), rev.getOutAngle()}
  }};
}

double kinematic_edge_lower_bound(
    const F2CRobot& robot, const F2CSwath& a, const F2CSwath& b) {
  const double eu = mst_endpoint_distance(a, b);
  const auto sa = traversal_states(a);
  const auto sb = traversal_states(b);
  double best = std::numeric_limits<double>::infinity();

  for (const auto& xa : sa) {
    for (const auto& xb : sb) {
      best = std::min(best, uncached_dubins_pose_distance(
          robot, xa.out_p, xa.out_a, xb.in_p, xb.in_a));
      best = std::min(best, uncached_dubins_pose_distance(
          robot, xb.out_p, xb.out_a, xa.in_p, xa.in_a));
    }
  }
  if (!std::isfinite(best)) return eu;
  return std::max(eu, best);
}

template <class EdgeFn>
double mst_from_flat_swaths(
    const std::vector<F2CSwath>& flat, EdgeFn edge_fn) {
  const size_t n = flat.size();
  if (n <= 1) return 0.0;

  std::vector<double> key(n, std::numeric_limits<double>::infinity());
  std::vector<bool> used(n, false);
  key[0] = 0.0;
  double total = 0.0;

  for (size_t it = 0; it < n; ++it) {
    size_t u = n;
    double best = std::numeric_limits<double>::infinity();
    for (size_t i = 0; i < n; ++i) {
      if (!used[i] && key[i] < best) {
        best = key[i];
        u = i;
      }
    }
    if (u == n || !std::isfinite(best)) {
      throw std::runtime_error("Kinematic MST graph disconnected");
    }
    used[u] = true;
    total += best;

    for (size_t v = 0; v < n; ++v) {
      if (!used[v]) {
        const double w = edge_fn(flat[u], flat[v]);
        if (w < key[v]) key[v] = w;
      }
    }
  }
  return total;
}

double kinematic_mst_connection_bound(
    const F2CSwathsByCells& groups, int expected_count,
    const F2CRobot& robot) {
  std::vector<F2CSwath> flat;
  flat.reserve(static_cast<size_t>(std::max(0, expected_count)));
  for (size_t i = 0; i < groups.size(); ++i) {
    const auto swaths = groups.at(i);
    for (const auto& swath : swaths) flat.push_back(swath);
  }
  if (static_cast<int>(flat.size()) != expected_count) {
    throw std::runtime_error("Kinematic MST swath flatten count mismatch");
  }
  return mst_from_flat_swaths(flat,
      [&robot](const F2CSwath& a, const F2CSwath& b) {
        return kinematic_edge_lower_bound(robot, a, b);
      });
}

int main(int argc, char** argv) {
  std::string wkt_file;
  double angle_deg = NAN;
  bool swath_only = false;
  bool mst_probe = false;
  bool kinematic_probe = false;
  for (int i = 1; i < argc; ++i) {
    const std::string arg(argv[i]);
    if (arg == "--wkt-file" && i + 1 < argc) wkt_file = argv[++i];
    else if (arg == "--angle-deg" && i + 1 < argc) angle_deg = std::stod(argv[++i]);
    else if (arg == "--swath-only") swath_only = true;
    else if (arg == "--mst-probe") mst_probe = true;
    else if (arg == "--kinematic-probe") kinematic_probe = true;
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
    const auto mst_upstream_t0 = MstClock::now();
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
    const auto mst_upstream_t1 = MstClock::now();

    if (kinematic_probe) {
      const auto eu_t0 = MstClock::now();
      const double eu_conn = mst_connection_bound(swaths, swath_count);
      const auto eu_t1 = MstClock::now();

      const auto kin_t0 = MstClock::now();
      const double kin_conn =
          kinematic_mst_connection_bound(swaths, swath_count, robot);
      const auto kin_t1 = MstClock::now();

      const double eu_total = swath_total + eu_conn;
      const double kin_total = swath_total + kin_conn;

      std::cout << std::fixed << std::setprecision(12)
                << "{\"swath_count\":" << swath_count
                << ",\"swath_total_length_m\":" << swath_total
                << ",\"mst_connection_lb_m\":" << eu_conn
                << ",\"mst_total_lb_m\":" << eu_total
                << ",\"kinematic_mst_connection_lb_m\":" << kin_conn
                << ",\"kinematic_mst_total_lb_m\":" << kin_total
                << ",\"upstream_seconds\":"
                << mst_seconds(mst_upstream_t0, mst_upstream_t1)
                << ",\"euclidean_mst_seconds\":"
                << mst_seconds(eu_t0, eu_t1)
                << ",\"kinematic_mst_seconds\":"
                << mst_seconds(kin_t0, kin_t1)
                << ",\"kinematic_probe_total_seconds\":"
                << mst_seconds(mst_upstream_t0, kin_t1)
                << "}\n";
      return 0;
    }

    if (mst_probe) {
      const auto mst_t0 = MstClock::now();
      const double connection_lb = mst_connection_bound(swaths, swath_count);
      const double total_lb = swath_total + connection_lb;
      const auto mst_t1 = MstClock::now();

      std::cout << std::setprecision(17)
                << "{\"swath_count\":" << swath_count
                << ",\"swath_total_length_m\":" << swath_total
                << ",\"mst_connection_lb_m\":" << connection_lb
                << ",\"mst_total_lb_m\":" << total_lb
                << ",\"upstream_seconds\":"
                << mst_seconds(mst_upstream_t0, mst_upstream_t1)
                << ",\"mst_seconds\":" << mst_seconds(mst_t0, mst_t1)
                << ",\"mst_probe_total_seconds\":"
                << mst_seconds(mst_upstream_t0, mst_t1)
                << "}\n";
      return 0;
    }

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

    std::cout << std::setprecision(17)
              << "{\"swath_count\":" << swath_count
              << ",\"swath_total_length_m\":" << swath_total
              << ",\"complete_path_success\":true"
              << ",\"complete_path_length_m\":" << complete
              << ",\"swath_section_length_m\":" << swath_total
              << ",\"turn_section_length_m\":" << turns << "}\n";
  } catch (const std::exception& e) {
    std::cerr << "F2C_RUNNER_ERROR: " << e.what() << '\n';
    return 1;
  }
  return 0;
}
