"""Conquest API Python Wrapper

This module allows the user to interact with the Conquest API using Python.

Requirements:
    Python 3.x
    requests
    Conquest API

Installation:
    The module can be installed with pip using the below command.
    Consider installing in to a virtualenv.
    pip install git+https://github.com/nwduncan/conquest_api.git

To do:
    Parse error CSV output correctly so that is doesn't split at commas in "strings".
    Implement further API functionality

Author: Nathan Duncan
Version: 0.9

"""

import urllib.parse
import json
import csv
import time
import os
import requests
from datetime import datetime as dt
from datetime import timedelta
from typing import NoReturn, Union

# suppress the insecure request warnings
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# defaults
verify = False
output_path = os.environ['TEMP']

# classes
class Token(object):
    def __init__(self, api_url:str, username:str, password:str, connection:str) -> None:
        """Token handling class.

        This class generates an access token which is needed to interact with the API.
        A token is not generated on an instance initialisation, but rather as needed
        by other classes when attempting to interact with the API. The instance will
        attempt to refresh the token if it expires.

        Args:
            api_url (str): URL of the Conquest API. E.g. 'https://api.domain.gov.au'.
            username (str): Username to be used for generating a token.
            password (str): Password to be used for generating a token.
            connection (str): Name of the Conquest connection to generate a token for.

        """
        self.api_url = api_url
        self.token_url = api_url+"api/token"
        self.connection = connection
        self.username = username
        self.password = password
        self.expire = None #: datetime object pointing to time of token expiration
        self.token = None #: str representing the token
        self.refresh_token = None #: str representing the refresh token code

    def get_token(self) -> str:
        """Generate token method.

        This method returns a token when requested. If no token has been previously
        generated it will attempt to create one with the provided credentials.
        If a token has already been created and is still valid, it will return the
        previously created token. If a token is unable to be generated, a ValueError
        is raised which includes the error messages from the server.

        """
        # if no token exists, generate it
        if self.token is None:
            headers = { "X-ConnectionName": self.connection,
                        "Accept": "application/json" }
            payload = { "grant_type": "password",
                        "username": self.username,
                        "password": self.password }
            response = requests.post(self.token_url, data=urllib.parse.urlencode(payload), headers=headers, verify=verify)
            response = json.loads(response.text)
            try:
                self.token = response["access_token"]
                self.refresh_token = response["refresh_token"]
                self.expire = dt.now()+timedelta(seconds=response["expires_in"])
                return self.token
            # error is raised if token generation was unsuccesful
            except KeyError:
                raise ValueError(f"Unable to generate access token - {response['error']}: {response['error_description']}")
        # if the token is still valid, return it
        elif (dt.now() - timedelta(seconds=180)) < self.expire:
            return self.token
        # otherwise generate a new token using the refresh token
        else:
            self.refresh()
            return self.token

    def refresh(self) -> NoReturn:
        """The refresh method refreshes the token using the refresh_token code.

        """
        headers = { "X-ConnectionName": self.connection,
                    "Accept": "application/json" }
        payload = { "grant_type": "refresh_token",
                    "refresh_token": self.refresh_token }
        response = requests.post(self.token_url, data=urllib.parse.urlencode(payload), headers=headers, verify=verify)
        response = json.loads(response.text)
        self.token = response["access_token"]
        self.refresh_token = response["refresh_token"]
        self.expire = dt.now()+timedelta(seconds=response["expires_in"])


