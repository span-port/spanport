"""In-memory fakes for the repository Protocols. Reuse these instead of redefining them."""

import dataclasses
from collections.abc import Sequence
from datetime import UTC, datetime

from spanport_server.core.constants import FULL_ACCESS_ROLES
from spanport_server.core.errors import ConflictError, DeliveryError, StorageUnavailableError
from spanport_server.core.ids import UuidV7, new_id
from spanport_server.core.key_hashing import hash_api_key, visible_suffix
from spanport_server.schemas.alert import (
    AlertEventItem,
    AlertRuleFields,
    AlertRuleRecord,
    AlertState,
    OpenAlert,
)
from spanport_server.schemas.api_key import ApiKeyRecord, KeyType, Scope
from spanport_server.schemas.auth import Caller, Role, UserRecord
from spanport_server.schemas.log_row import LogRow
from spanport_server.schemas.log_search import LogItem, LogPosition, LogQuery
from spanport_server.schemas.span_row import SpanRow
from spanport_server.schemas.team import (
    AccountOwner,
    InviteDetails,
    InviteItem,
    ProjectAccess,
    TeamChange,
    UserItem,
)
from spanport_server.schemas.tenant import ProjectItem, ProjectRef
from spanport_server.schemas.trace import RequestItem, RequestQuery, SpanPosition, StoredSpan

SAMPLE_DATA_KEY = "sp_ingest_test-key-0000000000000000000000a1b2"
SAMPLE_ADMIN_KEY = "sp_admin_test-key-00000000000000000000000c3d4"


class FakeApiKeyStore:
    """Stores keys by hash, like the api_keys table."""

    def __init__(self) -> None:
        self.records_by_hash: dict[str, ApiKeyRecord] = {}

    async def find_by_hash(self, key_hash: str) -> ApiKeyRecord | None:
        return self.records_by_hash.get(key_hash)

    async def insert_key(
        self,
        org_id: UuidV7,
        project_id: UuidV7 | None,
        key_type: KeyType,
        key_hash: str,
        last_four: str,
        scopes: tuple[Scope, ...] = (),
        expires_at: datetime | None = None,
        name: str | None = None,
    ) -> ApiKeyRecord:
        record = ApiKeyRecord(
            id=new_id(),
            org_id=org_id,
            project_id=project_id,
            key_type=key_type,
            last_four=last_four,
            scopes=scopes,
            created_at=datetime.now(UTC),
            expires_at=expires_at,
            revoked_at=None,
            name=name,
        )
        self.records_by_hash[key_hash] = record
        return record

    async def list_for_org(self, org_id: UuidV7) -> list[ApiKeyRecord]:
        return [record for record in self.records_by_hash.values() if record.org_id == org_id]

    async def list_page(
        self, org_id: UuidV7, before_id: UuidV7 | None, limit: int
    ) -> list[ApiKeyRecord]:
        newest_first = sorted(await self.list_for_org(org_id), key=lambda r: r.id, reverse=True)
        return [r for r in newest_first if before_id is None or r.id < before_id][:limit]

    async def rename(self, org_id: UuidV7, key_id: UuidV7, name: str) -> ApiKeyRecord | None:
        for key_hash, record in self.records_by_hash.items():
            if record.org_id == org_id and record.id == key_id:
                self.records_by_hash[key_hash] = dataclasses.replace(record, name=name)
                return self.records_by_hash[key_hash]
        return None

    async def delete_revoked(self, org_id: UuidV7, key_id: UuidV7) -> bool:
        for key_hash, record in self.records_by_hash.items():
            if record.org_id == org_id and record.id == key_id and record.revoked_at:
                del self.records_by_hash[key_hash]
                return True
        return False

    async def revoke(self, org_id: UuidV7, key_id: UuidV7, revoked_at: datetime) -> bool:
        for key_hash, record in self.records_by_hash.items():
            if record.org_id == org_id and record.id == key_id and record.revoked_at is None:
                self.records_by_hash[key_hash] = dataclasses.replace(record, revoked_at=revoked_at)
                return True
        return False

    def add_key(
        self,
        raw_key: str,
        key_type: KeyType = KeyType.INGEST,
        revoked_at: datetime | None = None,
        expires_at: datetime | None = None,
        scopes: tuple[Scope, ...] = (),
        org_id: UuidV7 | None = None,
    ) -> ApiKeyRecord:
        record = ApiKeyRecord(
            id=new_id(),
            org_id=org_id or new_id(),
            project_id=new_id() if key_type == KeyType.INGEST else None,
            key_type=key_type,
            last_four=visible_suffix(raw_key),
            scopes=scopes,
            created_at=datetime.now(UTC),
            expires_at=expires_at,
            revoked_at=revoked_at,
        )
        self.records_by_hash[hash_api_key(raw_key)] = record
        return record


