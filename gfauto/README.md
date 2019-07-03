
# GraphicsFuzz auto

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Build Status](https://paulthomson.visualstudio.com/gfauto/_apis/build/status/google.graphicsfuzz?branchName=master)](https://paulthomson.visualstudio.com/gfauto/_build/latest?definitionId=2&branchName=master)


## GraphicsFuzz auto is a set of Python scripts for running GraphicsFuzz

[GraphicsFuzz](https://github.com/google/graphicsfuzz) provides tools that automatically find and simplify bugs in graphics shader compilers.
GraphicsFuzz auto (this project) provides scripts for running these tools with minimal interaction.

## Development setup

Execute `./dev_shell.sh.template` (or, copy to `./dev_shell.sh` and modify as needed before executing).
This generates and activates a Python virtual environment (located at `.venv/`) with all dependencies installed. 

* Execute `./check_all.sh` to run various presubmit checks, linters, etc.
* Execute `./fix_all.sh` automatically fix certain issues, such as formatting.

### PyCharm

Use PyCharm to open the top-level `gfauto` directory.
It should pick up the Python virtual environment (at `.venv/`) automatically
for both the code
and when you open a `Terminal` or `Python Console` tab.

Install and configure plugins:

* Protobuf Support
* File Watchers (may already be installed)
  * The watcher task should already be under version control with the following settings:
    * File type: Python
    * Program: `$ProjectFileDir$/fix_all.sh`


## Using iPython

Using an iPython shell is useful for modifying artifacts interactively.


```python
# Start iPython, if not running already.
ipython

# Disabling jedi can help with autocompletion of protobuf objects.
%config IPCompleter.use_jedi=False

from gfauto.artifacts import *

# This is executed as a shell command.
cd /data/artifacts

a = ArtifactMetadata()
a.data.glsl_shader_job.shader_job_file = "shader.json"

artifact_write_metadata(a, '//my_glsl_shader_job')
```