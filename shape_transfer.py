import json
from pprint import pprint
import sqlite3
from sqlite3 import Error
from sqlalchemy import (inspect, create_engine, MetaData, Table, Column,
                        VARCHAR, INTEGER, BIGINT, REAL, TIMESTAMP, TEXT,
                        BINARY)
from sqlalchemy.sql.sqltypes import NVARCHAR


class ShapeTransferer:
    connection_strings = {}
    type_matchings = []
    from_db_engine = None
    to_db_engine = None

    def read_connection(self):
        with open("config.json", "r") as f:
            connections = json.load(f)
            self.connection_strings = filter(lambda x: x["transferType"] == "shape", connections)

    def read_type_matchings(self):
        with open("type_matchings.json", "r") as f:
            self.type_matchings = json.load(f)

    def create_db_connections(self):
        self.from_db_engine = create_engine(self.config["from"])
        self.to_db_engine = create_engine(self.config["to"])

    def _convert_col_type_to_suitable_type(self, col_type):
        pass
        # if type(col["type"]).__name__ == "VARCHAR":
        #     return NVARCHAR(col_type.length)
        # return col_type

    def create_sqlalchemy_tables(self):
        to_db_meta = MetaData()

        db_inspector = inspect(self.from_db_engine)
        tables = db_inspector.get_table_names()

        db_schema = [{
            "table_name": table,
            "columns": db_inspector.get_columns(table)
        } for table in tables]

        for table in db_schema:
            columns = []
            for col in table["columns"]:
                columns.append(
                    Column(col["name"],
                           self._convert_col_type_to_suitable_type(col["type"]),
                           nullable=col["nullable"],
                           default=col["default"],
                           autoincrement=col["autoincrement"],
                           comment=col["comment"]))
            Table(table["table_name"], to_db_meta, *columns)

        to_db_meta.create_all(self.to_db_engine)
