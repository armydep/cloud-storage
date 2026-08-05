import uuid
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.core.security import get_password_hash, verify_password
from app.models import Folder, Item, ItemCreate, User, UserCreate, UserUpdate

ROOT_FOLDER_PATH = "root"


def create_user(*, session: Session, user_create: UserCreate) -> User:
    db_obj = User.model_validate(
        user_create, update={"hashed_password": get_password_hash(user_create.password)}
    )
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_user(*, session: Session, db_user: User, user_in: UserUpdate) -> Any:
    user_data = user_in.model_dump(exclude_unset=True)
    extra_data = {}
    if "password" in user_data:
        password = user_data["password"]
        hashed_password = get_password_hash(password)
        extra_data["hashed_password"] = hashed_password
    db_user.sqlmodel_update(user_data, update=extra_data)
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user


def get_user_by_email(*, session: Session, email: str) -> User | None:
    statement = select(User).where(User.email == email)
    session_user = session.exec(statement).first()
    return session_user


# Dummy hash to use for timing attack prevention when user is not found
# This is an Argon2 hash of a random password, used to ensure constant-time comparison
DUMMY_HASH = "$argon2id$v=19$m=65536,t=3,p=4$MjQyZWE1MzBjYjJlZTI0Yw$YTU4NGM5ZTZmYjE2NzZlZjY0ZWY3ZGRkY2U2OWFjNjk"


def authenticate(*, session: Session, email: str, password: str) -> User | None:
    db_user = get_user_by_email(session=session, email=email)
    if not db_user:
        # Prevent timing attacks by running password verification even when user doesn't exist
        # This ensures the response time is similar whether or not the email exists
        verify_password(password, DUMMY_HASH)
        return None
    verified, updated_password_hash = verify_password(password, db_user.hashed_password)
    if not verified:
        return None
    if updated_password_hash:
        db_user.hashed_password = updated_password_hash
        session.add(db_user)
        session.commit()
        session.refresh(db_user)
    return db_user


def create_item(*, session: Session, item_in: ItemCreate, owner_id: uuid.UUID) -> Item:
    db_item = Item.model_validate(item_in, update={"owner_id": owner_id})
    session.add(db_item)
    session.commit()
    session.refresh(db_item)
    return db_item


def get_folder_by_path(
    *, session: Session, owner_id: uuid.UUID, path: str
) -> Folder | None:
    statement = select(Folder).where(Folder.owner_id == owner_id, Folder.path == path)
    return session.exec(statement).first()


def get_or_create_root_folder(*, session: Session, owner_id: uuid.UUID) -> Folder:
    """
    Return the owner's root folder, creating it on first use.

    Two concurrent first requests can both find no root and both try to insert
    one. The uq_folders_owner_path constraint lets the loser of that race fail
    and read the winner's row instead of creating a second root.
    """
    folder = get_folder_by_path(
        session=session, owner_id=owner_id, path=ROOT_FOLDER_PATH
    )
    if folder:
        return folder

    folder = Folder(name=ROOT_FOLDER_PATH, path=ROOT_FOLDER_PATH, owner_id=owner_id)
    session.add(folder)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        statement = select(Folder).where(
            Folder.owner_id == owner_id, Folder.path == ROOT_FOLDER_PATH
        )
        return session.exec(statement).one()
    session.refresh(folder)
    return folder
