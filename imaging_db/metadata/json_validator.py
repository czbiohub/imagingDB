import json
import jsonschema


CREDENTIALS_SCHEMA = {
    "type": "object",
    "properties": {
        "drivername": {"type": "string"},
        "username": {"type": "string"},
        "password": {"type": "string"},
        "host": {"type": "string"},
        "port": {"type": "integer"},
        "dbname": {"type": "string"},
    },
    "required": ["drivername", "username", "password", "host", "port", "dbname"],
}

# More Micromanager metadata properties should be added
# Ask Kevin which ones are required
MICROMETA_SCHEMA = {
    "type": "object",
    "properties": {
        "ChannelIndex": {"type": "integer"},
        "Slice": {"type": "integer"},
        "FrameIndex": {"type": "integer"},
        "Exposure-ms": {"type": "number"},
    },
    "required": ["ChannelIndex", "Slice", "FrameIndex"]
}


def validate_schema(json_object, schema):
    """
    Validate JSON object against predefined schema.

    :param json json_object:
    :param str/dict schema: predefined schema or
        name of schema defined in this file
        current options are:
        CREDENTIALS_SCHEMA: database credentials (and AWS in future?)
        MICROMETA_SCHEMA: MicroManager metadata from ome.tif files
    :raise ValidationError: if validation fails
    """
    # Assign schema from schema name
    if isinstance(schema, dict):
        schema_object = schema
    elif isinstance(schema, str):
        try:
            schema_object = globals()[schema]
        except KeyError as e:
            print(e)
            raise
    else:
        raise AssertionError("Schema neither string or dict")

    # Validate json schema
    try:
        jsonschema.validate(json_object, schema_object)
    except jsonschema.exceptions.ValidationError as e:
        print(e)
        raise


def read_json_file(json_filename, schema_name=None):
    """
    Read  JSON file and validate schema

    Note: I might do something useful with the exeptions down the line,
    maybe exit gracefully or at least log them instead of just raising them

    :param str json_filename: json file name
    :param str schema_name: if specified, the json will be validated against
        this schema if it is defined in this file
    :param dict schema:
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
    except FileNotFoundError as e:
        print(e)
        raise
    # Validate schema
    if schema_name is not None:
        validate_schema(json_object, schema_name)

    return json_object


def write_json_file(meta_dict, json_filename):
    """
    Writes dict to json file
    TODO: Not validating anything but belongs with jsons... change file name?

    :param dict meta_dict: Dict to be saved as json
    :param json_filename: json file name with full path
    """
    json_dump = json.dumps(meta_dict)
    with open(json_filename, "w") as write_file:
        write_file.write(json_dump)


def get_metadata_from_tags(frame, meta_schema, validate=True):
    """
    Populates metadata dict based on user specified schema
    NOTE: currently only supports flat structure, should add recursion
    if schemas are more complex
    TODO: Preprocess frame to dict and make metadata extraction recursive?

    :param TiffPage frame: contains tags with metadata
    :param dict meta_schema: JSON schema for required metadata
    :param bool validate: validate generated json dict against meta_schema
    :return dict json_required: all metadata in tags specified by schema
    :return dict meta_required: required individual parameters specified
        by schema
    """
    json_required = {}
    meta_required = {}
    assert meta_schema["type"] == "object"
    for key, props in meta_schema["properties"].items():
        if props.get('type') == 'object':
            json_required[key] = frame.tags[key].value
            req_params = props.get('required', [])
            if isinstance(req_params, str):
                req_params = [req_params]
            # Collect required params like slice, frame, ...
            for req_key in req_params:
                meta_required[req_key] = json_required[key][req_key]
    # Make sure the required fields are present
    if validate:
        validate_schema(json_required, schema=meta_schema)
    return json_required, meta_required


def get_global_meta(frame, file_name):
    """
    Global meta consists of file origin and IJMetadata, because the latter
    only exists in the first frame
    :param TiffPage frame: first frame containing IJMetadata
    :param str file_name: full path to origin file
    :return dict global_json: global metadata, IJMetadata + file name
    :return list channel_names: channel names for frame metadata
    """
    global_json = {
        "file_origin": file_name,
    }
    channel_names = []
    try:
        meta_temp = frame.tags["IJMetadata"].value["Info"]
        if isinstance(meta_temp, str):
            meta_temp = json.loads(meta_temp)
        global_json["IJMetadata"] = meta_temp
        channel_names = meta_temp["ChNames"]
        if isinstance(channel_names, str):
            channel_names = [channel_names]
    except Exception as e:
        print("Can't read IJMetadata", e)

    return global_json, channel_names
