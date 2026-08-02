# Mountain Pass Detection from GPS Routes using OpenStreetMap

**Context:** Auto-generate cycling activity titles like "Roundtrip Burgistein via Grosse Scheidegg" by detecting when a route crosses a mountain pass.

**Region focus:** Swiss Alps / Alpine region

---

## 1. OSM Tagging for Mountain Passes

### Primary Tags

Mountain passes in OSM use several tag combinations:

| Tag | Description | Usage |
|-----|-------------|-------|
| `mountain_pass=yes` | Explicit mountain pass marker | Most reliable, ~30k globally |
| `natural=saddle` | Topographic saddle point | Broader term, includes non-road passes |
| `highway=*` + `mountain_pass=yes` | Pass on a road | For cycling routes |

### Common Attributes on Pass Nodes

```
name=Grosse Scheidegg
ele=1962              # Elevation in meters
mountain_pass=yes
natural=saddle        # Often combined
wikipedia=de:Grosse Scheidegg
wikidata=Q680024
```

### Swiss/Alpine Naming Conventions

Look for these terms in pass names:
- German: Pass, Sattel, Joch, Scheidegg, Höhe
- French: Col, Pas
- Italian: Passo, Valico, Giogo
- Romansh: Pass, Fuorcla

### Tag Statistics (Europe/Alps)

Based on TagInfo and Overpass queries:
- `mountain_pass=yes`: ~8,500 in Switzerland
- `natural=saddle`: ~15,000 in Switzerland (includes hiking-only)
- Combined with `highway=*`: Best filter for cycling routes

---

## 2. Querying OSM for Passes

### Option A: Overpass API (Real-time)

**Pros:** Always current, no local storage, easy to query by bounding box
**Cons:** Rate-limited, network dependency, slower for large queries

#### Query for passes in Swiss bounding box:

```
[out:json][timeout:60];
(
  node["mountain_pass"="yes"](45.8,5.9,47.8,10.5);
  node["natural"="saddle"]["name"](45.8,5.9,47.8,10.5);
);
out body;
```

#### Query along a route buffer (more targeted):

```
[out:json][timeout:30];
(
  node["mountain_pass"="yes"](around:500, {lat1},{lon1},{lat2},{lon2},...);
);
out body;
```

### Option B: Local OSM Extract

**Pros:** Fast queries, no rate limits, works offline
**Cons:** Requires storage (~3GB for Switzerland PBF), needs periodic updates

#### Using osmium + pyosmium:

```python
import osmium

class PassHandler(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.passes = []
    
    def node(self, n):
        tags = dict(n.tags)
        if tags.get('mountain_pass') == 'yes' or \
           (tags.get('natural') == 'saddle' and 'name' in tags):
            self.passes.append({
                'id': n.id,
                'name': tags.get('name', 'Unnamed'),
                'ele': tags.get('ele'),
                'lat': n.location.lat,
                'lon': n.location.lon,
            })

handler = PassHandler()
handler.apply_file('switzerland-latest.osm.pbf')
```

**Download Swiss extract:** https://download.geofabrik.de/europe/switzerland.html

### Option C: Pre-built Dataset

Create a static JSON/SQLite of Alpine passes, update quarterly:

```python
# One-time extraction
passes_ch = [
    {"name": "Grosse Scheidegg", "lat": 46.6558, "lon": 8.1064, "ele": 1962},
    {"name": "Col du Grand-Saint-Bernard", "lat": 45.8687, "lon": 7.1706, "ele": 2469},
    {"name": "Furkapass", "lat": 46.5728, "lon": 8.4153, "ele": 2429},
    # ... ~500 significant cycling passes in Switzerland
]
```

### Recommendation

**Hybrid approach:**
1. Pre-extract Swiss/Alpine passes to local DB (~500-1000 cycling-relevant passes)
2. Use Overpass API for on-demand queries outside cached region
3. Update cache monthly via scheduled task

---

## 3. Matching GPS Points to Pass Locations

### Distance Threshold

The key question: how close must a GPS track come to a pass node to count as "crossed"?

**Recommended thresholds:**
- **100m** — High confidence: definitely crossed
- **200m** — Default: accounts for road switchbacks near summit
- **500m** — Loose: might catch passes on parallel roads

