"""Integration tests for the map tile proxy endpoints (routers/tiles.py)."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestOsmTileProxy:
    @pytest.mark.asyncio
    async def test_valid_tile_fetched_and_returned(self, http_client, tmp_path, monkeypatch):
        monkeypatch.setenv("TILE_CACHE_DIR", str(tmp_path))
        # Reload the module so the router picks up the new cache dir
        import importlib
        import trainingdash.routers.tiles as tiles_mod
        importlib.reload(tiles_mod)

        fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        mock_response = MagicMock()
        mock_response.content = fake_png
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("trainingdash.routers.tiles.httpx.AsyncClient", return_value=mock_client):
            response = await http_client.get("/tiles/10/512/512.png")

        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
        assert response.headers["x-cache"] == "MISS"

    @pytest.mark.asyncio
    async def test_tile_served_from_cache_on_second_request(self, http_client, tmp_path, monkeypatch):
        monkeypatch.setenv("TILE_CACHE_DIR", str(tmp_path))
        import importlib
        import trainingdash.routers.tiles as tiles_mod
        importlib.reload(tiles_mod)

        fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        mock_response = MagicMock()
        mock_response.content = fake_png
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("trainingdash.routers.tiles.httpx.AsyncClient", return_value=mock_client):
            await http_client.get("/tiles/10/512/512.png")
            response = await http_client.get("/tiles/10/512/512.png")

        assert response.status_code == 200
        assert response.headers["x-cache"] == "HIT"
        # Upstream should only have been called once
        assert mock_client.get.call_count == 1

    @pytest.mark.asyncio
    async def test_invalid_zoom_returns_400(self, http_client):
        response = await http_client.get("/tiles/99/0/0.png")
        assert response.status_code == 400
        assert "zoom" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_invalid_tile_coords_returns_400(self, http_client):
        # At zoom 0 the only valid tile is 0/0
        response = await http_client.get("/tiles/0/1/0.png")
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_upstream_error_returns_502(self, http_client, tmp_path, monkeypatch):
        import httpx

        monkeypatch.setenv("TILE_CACHE_DIR", str(tmp_path))
        import importlib
        import trainingdash.routers.tiles as tiles_mod
        importlib.reload(tiles_mod)

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=httpx.RequestError("timeout"))

        with patch("trainingdash.routers.tiles.httpx.AsyncClient", return_value=mock_client):
            response = await http_client.get("/tiles/10/512/512.png")

        assert response.status_code == 502


class TestCartoTileProxy:
    @pytest.mark.asyncio
    async def test_light_tile_fetched_and_returned(self, http_client, tmp_path, monkeypatch):
        monkeypatch.setenv("TILE_CACHE_DIR", str(tmp_path))
        import importlib
        import trainingdash.routers.tiles as tiles_mod
        importlib.reload(tiles_mod)

        fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        mock_response = MagicMock()
        mock_response.content = fake_png
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("trainingdash.routers.tiles.httpx.AsyncClient", return_value=mock_client):
            response = await http_client.get("/tiles/carto/light/10/512/512.png")

        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
        assert response.headers["x-cache"] == "MISS"
        # Verify it hit the correct CartoDB URL
        call_url = mock_client.get.call_args[0][0]
        assert "light_all" in call_url

    @pytest.mark.asyncio
    async def test_dark_tile_hits_dark_matter_url(self, http_client, tmp_path, monkeypatch):
        monkeypatch.setenv("TILE_CACHE_DIR", str(tmp_path))
        import importlib
        import trainingdash.routers.tiles as tiles_mod
        importlib.reload(tiles_mod)

        fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        mock_response = MagicMock()
        mock_response.content = fake_png
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("trainingdash.routers.tiles.httpx.AsyncClient", return_value=mock_client):
            response = await http_client.get("/tiles/carto/dark/10/512/512.png")

        assert response.status_code == 200
        call_url = mock_client.get.call_args[0][0]
        assert "dark_all" in call_url

    @pytest.mark.asyncio
    async def test_carto_tile_served_from_cache_on_second_request(
        self, http_client, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("TILE_CACHE_DIR", str(tmp_path))
        import importlib
        import trainingdash.routers.tiles as tiles_mod
        importlib.reload(tiles_mod)

        fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        mock_response = MagicMock()
        mock_response.content = fake_png
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("trainingdash.routers.tiles.httpx.AsyncClient", return_value=mock_client):
            await http_client.get("/tiles/carto/light/10/512/512.png")
            response = await http_client.get("/tiles/carto/light/10/512/512.png")

        assert response.headers["x-cache"] == "HIT"
        assert mock_client.get.call_count == 1

    @pytest.mark.asyncio
    async def test_unknown_style_returns_400(self, http_client):
        response = await http_client.get("/tiles/carto/satellite/10/512/512.png")
        assert response.status_code == 400
        assert "style" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_invalid_zoom_returns_400(self, http_client):
        response = await http_client.get("/tiles/carto/light/99/0/0.png")
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_invalid_tile_coords_returns_400(self, http_client):
        response = await http_client.get("/tiles/carto/light/0/1/0.png")
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_upstream_error_returns_502(self, http_client, tmp_path, monkeypatch):
        import httpx

        monkeypatch.setenv("TILE_CACHE_DIR", str(tmp_path))
        import importlib
        import trainingdash.routers.tiles as tiles_mod
        importlib.reload(tiles_mod)

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=httpx.RequestError("timeout"))

        with patch("trainingdash.routers.tiles.httpx.AsyncClient", return_value=mock_client):
            response = await http_client.get("/tiles/carto/light/10/512/512.png")

        assert response.status_code == 502

    @pytest.mark.asyncio
    async def test_light_and_dark_cached_separately(self, http_client, tmp_path, monkeypatch):
        """Light and dark tiles must not share cache entries."""
        monkeypatch.setenv("TILE_CACHE_DIR", str(tmp_path))
        import importlib
        import trainingdash.routers.tiles as tiles_mod
        importlib.reload(tiles_mod)

        fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        mock_response = MagicMock()
        mock_response.content = fake_png
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("trainingdash.routers.tiles.httpx.AsyncClient", return_value=mock_client):
            r_light = await http_client.get("/tiles/carto/light/10/512/512.png")
            r_dark = await http_client.get("/tiles/carto/dark/10/512/512.png")

        assert r_light.status_code == 200
        assert r_dark.status_code == 200
        # Both should be MISS — different cache paths
        assert r_light.headers["x-cache"] == "MISS"
        assert r_dark.headers["x-cache"] == "MISS"
        assert mock_client.get.call_count == 2
