from blueno import job_registry
from blueno.cli import run


run(
    project_dir="./examples/jaffle_shop",
    select=["++mart_orders", "++mart_order_items"],
    display_mode="log",
    log_level="DEBUG"
)