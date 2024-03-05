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

class Resource(Enum):
  NOTEBOOK_SERVICE_PRINCIPAL = 1
  COLLABORATOR_SHARES = 2
  WORKSPACE = 3
  METASTORE = 4
  NOTEBOOK = 5
  NOTEBOOK_JOB_RUN = 6

class CleanRoomRestClient:
  _workspace_url: Optional[str]
  _auth_token: Optional[str]
  _headers: dict[str, str]

  def __init__(self):
    self._workspace_url = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiUrl().getOrElse(None)
    self._auth_token = dbutils.notebook.entry_point.getDbutils().notebook().getContext().apiToken().getOrElse(None)
    if (not self._workspace_url or not self._auth_token):
      raise RuntimeError("Please run this in a UC shared cluster.")
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
    return self._workspace_url + f"/api/2.1/unity-catalog/clean-room-stations/{urllib.parse.quote(clean_room)}.{urllib.parse.quote(station_name)}"

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
  def createStation(self, clean_room: str, station_name: str,
                    notebook_collaborator: str, notebook_name: str,
                    notebook_parameters: dict[str, str],
                    table_output_parameters: dict[str, str]) -> dict:
    url = self._workspace_url + f"/api/2.1/unity-catalog/clean-room-stations"
    results = self._post(
      url,
      json={
        "clean_room_name": clean_room,
        "station_name": station_name,
        "notebook": {
          "notebook_collaborator": notebook_collaborator,
          "notebook_name": notebook_name,
          "notebook_base_parameters": notebook_parameters,
          "notebook_output_table_parameters": table_output_parameters
        }
      }
    )
    self._check_results(results)
    return results.json()

  """
  Sets up station resource
  """
  def setupStationResource(self, clean_room: str, station_name: str, resource: Resource) -> dict:
    url = self._get_station_url(clean_room, station_name) + "/setup-resource"
    results = self._post(
      url,
      json={
        "resource": {
          "resource_type": resource.name
        }
      }
    )
    self._check_results(results)
    return results.json()

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
  def teardownStationResource(self, clean_room: str, station_name: str, resource: Resource) -> dict:
    url = self._get_station_url(clean_room, station_name) + "/teardown-resource"
    results = self._post(
      url,
      json={
        "resource": {
          "resource_type": resource.name
        }
      }
    )
    self._check_results(results)
    return results.json()

  """
  Deletes the station
  """
  def deleteStation(self, clean_room: str, station_name: str) -> None:
    url = self._get_station_url(clean_room, station_name)
    results = self._delete(
      url
    )
    self._check_results(results)

  """
  Lists all stations
  """
  def listStations(self, clean_room: str) -> List[dict]:
    url = self._workspace_url + f"/api/2.1/unity-catalog/clean-room-stations"
    results = self._get(
      url,
      params = {"clean_room_name": clean_room}
    )
    self._check_results(results)
    return results.json().get("clean_room_stations", [])

class CleanRoomClient:
  _clean_room: str
  _station_name: str
  _rest_client: CleanRoomRestClient

  def __init__(self):
    dbutils.widgets.text("Clean Room", "")
    dbutils.widgets.text("Station Name", "")
    self._clean_room = dbutils.widgets.get("Clean Room")
    self._station_name = dbutils.widgets.get("Station Name")
    self._rest_client = CleanRoomRestClient()

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

    # Also verifies that the station was properly set up
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
    self._rest_client.createStation(
      self._clean_room,
      self._station_name,
      notebook_collaborator,
      notebook_name,
      notebook_parameters,
      output_table_parameters)

    # Setup all resources
    print("Setting up station metastore")
    self._rest_client.setupStationResource(self._clean_room, self._station_name, Resource.METASTORE)
    print("Setting up station workspace")
    self._rest_client.setupStationResource(self._clean_room, self._station_name, Resource.WORKSPACE)
    print("Waiting for workspace to be provisioned...")
    while True:
      response = self._rest_client.getStationWorkspaceStatus(self._clean_room, self._station_name)
      if (response["workspace_status"] == "RUNNING"):
        break
      if (response["workspace_status"] != "PROVISIONING"):
        raise RuntimeError("Workspace could not be provisioned")
      time.sleep(10)
    
    print("Finalize station workspace setup")
    self._rest_client.setupStationResource(self._clean_room, self._station_name, Resource.WORKSPACE)
    print("Setting up station collaborator shares")
    self._rest_client.setupStationResource(self._clean_room, self._station_name, Resource.COLLABORATOR_SHARES)
    print("Setting up station notebook service principal")
    self._rest_client.setupStationResource(self._clean_room, self._station_name, Resource.NOTEBOOK_SERVICE_PRINCIPAL)
    print("Setting up station notebook")
    self._rest_client.setupStationResource(self._clean_room, self._station_name, Resource.NOTEBOOK)

    # Run the clean room notebook
    print("Setting up station notebook job run")
    self._rest_client.setupStationResource(self._clean_room, self._station_name, Resource.NOTEBOOK_JOB_RUN)
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
    content = output["notebook_contents"]
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
      self._teardownStationHelper(self._clean_room, self._station_name)
      notebook_url = dbutils.jobs.taskValues.get(taskKey="Step1", key="notebook_url", default="")
      notebook_run_state = dbutils.jobs.taskValues.get(taskKey="Step1", key="notebook_run_state", default="")
      if notebook_url and notebook_run_state:
        displayHTML(f"<a href='{notebook_url}'>Notebook Results</a>")
        if ("result_state" in notebook_run_state and notebook_run_state["result_state"] != "SUCCESS"):
          print("Notebook run failed. Please inspect results.")

  def _teardownStationHelper(self, clean_room: str, station_name: str) -> None:
    print(f"Begin tearing down station {clean_room}.{station_name}")
    print("Tearing down station notebook job run")
    self._rest_client.teardownStationResource(clean_room, station_name, Resource.NOTEBOOK_JOB_RUN)
    print("Tearing down station notebook")
    self._rest_client.teardownStationResource(clean_room, station_name, Resource.NOTEBOOK)
    print("Tearing down station notebook service principal")
    self._rest_client.teardownStationResource(clean_room, station_name, Resource.NOTEBOOK_SERVICE_PRINCIPAL)
    print("Tearing down station collaborator shares")
    self._rest_client.teardownStationResource(clean_room, station_name, Resource.COLLABORATOR_SHARES)
    print("Tearing down station workspace")
    self._rest_client.teardownStationResource(clean_room, station_name, Resource.WORKSPACE)
    print("Tearing down station metastore")
    self._rest_client.teardownStationResource(clean_room, station_name, Resource.METASTORE)
    print(f"Deleting station")
    self._rest_client.deleteStation(clean_room, station_name)
    print(f"Finished tearing down station {clean_room}.{station_name}")

  def teardownAllStations(self):
    stations = self._rest_client.listStations(self._clean_room)
    print(f"Found {len(stations)} stations to tear down:")
    for station in stations:
      print(station["full_name"])
    print()
    for station in stations:
      self._teardownStationHelper(self._clean_room, station["name"])
    print(f"Finished tearing down all stations")