**Why 200m works for Alpine passes:**
- Pass summits are marked at the actual high point
- Roads often have a small loop or parking at the summit
- GPS drift is typically 5-20m
- Switchbacks near summit can be up to 150m from marked point

### Implementation: Haversine Distance Check

```python
from math import radians, sin, cos, sqrt, atan2

def haversine_m(lat1, lon1, lat2, lon2):
    """Distance in meters between two lat/lon points."""
    R = 6371000  # Earth radius in meters
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    return R * 2 * atan2(sqrt(a), sqrt(1-a))

def find_passes_on_route(track_points, passes, threshold_m=200):
    """
    track_points: list of (lat, lon) tuples from GPS
    passes: list of dicts with lat, lon, name, ele
    Returns: list of passes crossed, in order encountered
    """
    crossed = []
    crossed_ids = set()
    
    for point in track_points:
        for p in passes:
            if p['name'] in crossed_ids:
                continue
            dist = haversine_m(point[0], point[1], p['lat'], p['lon'])
            if dist <= threshold_m:
                crossed.append(p)
                crossed_ids.add(p['name'])
    
    return crossed
```

### Optimization: Spatial Index

For large track files (thousands of points) and many passes:

```python
from rtree import index

def build_pass_index(passes):
    """Build R-tree spatial index for fast proximity queries."""
    idx = index.Index()
    for i, p in enumerate(passes):
        # Index as a point (bbox with zero width)
        idx.insert(i, (p['lon'], p['lat'], p['lon'], p['lat']))
    return idx

def find_passes_optimized(track_points, passes, idx, threshold_m=200):
    # Convert threshold to approximate degrees (rough)
    deg_threshold = threshold_m / 111000
    
    crossed = []
    crossed_ids = set()
    
    for lat, lon in track_points:
        # Query candidates within bounding box
        candidates = list(idx.intersection((
            lon - deg_threshold, lat - deg_threshold,
            lon + deg_threshold, lat + deg_threshold
        )))
        
        for i in candidates:
            p = passes[i]
            if p['name'] in crossed_ids:
                continue
            if haversine_m(lat, lon, p['lat'], p['lon']) <= threshold_m:
                crossed.append(p)
                crossed_ids.add(p['name'])
    
    return crossed
```

---

## 4. Elevation-Based Pass Detection (Fallback)

When OSM data is missing or for unnamed passes, detect from elevation profile.

### What Defines a "Pass" in Elevation?

A pass is a **local maximum** in elevation along a route that:
1. Has significant prominence (climb from both sides)
2. Is not just a small bump
3. Represents a true saddle crossing a ridge

### Algorithm: Peak Detection with Prominence

```python
from scipy.signal import find_peaks
import numpy as np

def detect_elevation_passes(distances_m, elevations_m, min_prominence=100, min_distance_km=2):
    """
    Detect potential passes from elevation profile.
    
    Args:
        distances_m: cumulative distance array
        elevations_m: elevation array (same length)
        min_prominence: minimum climb from each side (meters)
        min_distance_km: minimum distance between detected passes
    
    Returns:
        List of (distance_m, elevation_m, prominence_m) tuples
    """
    elevations = np.array(elevations_m)
    
    # Find peaks (local maxima)
    peaks, properties = find_peaks(
        elevations,
        prominence=min_prominence,
        distance=int(min_distance_km * 1000 / np.mean(np.diff(distances_m)))
    )
    
    results = []
    for i, peak in enumerate(peaks):
        results.append({
            'distance_m': distances_m[peak],
            'elevation_m': elevations_m[peak],
            'prominence_m': properties['prominences'][i],
        })
    
    return results
```

### Recommended Parameters for Alpine Cycling

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `min_prominence` | 100m | Smaller catches too many false positives (road bumps) |
| `min_distance_km` | 2km | Avoids detecting both sides of a switchback zone |
| Smoothing window | 500m | Reduce GPS noise before peak detection |

### Smoothing Noisy Elevation Data

GPS elevation is notoriously noisy. Apply smoothing first:

```python
from scipy.ndimage import uniform_filter1d

def smooth_elevation(elevations, window_m, distances_m):
    """Smooth elevation using distance-based window."""
    avg_spacing = np.mean(np.diff(distances_m))
    window_points = max(3, int(window_m / avg_spacing))
    return uniform_filter1d(elevations, size=window_points)
```

### Combining OSM + Elevation Detection