class FakeTenantStore:
    """Returns the same ids for the same slugs, like the tenant tables."""

    def __init__(self) -> None:
        self.projects: dict[tuple[str, str, str, str], ProjectRef] = {}
        self.org_ids: dict[str, UuidV7] = {}
        self.archived: set[UuidV7] = set()

    async def get_or_create_project(
        self, org_slug: str, client_slug: str, project_slug: str, environment: str
    ) -> ProjectRef:
        org_id = self.org_ids.setdefault(org_slug, new_id())
        slugs = (org_slug, client_slug, project_slug, environment)
        return self.projects.setdefault(slugs, ProjectRef(org_id=org_id, project_id=new_id()))

    async def find_org_id(self, org_slug: str) -> UuidV7 | None:
        return self.org_ids.get(org_slug)

    async def project_exists(self, org_id: UuidV7, project_id: UuidV7) -> bool:
        return ProjectRef(org_id=org_id, project_id=project_id) in self.projects.values()

    async def create_project(
        self, org_id: UuidV7, client_slug: str, project_slug: str, environment: str
    ) -> ProjectItem | None:
        org_slug = next(slug for slug, known_id in self.org_ids.items() if known_id == org_id)
        slugs = (org_slug, client_slug, project_slug, environment)
        if slugs in self.projects:
            return None
        ref = await self.get_or_create_project(*slugs)
        return ProjectItem(
            id=ref.project_id, client=client_slug, project=project_slug, environment=environment
        )

    async def list_projects(
        self,
        org_id: UuidV7,
        after_id: UuidV7 | None,
        limit: int,
        only_ids: frozenset[UuidV7] | None = None,
    ) -> list[ProjectItem]:
        items = sorted(
            (
                self._item(slugs, ref)
                for slugs, ref in self.projects.items()
                if ref.org_id == org_id and (only_ids is None or ref.project_id in only_ids)
            ),
            key=lambda item: item.id,
        )
        return [item for item in items if after_id is None or item.id > after_id][:limit]

    async def find_project(self, org_id: UuidV7, project_id: UuidV7) -> ProjectItem | None:
        return next(
            (
                self._item(slugs, ref)
                for slugs, ref in self.projects.items()
                if ref == ProjectRef(org_id=org_id, project_id=project_id)
            ),
            None,
        )

    async def update_project(
        self, org_id: UuidV7, project_id: UuidV7, project_slug: str, environment: str
    ) -> ProjectItem | None:
        ref = ProjectRef(org_id=org_id, project_id=project_id)
        old_slugs = next((slugs for slugs, known in self.projects.items() if known == ref), None)
        if old_slugs is None:
            return None
        new_slugs = (old_slugs[0], old_slugs[1], project_slug, environment)
        if new_slugs != old_slugs and new_slugs in self.projects:
            raise ConflictError("exists")
        del self.projects[old_slugs]
        self.projects[new_slugs] = ref
        return self._item(new_slugs, ref)

    async def set_archived(
        self, org_id: UuidV7, project_id: UuidV7, archived_at: datetime | None
    ) -> ProjectItem | None:
        if await self.find_project(org_id, project_id) is None:
            return None
        if archived_at is None:
            self.archived.discard(project_id)
        else:
            self.archived.add(project_id)
        return await self.find_project(org_id, project_id)

    async def delete_project(self, org_id: UuidV7, project_id: UuidV7) -> bool:
        ref = ProjectRef(org_id=org_id, project_id=project_id)
        slugs = next((slugs for slugs, known in self.projects.items() if known == ref), None)
        if slugs is None:
            return False
        del self.projects[slugs]
        return True

    def _item(self, slugs: tuple[str, str, str, str], ref: ProjectRef) -> ProjectItem:
        _, client, project, environment = slugs
        return ProjectItem(
            id=ref.project_id,
            client=client,
            project=project,
            environment=environment,
            archived=ref.project_id in self.archived,
        )


