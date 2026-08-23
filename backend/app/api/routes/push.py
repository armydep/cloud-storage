from typing import Any

from fastapi import APIRouter

from app.api.deps import CurrentUser, SessionDep
from app.push import service
from app.push.schemas import DeviceTokenPublic, DeviceTokenRegister

router = APIRouter(prefix="/push", tags=["push"])


@router.post("/device-tokens", response_model=DeviceTokenPublic)
def register_device_token(
    *, session: SessionDep, current_user: CurrentUser, body: DeviceTokenRegister
) -> Any:
    return service.register_device_token(
        session=session,
        user=current_user,
        token=body.token,
        platform=body.platform.value,
    )


@router.delete("/device-tokens/{token}", status_code=204)
def unregister_device_token(
    *, session: SessionDep, current_user: CurrentUser, token: str
) -> None:
    service.unregister_device_token(session=session, user=current_user, token=token)
