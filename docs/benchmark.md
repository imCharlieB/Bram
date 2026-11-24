# Testing your model

`bram-bench` checks an Ollama model's tool use, safety behavior, vision, recall, and speed. It uses an invented house and never contacts Home Assistant. Set up first with [Development](development.md).

    bram-bench --url http://HOST:11434                  # list installed models
    bram-bench --url http://HOST:11434 --model MODEL

| Option | Meaning | Default |
|---|---|---|
| `--url` | Ollama address | required |
| `--model` | Model to test; omit to list models | |
| `--context` | Context size in tokens | 8192 |
| `--timeout` | Seconds allowed per request | 180 |
| `--repeat` | Times to run each test | 3 |
| `--think` | `on`, `off`, or the model's `default` | default |
| `--keep-loaded` | Never unload the model | unloads after 30 minutes idle |
| `--out` | Save full results as JSON | |

**Sharing Ollama with something else?** A different context size reloads the model, and the default unload time replaces the current one. Check `http://HOST:11434/api/ps`, then match `--context`, and add `--keep-loaded` if the model is set never to unload.

Exit code 0 means everything passed, 1 means a test failed, 2 means the benchmark could not run.

A perfect score is a smoke test. It does not let a model control anything. Repeated prompts may be cached, which inflates prompt speed.