def caller_for(org_id: UuidV7) -> Caller:
    """A signed-in caller in this organization, as the data endpoints receive it."""
    return Caller(org_id=org_id, label="user=test")


class FakeUserStore:
    """Users and setup tokens in memory, with the repository's rules (single use, expiring)."""

    def __init__(self) -> None:
        self.users: dict[UuidV7, tuple[UserRecord, str]] = {}
        self.setup_tokens: dict[str, datetime] = {}
        self.used_tokens: set[str] = set()
        self.disabled: set[UuidV7] = set()
        self.invites: dict[UuidV7, FakeInvite] = {}
        self.login_failures: dict[str, list[datetime]] = {}

    async def recent_login_failures(self, email_hash: str, since: datetime) -> list[datetime]:
        return sorted(at for at in self.login_failures.get(email_hash, []) if at > since)

    async def record_login_failure(
        self, email_hash: str, now: datetime, forget_before: datetime
    ) -> None:
        for times in self.login_failures.values():
            times[:] = [at for at in times if at >= forget_before]
        self.login_failures.setdefault(email_hash, []).append(now)

    async def clear_login_failures(self, email_hash: str) -> None:
        self.login_failures.pop(email_hash, None)

    async def count_users(self) -> int:
        return len(self.users)

    async def insert_setup_token(self, token_hash: str, expires_at: datetime) -> None:
        self.setup_tokens[token_hash] = expires_at

    async def create_owner(
        self,
        token_hash: str,
        now: datetime,
        org_slug: str,
        name: str,
        email: str,
        password_hash: str,
    ) -> UserRecord | None:
        expires_at = self.setup_tokens.get(token_hash)
        if expires_at is None or expires_at <= now or token_hash in self.used_tokens or self.users:
            return None
        self.used_tokens.add(token_hash)
        return self.add_user(email, password_hash, Role.OWNER, org_slug, name)

    async def find_for_login(self, email: str) -> tuple[UserRecord, str] | None:
        return next(
            (
                entry
                for entry in self.users.values()
                if entry[0].email == email and entry[0].id not in self.disabled
            ),
            None,
        )

    async def find_by_id(self, user_id: UuidV7) -> UserRecord | None:
        entry = self.users.get(user_id)
        return entry[0] if entry and user_id not in self.disabled else None

    async def find_open_invite(self, token_hash: str, now: datetime) -> InviteDetails | None:
        invite = self._open_invite(token_hash, now)
        if invite is None:
            return None
        return InviteDetails(
            email=invite.email, role=invite.role, organization="acme", invited_by="Sam Rao"
        )

    async def accept_invite(
        self, token_hash: str, now: datetime, name: str, password_hash: str
    ) -> UserRecord | None:
        invite = self._open_invite(token_hash, now)
        if invite is None:
            return None
        existing = next((u for u, _ in self.users.values() if u.email == invite.email), None)
        if existing is not None and not (
            existing.id in self.disabled and existing.org_id == invite.org_id
        ):
            return None
        invite.accepted = True
        if existing is not None:
            self.disabled.discard(existing.id)
            del self.users[existing.id]
        user = self.add_user(
            invite.email, password_hash, invite.role, name=name, org_id=invite.org_id
        )
        if not invite.all_projects and invite.role not in FULL_ACCESS_ROLES:
            user = dataclasses.replace(user, project_ids=frozenset(invite.project_ids))
            self.users[user.id] = (user, password_hash)
        return user

    def _open_invite(self, token_hash: str, now: datetime) -> FakeInvite | None:
        return next(
            (
                invite
                for invite in self.invites.values()
                if invite.token_hash == token_hash and invite.is_open(now)
            ),
            None,
        )

    async def set_password(self, email: str, password_hash: str) -> UuidV7 | None:
        found = await self.find_for_login(email)
        if found is None:
            return None
        self.users[found[0].id] = (found[0], password_hash)
        return found[0].id

    def add_user(
        self,
        email: str,
        password_hash: str,
        role: Role = Role.MEMBER,
        org_slug: str = "acme",
        name: str = "Sam Rao",
        org_id: UuidV7 | None = None,
    ) -> UserRecord:
        user = UserRecord(
            id=new_id(),
            org_id=org_id or new_id(),
            org_slug=org_slug,
            email=email,
            name=name,
            role=role,
        )
        self.users[user.id] = (user, password_hash)
        return user


