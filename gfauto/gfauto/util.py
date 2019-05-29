# Copyright 2019 The GraphicsFuzz Project Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import pathlib
import shutil
from contextlib import contextmanager


# Note: Could use the built-in |file.open| and |file.write_text|, etc.


def file_open_binary(file: pathlib.Path, mode: str):
    assert mode.find("b") != -1
    return open(str(file), mode)


def file_open_text(file: pathlib.Path, mode: str):
    assert mode.find("b") == -1
    return open(str(file), mode, encoding="utf-8", errors="ignore")


def file_read_text(file: pathlib.Path):
    with file_open_text(file, "r") as f:
        return f.read()


def file_read_lines(file: pathlib.Path):
    with file_open_text(file, "r") as f:
        return f.readline()


def file_write_text(file: pathlib.Path, text: str):
    file_mkdirs_parent(file)
    with file_open_text(file, "w") as f:
        return f.write(text)


def mkdirs_p(path: pathlib.Path):
    path.mkdir(parents=True, exist_ok=True)


def file_mkdirs_parent(file: pathlib.Path):
    mkdirs_p(file.parent)


class ToolNotOnPathError(Exception):
    pass


def tool_on_path(tool: str) -> pathlib.Path:
    result = shutil.which(tool)
    if result is None:
        raise ToolNotOnPathError(
            "Could not find {} on PATH. Please add to PATH.".format(tool)
        )
    return pathlib.Path(result)


def spirv_dis_on_path() -> pathlib.Path:
    return tool_on_path("spirv-dis")


def copy_file(source_file_path: pathlib.Path, dest_file_path: pathlib.Path):
    file_mkdirs_parent(dest_file_path)
    shutil.copy(str(source_file_path), str(dest_file_path))


def remove_end(str_in: str, str_end: str):
    assert str_in.endswith(str_end), "Expected {} to end with {}".format(
        str_in, str_end
    )
    return str_in[: -len(str_end)]


def norm_path(path: pathlib.Path):
    return pathlib.Path(os.path.normpath(str(path)))


@contextmanager
def pushd(path: pathlib.Path):
    curr_dir = pathlib.Path().resolve()
    os.chdir(str(path))
    try:
        yield
    finally:
        os.chdir(str(curr_dir))