from __future__ import with_statement
from alembic import context
import os
from sqlalchemy import engine_from_config, pool
from logging.config import fileConfig

import imaging_db.database.db_operations as db_ops
import imaging_db.metadata.json_operations as json_ops


# Edit this depending on where your database credential file is stored
# This assumes it's stored in dir above imagingDB
dir_name = os.path.abspath(os.path.join('..'))
DB_CREDENTIALS_PATH = os.path.join(dir_name, 'db_credentials.json')


# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Overwrite the ini-file sqlalchemy.url path
credentials_json = json_ops.read_json_file(
    json_filename=DB_CREDENTIALS_PATH,
    schema_name="CREDENTIALS_SCHEMA")

config.set_main_option(
    'sqlalchemy.url',
    db_ops.json_to_uri(credentials_json=credentials_json))

print("Using url:", config.get_main_option('sqlalchemy.url'))

# Add model metadata object
target_metadata = db_ops.Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline():
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url, target_metadata=target_metadata, literal_binds=True)

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix='sqlalchemy.',
        poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
