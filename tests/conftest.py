import pytest

from backend import db


@pytest.fixture
def conn():
    connection = db.get_connection(db_path=":memory:")
    db.init_db(connection)
    yield connection
    connection.close()
