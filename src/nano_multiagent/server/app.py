from fastapi import FastAPI
from pydantic import BaseModel

from nano_multiagent import __version__
from nano_multiagent.session.service import SessionService


class CreateSessionResponse(BaseModel):
    session_id: str
    status: str
    created_at: str


def create_app() -> FastAPI:
    app = FastAPI(title="nano-multiagent", version=__version__)
    app.state.session_service = SessionService()

    @app.get('/v1/health')
    def health() -> dict[str, bool | str]:
        return {
            'healthy': True,
            'version': __version__,
            'node_id': 'local-dev',
        }

    @app.post('/v1/sessions', status_code=201, response_model=CreateSessionResponse)
    def create_session() -> CreateSessionResponse:
        session = app.state.session_service.create_session()
        return CreateSessionResponse(
            session_id=session.session_id,
            status=session.status,
            created_at=session.created_at,
        )

    return app


app = create_app()