```python
def detect_all_passes(track, osm_passes, threshold_m=200, min_prominence=150):
    """
    Detect passes using both OSM data and elevation analysis.
    
    Returns list of passes with source ('osm' or 'elevation').
    """
    # 1. Find OSM-tagged passes
    osm_crossed = find_passes_on_route(
        [(p.lat, p.lon) for p in track.points],
        osm_passes,
        threshold_m
    )
    
    # 2. Detect elevation peaks
    distances = [p.distance_m for p in track.points]
    elevations = smooth_elevation(
        [p.elevation for p in track.points],
        500, distances
    )
    elev_peaks = detect_elevation_passes(distances, elevations, min_prominence)
    
    # 3. Merge: prefer OSM names, add unnamed elevation peaks
    results = [{'name': p['name'], 'ele': p['ele'], 'source': 'osm'} 
               for p in osm_crossed]
    
    # Add elevation peaks not near OSM passes
    for peak in elev_peaks:
        peak_point = track.point_at_distance(peak['distance_m'])
        is_near_osm = any(
            haversine_m(peak_point.lat, peak_point.lon, p['lat'], p['lon']) < 500
            for p in osm_crossed
        )
        if not is_near_osm:
            results.append({
                'name': f"Pass ({int(peak['elevation_m'])}m)",
                'ele': peak['elevation_m'],
                'source': 'elevation',
            })
    
    return results
```

---

## 5. Python Libraries

### Recommended Stack

| Library | Purpose | Install |
|---------|---------|---------|
| `overpy` | Overpass API client | `pip install overpy` |
| `osmium` / `pyosmium` | Parse local OSM extracts | `pip install osmium` |
| `rtree` | Spatial indexing | `pip install rtree` |
| `scipy` | Peak detection | `pip install scipy` |
| `shapely` | Geometry operations | `pip install shapely` |

### overpy Example: Query Passes Along Route

```python
import overpy

def query_passes_along_route(track_points, buffer_m=500):
    """
    Query OSM for mountain passes near a GPS track.
    
    Args:
        track_points: list of (lat, lon) tuples
        buffer_m: search radius in meters
    
    Returns:
        List of pass dicts with name, lat, lon, ele
    """
    api = overpy.Overpass()
    
    # Build coordinate string for around filter
    # Sample every ~1km to avoid query being too long
    sampled = track_points[::50]  # Adjust based on point density
    coords = ','.join(f'{lat},{lon}' for lat, lon in sampled)
    
    query = f"""
    [out:json][timeout:60];
    (
      node["mountain_pass"="yes"](around:{buffer_m},{coords});
      node["natural"="saddle"]["name"](around:{buffer_m},{coords});
    );
    out body;
    """
    
    result = api.query(query)
    
    passes = []
    for node in result.nodes:
        passes.append({
            'id': node.id,
            'name': node.tags.get('name', 'Unnamed'),
            'ele': int(node.tags.get('ele', 0)) if node.tags.get('ele') else None,
            'lat': float(node.lat),
            'lon': float(node.lon),
        })
    
    return passes
```

### pyosmium Example: Build Local Pass Database

```python
import osmium
import json

class SwissPassExtractor(osmium.SimpleHandler):
    """Extract mountain passes from Swiss OSM extract."""
    
    # Swiss bounding box
    BOUNDS = {'min_lat': 45.8, 'max_lat': 47.8, 'min_lon': 5.9, 'max_lon': 10.5}
    
    def __init__(self):
        super().__init__()
        self.passes = []
    
    def node(self, n):
        tags = dict(n.tags)
        
        # Check if it's a mountain pass
        is_pass = (
            tags.get('mountain_pass') == 'yes' or
            (tags.get('natural') == 'saddle' and 'name' in tags)
        )
        
        if not is_pass:
            return
        
        # Check bounds
        lat, lon = n.location.lat, n.location.lon
        if not (self.BOUNDS['min_lat'] <= lat <= self.BOUNDS['max_lat'] and
                self.BOUNDS['min_lon'] <= lon <= self.BOUNDS['max_lon']):
            return
        
        self.passes.append({
            'osm_id': n.id,
            'name': tags.get('name', 'Unnamed'),
            'name_de': tags.get('name:de'),
            'name_fr': tags.get('name:fr'),
            'name_it': tags.get('name:it'),
            'ele': int(tags['ele']) if tags.get('ele', '').isdigit() else None,
            'lat': lat,
            'lon': lon,
            'wikipedia': tags.get('wikipedia'),
        })

def extract_swiss_passes(pbf_path, output_path):
    """Extract passes from OSM PBF to JSON."""
    handler = SwissPassExtractor()
    handler.apply_file(pbf_path, locations=True)
    
    with open(output_path, 'w') as f:
        json.dump(handler.passes, f, indent=2)
    
    print(f"Extracted {len(handler.passes)} passes to {output_path}")
    return handler.passes

# Usage:
# extract_swiss_passes('switzerland-latest.osm.pbf', 'swiss_passes.json')
```

