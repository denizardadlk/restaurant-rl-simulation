import networkx as nx
from typing import Dict, Tuple, Any
from .grid import RestaurantGrid

class Pathfinder:
    def __init__(self, grid: RestaurantGrid):
        self.grid = grid
        self.graph = nx.Graph()
        self.distance_matrix: Dict[Tuple[int, int], Dict[Tuple[int, int], float]] = {}
        self._build_graph()
        self._precompute_distances()

    def _build_graph(self):
        # Create nodes for all walkable cells
        # We also add obstacle cells to the graph so that agents can path TO them,
        # but we do not add edges going THROUGH them. 
        # Wait, if an actor paths TO a table (obstacle), the table cell must be connected 
        # to adjacent walkable cells.
        
        for y in range(self.grid.height):
            for x in range(self.grid.width):
                self.graph.add_node((x, y))

        # Add edges for 4-way movement (up, down, left, right)
        for y in range(self.grid.height):
            for x in range(self.grid.width):
                # If current is an obstacle, it can only be a DESTINATION, not a through-path.
                # Actually, standard grid pathing: edges between walkable cells, and edges from walkable to obstacles.
                if not self.grid.is_walkable(x, y) and (x, y) not in self.grid.obstacles:
                    continue # out of bounds or walls
                
                neighbors = [(x+1, y), (x-1, y), (x, y+1), (x, y-1)]
                for nx_, ny_ in neighbors:
                    if 0 <= nx_ < self.grid.width and 0 <= ny_ < self.grid.height:
                        # Add edge if the FROM cell is walkable, or if we are just connecting
                        # to make the obstacle reachable from a walkable cell.
                        if self.grid.is_walkable(x, y) and self.grid.is_walkable(nx_, ny_):
                            self.graph.add_edge((x, y), (nx_, ny_), weight=1.0)
                        elif self.grid.is_walkable(x, y) and (nx_, ny_) in self.grid.obstacles:
                            self.graph.add_edge((x, y), (nx_, ny_), weight=1.0)
                        elif (x, y) in self.grid.obstacles and self.grid.is_walkable(nx_, ny_):
                            self.graph.add_edge((x, y), (nx_, ny_), weight=1.0)

    def _precompute_distances(self):
        # We compute all-pairs shortest paths for the graph.
        # This takes O(V^3) which is totally fine for 10x10 or 20x20 grids.
        # nx.all_pairs_dijkstra_path_length returns a generator
        lengths = dict(nx.all_pairs_dijkstra_path_length(self.graph))
        self.distance_matrix = lengths

    def get_distance(self, start: Tuple[int, int], end: Tuple[int, int]) -> float:
        """Returns the shortest path distance. Returns float('inf') if unreachable."""
        if start in self.distance_matrix and end in self.distance_matrix[start]:
            return float(self.distance_matrix[start][end])
        return float('inf')
