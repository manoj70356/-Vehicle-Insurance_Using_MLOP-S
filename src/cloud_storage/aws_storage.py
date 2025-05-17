import boto3
from src.configuration.aws_connection import S3Client
from io import StringIO
from typing import Union, List
import os
import sys
from src.logger import logging
from mypy_boto3_s3.service_resource import Bucket
from src.exception import MyException
from botocore.exceptions import ClientError
from pandas import DataFrame, read_csv
import pickle

class S3Client:
    """
    A simple wrapper to initialize boto3 S3 resource and client.
    """
    def __init__(self):
        self.s3_resource = boto3.resource('s3')
        self.s3_client = boto3.client('s3')


class SimpleStorageService:
    """
    A class for interacting with AWS S3 storage, providing methods for file management, 
    data uploads, and data retrieval in S3 buckets.
    """

    def __init__(self):
        """
        Initializes the SimpleStorageService instance with S3 resource and client
        from the S3Client class.
        """
        s3_client = S3Client()
        # Verify that s3_resource is properly initialized
        if s3_client.s3_resource is None:
            raise MyException("S3 resource is not initialized. Check S3Client implementation.", sys)
        self.s3_resource = s3_client.s3_resource
        self.s3_client = s3_client.s3_client

    def s3_key_path_available(self, bucket_name, s3_key) -> bool:
        """
        Checks if a specified S3 key path (file path) is available in the specified bucket.
        """
        try:
            bucket = self.get_bucket(bucket_name)
            file_objects = [file_object for file_object in bucket.objects.filter(Prefix=s3_key)]
            return len(file_objects) > 0
        except Exception as e:
            raise MyException(e, sys)

    @staticmethod
    def read_object(object_name: Union[object, str], decode: bool = True, make_readable: bool = False) -> Union[StringIO, str]:
        """
        Reads the specified S3 object with optional decoding and formatting.
        """
        try:
            # If object_name is a boto3 Object, fetch its body
            if hasattr(object_name, 'get'):
                obj_body = object_name.get()["Body"].read()
            elif isinstance(object_name, str):
                # If object_name is a string, treat it as a filename or URL? Usually, pass a boto3 Object
                raise MyException("Invalid argument: object_name should be a boto3 Object", sys)
            else:
                raise MyException("Invalid argument type for read_object", sys)

            content_bytes = obj_body
            content_str = content_bytes.decode() if decode else content_bytes
            if make_readable:
                return StringIO(content_str)
            return content_str
        except Exception as e:
            raise MyException(e, sys) from e

    def get_bucket(self, bucket_name: str) -> Bucket:
        """
        Retrieves the S3 bucket object based on the provided bucket name.
        """
        logging.info("Entered the get_bucket method of SimpleStorageService class")
        try:
            bucket = self.s3_resource.Bucket(bucket_name)
            logging.info("Exited the get_bucket method of SimpleStorageService class")
            return bucket
        except Exception as e:
            raise MyException(e, sys) from e

    def get_file_object(self, filename: str, bucket_name: str) -> Union[List, object]:
        """
        Retrieves the file object(s) from the specified bucket based on the filename.
        """
        logging.info("Entered the get_file_object method of SimpleStorageService class")
        try:
            bucket = self.get_bucket(bucket_name)
            file_objects = [file_object for file_object in bucket.objects.filter(Prefix=filename)]
            if len(file_objects) == 1:
                return file_objects[0]
            return file_objects
        except Exception as e:
            raise MyException(e, sys) from e

    def load_model(self, model_name: str, bucket_name: str, model_dir: str = None) -> object:
        """
        Loads a serialized model from the specified S3 bucket.
        """
        try:
            model_file = f"{model_dir}/{model_name}" if model_dir else model_name
            file_object = self.get_file_object(model_file, bucket_name)
            model_obj_bytes = self.read_object(file_object, decode=False)
            model = pickle.loads(model_obj_bytes)
            logging.info("Production model loaded from S3 bucket.")
            return model
        except Exception as e:
            raise MyException(e, sys) from e

    def create_folder(self, folder_name: str, bucket_name: str) -> None:
        """
        Creates a folder in the specified S3 bucket.
        """
        logging.info("Entered the create_folder method of SimpleStorageService class")
        try:
            # Check if folder exists by attempting to load it
            self.s3_resource.Object(bucket_name, folder_name + "/").load()
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                folder_obj = folder_name + "/"
                self.s3_client.put_object(Bucket=bucket_name, Key=folder_obj)
        logging.info("Exited the create_folder method of SimpleStorageService class")

    def upload_file(self, from_filename: str, to_filename: str, bucket_name: str, remove: bool = True):
        """
        Uploads a file to S3.
        """
        logging.info("Entered the upload_file method of SimpleStorageService class")
        try:
            if self.s3_resource is None:
                raise MyException("s3_resource is not initialized", sys)
            logging.info(f"Uploading {from_filename} to {to_filename} in {bucket_name}")
            self.s3_resource.meta.client.upload_file(from_filename, bucket_name, to_filename)
            if remove:
                os.remove(from_filename)
                logging.info(f"Removed local file {from_filename} after upload")
            logging.info("Exited the upload_file method of SimpleStorageService class")
        except Exception as e:
            raise MyException(e, sys) from e

    def upload_df_as_csv(self, data_frame: DataFrame, local_filename: str, bucket_filename: str, bucket_name: str) -> None:
        """
        Uploads a DataFrame as a CSV file to S3.
        """
        logging.info("Entered the upload_df_as_csv method of SimpleStorageService class")
        try:
            # Save DataFrame locally
            data_frame.to_csv(local_filename, index=False, header=True)
            # Upload to S3
            self.upload_file(local_filename, bucket_filename, bucket_name)
        except Exception as e:
            raise MyException(e, sys) from e

    def get_df_from_object(self, object_: object) -> DataFrame:
        """
        Converts an S3 object to a pandas DataFrame.
        """
        logging.info("Entered the get_df_from_object method of SimpleStorageService class")
        try:
            content = self.read_object(object_, make_readable=True)
            df = read_csv(content, na_values="na")
            logging.info("Exited the get_df_from_object method of SimpleStorageService class")
            return df
        except Exception as e:
            raise MyException(e, sys) from e

    def read_csv(self, filename: str, bucket_name: str) -> DataFrame:
        """
        Reads a CSV file from S3 and returns a pandas DataFrame.
        """
        logging.info("Entered the read_csv method of SimpleStorageService class")
        try:
            csv_obj = self.get_file_object(filename, bucket_name)
            df = self.get_df_from_object(csv_obj)
            logging.info("Exited the read_csv method of SimpleStorageService class")
            return df
        except Exception as e:
            raise MyException(e, sys) from e