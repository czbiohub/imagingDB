# Imaging Database

This is a pipeline for interacting with images and their metadata using the imaging database.
Each image is assumed to be a dataset which has a unique identifier associated with
it of the form 

\<ID>-YYYY-MM-DD-HH-MM-SS-\<SSSS>

where ID is a project id (e.g. ISP or ML), followed by a timestamp, and the last
section is a four digit serial number.

Below is a visualization of the database schema, generated using [eralchemy](https://github.com/Alexis-benoist/eralchemy). The arch on the top of the data_set table should connect parent_id with id, and it also doesn't show foreign keys clearly, other than that it gives an overview of schema. 

![Database schema](db_schema.png?raw=true "Title")


## Getting Started

There are two main CLIs, data_uploader and data_downloader. During
data upload, you can choose between doing 'file' or 'frames' upload type.
File will just write the existing file as is on S3, whereas 'frames'' will
attempt to read the file, separate frames from metadata and upload each
frame individually as a png, and write both global and frame level metadata to 
the database. Files will be written to the 'raw_files' folder
in the S3 buckets, and frames will be written to 'raw_frames'.

The data uploader takes:
 * a csv file containing file information, please see the
 _files_for_upload.csv_ in this repository for required fields and example values.
* a json file containing database login credentials (see db_credentials.json)

If you want to validate metadata for each frame, you can specify a JSON schema file in the
_meta_schema_ field of the csv. This metadata will be evaluated for each
frame of the file. See metadata_schema.json for an example schema.

```buildoutcfg
python imaging_db/cli/data_uploader.py --csv files_for_upload.csv --login db_credentials.json
```

The data_downloader CLI takes three command line inputs: 
* a JSON file with DB login credentials
* a destination folder where the data will be downloaded
* a unique dataset identifier

```buildoutcfg
python imaging_db/cli/data_downloader.py --id ID-2018-04-05-00-00-00-0001 --dest /My/local/folder --login db_credentials.json
```

In addition to the CLIs, you can see examples on how to query data in the Jupyter
notebook in the notebook folder.

### Prerequisites

Python requirements can be found in the file requirements.txt

####  Data lives in the AWS S3 bucket czbiohub-imaging
You will need to have a biohub AWS account and to configure your AWS CLI with your access key ID and secret key using the command
```
aws configure
```
#### The database lives in an AWS PostgreSQL RDS
You will need to be added as a user there too, and add your username, password and the host in a json file
for database access (see db_credentials.json)

Please contact Jenny on Slack (or jenny.folkesson@czbiohub.org) if you want to be added as a user.

## Running the tests

There's currently some patchy unit test coverage which I intend to expand as
the repository opens up to more users. Tests live in the same directory as
the files they're testing with an appended '_tests' at the end of the file name.
An example test run:

```buildoutcfg
nosetests imaging_db/filestorage/s3_storage_tests.py
```

## Built With

* [SQLAlchemy](https://www.sqlalchemy.org/) - Python SQL Toolkit and Object Relational Mapper
* [Boto 3](https://boto3.readthedocs.io/en/latest/) - AWS SDK for Python

## Authors

* **Jenny Folkesson** - *Initial work* - jenny.folkesson@czbiohub.org [GitHub](https://github.com/jennyfolkesson)

## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details
