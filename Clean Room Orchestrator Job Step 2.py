# Databricks notebook source
# MAGIC %pip install git+https://github.com/databricks/clean-room-orchestration -q

# COMMAND ----------

from databricks_clean_room_orchestrator.client import CleanRoomClient
CleanRoomClient().teardownStation()
