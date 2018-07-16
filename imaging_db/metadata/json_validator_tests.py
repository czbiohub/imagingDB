import json
import jsonschema
import nose.tools
import os
from testfixtures import TempDirectory

import imaging_db.metadata.json_validator as json_validator


def test_valid_json():
    with TempDirectory() as tempdir:
        valid_json = {
            "drivername": "postgres",
            "username": "user",
            "password": "pwd",
            "host": "db_host",
            "port": 666,
            "dbname": "db_name"
        }
        tempdir.write('valid_json_file.json', json.dumps(valid_json).encode())
        json_object = json_validator.read_json_file(
            os.path.join(tempdir.path, "valid_json_file.json"),
            schema_name="CREDENTIALS_SCHEMA")
        nose.tools.assert_equal(json_object, valid_json)


@nose.tools.raises(json.JSONDecodeError)
def test_not_a_json():
    with TempDirectory() as tempdir:
        invalid_json = {
            "drivername": "postgres",
            "username": "user"
        }
        # Remove last bracket
        invalid_json_str = json.dumps(invalid_json)[:-1]
        tempdir.write('invalid_json_file.json', invalid_json_str.encode())
        json_object = json_validator.read_json_file(
            os.path.join(tempdir.path, "invalid_json_file.json"))


@nose.tools.raises(jsonschema.exceptions.ValidationError)
def test_invalid_json():
    invalid_json = {
        "drivername": "postgres",
        "username": "user",
        "password": "pwd",
        "host": "db_host",
        "port": "notanumber",
        "dbname": "db_name"
    }
    json_validator.validate_schema(
        invalid_json,
        schema_name="CREDENTIALS_SCHEMA")


def test_valid_micrometa():
    micrometa_json = {
        "ChannelIndex": 4,
        "Slice": 1,
        "FrameIndex": 0,
        "Exposure-ms": 50,
        'COM1-DataBits': '8'
    }
    json_validator.validate_schema(
        micrometa_json,
        schema_name="MICROMETA_SCHEMA")


@nose.tools.raises(jsonschema.exceptions.ValidationError)
def test_invalid_micrometa():
    micrometa_json = {
        "ChannelIndex": 4,
        'COM1-DataBits': '8'
    }
    json_validator.validate_schema(
        micrometa_json,
        schema_name="MICROMETA_SCHEMA")


@nose.tools.raises(KeyError)
def test_not_a_schema():
    json_obj = {
        "drivername": "postgres",
        "username": "user"
    }
    json_validator.validate_schema(
        json_obj,
        schema_name="NOTA_SCHEMA")


@nose.tools.raises(FileNotFoundError)
def test_nonexisting_json():
    json_object = json_validator.read_json_file("not_a_json_file.json")