@dataclasses.dataclass
class FakeInvite:
    org_id: UuidV7
    email: str
    role: Role
    token_hash: str
    expires_at: datetime
    all_projects: bool = True
    project_ids: list[UuidV7] = dataclasses.field(default_factory=list)
    accepted: bool = False
    cancelled: bool = False

    def is_open(self, now: datetime) -> bool:
        return not self.accepted and not self.cancelled and self.expires_at > now


class FakeTeamStore:
    """The team view of a FakeUserStore: users, roles, removal and invites, with the
    repository's keep-an-owner rule.
    """

    def __init__(self, users: FakeUserStore, tenants: FakeTenantStore | None = None) -> None:
        self.users = users
        self.tenants = tenants or FakeTenantStore()

    async def set_project_access(
        self, org_id: UuidV7, user_id: UuidV7, all_projects: bool, project_ids: list[UuidV7]
    ) -> bool:
        if await self.find_user(org_id, user_id) is None:
            return False
        user, password_hash = self.users.users[user_id]
        visible = None if all_projects else frozenset(project_ids)
        self.users.users[user_id] = (dataclasses.replace(user, project_ids=visible), password_hash)
        return True

    async def count_org_projects(self, org_id: UuidV7, project_ids: list[UuidV7]) -> int:
        known = {ref.project_id for ref in self.tenants.projects.values() if ref.org_id == org_id}
        return len(known & set(project_ids))

    async def list_users(
        self, org_id: UuidV7, after_id: UuidV7 | None, limit: int
    ) -> list[UserItem]:
        items = sorted((item for item in self._active(org_id)), key=lambda item: item.id)
        return [item for item in items if after_id is None or item.id > after_id][:limit]

    async def find_user(self, org_id: UuidV7, user_id: UuidV7) -> UserItem | None:
        return next((item for item in self._active(org_id) if item.id == user_id), None)

    async def change_role(self, org_id: UuidV7, user_id: UuidV7, role: Role) -> TeamChange:
        outcome = await self._owner_kept(org_id, user_id, role)
        if outcome is TeamChange.DONE:
            user, password_hash = self.users.users[user_id]
            self.users.users[user_id] = (dataclasses.replace(user, role=role), password_hash)
        return outcome

    async def disable_user(self, org_id: UuidV7, user_id: UuidV7, now: datetime) -> TeamChange:
        outcome = await self._owner_kept(org_id, user_id, None)
        if outcome is TeamChange.DONE:
            self.users.disabled.add(user_id)
        return outcome

    async def find_account(self, email: str) -> AccountOwner | None:
        for user, _ in self.users.users.values():
            if user.email == email:
                return AccountOwner(org_id=user.org_id, disabled=user.id in self.users.disabled)
        return None

    async def insert_invite(
        self,
        org_id: UuidV7,
        email: str,
        role: Role,
        access: ProjectAccess,
        token_hash: str,
        invited_by: UuidV7,
        now: datetime,
        expires_at: datetime,
    ) -> InviteItem:
        for invite in self.users.invites.values():
            if (invite.org_id, invite.email) == (org_id, email) and invite.is_open(now):
                invite.cancelled = True
        invite_id = new_id()
        self.users.invites[invite_id] = FakeInvite(
            org_id,
            email,
            role,
            token_hash,
            expires_at,
            access.all_projects,
            list(access.project_ids),
        )
        return self._item(invite_id, now)

    async def list_open_invites(
        self, org_id: UuidV7, now: datetime, after_id: UuidV7 | None, limit: int
    ) -> list[InviteItem]:
        found = [
            self._item(invite_id, now)
            for invite_id, invite in sorted(self.users.invites.items())
            if invite.org_id == org_id and invite.is_open(now)
        ]
        return [item for item in found if after_id is None or item.id > after_id][:limit]

    async def cancel_invite(self, org_id: UuidV7, invite_id: UuidV7, now: datetime) -> bool:
        invite = self.users.invites.get(invite_id)
        if invite is None or invite.org_id != org_id or not invite.is_open(now):
            return False
        invite.cancelled = True
        return True

    def _active(self, org_id: UuidV7) -> list[UserItem]:
        return [
            UserItem(
                id=user.id,
                name=user.name,
                email=user.email,
                role=user.role,
                created_at=datetime.now(UTC),
                all_projects=user.project_ids is None,
                project_ids=sorted(user.project_ids or []),
            )
            for user, _ in self.users.users.values()
            if user.org_id == org_id and user.id not in self.users.disabled
        ]

    async def _owner_kept(
        self, org_id: UuidV7, user_id: UuidV7, new_role: Role | None
    ) -> TeamChange:
        active = self._active(org_id)
        if not any(item.id == user_id for item in active):
            return TeamChange.NOT_FOUND
        owners = {item.id for item in active if item.role is Role.OWNER}
        if owners == {user_id} and new_role is not Role.OWNER:
            return TeamChange.LAST_OWNER
        return TeamChange.DONE

    def _item(self, invite_id: UuidV7, now: datetime) -> InviteItem:
        invite = self.users.invites[invite_id]
        return InviteItem(
            id=invite_id,
            email=invite.email,
            role=invite.role,
            invited_by="Sam Rao",
            created_at=now,
            expires_at=invite.expires_at,
            all_projects=invite.all_projects,
            project_ids=invite.project_ids,
        )


