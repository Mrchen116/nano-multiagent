from fastapi import FastAPI

from nano_multiagent import __version__


def create_app() -> FastAPI:
    app = FastAPI(title="nano-multiagent", version=__version__)

    @app.get('/v1/health')
    def health() -> dict[str, bool | str]:
        return {
            'healthy': True,
            'version': __version__,
            'node_id': 'local-dev',
        }

    return app


app = create_app()
