#!/usr/bin/env python3

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

import argparse
import sys
import os
import shutil

# This file is self-contained so it can be provided alongside Amber test files.

SHORT_DESCRIPTION_LINE_PREFIX = "# Short description: "

MUST_PASS_PATHS = [
    os.path.join("android", "cts", "master", "vk-master.txt"),
    os.path.join(
        "external", "vulkancts", "mustpass", "master", "vk-default-no-waivers.txt"
    ),
    os.path.join("external", "vulkancts", "mustpass", "master", "vk-default.txt"),
]


def log(message=""):
    print(message, flush=True)


def remove_start(string, start):
    assert string.startswith(start)
    return string[len(start) :]


def open_helper(file, mode):
    return open(file, mode, encoding="utf-8", errors="ignore")


def check_dir_exists(directory):
    log("Checking that directory {} exists".format(directory))
    if not os.path.isdir(directory):
        raise FileNotFoundError("Directory not found: {}".format(directory))


def check_file_exists(file):
    log("Checking that file {} exists".format(file))
    if not os.path.isfile(file):
        raise FileNotFoundError("File not found: {}".format(file))


def get_amber_test_file_path(vk_gl_cts, amber_test_name):
    return os.path.join(
        vk_gl_cts,
        "external",
        "vulkancts",
        "data",
        "vulkan",
        "amber",
        "graphicsfuzz",
        amber_test_name + ".amber",
    )


def get_graphics_fuzz_tests_cpp_file_path(vk_gl_cts):
    return os.path.join(
        vk_gl_cts,
        "external",
        "vulkancts",
        "modules",
        "vulkan",
        "amber",
        "vktAmberGraphicsFuzzTests.cpp",
    )


def get_amber_test_short_description(amber_test_file_path):
    with open_helper(amber_test_file_path, "r") as f:
        for line in f:
            if line.startswith(SHORT_DESCRIPTION_LINE_PREFIX):
                line = remove_start(line, SHORT_DESCRIPTION_LINE_PREFIX)
                # Remove \n
                line = line[:-1]
                return line
    return ""


def check_and_add_tabs(line, string_name, string_value, field_index, tab_size):

    # Field index starts at 1. Change it to start at 0.
    field_index -= 1

    assert len(line.expandtabs(tab_size)) <= field_index, '{} "{}" is too long!'.format(
        string_name, string_value
    )

    while len(line.expandtabs(tab_size)) < field_index:
        line += "\t"

    assert (
        len(line.expandtabs(tab_size)) == field_index
    ), "Field index {} is incorrect; Python script needs fixing".format(field_index)

    return line


def get_cpp_line_to_write(amber_test_name, short_description):

    # A test line has the following form, except with tabs aligning each field.
    # { "name.amber", "name", "description" },
    #   |             |       |             |
    #   1             2       3             4

    # 1
    test_file_name_start_index = 13
    # 2
    test_name_start_index = 61
    # 3
    test_description_start_index = 101
    # 4
    test_close_bracket_index = 189

    tab_size = 4

    line = "\t\t{"

    line = check_and_add_tabs(
        line, "internal", "internal", test_file_name_start_index, tab_size
    )

    line += '"{}.amber",'.format(amber_test_name)

    line = check_and_add_tabs(
        line, "amber test name", amber_test_name, test_name_start_index, tab_size
    )

    line += '"{}",'.format(amber_test_name)

    line = check_and_add_tabs(
        line, "amber test name", amber_test_name, test_description_start_index, tab_size
    )

    line += '"{}"'.format(short_description)

    line = check_and_add_tabs(
        line, "short description", short_description, test_close_bracket_index, tab_size
    )

    line += "},\n"

    return line


