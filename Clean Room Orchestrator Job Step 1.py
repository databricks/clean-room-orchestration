# Databricks notebook source
# MAGIC %pip install git+https://github.com/databricks/clean-room-orchestration@v0.1 -q

# COMMAND ----------

from databricks_clean_room_orchestrator.client import CleanRoomClient
CleanRoomClient().prepareAndRunNotebook()
