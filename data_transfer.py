import pandas as pd
import numpy as np
import sqlalchemy
from sqlalchemy.sql import text
import json
import logging

logging.basicConfig(
    format='%(levelname)s:%(asctime)s - %(message)s',
    level=logging.DEBUG,
    datefmt='%Y-%m-%d %H:%M:%S',
)


class DataTransferer:
    flows = []
    connection_strings = {}

    def read_connections(self, file, from_field=None, to_field=None):
        # from_field = "from" if not from_field else from_field
        # to_field = "to" if not to_field else to_field
        with open(file, "r") as c:
            connections = json.load(c)
            self.connection_strings = filter(lambda x: x["transferType"] == "data", connections)

    def read_flows(self, file, flow_field=None):
        flow_field = "flows" if not flow_field else flow_field
        with open(file, "r") as f:
            flows = json.load(f)
            self.flows = flows[flow_field]

    def create_connections(self):
        from_engine = sqlalchemy.create_engine(self.connection_strings["from"])
        to_engine = sqlalchemy.create_engine(self.connection_strings["to"])
        return from_engine, to_engine

    def _construct_select_query(self, match):
        join_query = "SELECT *\n"
        for index, table_pair in enumerate(match["from_tables"]):
            if not table_pair.get("table_right", None):
                join_query += "FROM {from_table}".format(
                    from_table=table_pair["table_left"])
            else:
                if index == 0:
                    join_query += "FROM {from_table}\n".format(
                        from_table=table_pair["table_left"])

                join_query += "LEFT JOIN {to_table} ON {from_table}.{from_column} = {to_table}.{to_column}".format(
                    from_table=table_pair["table_left"],
                    to_table=table_pair["table_right"],
                    from_column=table_pair["join_on_left"],
                    to_column=table_pair["join_on_right"])
        return join_query

    def get_data_from_source_tables(self, from_engine, match):
        logging.info("Reading data from tables '%s'.",
                     ", ".join(map(lambda x: (x['table_left'], x['table_right'])), match["from_tables"]))
        join_query = self._construct_select_query(match)

        table_data = pd.read_sql(join_query, from_engine)
        return table_data

    def truncate_destination_tables(self, to_engine, match):
        with to_engine.connect() as connection:
            logging.info("Truncating table '%s'.", match["to_table"])
            connection.execute(
                text("TRUNCATE TABLE \"{}\"".format(match["to_table"])))

    def fill_empty_cells(self, switched_pairs, table_data):
        for col in switched_pairs.values():
            if col not in table_data.columns:
                table_data[col] = np.nan

    def transfer(self):
        from_con, to_con = self.create_connections()
        for flow in self.flows:
            for match in flow["matches"]:
                switched_pairs = dict(
                    (from_col.lower(), to_col) if from_col else (to_col, to_col)
                    for to_col, from_col in match["column_pairs"].items())

                table_data = self.get_data_from_source_tables(from_con, match)
                table_data = table_data.rename(columns=switched_pairs)
                self.truncate_destination_tables(to_con, match)

                self.fill_empty_cells(switched_pairs, table_data)
                logging.info("Inserting data to table '%s'.", match["to_table"])
                table_data[switched_pairs.values()].to_sql(match["to_table"],
                                                           to_con,
                                                           schema="public",
                                                           if_exists="append",
                                                           index=False)