def add_amber_test_to_cpp(vk_gl_cts, amber_test_name):
    log("Adding Amber test to the C++.")

    short_description = get_amber_test_short_description(
        get_amber_test_file_path(vk_gl_cts, amber_test_name)
    )

    cpp_file = get_graphics_fuzz_tests_cpp_file_path(vk_gl_cts)
    cpp_file_bak = cpp_file + ".bak"

    copyfile(cpp_file, cpp_file_bak)

    line_to_write = get_cpp_line_to_write(amber_test_name, short_description)

    log("Writing from {} to {}.".format(cpp_file_bak, cpp_file))

    with open_helper(cpp_file_bak, "r") as cpp_in:
        with open_helper(cpp_file, "w") as cpp_out:

            # The start of the tests look like this (except with tabs!):
            #     tests[] =
            #     {
            #         {    "continue-and-merge.amber",...
            #         {    "control-flow-switch.amber",...

            # Get to just before the first test line, writing lines as we go.
            for line in cpp_in:
                cpp_out.write(line)
                if line.startswith("\ttests[] ="):
                    break
            cpp_out.write(cpp_in.readline())

            # Get to the point where we should insert our line.
            line = ""
            for line in cpp_in:
                if not line.startswith("		{"):
                    break
                elif line >= line_to_write:
                    break
                else:
                    cpp_out.write(line)

            # Write our line and then the previously read line.

            # Don't write the line if it already exists; idempotent.
            if line != line_to_write:
                log("Writing line: {}".format(line_to_write[:-1]))
                cpp_out.write(line_to_write)
            else:
                log("Line already exists.")
            cpp_out.write(line)

            # Write the remaining lines.
            for line in cpp_in:
                cpp_out.write(line)

    remove(cpp_file_bak)


def add_amber_test_to_must_pass(amber_test_name, must_pass_file_path):
    log("Adding the Amber test to {}".format(must_pass_file_path))

    must_pass_file_path_bak = must_pass_file_path + ".bak"
    copyfile(must_pass_file_path, must_pass_file_path_bak)

    line_to_write = "dEQP-VK.graphicsfuzz.{}\n".format(amber_test_name)

    log("Writing from {} to {}.".format(must_pass_file_path_bak, must_pass_file_path))

    with open_helper(must_pass_file_path_bak, "r") as pass_in:
        with open_helper(must_pass_file_path, "w") as pass_out:
            # Get to just before the first GraphicsFuzz test.
            line = ""
            for line in pass_in:
                if line.startswith("dEQP-VK.graphicsfuzz."):
                    break
                pass_out.write(line)

            # |line| contains an unwritten line.
            # Get to the point where we need to write line_to_write.
            while True:
                if len(line) == 0 or line >= line_to_write:
                    break
                pass_out.write(line)
                line = pass_in.readline()

            # Don't write the line if it already exists; idempotent.
            if line != line_to_write:
                log("Writing line: {}".format(line_to_write[:-1]))
                pass_out.write(line_to_write)
            else:
                log("Line already exists.")
            pass_out.write(line)

            # Write remaining lines.
            for line in pass_in:
                pass_out.write(line)

    remove(must_pass_file_path_bak)


def copyfile(source, dest):
    log("Copying {} to {}".format(source, dest))
    shutil.copyfile(source, dest)


def remove(file):
    log("Deleting {}".format(file))
    os.remove(file)


def copy_amber_test_file(vk_gl_cts, amber_test_name, input_amber_test_file_path):
    log("Copying Amber test file")

    amber_test_file_path = get_amber_test_file_path(vk_gl_cts, amber_test_name)

    check_dir_exists(os.path.dirname(amber_test_file_path))

    copyfile(input_amber_test_file_path, amber_test_file_path)


def add_amber_test(input_amber_test_file_path, vk_gl_cts):
    log('Adding Amber test "{}" to "{}"'.format(input_amber_test_file_path, vk_gl_cts))
    # E.g. "continue-and-merge"
    amber_test_name = os.path.basename(input_amber_test_file_path)
    amber_test_name = os.path.splitext(amber_test_name)[0]

    log('Using test name "{}"'.format(amber_test_name))

    copy_amber_test_file(vk_gl_cts, amber_test_name, input_amber_test_file_path)

    add_amber_test_to_cpp(vk_gl_cts, amber_test_name)

    for must_pass_file_path in MUST_PASS_PATHS:
        add_amber_test_to_must_pass(
            amber_test_name, os.path.join(vk_gl_cts, must_pass_file_path)
        )


def main(args):
    parser = argparse.ArgumentParser(
        description="A script to add Amber tests to the CTS."
    )

    parser.add_argument("vk_gl_cts", help="Path to a checkout of VK-GL-CTS")

    parser.add_argument(
        "files",
        help="One or more Amber test files (often ending in .amber_script, .amber, .vkscript)",
        nargs="+",
    )

    args = parser.parse_args(args)

    vk_gl_cts = args.vk_gl_cts
    files = args.files

    check_dir_exists(vk_gl_cts)
    check_file_exists(get_graphics_fuzz_tests_cpp_file_path(vk_gl_cts))

    for file in files:
        add_amber_test(file, vk_gl_cts)


if __name__ == "__main__":
    main(sys.argv[1:])
    sys.exit(0)