# Remote execution

You can also use your Microsoft Fabric compute to run your blueprints using the CLI command:

```sh
blueno run-remote
```

For more information on usage run:
```sh
blueno run-remote -h
```

## Prerequisites

- Azure CLI installed
- AzCopy installed
- The `RunBlueprints` notebook (see below)

## RunBlueprints notebook
Find the notebook in [RunBlueprints](https://github.com/mrjsj/blueno/blob/main/fabric/notebooks/RunBlueprints.ipynb) and upload it to your desired Microsoft Fabric workspace.

## How it works

The `run-remote` CLI command takes in the specified `project_path` where local blueprints are stored and uploads it to temporary folder the "Files" directory in the target lakehouse.
It then runs the `RunBlueprints` notebook which installs the `blueno` and runs the regular `blueno run` command using the temporary folder as input for the `project_path`.