@dataclasses.dataclass
class FakeSession:
    user_id: UuidV7
    csrf_hash: str
    last_seen_at: datetime
    revoked_at: datetime | None = None


class FakeSessionStore:
    """Sessions in memory, keyed by token hash."""

    def __init__(self) -> None:
        self.sessions: dict[str, FakeSession] = {}

    async def insert(self, user_id: UuidV7, token_hash: str, csrf_hash: str) -> None:
        self.sessions[token_hash] = FakeSession(user_id, csrf_hash, datetime.now(UTC))

    async def touch_active(
        self, token_hash: str, idle_since: datetime, now: datetime
    ) -> tuple[UuidV7, str] | None:
        session = self.sessions.get(token_hash)
        if session is None or session.revoked_at or session.last_seen_at < idle_since:
            return None
        session.last_seen_at = now
        return session.user_id, session.csrf_hash

    async def revoke(self, token_hash: str, now: datetime) -> UuidV7 | None:
        session = self.sessions.get(token_hash)
        if session is None or session.revoked_at:
            return None
        session.revoked_at = now
        return session.user_id

    async def revoke_for_user(self, user_id: UuidV7, now: datetime) -> int:
        live = [s for s in self.sessions.values() if s.user_id == user_id and not s.revoked_at]
        for session in live:
            session.revoked_at = now
        return len(live)


class FakeLogSearchStore:
    """Returns prepared rows and remembers what it was asked."""

    def __init__(self, rows: list[LogItem] | None = None) -> None:
        self.rows = rows or []
        self.by_level: dict[str, int] = {}
        self.queries: list[tuple[LogQuery, LogPosition | None, int]] = []
        self.storage_down = False

    async def search(self, query: LogQuery, after: LogPosition | None, limit: int) -> list[LogItem]:
        """Rows newest first, continuing strictly after `after` like the real keyset paging."""
        self.queries.append((query, after, limit))
        newest_first = sorted(self.rows, key=lambda row: (row.ts, row.log_id), reverse=True)
        if after is not None:
            newest_first = [r for r in newest_first if (r.ts, r.log_id) < (after.ts, after.log_id)]
        return newest_first[:limit]

    async def count_by_level(self, query: LogQuery) -> dict[str, int]:
        if self.storage_down:
            raise StorageUnavailableError("Log storage is unavailable. Retry later.")
        self.queries.append((query, None, 0))
        return self.by_level


class FakeLogWriter:
    """Keeps inserted rows; can pretend ClickHouse is down."""

    def __init__(self, storage_down: bool = False) -> None:
        self.rows: list[LogRow] = []
        self.storage_down = storage_down
        self.deleted_projects: list[tuple[UuidV7, UuidV7]] = []

    async def insert_logs(self, rows: Sequence[LogRow]) -> None:
        if self.storage_down:
            raise StorageUnavailableError("Log storage is unavailable. Retry later.")
        self.rows.extend(rows)

    async def delete_project_data(self, org_id: UuidV7, project_id: UuidV7) -> None:
        if self.storage_down:
            raise StorageUnavailableError("Log storage is unavailable. Retry later.")
        self.deleted_projects.append((org_id, project_id))


class FakeSpanWriter:
    """Keeps inserted span rows; can pretend ClickHouse is down."""

    def __init__(self, storage_down: bool = False) -> None:
        self.rows: list[SpanRow] = []
        self.storage_down = storage_down

    async def insert_spans(self, rows: Sequence[SpanRow]) -> None:
        if self.storage_down:
            raise StorageUnavailableError("Log storage is unavailable. Retry later.")
        self.rows.extend(rows)


