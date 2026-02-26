from fastapi import APIRouter

from nano_multiagent import __version__

router = APIRouter()


@router.get("/v1/health")
def health() -> dict[str, bool | str]:
    return {
        "healthy": True,
        "version": __version__,
        "node_id": "local-dev",
    }
