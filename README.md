# target-nationbuilder

`target-nationbuilder` is a Singer target for Nationbuilder.


## Installation



```bash
pipx install target-nationbuilder
```

## Configuration

### Accepted Config Options

- [ ] `Developer TODO:` Provide a list of config options accepted by the target.

A full list of supported settings and capabilities for this
target is available by running:

```bash
target-nationbuilder --about
```

### Configure using environment variables

This Singer target will automatically import any environment variables within the working directory's
`.env` if the `--config=ENV` is provided, such that config values will be considered if a matching
environment variable is set either in the terminal context or in the `.env` file.

### Source Authentication and Authorization

- [ ] `Developer TODO:` If your target requires special access on the source system, or any special authentication requirements, provide those here.

## Usage

You can easily run `target-nationbuilder`

### Executing the Target Directly

```bash
target-nationbuilder --version
target-nationbuilder --help
# Test using the "Carbon Intensity" sample:
tap-carbon-intensity | target-nationbuilder --config /path/to/target-nationbuilder-config.json
```

### Initialize your Development Environment

```bash
pipx install poetry
poetry install
```

### Create and Run Tests

Create tests within the `target_nationbuilder/tests` subfolder and
  then run:

```bash
poetry run pytest
```

You can also test the `target-nationbuilder` CLI interface directly using `poetry run`:

```bash
poetry run target-nationbuilder --help
```