class FakeSpanSearchStore:
    """Requests and trace spans in memory; remembers the request queries it was asked."""

    def __init__(self) -> None:
        self.requests: list[RequestItem] = []
        self.spans: dict[str, list[StoredSpan]] = {}
        self.queries: list[RequestQuery] = []

    async def search_requests(
        self, query: RequestQuery, after: SpanPosition | None, limit: int
    ) -> list[RequestItem]:
        self.queries.append(query)
        newest_first = sorted(self.requests, key=lambda r: (r.start_ts, r.span_id), reverse=True)
        if after is not None:
            newest_first = [
                r for r in newest_first if (r.start_ts, r.span_id) < (after.ts, after.span_id)
            ]
        return newest_first[:limit]

    async def trace_spans(
        self, org_id: UuidV7, project_id: UuidV7, trace_id: str, since: datetime, limit: int
    ) -> list[StoredSpan]:
        return self.spans.get(trace_id, [])[:limit]


class FakeAlertRuleStore:
    """Alert rules in memory, with due times like the alert_rules table."""

    def __init__(self) -> None:
        self.rules: dict[UuidV7, AlertRuleRecord] = {}
        self.next_check: dict[UuidV7, datetime] = {}

    async def list_rules(
        self, org_id: UuidV7, project_id: UuidV7, after_id: UuidV7 | None, limit: int
    ) -> list[AlertRuleRecord]:
        found = sorted(
            (r for r in self.rules.values() if (r.org_id, r.project_id) == (org_id, project_id)),
            key=lambda rule: rule.id,
        )
        return [r for r in found if after_id is None or r.id > after_id][:limit]

    async def find_rule(self, org_id: UuidV7, rule_id: UuidV7) -> AlertRuleRecord | None:
        rule = self.rules.get(rule_id)
        return rule if rule and rule.org_id == org_id else None

    async def insert_rule(
        self,
        org_id: UuidV7,
        project_id: UuidV7,
        settings: AlertRuleFields,
        next_check_at: datetime,
    ) -> AlertRuleRecord:
        rule = self._record(new_id(), org_id, project_id, settings)
        self.rules[rule.id] = rule
        self.next_check[rule.id] = next_check_at
        return rule

    async def update_rule(
        self,
        org_id: UuidV7,
        rule_id: UuidV7,
        settings: AlertRuleFields,
        next_check_at: datetime,
    ) -> AlertRuleRecord | None:
        current = await self.find_rule(org_id, rule_id)
        if current is None:
            return None
        self.rules[rule_id] = self._record(rule_id, org_id, current.project_id, settings)
        self.next_check[rule_id] = next_check_at
        return self.rules[rule_id]

    async def delete_rule(self, org_id: UuidV7, rule_id: UuidV7) -> bool:
        if await self.find_rule(org_id, rule_id) is None:
            return False
        del self.rules[rule_id]
        return True

    async def list_org_ids(self) -> list[UuidV7]:
        return sorted({rule.org_id for rule in self.rules.values()})

    async def claim_due_rules(
        self, org_id: UuidV7, now: datetime, next_check_at: datetime, limit: int
    ) -> list[AlertRuleRecord]:
        due = [
            rule
            for rule in self.rules.values()
            if rule.org_id == org_id and rule.enabled and self.next_check[rule.id] <= now
        ][:limit]
        for rule in due:
            self.next_check[rule.id] = next_check_at
        return due

    def _record(
        self, rule_id: UuidV7, org_id: UuidV7, project_id: UuidV7, settings: AlertRuleFields
    ) -> AlertRuleRecord:
        return AlertRuleRecord(
            id=rule_id,
            org_id=org_id,
            project_id=project_id,
            name=settings.name,
            query=settings.query,
            threshold=settings.threshold,
            window_minutes=settings.window_minutes,
            email_recipients=tuple(settings.email_recipients),
            enabled=settings.enabled,
            created_at=datetime.now(UTC),
        )


@dataclasses.dataclass
class FakeAlert:
    org_id: UuidV7
    rule_id: UuidV7
    state: AlertState
    matched_count: int
    fired_at: datetime
    acknowledged_by: UuidV7 | None = None
    resolved_by: UuidV7 | None = None


