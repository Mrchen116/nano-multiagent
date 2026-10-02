"""Narrow operation-only device proof endpoints and active browser acceptance."""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from IM.api.deps import current_user
from IM.domain.models import User

router = APIRouter(prefix="/im/v1/device-binding", tags=["device-binding"])


class Start(BaseModel):
    node_id: str = Field(min_length=1, max_length=128)
    node_name: str = Field(min_length=1, max_length=256)
    public_key: str = Field(max_length=128)
    key_id: str = Field(max_length=128)


class Operation(BaseModel):
    operation_id: str = Field(max_length=128)
    operation_token: str = Field(max_length=128)


class Proof(Operation):
    challenge: str = Field(max_length=128)


class Commit(Operation):
    proof: str = Field(max_length=128)
    envelopes: dict = Field(default_factory=dict)


class Accept(BaseModel):
    browser_token: str = Field(max_length=128)


def call(request: Request, method: str, payload: dict) -> dict:
    try:
        return getattr(request.app.state.device_binding_store, method)(**payload)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post("/start")
def start(payload: Start, request: Request) -> dict:
    result = call(request, "start", payload.model_dump())
    result["bind_url"] = (
        request.app.state.public_url.rstrip("/")
        + "/bind/confirm#token="
        + result["browser_token"]
    )
    return result


@router.post("/prove")
def prove(payload: Proof, request: Request) -> dict:
    return call(request, "prove", payload.model_dump())


@router.post("/accept")
def accept(
    payload: Accept, request: Request, user: User = Depends(current_user)
) -> dict:
    return call(request, "accept", {**payload.model_dump(), "user_id": user.id})


@router.post("/prepare")
def prepare(payload: Operation, request: Request) -> dict:
    return call(request, "prepare", payload.model_dump())


@router.post("/commit")
async def commit(payload: Commit, request: Request) -> dict:
    result = call(request, "commit", payload.model_dump())
    recovered = call(
        request,
        "recover",
        {
            "operation_id": payload.operation_id,
            "operation_token": payload.operation_token,
        },
    )
    await request.app.state.gateway_sessions.revoke_node(node_id=recovered["node_id"])
    return result


@router.post("/recover")
def recover(payload: Operation, request: Request) -> dict:
    return call(request, "recover", payload.model_dump())


@router.post("/recover-device")
async def recover_device(payload: Operation, request: Request) -> dict:
    result = call(request, "recover_device", payload.model_dump())
    recovered = call(request, "recover", payload.model_dump())
    await request.app.state.gateway_sessions.revoke_node(node_id=recovered["node_id"])
    return result


@router.post("/inspect")
def inspect(
    payload: Accept, request: Request, user: User = Depends(current_user)
) -> dict:
    return call(request, "inspect", {**payload.model_dump(), "user_id": user.id})


@router.post("/decline")
def decline(
    payload: Accept, request: Request, user: User = Depends(current_user)
) -> dict:
    return call(request, "decline", {**payload.model_dump(), "user_id": user.id})


@router.post("/cancel")
def cancel(payload: Operation, request: Request) -> dict:
    return call(request, "cancel", payload.model_dump())