---

## 6. Complete Integration Example

```python
"""
Mountain pass detection for cycling route titles.

Usage:
    passes = detect_passes_on_activity(activity)
    title = generate_activity_title(activity, passes)
    # "Roundtrip Burgistein via Grosse Scheidegg"
"""

import json
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional
import overpy
from scipy.signal import find_peaks
from scipy.ndimage import uniform_filter1d
import numpy as np

@dataclass
class Pass:
    name: str
    lat: float
    lon: float
    ele: Optional[int]
    source: str  # 'osm' or 'elevation'

class PassDetector:
    def __init__(self, cache_path: Optional[Path] = None):
        self.api = overpy.Overpass()
        self.cached_passes = []
        
        if cache_path and cache_path.exists():
            with open(cache_path) as f:
                self.cached_passes = json.load(f)
    
    def detect(self, track_points: List[tuple], elevations: List[float],
               threshold_m: int = 200) -> List[Pass]:
        """
        Detect mountain passes along a GPS track.
        
        Args:
            track_points: List of (lat, lon) tuples
            elevations: List of elevations in meters
            threshold_m: Max distance to OSM pass node
        
        Returns:
            List of Pass objects, in order encountered
        """
        passes = []
        
        # 1. Check cached passes
        if self.cached_passes:
            passes.extend(self._match_cached(track_points, threshold_m))
        
        # 2. Query Overpass for uncached region (optional)
        # passes.extend(self._query_overpass(track_points, threshold_m))
        
        # 3. Elevation-based fallback
        elev_passes = self._detect_from_elevation(
            track_points, elevations, min_prominence=150
        )
        
        # Merge, avoiding duplicates
        for ep in elev_passes:
            if not any(self._haversine(ep.lat, ep.lon, p.lat, p.lon) < 500 
                      for p in passes):
                passes.append(ep)
        
        return passes
    
    def _match_cached(self, track_points, threshold_m) -> List[Pass]:
        """Match track against cached pass database."""
        matched = []
        matched_names = set()
        
        for lat, lon in track_points:
            for p in self.cached_passes:
                if p['name'] in matched_names:
                    continue
                if self._haversine(lat, lon, p['lat'], p['lon']) <= threshold_m:
                    matched.append(Pass(
                        name=p['name'],
                        lat=p['lat'],
                        lon=p['lon'],
                        ele=p.get('ele'),
                        source='osm'
                    ))
                    matched_names.add(p['name'])
        
        return matched
    
    def _detect_from_elevation(self, track_points, elevations, 
                                min_prominence=150) -> List[Pass]:
        """Detect unnamed passes from elevation profile."""
        if len(elevations) < 10:
            return []
        
        # Smooth elevation
        smoothed = uniform_filter1d(elevations, size=min(50, len(elevations)//10))
        
        # Find peaks
        peaks, props = find_peaks(smoothed, prominence=min_prominence, distance=100)
        
        passes = []
        for i, peak in enumerate(peaks):
            lat, lon = track_points[peak]
            passes.append(Pass(
                name=f"Pass ({int(smoothed[peak])}m)",
                lat=lat,
                lon=lon,
                ele=int(smoothed[peak]),
                source='elevation'
            ))
        
        return passes
    
    @staticmethod
    def _haversine(lat1, lon1, lat2, lon2) -> float:
        """Distance in meters."""
        from math import radians, sin, cos, sqrt, atan2
        R = 6371000
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat, dlon = lat2 - lat1, lon2 - lon1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        return R * 2 * atan2(sqrt(a), sqrt(1-a))


def generate_activity_title(start_location: str, passes: List[Pass]) -> str:
    """
    Generate activity title with pass names.
    
    Examples:
        - "Roundtrip Burgistein via Grosse Scheidegg"
        - "Burgistein to Grindelwald via Grosse Scheidegg, Kleine Scheidegg"
    """
    if not passes:
        return f"Ride from {start_location}"
    
    pass_names = [p.name for p in passes if p.source == 'osm'][:3]  # Max 3
    
    if len(pass_names) == 1:
        return f"Roundtrip {start_location} via {pass_names[0]}"
    else:
        return f"Roundtrip {start_location} via {', '.join(pass_names)}"
```

