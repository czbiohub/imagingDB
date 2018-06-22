# Imaging Database
===================

This is a pipeline for interacting with images and their metadata using the imaging database.
Current development focus is uploading images and metadata to the database,
support for queries and downloads will be added as I go along.
So far I only have some initial json validation and database connection stuff...

## Getting Started

These instructions will get the project up and running on your local machine.

```
Command line
```

### Prerequisites

Python requirements can be found in the file requirements.txt

####  Data lives in the AWS S3 bucket czbiohub-imaging
You will need to have a biohub AWS account and to configure your AWS CLI with your access key ID and secret key using the command
```
aws configure
```
#### The database lives in an AWS PostreSQL RDS
You will need to be added as a user there too, and add your username and password in a json file
for database access (see db_credentials.json)

Please contact jenny.folkesson@czbiohub.org if you want to be added as a user.

### Installing

A step by step series of examples that tell you how to get a development env running

```
Command line
```

## Running the tests

Explain what these tests test and why

```
Give an example
```

## Deployment

No.

## Built With

* [SQLAlchemy](https://www.sqlalchemy.org/) - Python SQL Toolkit and Object Relational Mapper
* [Boto 3](https://boto3.readthedocs.io/en/latest/) - AWS SDK for Python

## Authors

* **Jenny Folkesson** - *Initial work* - jenny.folkesson@czbiohub.org [GitHub](https://github.com/jennyfolkesson)

## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details

## Acknowledgments