class Import(object):
    def __init__(self, token:Token) -> None:
        """Import class used to import files in to Conquest.

        An Import class instance is initialised using a Token object. Files can
        then be imported using the 'add' method by specifying the file and
        import type as arguments.

        Args:
            token (Token): Token object

        Attributes:
            import_items (list): A list containing valid import types. The
                import_type argument in the add method is checked against this list.

        Notes:
            The 'add' method returns a dict built using the 'result' method.
            This object can be used to test the success of the import attempt
            and access any error messages and/or error CSV files.

        Examples:
            See https://github.com/nwduncan/conquest_api.git for examples on using
            this class.

        """
        self.token = token
        self.import_types = ["Action", "Asset", "Defect", "Request", "AssetInspection", "RiskEvent", "LogBook"]

    def add(self, filename:str, import_type:str) -> dict:
        """A method for importing files in to Conquest.

        This method returns a dict containing a boolean representing the success
        of the import which can be tested to determine whether the import process
        was successful. (See notes on 'result' method for details about the return
        object).

        Args:
            filename (str): Path fo the file to be imported in to Conquest
            import_type (str): Type of import to be attempted. See self.import_types
                or the API documentation for a list of valid import types.

        Returns:
            A dict containing the batch id (str), attempt successfulness (bool),
            error messages (str), and error files generated (str).

        """
        # make sure we have a valid import type
        if import_type in self.import_types:
            with open(filename, "rb") as open_file:
                url = self.token.api_url+"api/import/add/"+str(import_type)
                headers = { "X-ConnectionName": self.token.connection,
                            "Authorization": "bearer "+self.token.get_token() }
                files = { "files": open_file }
                response = requests.post(url, files=files, headers=headers, verify=verify)
                batch = json.loads(response.content.decode("utf-8"))
                while True:
                    status = self.get_state(batch)
                    # wait
                    if status["Status"] == "Processing":
                        time.sleep(0.1)
                    # success
                    elif status["Status"] == "Completed":
                        return self.result(batch, True)
                    # error
                    else:
                        if "Output to CSV" in status["Error"]:
                            error_csv = self.output_to_csv(batch, filename)
                        else:
                            error_csv = None
                        return self.result(batch, False, status["Error"], error_csv)

        else:
            return self.result(None, False, f"Import type of {import_type} is not a valid option.", None)

    def get_state(self, batch:str) -> dict:
        """A method for getting the state of a batch.

        This is used internally by the 'add' method to check the status of a
        process.

        Args:
            batch (str): Id of the batch to check.

        Returns:
            A response from the server (dict).

        """
        url = self.token.api_url+r"api/import/state/"+batch
        headers = { "X-ConnectionName": self.token.connection,
                    "Authorization": "bearer "+self.token.get_token() }
        response = requests.get(url, headers=headers, verify=verify)
        response = json.loads(response.text)
        return response

    def output_to_csv(self, batch:str, filename:str) -> str:
        """The method used to 'Output to CSV' when an error is found during an import.

        Args:
            batch (str): Batch id of the item with errors to output.
            filename (str): Filename of the file which attempted an import.

        Returns:
            Filename (str) of the error CSV.

        """
        url = self.token.api_url+r"/api/import/error_csv/"+batch
        headers = { "X-ConnectionName": self.token.connection,
                    "Authorization": "bearer "+self.token.get_token() }
        response = requests.get(url, headers=headers, verify=verify)
        name, ext = os.path.splitext(os.path.basename(filename))
        out_filename = os.path.join(output_path, name+"_ERROR"+ext)
        with open(out_filename, "w", newline="") as open_file:
            err_wr = csv.writer(open_file)
            for row in response.content.decode("utf-8").split("\r\n"):
                err_wr.writerow(row.split(","))
        return out_filename

    def result(self, batch:Union[str, None], success:bool, error_msg:Union[str, None]=None, error_file:Union[str, None]=None) -> dict:
        """Returns a dict containing details about an import process.

        After an import process is attempted a dict created by this
        class is returned. The dict contains details which can be used to guide
        further processes, uncluding the batch id used to start an import, any
        errors which were found, and a path to any error files generated. This
        method is used internally only.

        Args:
            batch (str or None): Batch id (None indicates invalid import type)
            success (bool): Boolean indicating whether an 'import' process was
                successful
            error_msg (str or None, optional): Any error messages received from
            the server are passed to this argument.
            error_file (str or None, optional): If an error file has been generated
                the path is passed to this argument.

        Returns:
            Dict.

        """
        result = dict(batch=batch, success=success, error_msg=error_msg, error_file=error_file)
        return result


class Asset(object):
    def __init__(self, token:Token) -> None:
        """Asset class for accessing data relating to assets.

        Once initialised this class can be used to find basic and detailed information
        about assets, and for finding assets based on unique field values.

        Args:
            token (Token): Token object.

        Notes:
            The objects returned from all methods are in the same format of a dict
            containing dict objects representing each asset queried. If an asset
            is not found (i.e. no asset exists with that AssetID) then the return
            object will not contain any reference to that asset.

        Examples:
            See https://github.com/nwduncan/conquest_api.git for examples on using
            this class.

        """
        self.token = token

    def get_detailed(self, assets:Union[str, int, list]) -> dict:
        """Method which returns all attributes for an asset/list of assets.

        Args:
            assets (str or int or list): Assets for which data will be returned.

        Returns:
            Dict containing a dict object for each asset queried.

        """
        assets = [assets] if type(assets) != list else assets
        asset_data = {}
        for asset in assets:
            url = self.token.api_url+r"/api/Asset/"+str(asset)
            headers = { "X-ConnectionName": self.token.connection,
                        "Authorization": "bearer "+self.token.get_token() }
            response = requests.get(url, headers=headers, verify=verify)
            response = json.loads(response.text)
            if "ErrorType" not in response:
                asset_data[asset] = response
        return asset_data

    def get_basic(self, assets:Union[str, int, list]) -> dict:
        """Method which returns basic attributes for an asset/list of assets.

        Args:
            assets (str or int or list): Assets for which data will be returned.

        Returns:
            Dict containing a dict object for each asset queried.

        """
        assets = [assets] if type(assets) != list else assets
        asset_data = {}
        for asset in assets:
            url = self.token.api_url+r"/api/Asset/basic/"+str(asset)
            headers = { "X-ConnectionName": self.token.connection,
                        "Authorization": "bearer "+self.token.get_token() }
            response = requests.get(url, headers=headers, verify=verify)
            response = json.loads(response.text)
            if "ErrorType" not in response:
                asset_data[asset] = response
        return asset_data

    def find_by_field(self, field:str, value:Union[str, int]) -> dict:
        """Method which returns all attributes for an asset based on a field search.

        Note:
            This method only works if a unique match is found. Any searches that
            find more than one asset matching the criterion will return an empty
            dict.

        Args:
            field (str): name of the field to search.
            value: (str) value to earch the field arg for.

        Returns:
            Dict containing details of the asset.

        """
        value = str(value)
        url = self.token.api_url+r"/api/asset/find_by_field"
        headers = { "X-ConnectionName": self.token.connection,
                    "Authorization": "bearer "+self.token.get_token(),
                    "Content-Type": "application/x-www-form-urlencoded" }
        payload = { "Field": str(field),
                    "Value": str(value) }
        response = requests.post(url, data=urllib.parse.urlencode(payload), headers=headers, verify=verify)
        asset_data = json.loads(response.text)
        if "ErrorType" in asset_data:
            asset_data = {}
        return asset_data


