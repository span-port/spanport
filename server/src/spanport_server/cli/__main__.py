"""Admin commands.

    python -m spanport_server.cli migrate
    python -m spanport_server.cli rollback-postgres
    python -m spanport_server.cli rollback-clickhouse
    python -m spanport_server.cli create-data-key --org acme --client northwind \
        --project hr-portal --environment production
    python -m spanport_server.cli create-admin-key --org acme --scope logs:read
    python -m spanport_server.cli list-keys --org acme
    python -m spanport_server.cli revoke-key --org acme --key-id <id from list-keys>
    python -m spanport_server.cli reset-password --email owner@example.com

Logs go to stderr, so stdout carries only a command's output (the new key).
"""

import argparse
import asyncio
import getpass
import logging.config
import sys
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import async_sessionmaker

from spanport_server.core.config import DatabaseSettings, load_settings
from spanport_server.core.constants import CLI_LOG_STREAM, MAX_ADMIN_KEY_DAYS
from spanport_server.core.errors import SpanportError
from spanport_server.core.logging import build_logging_config
from spanport_server.repositories.clickhouse.database import create_clickhouse_client
from spanport_server.repositories.clickhouse.schema_repository import ClickHouseSchemaRepository
from spanport_server.repositories.postgres.api_key_repository import ApiKeyRepository
from spanport_server.repositories.postgres.database import create_postgres_engine
from spanport_server.repositories.postgres.schema_repository import PostgresSchemaRepository
from spanport_server.repositories.postgres.session_repository import SessionRepository
from spanport_server.repositories.postgres.tenant_repository import TenantRepository
from spanport_server.repositories.postgres.user_repository import UserRepository
from spanport_server.schemas.api_key import ApiKeyRecord, Scope
from spanport_server.services.api_key_service import ApiKeyService
from spanport_server.services.auth_service import AuthService
from spanport_server.services.schema_migration_service import SchemaMigrationService

SchemaAction = Callable[[SchemaMigrationService], Awaitable[object]]


async def run_schema_action(settings: DatabaseSettings, action: SchemaAction) -> None:
    """Run one SchemaMigrationService method (upgrade or a rollback), then close ClickHouse."""
    clickhouse_client = await create_clickhouse_client(settings)
    service = SchemaMigrationService(
        PostgresSchemaRepository(settings), ClickHouseSchemaRepository(clickhouse_client)
    )
    try:
        await action(service)
    finally:
        await clickhouse_client.close()


async def run_key_action[Result](
    settings: DatabaseSettings, action: Callable[[ApiKeyService], Awaitable[Result]]
) -> Result:
    """Run one ApiKeyService call on a fresh Postgres pool, then close the pool."""
    postgres_engine = create_postgres_engine(settings)
    sessionmaker = async_sessionmaker(postgres_engine, expire_on_commit=False)
    service = ApiKeyService(TenantRepository(sessionmaker), ApiKeyRepository(sessionmaker))
    try:
        return await action(service)
    finally:
        await postgres_engine.dispose()


def key_status(record: ApiKeyRecord) -> str:
    """ "revoked", "expired" or "active", for the key list."""
    if record.revoked_at is not None:
        return "revoked"
    if record.expires_at is not None and record.expires_at <= datetime.now(UTC):
        return "expired"
    return "active"


def format_key_line(record: ApiKeyRecord) -> str:
    """One line of `list-keys` output. Never includes the key or its hash."""
    expires = record.expires_at.isoformat() if record.expires_at else "never"
    return (
        f"{record.id}  {record.key_type:<6}  ...{record.last_four}  {key_status(record):<7}  "
        f"created {record.created_at.isoformat()}  expires {expires}  "
        f"project {record.project_id or '-'}  scopes {','.join(record.scopes) or '-'}"
    )


def run_migrate(settings: DatabaseSettings, args: argparse.Namespace) -> None:
    """`migrate` command."""
    asyncio.run(run_schema_action(settings, SchemaMigrationService.upgrade))


def run_rollback_postgres(settings: DatabaseSettings, args: argparse.Namespace) -> None:
    """`rollback-postgres` command."""
    asyncio.run(run_schema_action(settings, SchemaMigrationService.rollback_postgres))


def run_rollback_clickhouse(settings: DatabaseSettings, args: argparse.Namespace) -> None:
    """`rollback-clickhouse` command."""
    asyncio.run(run_schema_action(settings, SchemaMigrationService.rollback_clickhouse))