class FakeAlertEventStore:
    """Alerts in memory, keeping the table's one-open-alert-per-rule rule."""

    def __init__(self, rules: FakeAlertRuleStore | None = None) -> None:
        self.alerts: dict[UuidV7, FakeAlert] = {}
        self.rules = rules or FakeAlertRuleStore()

    async def find_open(self, org_id: UuidV7, rule_id: UuidV7) -> OpenAlert | None:
        for alert_id, alert in self.alerts.items():
            if (alert.org_id, alert.rule_id) == (org_id, rule_id) and alert.state != "resolved":
                return OpenAlert(id=alert_id, state=alert.state, fired_at=alert.fired_at)
        return None

    async def open_alert(
        self, org_id: UuidV7, rule_id: UuidV7, matched_count: int
    ) -> OpenAlert | None:
        if await self.find_open(org_id, rule_id):
            return None
        alert_id = new_id()
        fired_at = datetime.now(UTC)
        self.alerts[alert_id] = FakeAlert(
            org_id, rule_id, AlertState.FIRING, matched_count, fired_at
        )
        return OpenAlert(id=alert_id, state=AlertState.FIRING, fired_at=fired_at)

    async def resolve(
        self, org_id: UuidV7, event_id: UuidV7, resolved_by: UuidV7 | None, now: datetime
    ) -> bool:
        alert = self.alerts.get(event_id)
        if alert is None or alert.org_id != org_id or alert.state == AlertState.RESOLVED:
            return False
        alert.state = AlertState.RESOLVED
        alert.resolved_by = resolved_by
        return True

    async def find_event_project(self, org_id: UuidV7, event_id: UuidV7) -> UuidV7 | None:
        alert = self.alerts.get(event_id)
        if alert is None or alert.org_id != org_id:
            return None
        rule = self.rules.rules.get(alert.rule_id)
        return rule.project_id if rule else None

    async def acknowledge(
        self, org_id: UuidV7, event_id: UuidV7, user_id: UuidV7, now: datetime
    ) -> bool:
        alert = self.alerts.get(event_id)
        if alert is None or alert.org_id != org_id or alert.state != AlertState.FIRING:
            return False
        alert.state = AlertState.ACKNOWLEDGED
        alert.acknowledged_by = user_id
        return True

    async def list_events(
        self, org_id: UuidV7, project_id: UuidV7, before_id: UuidV7 | None, limit: int
    ) -> list[AlertEventItem]:
        items = []
        for alert_id, alert in sorted(self.alerts.items(), reverse=True):
            rule = self.rules.rules.get(alert.rule_id)
            if rule is None or (alert.org_id, rule.project_id) != (org_id, project_id):
                continue
            if before_id is not None and alert_id >= before_id:
                continue
            items.append(
                AlertEventItem(
                    id=alert_id,
                    rule_id=rule.id,
                    rule_name=rule.name,
                    query=rule.query,
                    threshold=rule.threshold,
                    window_minutes=rule.window_minutes,
                    state=alert.state,
                    matched_count=alert.matched_count,
                    fired_at=alert.fired_at,
                    acknowledged_at=None,
                    acknowledged_by=None,
                    resolved_at=None,
                    resolved_by=None,
                )
            )
        return items[:limit]


class FakeEmailSender:
    """Keeps sent emails; can pretend the mail server refuses them."""

    def __init__(self, refuse: bool = False) -> None:
        # (recipients, subject, plain text, HTML) per email sent.
        self.sent: list[tuple[list[str], str, str, str]] = []
        self.refuse = refuse

    async def send(self, recipients: list[str], subject: str, text: str, html: str) -> None:
        if self.refuse:
            raise DeliveryError("Email could not be sent: SMTPRecipientsRefused.")
        self.sent.append((recipients, subject, text, html))


class FakePostgresSchema:
    def __init__(self) -> None:
        self.upgraded = False
        self.downgrades = 0

    async def upgrade_to_latest(self) -> None:
        self.upgraded = True

    async def downgrade_one(self) -> None:
        self.downgrades += 1


class FakeClickHouseSchema:
    def __init__(self, available: list[str], applied: list[str]) -> None:
        self.available = available
        self.applied = applied

    def available_versions(self) -> list[str]:
        return self.available

    async def applied_versions(self) -> list[str]:
        return sorted(self.applied)

    async def apply(self, version: str) -> None:
        self.applied.append(version)

    async def revert(self, version: str) -> None:
        self.applied.remove(version)
