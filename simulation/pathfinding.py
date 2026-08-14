import networkx as nx
from typing import Dict, Tuple, Any
from .grid import RestaurantGrid

_GLOBAL_DISTANCE_CACHE: Dict[Tuple[int, int, Tuple[Tuple[int, int], ...]], Dict[Tuple[int, int], Dict[Tuple[int, int], float]]] = {}

class Pathfinder:
    def __init__(self, grid: RestaurantGrid):
        self.grid = grid
        self.graph = nx.Graph()
        self.distance_matrix: Dict[Tuple[int, int], Dict[Tuple[int, int], float]] = {}
        self._build_graph()
        self._precompute_distances()

    def _get_cache_key(self) -> Tuple[int, int, Tuple[Tuple[int, int], ...]]:
        return (self.grid.width, self.grid.height, tuple(sorted(self.grid.obstacles)))

    def _build_graph(self):
        # Create nodes for all walkable cells
        for y in range(self.grid.height):
            for x in range(self.grid.width):
                self.graph.add_node((x, y))

        # Add edges for 4-way movement (up, down, left, right)
        for y in range(self.grid.height):
            for x in range(self.grid.width):
                if not self.grid.is_walkable(x, y) and (x, y) not in self.grid.obstacles:
                    continue # out of bounds or walls
                
                neighbors = [(x+1, y), (x-1, y), (x, y+1), (x, y-1)]
                for nx_, ny_ in neighbors:
                    if 0 <= nx_ < self.grid.width and 0 <= ny_ < self.grid.height:
                        if self.grid.is_walkable(x, y) and self.grid.is_walkable(nx_, ny_):
                            self.graph.add_edge((x, y), (nx_, ny_), weight=1.0)
                        elif self.grid.is_walkable(x, y) and (nx_, ny_) in self.grid.obstacles:
                            self.graph.add_edge((x, y), (nx_, ny_), weight=1.0)
                        elif (x, y) in self.grid.obstacles and self.grid.is_walkable(nx_, ny_):
                            self.graph.add_edge((x, y), (nx_, ny_), weight=1.0)

    def _precompute_distances(self):
        key = self._get_cache_key()
        if key in _GLOBAL_DISTANCE_CACHE:
            self.distance_matrix = _GLOBAL_DISTANCE_CACHE[key]
            return

        # Compute all-pairs shortest paths once and cache
        lengths = dict(nx.all_pairs_dijkstra_path_length(self.graph))
        _GLOBAL_DISTANCE_CACHE[key] = lengths
        self.distance_matrix = lengths

    def get_distance(self, start: Tuple[int, int], end: Tuple[int, int]) -> float:
        """Returns the shortest path distance. Returns float('inf') if unreachable."""
        if start in self.distance_matrix and end in self.distance_matrix[start]:
            return float(self.distance_matrix[start][end])
        return float('inf')
