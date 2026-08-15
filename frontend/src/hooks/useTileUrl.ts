import { useUserOptional } from "../contexts/UserContext";
import type { User } from "../api";

type MapTileStyle = User["map_tile_style"];

interface TileConfig {
  /** URL template for the tile layer (use {z}, {x}, {y} placeholders) */
  url: string;
  /** Attribution HTML for the tile provider */
  attribution: string;
  /** Base URL for direct tile fetches (without placeholders) */
  baseUrl: string;
}

const TILE_CONFIGS: Record<MapTileStyle, TileConfig> = {
  osm: {
    url: "/tiles/{z}/{x}/{y}.png",
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    baseUrl: "/tiles",
  },
  positron: {
    url: "/tiles/carto/light/{z}/{x}/{y}.png",
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
    baseUrl: "/tiles/carto/light",
  },
  dark_matter: {
    url: "/tiles/carto/dark/{z}/{x}/{y}.png",
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
    baseUrl: "/tiles/carto/dark",
  },
  voyager: {
    url: "/tiles/carto/voyager/{z}/{x}/{y}.png",
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
    baseUrl: "/tiles/carto/voyager",
  },
};

/**
 * Hook to get the tile URL configuration based on the user's map_tile_style preference.
 * Falls back to OSM if user is not available (e.g., during loading or in tests).
 */
export function useTileConfig(): TileConfig {
  const user = useUserOptional();
  const style = user?.map_tile_style ?? "osm";
  return TILE_CONFIGS[style];
}

/**
 * Get tile config for a specific style (for use outside React components).
 */
export function getTileConfig(style: MapTileStyle): TileConfig {
  return TILE_CONFIGS[style];
}
