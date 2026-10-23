from django.http import HttpRequest
from ninja import Router
from ninja.errors import HttpError

from apps.organizations.schemas import (
    OrganizationCreateIn,
    OrganizationListOut,
    OrganizationOut,
    OrganizationPatchIn,
)
from apps.organizations.selectors import list_organizations
from apps.organizations.services import (
    create_organization,
    delete_organization,
    update_organization,
)
from config.api_errors import api_response
from apps.identity_access.api.dependencies import request_user_id
from apps.organizations.access import (
    organization_organizer_auth,
    require_organizer_organization,
)

router = Router(tags=["Organizer — organizations"], auth=organization_organizer_auth)




@router.get("/organizations", response=api_response(OrganizationListOut))
def organizations_list(request: HttpRequest):
    """Возвращает организации для выбора организатором"""
    items = list(list_organizations(request_user_id(request)))
    return {"items": items, "total": len(items)}


@router.post("/organizations", response=api_response({201: OrganizationOut}))
def organization_create(request: HttpRequest, payload: OrganizationCreateIn):
    """Создает организацию с проверкой slug и часового пояса"""
    organization = create_organization(
        payload.model_dump(), creator_id=request_user_id(request)
    )
    return 201, organization


@router.patch(
    "/organizations/{organization_id}", response=api_response(OrganizationOut)
)
def organization_patch(
    request: HttpRequest, organization_id: int, payload: OrganizationPatchIn
):
    """Частично изменяет поля существующей организации"""
    require_organizer_organization(request, organization_id)
    return update_organization(
        organization_id, payload.model_dump(exclude_unset=True)
    )


@router.delete("/organizations/{organization_id}", response=api_response({204: None}))
def organization_delete(request: HttpRequest, organization_id: int):
    """Удаляет организацию, если нет защищённых ссылок на нее"""
    require_organizer_organization(request, organization_id)
    delete_organization(organization_id)
    return 204, None