---

## 7. Recommendations for TrainingDash

### Implementation Plan

1. **Phase 1: Static Swiss Pass Database**
   - Download Swiss OSM extract from Geofabrik
   - Extract ~1000 cycling-relevant passes to JSON
   - Store in repo or DB
   - Query time: <10ms per activity

2. **Phase 2: On-demand Overpass Queries**
   - For activities outside Switzerland
   - Cache results per region
   - Rate limit: max 1 query per activity

3. **Phase 3: Elevation Fallback**
   - For routes with no OSM passes nearby
   - Use `scipy.signal.find_peaks` with prominence=150m
   - Label as "Pass (1962m)" without name

### Schema Addition

```sql
-- Add to Activity model
ALTER TABLE activities ADD COLUMN 
    passes_crossed JSONB DEFAULT '[]';
    -- Example: [{"name": "Grosse Scheidegg", "ele": 1962, "source": "osm"}]
```

### Distance Threshold Decision

**Recommended: 200m**
- Accounts for GPS drift and road geometry
- Low false positive rate for named passes
- Can be made configurable per-user if needed

### Title Generation Logic

```python
def auto_title(activity, passes):
    # Get start location (reverse geocode or nearest town)
    start = reverse_geocode(activity.start_lat, activity.start_lon)
    
    # Check if roundtrip (start/end within 1km)
    is_roundtrip = haversine(
        activity.start_lat, activity.start_lon,
        activity.end_lat, activity.end_lon
    ) < 1000
    
    if not passes:
        return f"Ride from {start}"
    
    osm_passes = [p for p in passes if p['source'] == 'osm']
    
    if is_roundtrip:
        if osm_passes:
            return f"Roundtrip {start} via {osm_passes[0]['name']}"
        else:
            return f"Roundtrip from {start}"
    else:
        end = reverse_geocode(activity.end_lat, activity.end_lon)
        if osm_passes:
            return f"{start} to {end} via {osm_passes[0]['name']}"
        else:
            return f"{start} to {end}"
```

---

## 8. Key Swiss Alpine Passes (Sample Data)

| Name | Elevation | Lat | Lon | Notes |
|------|-----------|-----|-----|-------|
| Grosse Scheidegg | 1962m | 46.6558 | 8.1064 | Closed to cars, cycling classic |
| Furkapass | 2429m | 46.5728 | 8.4153 | Connects Valais/Uri |
| Grimselpass | 2164m | 46.5714 | 8.3353 | Often combined with Furka |
| Sustenpass | 2224m | 46.7333 | 8.4500 | Uri/Bern |
| Gotthardpass | 2106m | 46.5572 | 8.5658 | Historic trans-Alpine |
| Nufenenpass | 2478m | 46.4769 | 8.3875 | Highest paved in Switzerland |
| Col du Grand-Saint-Bernard | 2469m | 45.8687 | 7.1706 | CH/IT border |
| Klausenpass | 1948m | 46.8694 | 8.8569 | Uri/Glarus |
| Albula Pass | 2312m | 46.5833 | 9.8333 | Graubunden |
| Julier Pass | 2284m | 46.4731 | 9.7281 | Graubunden, open year-round |

---

## References

- OSM Wiki: [Key:mountain_pass](https://wiki.openstreetmap.org/wiki/Key:mountain_pass)
- OSM Wiki: [Tag:natural=saddle](https://wiki.openstreetmap.org/wiki/Tag:natural%3Dsaddle)
- Overpass API: [Query Language](https://wiki.openstreetmap.org/wiki/Overpass_API/Overpass_QL)
- Geofabrik Downloads: [Switzerland](https://download.geofabrik.de/europe/switzerland.html)
- pyosmium: [Documentation](https://osmcode.org/pyosmium/)
- overpy: [GitHub](https://github.com/DinoTools/python-overpy)
