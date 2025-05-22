
![blueno logo](./assets/images/blueno-128x128.png)
 
A Python library for writing declarative data pipelines the ***bueno*** way

# blueno
A collection of Spark-free Python ETL utilities for working with data pipelines with built in orchestration.

Mainly focused on Data Engineering tasks utilising [Polars](https://github.com/pola-rs/polars) and [delta-rs](https://github.com/delta-io/delta-rs).

It features **blueprints** as the central orchestration unit, and is inspired by the likes of dbt [models](https://docs.getdbt.com/docs/build/models), SQLMesh [models](https://sqlmesh.readthedocs.io/en/stable/concepts/models/sql_models/) and Dagster's [software defined assets](https://dagster.io/glossary/software-defined-assets).

While it also has features for running on Microsoft Fabric, its utilities are decoupled in a way to let you choose your own storage and compute.


## Table of contents

- [Table of contents](#table-of-contents)
- [Installation](#installation)
- [Features](#features)
  - [Local development first](#local-development-first)
  - [Remote code execution](#remote-code-execution)
  - [ETL helper functions](#etl-helper-functions)
  - [Blueprints](#blueprints)
- [Documentation](#documentation)
- [Contributing](#contributing)

## Installation
Regular installation:
```bash
pip install blueno
```

For Microsoft Fabric or Azure:
```bash
pip install "blueno[azure]"
```

## Features

### Local development first
Aim to provide a local development environment. This means you can develop, run code and store data locally as part of your development cycle. You can also read and write to Azure Data Lake or Microsoft Fabric lakehouses.

### Remote code execution (Fabric only)
While local development is favored, sometimes we need run our data pipelines a real setting. The library lets you run code directly in Microsoft Fabric.

### ETL helper functions
- Read from delta tables or parquet files with automatic authentication to Azure Data Lake or OneLake
- Common transformations (add audit columns, reorder columns, deduplicate etc.)
- Load delta tables with one of the provided load methods (upsert, overwrite, append etc.)

### Blueprints
Blueprints is a feature to declaratively specify your entities in your data pipelines.

Configuration such as storage location, write behaviour and other configuration is set in the decorator, while the function itself only is concerned about business logic.

```python
from blueno import blueprint, Blueprint
import polars as pl

workspace_name = ...
lakehouse_name = ...

lakehouse_base_uri = f"abfss://{workspace_name}@onelake.dfs.fabric.microsoft.com/{lakehouse_name}.Lakehouse/Tables"

@blueprint(
    table_uri=f"{storage_base_uri}/silver/customer",
    primary_keys=["customer_id"],
    write_mode="overwrite",
)
def silver_customer(self: Blueprint, bronze_customer: pl.DataFrame) -> pl.DataFrame
    
    # Deduplicate customers
    df = bronze_customers.unique(subset=self.primary_keys)

    return df
```

Given you also specified a blueprint for `bronze_customer` specified as a dependency for `silver_customer`, the blueprints will automatically be wired and executed in the correct order.

See the documentation for an elaborate example.

## Documentation
For quick start and detailed documentation, examples, and API reference, visit our [GitHub Pages documentation](https://mrjsj.github.io/blueno/).

## Contributing
Contributions are welcome! Here are some ways you can contribute:

- Report bugs and feature requests through GitHub issues
- Submit pull requests for bug fixes or new features
- Improve documentation
- Share ideas for new utilities

