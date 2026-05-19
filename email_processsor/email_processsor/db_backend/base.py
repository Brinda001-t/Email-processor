# import os
# import struct
# import msal
# from mssql.base import DatabaseWrapper as MssqlDatabaseWrapper

# SQL_COPT_SS_ACCESS_TOKEN = 1256


# def _get_token():
#     app = msal.ConfidentialClientApplication(
#         client_id=os.environ["AZURE_SQL_CLIENT_ID"],
#         client_credential=os.environ["AZURE_SQL_CLIENT_SECRET"],
#         authority=f"https://login.microsoftonline.com/{os.environ['AZURE_SQL_TENANT_ID']}",
#     )
#     result = app.acquire_token_for_client(
#         scopes=["https://database.windows.net/.default"]
#     )
#     if "access_token" not in result:
#         raise RuntimeError(f"MSAL token error: {result.get('error_description')}")
#     token_bytes = result["access_token"].encode("utf-16-le")
#     return struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)


# class DatabaseWrapper(MssqlDatabaseWrapper):
#     def get_new_connection(self, conn_params):
#         conn_params["attrs_before"] = {SQL_COPT_SS_ACCESS_TOKEN: _get_token()}
#         return super().get_new_connection(conn_params)



# import struct
# from azure.identity import DefaultAzureCredential
# from mssql.base import DatabaseWrapper as MssqlDatabaseWrapper

# SQL_COPT_SS_ACCESS_TOKEN = 1256


# def _get_token():
#     credential = DefaultAzureCredential()
#     token = credential.get_token("https://database.windows.net/.default")
#     print(f"[DEBUG] Token acquired: {token.token[:30]}...")
#     token_bytes = token.token.encode("utf-16-le")
#     return struct.pack(f"<I{len(token_bytes)}s", len(token_bytes), token_bytes)


# class DatabaseWrapper(MssqlDatabaseWrapper):
#     def get_new_connection(self, conn_params):
#         conn_params["attrs_before"] = {SQL_COPT_SS_ACCESS_TOKEN: _get_token()}
#         return super().get_new_connection(conn_params)



from azure.identity import DefaultAzureCredential
from mssql.base import DatabaseWrapper as MssqlDatabaseWrapper


def _get_token():
    credential = DefaultAzureCredential()
    token = credential.get_token("https://database.windows.net/.default")
    return token.token


class DatabaseWrapper(MssqlDatabaseWrapper):
    # mssql uses type(self).__dict__ to find these, which breaks on subclasses
    sql_server_version = MssqlDatabaseWrapper.__dict__['sql_server_version']
    to_azure_sql_db = MssqlDatabaseWrapper.__dict__['to_azure_sql_db']

    def get_new_connection(self, conn_params):
        conn_params["TOKEN"] = _get_token()
        return super().get_new_connection(conn_params)

