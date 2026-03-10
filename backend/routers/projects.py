import logging

from cryptography.fernet import InvalidToken
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import Project
from schemas import ProjectCreate, ProjectUpdate, ProjectResponse
from services.encryption import encrypt_pat, decrypt_pat, mask_pat
from services.git_service import fetch_branches

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/projects", tags=["projects"])


def _to_response(project: Project) -> ProjectResponse:
    try:
        pat = decrypt_pat(project.encrypted_pat)
        masked = mask_pat(pat)
    except InvalidToken:
        logger.warning(f"Cannot decrypt PAT for project {project.id} — key mismatch")
        masked = "****[key mismatch]"
    return ProjectResponse(
        id=project.id,
        name=project.name,
        repo_url=project.repo_url,
        platform=project.platform,
        git_host=project.git_host,
        masked_pat=masked,
        git_user_name=project.git_user_name,
        git_user_email=project.git_user_email,
        merge_option=project.merge_option,
        notifications_enabled=project.notifications_enabled,
        last_base_branch=project.last_base_branch,
        default_model=project.default_model,
        created_at=project.created_at,
    )


@router.get("", response_model=list[ProjectResponse])
def list_projects(db: Session = Depends(get_db)):
    projects = db.query(Project).order_by(Project.created_at.desc()).all()
    return [_to_response(p) for p in projects]


@router.post("", response_model=ProjectResponse, status_code=201)
def create_project(data: ProjectCreate, db: Session = Depends(get_db)):
    project = Project(
        name=data.name,
        repo_url=data.repo_url,
        platform=data.platform,
        git_host=data.git_host,
        encrypted_pat=encrypt_pat(data.pat),
        merge_option=data.merge_option,
        notifications_enabled=data.notifications_enabled,
        default_model=data.default_model,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return _to_response(project)


@router.put("/{project_id}", response_model=ProjectResponse)
def update_project(project_id: int, data: ProjectUpdate, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if data.name is not None:
        project.name = data.name
    if data.repo_url is not None:
        project.repo_url = data.repo_url
    if data.platform is not None:
        project.platform = data.platform
    if data.git_host is not None:
        project.git_host = data.git_host
    if data.pat is not None and data.pat != "":
        project.encrypted_pat = encrypt_pat(data.pat)
    if data.git_user_name is not None:
        project.git_user_name = data.git_user_name.strip() or None
    if data.git_user_email is not None:
        project.git_user_email = data.git_user_email.strip() or None
    if "merge_option" in data.model_fields_set:
        project.merge_option = data.merge_option
    if "notifications_enabled" in data.model_fields_set:
        project.notifications_enabled = data.notifications_enabled
    if "default_model" in data.model_fields_set:
        project.default_model = data.default_model

    db.commit()
    db.refresh(project)
    return _to_response(project)


@router.get("/{project_id}/branches", response_model=list[str])
def list_branches(project_id: int, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        pat = decrypt_pat(project.encrypted_pat)
    except InvalidToken:
        raise HTTPException(status_code=422, detail="Could not decrypt project PAT")

    return fetch_branches(project.repo_url, pat, project.platform, project.git_host)


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: int, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    db.delete(project)
    db.commit()
