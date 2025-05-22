ENVIRONMENT = "dev"

match ENVIRONMENT:
    case "dev":
        # Development environment
        workspace_name = "your_workspace_name"
        lakehouse_name = "your_lakehouse_name"
        path = "Tables"
        
        storage_base_path = (
            f"abfss://{workspace_name}@onelake.dfs.fabric.microsoft.com/{lakehouse_name}.Lakehouse/{path}"
        )

    case "prod":
        # Production environment
        workspace_name = "your_workspace_name"
        lakehouse_name = "your_lakehouse_name"
        path = "Tables"

        storage_base_path = (
            f"abfss://{workspace_name}@onelake.dfs.fabric.microsoft.com/{lakehouse_name}.Lakehouse/{path}"
        )

    case _:
        # Local environment just saves to temp directory
        path = "blueno/blueprints"
        storage_base_path = f"/tmp/{path}"
