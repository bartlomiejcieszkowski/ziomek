"""Tests for ziomek.client.server — ZiomekClientApp structure."""
from ziomek.client.server import ZiomekClientApp


def test_client_app_has_required_methods():
    """ZiomekClientApp exposes the required public methods."""
    app = ZiomekClientApp()
    assert hasattr(app, 'start')
    assert hasattr(app, 'stop')
    assert hasattr(app, '_create_app')
    assert callable(app.start)
    assert callable(app.stop)


def test_client_app_default_port():
    """Default port is 5004."""
    app = ZiomekClientApp()
    assert app._port == 5004


def test_client_app_default_server_url():
    """Default server URL is http://localhost:5003."""
    app = ZiomekClientApp()
    assert app._server_url == "http://localhost:5003"


def test_client_app_no_browser():
    """Can disable browser on startup."""
    app = ZiomekClientApp(open_browser=False)
    assert app._open_browser is False
