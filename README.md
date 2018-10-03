# Imaging Database

This is a pipeline for interacting with images and their metadata using the imaging database.
Each image is assumed to be a dataset which has a unique identifier associated with
it of the form 

\<ID>-YYYY-MM-DD-HH-MM-SS-\<XXXX>

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

The data_downloader CLI takes the following command line inputs: 
* _login:_ a JSON file with DB login credentials
* _dest:_ a destination folder where the data will be downloaded
* _id:_ a unique dataset identifier
* _metadata:_ (default True) For files split to frames only. Writes metadata
            global metadata in json, local for each frame in csv
* _download:_ (default True) For Frames, there's the option of only retrieving the metadata files  

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

## Running imagingDB on a server

The recommended use is running imagingDB inside a docker container. 
Build the supplied Dockerfile.imagingDB, e.g.:
```buildoutcfg
docker build -t imaging_db:python37 -f Dockerfile.imagingDB .
```
Then you will have all the requirements necessary installed. Additionally,
you will need you AWS keys inside your Docker container. If you've stored your
key and secret key in ~/.aws/credentials you can get them as environment variable by running:
```buildoutcfg
AWS_ACCESS_KEY_ID=$(aws --profile default configure get aws_access_key_id)
AWS_SECRET_ACCESS_KEY=$(aws --profile default configure get aws_secret_access_key)
```
Then you can set these variables when you start your Docker container:
```buildoutcfg
docker run -it -p <your port>:8888 -v <your data dir>:/data -v <your repo>:/imagingDB -e AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID -e AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY imaging_db:python36  bash 
```
Note: exposing your environment variables like this is not the safest way to 
set up AWS credentials. Future work will include a safer way to do this.

If you want to launch a Jupyter notebook inside your container, you can do so with the following command:
```buildoutcfg
jupyter notebook --ip=0.0.0.0 --port=8888 --allow-root --no-browser
```
Then you can access your notebooks in your browser at (if you're on fry):
```buildoutcfg
http://fry:<whatever port you mapped to when starting up docker container>
```
You will need to copy/paste the token generated in your Docker container. 

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
