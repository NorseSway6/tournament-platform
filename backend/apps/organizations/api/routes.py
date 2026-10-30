from django.http import HttpRequest
from ninja import Router
from ninja.errors import HttpError

from apps.identity_access.api.dependencies import (
    access_token_auth,
    request_user_id,
)
from apps.organizations.access import (
    organization_organizer_auth,
    require_organizer_organization,
)
from apps.organizations.schemas import (
    OrganizationCreateIn,
    OrganizationListOut,
    OrganizationMemberAddIn,
    OrganizationMemberListOut,
    OrganizationMemberOut,
    OrganizationOut,
    OrganizationPatchIn,
)
from apps.organizations.selectors import (
    get_organization_by_slug,
    list_organization_members,
    list_organizations,
)
from apps.organizations.services import (
    add_organization_member,
    create_organization,
    delete_organization,
    remove_organization_member,
    update_organization,
)
from config.api_errors import api_response

router = Router(tags=["Organizer — organizations"], auth=organization_organizer_auth)
public_router = Router(tags=["Organizations"])


@public_router.get("/{slug}", response=api_response(OrganizationOut))
def organization_by_slug(request: HttpRequest, slug: str):
    """Возвращает публичную страницу организации по slug."""
    organization = get_organization_by_slug(slug)
    if organization is None:
        raise HttpError(404, "Organization not found")
    return organization


@router.get("/organizations", response=api_response(OrganizationListOut))
def organizations_list(request: HttpRequest):
    """Возвращает организации для выбора организатором"""
    items = list(list_organizations(request_user_id(request)))
    return {"items": items, "total": len(items)}


@router.post(
    "/organizations",
    response=api_response({201: OrganizationOut}),
    auth=access_token_auth,
)
def organization_create(request: HttpRequest, payload: OrganizationCreateIn):
    """Создает организацию и делает создателя её организатором."""
    organization = create_organization(payload.model_dump(), creator_id=request_user_id(request))
    return 201, organization


@router.get(
    "/organizations/{organization_id}/members",
    response=api_response(OrganizationMemberListOut),
)
def organization_members_list(request: HttpRequest, organization_id: int):
    """Возвращает участников организации и их роли."""
    require_organizer_organization(request, organization_id)
    items = list(list_organization_members(organization_id))
    return {"items": items, "total": len(items)}


@router.post(
    "/organizations/{organization_id}/members",
    response=api_response({200: OrganizationMemberOut, 201: OrganizationMemberOut}),
)
def organization_member_add(
    request: HttpRequest, organization_id: int, payload: OrganizationMemberAddIn
):
    """Добавляет участника по username или email."""
    require_organizer_organization(request, organization_id)
    member, created = add_organization_member(organization_id, payload.identifier, payload.role)
    return (201 if created else 200), member


@router.delete(
    "/organizations/{organization_id}/members/{member_id}",
    response=api_response({204: None}),
)
def organization_member_remove(request: HttpRequest, organization_id: int, member_id: int):
    """Удаляет участника, запрещая удалить последнего организатора."""
    require_organizer_organization(request, organization_id)
    remove_organization_member(organization_id, member_id)
    return 204, None


@router.patch("/organizations/{organization_id}", response=api_response(OrganizationOut))
def organization_patch(request: HttpRequest, organization_id: int, payload: OrganizationPatchIn):
    """Частично изменяет поля существующей организации"""
    require_organizer_organization(request, organization_id)
    return update_organization(organization_id, payload.model_dump(exclude_unset=True))


@router.delete("/organizations/{organization_id}", response=api_response({204: None}))
def organization_delete(request: HttpRequest, organization_id: int):
    """Удаляет организацию, если нет защищённых ссылок на нее"""
    require_organizer_organization(request, organization_id)
    delete_organization(organization_id)
    return 204, None