class Action(object):
    def __init__(self, token:Token) -> None:
        """Action class for accessing data relating to actions.

        Once initialised this class can be used to retrieve action data, find actions
        based on unique field values, and delete actions. During a get, if an action
        is not found (i.e. no action exists with that ActionID) then the return
        object will not contain any reference to that action.

        Args:
            token (Token): Token object.

        Examples:
            See https://github.com/nwduncan/conquest_api.git for examples on using
            this class.

        """
        self.token = token

    def get_detailed(self, actions:Union[str, list]) -> dict:
        """Method which returns all attributes for an asset/list of actions.

        Args:
            actions (str or int or list): Actions for which data will be returned.

        Returns:
            Dict containing a dict object for each action queried.

        """
        actions = [actions] if type(actions) != list else actions
        action_data = {}
        for action in actions:
            url = self.token.api_url+r"/api/Action/"+str(action)
            headers = { "X-ConnectionName": self.token.connection,
                        "Authorization": "bearer "+self.token.get_token() }
            response = requests.get(url, headers=headers, verify=verify)
            response = json.loads(response.text)
            if "ErrorType" not in response:
                action_data[action] = response
        return action_data

    def find_by_field(self, field:str, value:Union[str, int]) -> dict:
        """Method which returns all attributes for an action based on a field search.

        Note:
            This method only works if a unique match is found. Any searches that
            find more than one action matching the criterion will return an empty
            dict.

        Args:
            field (str): name of the field to search.
            value: (str) value to earch the field arg for.

        Returns:
            Dict containing details of the action.

        """
        value = str(value)
        url = self.token.api_url+r"/api/action/find_by_field"
        headers = { "X-ConnectionName": self.token.connection,
                    "Authorization": "bearer "+self.token.get_token(),
                    "Content-Type": "application/x-www-form-urlencoded" }
        payload = { "Field": str(field),
                    "Value": str(value) }
        response = requests.post(url, data=urllib.parse.urlencode(payload), headers=headers, verify=verify)
        action_data = json.loads(response.text)
        if "ErrorType" in action_data:
            action_data = {}
        return action_data

    def delete(self, actions:Union[str, list]) -> dict:
        """Method which deletes an action or list of actions by their action id.



        Args:
            actions (str or int or list): Actions to delete.

        Returns:
            Dict with the action ids as keys, and the server response as values.
            These are formatted as dicts which contain any errors - an empty
            dict corresponds with a successful deletion.

        """
        actions = [actions] if type(actions) != list else actions
        deleted = {}
        for action in actions:
            url = self.token.api_url+r"/api/Action/"+str(action)
            headers = { "X-ConnectionName": self.token.connection,
                        "Authorization": "bearer "+self.token.get_token() }
            response = requests.delete(url, headers=headers, verify=verify)
            if response.text != '':
                response = json.loads(response.text)
            else:
                response = {}
            deleted[action] = response
        return deleted


class System(object):
    def __init__(self, token:Token) -> None:
        """System class for accessing data relating to the system.

        Args:
            token (Token): Token object.

        Examples:
            See https://github.com/nwduncan/conquest_api.git for examples on using
            this class.

        """
        self.token = token

    def connections(self) -> list:
        """Method which returns a list of Conquest connections

        """
        url = self.token.api_url+r"/api/system/connections"
        headers = { "X-ConnectionName": self.token.connection,
                    "Authorization": "bearer "+self.token.get_token() }
        response = requests.get(url, headers=headers, verify=verify)
        response =  json.loads(response.text)
        return response

    def version(self) -> dict:
        """Method which returns a dict containing version details.

        """
        url = self.token.api_url+r"/api/system/version"
        headers = { "X-ConnectionName": self.token.connection,
                    "Authorization": "bearer "+self.token.get_token() }
        response = requests.get(url, headers=headers, verify=verify)
        response =  json.loads(response.text)
        return response

    def whoami(self) -> str:
        """Method which returns the a username as a string.

        """
        url = self.token.api_url+r"/api/system/whoami"
        headers = { "X-ConnectionName": self.token.connection,
                    "Authorization": "bearer "+self.token.get_token() }
        response = requests.get(url, headers=headers, verify=verify)
        response =  json.loads(response.text)
        return response
