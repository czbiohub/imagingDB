import json
import jsonschema


CREDENTIALS_SCHEMA = {
    "type" : "object",
    "properties" : {
        "drivername": {"type": "string"},
        "username": {"type": "string"},
        "password": {"type": "string"},
        "host": {"type": "string"},
        "port": {"type": "number"},
        "dbname": {"type": "string"},
    },
}


def read_json_file(json_filename, schema_name=None):
    """
    Read  JSON file and validate schema from predefined
    schemas available here.

    Note: I might do something useful with the exeptions down the line,
    maybe exit gracefully or at least log them instead of just raising them

    :param str json_filename: json file name
    :param str schema_name: if specified, the json will be validated against
        this schema if it is defined in this file
    :return: json credentials: credentials JSON object
    :raise FileNotFoundError: if file can't be read
    :raise JSONDecodeError: if file is not in json format
    :raise ValidationError: if json schema is invalid
    """
    # Load json file
    try:
        with open(json_filename, "r") as read_file:
            try:
                json_object = json.load(read_file)
            except json.JSONDecodeError as jsone:
                print(jsone)
                raise
    except FileNotFoundError as filee:
        print(filee)
        raise
    # Validate schema
    if schema_name is not None:
        # Assign schema from schema name
        try:
            schema_object = globals()[schema_name]
        except KeyError as keye:
            print(keye)
            raise
        # Validate json schema
        try:
            jsonschema.validate(json_object, schema_object)
        except jsonschema.exceptions.ValidationError as e:
            print(str(e))
            raise

    return json_object
