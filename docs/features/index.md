# Features

Let's look at what makes **blueno** special! Here are the key features that will help you build declarative data pipelines:

## Local Development First

Why wait for the cloud when you can develop locally? 💻

**blueno** lets you:

- Write and test your pipelines on your local machine
- Use the same code for local and cloud environments
- Connect to your blob storage when needed

## Deploy anywhere

There are no external dependencies on where you can run **blueno**. You can run it on any compute which has Python installed and bring your own blob storage. 

You can for example run on AWS Lambda, Azure Functions, Container Apps, Google Collab Notebook or some virtual machine with underlying data storage such as AWS S3 or Azure Data Lake Storage.

And of course you can also run on your local machine with your local file system as the storage layer.

## Serverless

Blueno is first and foremost ment to be run in a serverless manner. 

There are no services required to track state. Functional state is stored on the tables themselves (i.e. watermarks for incremental loads), and observability metrics are emitted through logs. 

## ETL Helper Functions

**blueno** comes with batteries included for all your ETL needs:

### Extract
- Blueno supports reading from delta tables or parquet files
- Automatic authentication with Azure Data Lake or Fabric OneLake


### Transform
Common data transformations out of the box:

- Add audit columns
- Normalize column names
- Remove duplicates
- And much more!

### Load
Multiple load strategies:

- Upsert (merge)
- Overwrite
- Incremental
- Append
- Replace range (overwrite range)
- SCD Type 2

## Blueprints

Blueprints are the heart of blueno. They let you:

- Write declarative data pipelines
- Focus on business logic, not boilerplate
- Automatically handle dependencies
- Automatic schema validation
- Visualize your data pipeline as a DAG
- Run your pipelines locally or in the cloud

## Extendable through plugins

**blueno** is has an interface for creating plugins. You can add custom plugins for custom transformations used as *post*-transformations or custom load strategies.


## Microsoft Fabric

While blueno works anywhere, it has special support for Microsoft Fabric:

- Run your **blueno** pipelines directly in a Microsoft Fabric notebook
- Authenticate automatically with OneLake
- Use local development workflow with cloud deployment
- Keep your code clean and platform-agnostic