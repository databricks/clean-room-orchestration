from databricks.sdk.runtime import *
from datetime import datetime
from enum import Enum
from requests.exceptions import HTTPError
from typing import List, Optional
import base64
import json
import os
import requests
import time
import urllib

class TeardownResource(Enum):
  NOTEBOOK_SERVICE_PRINCIPAL = 1
  COLLABORATOR_SHARES = 2
  WORKSPACE = 3
  METASTORE = 4

class CleanRoomRestClient:
  def __init__(self):
    self._workspace_url = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiUrl().getOrElse(None)
    self._auth_token = dbutils.secrets.get(scope="clean_room", key="token")
    self._headers = {"Authorization":"Bearer {}".format(self._auth_token), "Accept":"application/json" }

  def _get(self, url: str, **kwargs) -> requests.Response:
    return requests.get(
      url,
      headers = self._headers,
      **kwargs
    )

  def _post(self, url: str, **kwargs) -> requests.Response:
    return requests.post(
      url,
      headers = self._headers,
      **kwargs
    )

  def _delete(self, url: str, **kwargs) -> requests.Response:
    return requests.delete(
      url,
      headers = self._headers,
      **kwargs
    )

  def _get_station_url(self, clean_room: str, station_name: str) -> str:
    return self._workspace_url + f"/api/2.1/unity-catalog/clean-rooms/{urllib.parse.quote(clean_room)}/stations/{urllib.parse.quote(station_name)}"

  def _check_results(self, results) -> None:
    try:
      results.raise_for_status()
    except HTTPError as e:
      if results.text:
        raise HTTPError(f"{str(e)} Body: {results.text}")
      raise e

  """
  Imports notebook to the workstation
  """
  def importNotebook(self, path: str, content: str) -> None:
    url = self._workspace_url + "/api/2.0/workspace/import"
    results = self._post(
      url,
      json={
        "path": path,
        "content": content,
        "format": "HTML"
      }
    )
    self._check_results(results)

  """
  Gets notebook status
  """
  def getNotebookStatus(self, path: str) -> str:
    url = self._workspace_url + "/api/2.0/workspace/get-status"
    results = self._get(
      url,
      json={
        "path": path
      }
    )
    self._check_results(results)
    return results.json()

  """
  Creates station
  """
  def createStation(self, clean_room: str, station_name: str) -> dict:
    url = self._workspace_url + f"/api/2.1/unity-catalog/clean-rooms/{urllib.parse.quote(clean_room)}/stations"
    results = self._post(
      url,
      json={
        "station_name": station_name
      }
    )
    self._check_results(results)
    return results.json()

  def _setupStationResource(self, clean_room: str, station_name: str, json_body: dict) -> dict:
    url = self._get_station_url(clean_room, station_name) + "/setup-resource"
    results = self._post(
      url,
      json=json_body
    )
    self._check_results(results)
    return results.json()

  """
  Sets up station metastore
  """
  def setupStationMetastore(self, clean_room: str, station_name: str) -> dict:
    return self._setupStationResource(
      clean_room,
      station_name,
      {
        "metastore": {}
      }
    )

  """
  Sets up station workspace
  """
  def setupStationWorkspace(self, clean_room: str, station_name: str) -> dict:
    return self._setupStationResource(
      clean_room,
      station_name,
      {
        "workspace": {}
      }
    )

  """
  Gets station workspace status
  """
  def getStationWorkspaceStatus(self, clean_room: str, station_name: str) -> dict:
    url = self._get_station_url(clean_room, station_name) + "/get-workspace-status"
    results = self._get(
      url
    )
    self._check_results(results)
    return results.json()

  """
  Sets up station collaborator shares
  """
  def setupStationCollaboratorShares(self, clean_room: str, station_name: str, output_tables: dict[str, str]) -> dict:
    return self._setupStationResource(
      clean_room,
      station_name,
      {
        "collaborator_shares": {
          "output_tables": output_tables
        }
      }
    )

  """
  Sets up station notebook service principal
  """
  def setupStationNotebookServicePrincipal(self, clean_room: str, station_name: str) -> dict:
    return self._setupStationResource(
      clean_room,
      station_name,
      {
        "notebook_service_principal": {}
      }
    )

  """
  Sets up station notebook
  """
  def setupStationNotebook(self, clean_room: str, station_name: str, notebook_collaborator: str, notebook_name: str) -> dict:
    return self._setupStationResource(
      clean_room,
      station_name,
      {
        "notebook": {
          "notebook_collaborator": notebook_collaborator,
          "notebook_name": notebook_name
        }
      }
    )
  
  """
  Runs station notebook with parameters
  """
  def runStationNotebook(self, clean_room: str, station_name: str, base_parameters: dict[str, str]) -> dict:
    url = self._get_station_url(clean_room, station_name) + "/run-notebook"
    results = self._post(
      url,
      json={
        "base_parameters": base_parameters
      }
    )
    self._check_results(results)
    return results.json()

  """
  Gets station notebook run state
  """
  def getStationNotebookRunState(self, clean_room: str, station_name: str) -> dict:
    url = self._get_station_url(clean_room, station_name) + "/get-notebook-run-state"
    results = self._get(
      url
    )
    self._check_results(results)
    return results.json()

  """
  Exports station notebook output
  """
  def exportStationNotebookOutput(self, clean_room: str, station_name: str) -> dict:
    url = self._get_station_url(clean_room, station_name) + "/export-notebook-output"
    results = self._get(
      url
    )
    self._check_results(results)
    return results.json()

  """
  Tears down station resource
  """
  def teardownStationResource(self, clean_room: str, station_name: str, resource: TeardownResource) -> dict:
    print("Tearing down station resource: " + resource.name)
    url = self._get_station_url(clean_room, station_name) + "/teardown-resource"
    results = self._post(
      url,
      json={
        "resource": resource.name
      }
    )
    self._check_results(results)
    return results.json()

  """
  Deletes the station
  """
  def deleteStation(self, clean_room: str, station_name: str) -> None:
    print("Deleting station")
    url = self._get_station_url(clean_room, station_name)
    results = self._delete(
      url
    )
    self._check_results(results)

  """
  Lists all stations
  """
  def listStations(self, clean_room: str) -> List[dict]:
    url = self._workspace_url + f"/api/2.1/unity-catalog/clean-rooms/{urllib.parse.quote(clean_room)}/stations"
    results = self._get(
      url
    )
    self._check_results(results)
    return results.json()["stations"]

