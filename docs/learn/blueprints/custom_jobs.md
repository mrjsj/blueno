# Custom jobs

If the `blueprint` and `task` don't fit you needs, you can create your own implementation of the `BaseJob`.

It simply needs to inherit from the `blueno.orchetration.job.BaseJob` class and implement the `run` method.

In addition, a decorator should be implemented. You can see the simple implementation of `Task` for inspiration.

## Example

We want to create a custom job which can calls a webhook specified in the decorator.
The payload is set as the output of the decorated function.

```python
from blueno.orchestration.job import BaseJob, job_registry, track_step
from dataclasses import dataclass
from typing import Optional
import requests

@dataclass(kw_only=True)
class WebhookJob(BaseJob):
    """Class for the webhook_job decorator."""

    webhook_url: str

    @track_step
    def run(self):
        """Running the webhook job."""
        msg = self._transform_fn(*self.depends_on)
        payload = {
            "msg": msg
        }
        requests.post(self.webhook_url, data=payload)



def webhook_job(
    _func=None,
    *,
    name: Optional[str] = None,
    priority: int = 100,
    webhook_url: str
):
    """Create a definition for webhook_job"""

    def decorator(func: types.FunctionType):
        _name = name or func.__name__

        webhook_job = WebhookJob(
            name=_name,
            _transform_fn=func,
            webhook_url=webhook_url,
            priority=priority,
        )

        webhook_job._register(job_registry)

        return task

    # If used as @webhook_job
    if _func is not None and callable(_func):
        return decorator(_func)

    # If used as @webhook_job(...)
    return decorator

```

Now we can use the `webhook_job` decorator:

```{.python continuation}

@webhook_job(
    webhook_url="https://some-webhook-uri.com/webhook"
)
def send_on_complete() -> str:

    msg = "The data pipeline completed successfully"

    return msg

```