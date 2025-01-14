import alphashape
import numpy as np
from pyproj import Transformer
from sklearn.cluster import DBSCAN
from shapely.geometry import Point, Polygon, LineString


class GeospatialUtils:
    def __init__(self, epsilon_meters=10, buffer_meters=5, alpha=0.5):
        """
        Initialize the GeospatialClustering class.

        Args:
            epsilon_meters (float): Radius for clustering in meters.
            buffer_meters (float): Buffer size for polygons in meters.
            alpha (float): Alpha parameter for alphashape (concave hull).
        """
        self.epsilon_meters = epsilon_meters
        self.buffer_meters = buffer_meters
        self.alpha = alpha
        self.earth_radius_meters = 6371008.8  # Earth's radius in meters
        self.meters_per_degree_latitude = 111320  # Approximation for meters per degree latitude

        self.epsilon_radians = self.epsilon_meters / self.earth_radius_meters
        self.buffer_degrees = self.buffer_meters / self.meters_per_degree_latitude

        self.transformer = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)  # WGS84 to Web Mercator

    def _dbscan_coordinates(self):
        """Cluster the coordinates using DBSCAN."""
        db = DBSCAN(eps=self.epsilon_radians, min_samples=2, metric='haversine').fit(
            np.radians(self.coordinates[:, :2]))
        self.labels = db.labels_
        self.unique_labels = set(self.labels) - {-1}  # Exclude noise (-1)
        self.clusters = {label: self.coordinates[self.labels == label] for label in self.unique_labels}
        self.noise = self.coordinates[self.labels == -1]

    def cluster_coordinates(self, coordinates, boundary):
        """Generate dictionary data for clustered coordinates.

        Args:
            coordinates (list): List of [longitude, latitude, level] elements.
            boundary (list): List of [longitude, latitude] elements.

        Returns:
            list: A list containing clustered coordinates with their buffered polygons, average levels, and areas in square meter.
        """
        self.boundary = Polygon(boundary)
        self.coordinates = np.array(coordinates)
        self._dbscan_coordinates()
        result = []

        # Process clusters
        for _, cluster_points in self.clusters.items():
            alpha_shape = alphashape.alphashape(cluster_points[:, :2], alpha=self.alpha)

            if isinstance(alpha_shape, (Polygon, LineString)):
                buffered_shape = alpha_shape.buffer(self.buffer_degrees)
                clipped_polygon = buffered_shape.intersection(self.boundary)
                projected_polygon = Polygon(
                    [self.transformer.transform(x, y) for x, y in clipped_polygon.exterior.coords]
                )

                # Exclude level values of 0 during averaging
                valid_levels = cluster_points[cluster_points[:, 2] > 0, 2]
                if len(valid_levels) > 0:
                    avg_level = int(round(np.mean(valid_levels)))
                else:
                    avg_level = 0

                result.append({
                    "points": [[point[1], point[0]] for point in cluster_points],
                    "polygon": [[coord[1], coord[0]] for coord in clipped_polygon.exterior.coords],
                    "level": avg_level,
                    "area": projected_polygon.area
                })

        # Process noise
        for point in self.noise:
            noise_point = Point(point[0], point[1])
            noise_buffer = noise_point.buffer(self.buffer_degrees)
            clipped_polygon = noise_buffer.intersection(self.boundary)
            projected_polygon = Polygon(
                [self.transformer.transform(x, y) for x, y in clipped_polygon.exterior.coords]
            )
            result.append({
                "points": [[point[1], point[0]]],
                "polygon": [[coord[1], coord[0]] for coord in clipped_polygon.exterior.coords],
                "level": int(round(point[2])),
                "area": projected_polygon.area
            })

        return result