class CleanRoomClient:
  def __init__(self):
    dbutils.widgets.text("Clean Room", "")
    dbutils.widgets.text("Station Name", "")
    self._clean_room: str = dbutils.widgets.get("Clean Room")
    self._station_name: str = dbutils.widgets.get("Station Name")
    self._rest_client: CleanRoomClient = CleanRoomRestClient()

  @classmethod
  def parseParameters(cls, parameters: str) -> dict[str, str]:
    if not parameters:
      return dict()
    parameters_json = json.loads(parameters)
    for k, v in parameters_json.items():
      if not isinstance(k, str):
        raise RuntimeError(f"All keys in ${parameters} must be strings")
      if not isinstance(v, str):
        raise RuntimeError(f"All values in ${parameters} must be strings")
    return parameters_json

  def prepareAndRunNotebook(self):
    dbutils.widgets.text("Notebook Collaborator", "")
    dbutils.widgets.text("Notebook Name", "")
    dbutils.widgets.text("Notebook Parameters", "")
    dbutils.widgets.text("Output Table Parameters", "")
    notebook_collaborator: str = dbutils.widgets.get("Notebook Collaborator")
    notebook_name: str = dbutils.widgets.get("Notebook Name")
    notebook_parameters: str = CleanRoomClient.parseParameters(dbutils.widgets.get("Notebook Parameters"))
    output_table_parameters: str = CleanRoomClient.parseParameters(dbutils.widgets.get("Output Table Parameters"))
    if (not self._clean_room or not self._station_name):
      raise RuntimeError("Clean Room and Station Name must be non-empty")

    # Also verifies that the secrets are properly set up
    dbutils.jobs.taskValues.set(key="station_created", value=True)
    state, notebook_url = self._prepareAndRunNotebookHelper(
      notebook_collaborator, notebook_name, notebook_parameters, output_table_parameters)
    dbutils.jobs.taskValues.set(key="notebook_url", value=notebook_url)
    dbutils.jobs.taskValues.set(key="notebook_run_state", value=state)
    displayHTML(f"<a href='{notebook_url}'>Notebook Results</a>")
    if (state["result_state"] != "SUCCESS"):
      raise RuntimeError("Notebook run failed. Please inspect results.")

  def _prepareAndRunNotebookHelper(
      self, notebook_collaborator: str, notebook_name: str,
      notebook_parameters: dict[str, str], output_table_parameters: dict[str, str]) -> tuple[dict, str]:
    print("Creating station")
    self._rest_client.createStation(self._clean_room, self._station_name)

    # Setup all resources
    print("Setting up station metastore")
    self._rest_client.setupStationMetastore(self._clean_room, self._station_name)
    print("Setting up station collaborator shares")
    self._rest_client.setupStationCollaboratorShares(self._clean_room, self._station_name, output_table_parameters)
    print("Setting up station workspace")
    self._rest_client.setupStationWorkspace(self._clean_room, self._station_name)
    print("Waiting for workspace to be provisioned...")
    while True:
      response = self._rest_client.getStationWorkspaceStatus(self._clean_room, self._station_name)
      if (response["workspace_status"] == "RUNNING"):
        break
      if (response["workspace_status"] != "PROVISIONING"):
        raise RuntimeError("Workspace could not be provisioned")
      time.sleep(10)
    print("Setting up station notebook service principal")
    self._rest_client.setupStationNotebookServicePrincipal(self._clean_room, self._station_name)
    print("Setting up station notebook")
    self._rest_client.setupStationNotebook(self._clean_room, self._station_name, notebook_collaborator, notebook_name)

    # Run the clean room notebook
    print("Starting clean room notebook run")
    self._rest_client.runStationNotebook(self._clean_room, self._station_name, notebook_parameters)
    print("Waiting for clean room notebook to finish running...")
    state = None
    while True:
      response = self._rest_client.getStationNotebookRunState(self._clean_room, self._station_name)
      if (response["state"]["life_cycle_state"] == "TERMINATED"):
        state = response["state"]
        break
      if (response["state"]["life_cycle_state"] in ["SKIPPED", "INTERNAL_ERROR"]):
        raise RuntimeError("Notebook could not be run")
      time.sleep(10)

    # Export notebook results and import it into the user's workspace
    print("Exporting clean room notebook output")
    output = self._rest_client.exportStationNotebookOutput(self._clean_room, self._station_name)
    content = output["views"][0]["content"]
    content_b64 = base64.b64encode(content.encode('utf-8')).decode('utf-8')
    output_folder = f"/Users/{dbutils.notebook.entry_point.getDbutils().notebook().getContext().userName().get()}"
    current_date = datetime.now()
    path = os.path.join(output_folder, f"clean_room_output_{current_date.isoformat()}")
    print("Saving clean room notebook output to " + path)
    self._rest_client.importNotebook(path, content_b64)
    notebook_status = self._rest_client.getNotebookStatus(path)
    return (state, f"/#notebook/{notebook_status['object_id']}")

  def teardownStation(self):
    if dbutils.jobs.taskValues.get(taskKey="Step1", key="station_created", default=False):
      self._teardownStationHelper()
      notebook_url = dbutils.jobs.taskValues.get(taskKey="Step1", key="notebook_url", default="")
      notebook_run_state = dbutils.jobs.taskValues.get(taskKey="Step1", key="notebook_run_state", default="")
      if notebook_url and notebook_run_state:
        displayHTML(f"<a href='{notebook_url}'>Notebook Results</a>")
        if ("result_state" in notebook_run_state and notebook_run_state["result_state"] != "SUCCESS"):
          print("Notebook run failed. Please inspect results.")

  def _teardownStationHelper(self) -> None:
    print("Tearing down station notebook service principal")
    self._rest_client.teardownStationResource(self._clean_room, self._station_name, TeardownResource.NOTEBOOK_SERVICE_PRINCIPAL)
    print("Tearing down station workspace")
    self._rest_client.teardownStationResource(self._clean_room, self._station_name, TeardownResource.WORKSPACE)
    print("Tearing down station collaborator shares")
    self._rest_client.teardownStationResource(self._clean_room, self._station_name, TeardownResource.COLLABORATOR_SHARES)
    print("Tearing down station metastore")
    self._rest_client.teardownStationResource(self._clean_room, self._station_name, TeardownResource.METASTORE)
    print("Deleting station")
    self._rest_client.deleteStation(self._clean_room, self._station_name)