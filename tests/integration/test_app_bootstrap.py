from nano_multiagent.server.app import create_app


def test_app_exposes_health_route() -> None:
    app = create_app()
    routes = {route.path for route in app.routes}
    assert '/v1/health' in routes