def run_create_data_key(settings: DatabaseSettings, args: argparse.Namespace) -> None:
    """`create-data-key` command. The raw key is shown once, here, and never logged."""
    created = asyncio.run(
        run_key_action(
            settings,
            lambda service: service.create_data_key(
                args.org, args.client, args.project, args.environment
            ),
        )
    )
    sys.stdout.write(created.raw_key + "\n")


def run_create_admin_key(settings: DatabaseSettings, args: argparse.Namespace) -> None:
    """`create-admin-key` command. The raw key is shown once, here, and never logged."""
    scopes = tuple(Scope(scope) for scope in args.scope)
    created = asyncio.run(
        run_key_action(
            settings,
            lambda service: service.create_admin_key(args.org, scopes, args.expires_in_days),
        )
    )
    sys.stdout.write(created.raw_key + "\n")


def run_list_keys(settings: DatabaseSettings, args: argparse.Namespace) -> None:
    """`list-keys` command: every key of an organization, newest first."""
    records = asyncio.run(run_key_action(settings, lambda service: service.list_keys(args.org)))
    for record in records:
        sys.stdout.write(format_key_line(record) + "\n")


def run_revoke_key(settings: DatabaseSettings, args: argparse.Namespace) -> None:
    """`revoke-key` command. The key stops working on its next request."""
    asyncio.run(run_key_action(settings, lambda service: service.revoke_key(args.org, args.key_id)))


async def run_reset_password(settings: DatabaseSettings, email: str, password: str) -> None:
    """Set a user's password through AuthService on a fresh Postgres pool, then close the pool."""
    postgres_engine = create_postgres_engine(settings)
    sessionmaker = async_sessionmaker(postgres_engine, expire_on_commit=False)
    service = AuthService(UserRepository(sessionmaker), SessionRepository(sessionmaker))
    try:
        await service.reset_password(email, password)
    finally:
        await postgres_engine.dispose()


def run_reset_password_command(settings: DatabaseSettings, args: argparse.Namespace) -> None:
    """`reset-password` command. Asks for the new password twice; it is never echoed or logged."""
    password = getpass.getpass("New password: ")
    if password != getpass.getpass("Repeat it: "):
        sys.exit("The two passwords differ. Nothing changed.")
    asyncio.run(run_reset_password(settings, args.email, password))
    sys.stdout.write("Password changed. The user's sessions were signed out.\n")


def build_parser() -> argparse.ArgumentParser:
    """Define the commands, their options and the function each one runs."""
    parser = argparse.ArgumentParser(prog="python -m spanport_server.cli")
    commands = parser.add_subparsers(required=True)
    commands.add_parser(
        "migrate", help="apply pending Postgres and ClickHouse migrations"
    ).set_defaults(run=run_migrate)
    commands.add_parser(
        "rollback-postgres", help="revert the latest Postgres migration"
    ).set_defaults(run=run_rollback_postgres)
    commands.add_parser(
        "rollback-clickhouse", help="revert the latest ClickHouse migration"
    ).set_defaults(run=run_rollback_clickhouse)
    create = commands.add_parser("create-data-key", help="create a data key; prints it once")
    create.set_defaults(run=run_create_data_key)
    for option in ("--org", "--client", "--project", "--environment"):
        create.add_argument(option, required=True)
    admin = commands.add_parser("create-admin-key", help="create an admin key; prints it once")
    admin.set_defaults(run=run_create_admin_key)
    admin.add_argument("--org", required=True)
    admin.add_argument("--scope", action="append", required=True, choices=[s.value for s in Scope])
    admin.add_argument("--expires-in-days", type=int, default=MAX_ADMIN_KEY_DAYS)
    listing = commands.add_parser("list-keys", help="list an organization's keys")
    listing.set_defaults(run=run_list_keys)
    listing.add_argument("--org", required=True)
    revoke = commands.add_parser("revoke-key", help="revoke a key by its id (see list-keys)")
    revoke.set_defaults(run=run_revoke_key)
    revoke.add_argument("--org", required=True)
    revoke.add_argument("--key-id", required=True, type=uuid.UUID)
    reset = commands.add_parser("reset-password", help="set a user's password (asks for it)")
    reset.set_defaults(run=run_reset_password_command)
    reset.add_argument("--email", required=True)
    return parser


def main(argv: list[str] | None = None) -> None:
    """Parse the command line and run the command.

    Raises:
        SystemExit: A setting or an argument is invalid.
    """
    args = build_parser().parse_args(argv)
    settings = load_settings(DatabaseSettings)
    logging.config.dictConfig(build_logging_config(settings.log_level, CLI_LOG_STREAM))
    try:
        args.run(settings, args)
    except SpanportError as error:
        sys.exit(f"{error.code}: {error.detail}")


if __name__ == "__main__":
    main()
