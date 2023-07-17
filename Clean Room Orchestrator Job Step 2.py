# Databricks notebook source
# MAGIC %pip install git+https://github.com/databricks/clean-room-orchestration@v0.1-beta.5 -q
# MAGIC from databricks_clean_room_orchestrator.client import CleanRoomClient

# COMMAND ----------

CleanRoomClient().teardownStation()

# COMMAND ----------


