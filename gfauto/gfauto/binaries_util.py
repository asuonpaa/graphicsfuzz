# -*- coding: utf-8 -*-

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

"""Binary utilities module.

Defines the latest binaries (name and version) that will be used by default for new fuzzing sessions.
Defines the recipes (see recipe.proto) for all built-in binaries, including old versions of binaries.
Defines BinaryManager; see below.
"""

import abc
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import attr

from gfauto import artifact_util, recipe_wrap, test_util, util
from gfauto.common_pb2 import Archive, ArchiveSet, Binary
from gfauto.gflogging import log
from gfauto.recipe_pb2 import Recipe, RecipeDownloadAndExtractArchiveSet

LATEST_GRAPHICSFUZZ_ARTIFACT = "//binaries/graphicsfuzz_v1.2.1"

GLSLANG_VALIDATOR_NAME = "glslangValidator"
SPIRV_OPT_NAME = "spirv-opt"
SPIRV_VAL_NAME = "spirv-val"
SPIRV_DIS_NAME = "spirv-dis"
SWIFT_SHADER_NAME = "swift_shader_icd"

SPIRV_OPT_NO_VALIDATE_AFTER_ALL_TAG = "no-validate-after-all"

BUILT_IN_BINARY_RECIPES_PATH_PREFIX = "//binaries"

PLATFORM_SUFFIXES_DEBUG = ["Linux_x64_Debug", "Windows_x64_Debug", "Mac_x64_Debug"]
PLATFORM_SUFFIXES_RELEASE = [
    "Linux_x64_Release",
    "Windows_x64_Release",
    "Mac_x64_Release",
]
PLATFORM_SUFFIXES_RELWITHDEBINFO = [
    "Linux_x64_RelWithDebInfo",
    "Windows_x64_RelWithDebInfo",
    "Mac_x64_RelWithDebInfo",
]

DEFAULT_BINARIES = [
    Binary(
        name="glslangValidator",
        tags=["Debug"],
        version="9866ad9195cec8f266f16191fb4ec2ce4896e5c0",
    ),
    Binary(
        name="spirv-opt",
        tags=["Debug"],
        version="4a00a80c40484a6f6f72f48c9d34943cf8f180d4",
    ),
    Binary(
        name="spirv-dis",
        tags=["Debug"],
        version="4a00a80c40484a6f6f72f48c9d34943cf8f180d4",
    ),
    Binary(
        name="spirv-val",
        tags=["Debug"],
        version="4a00a80c40484a6f6f72f48c9d34943cf8f180d4",
    ),
    Binary(
        name="swift_shader_icd",
        tags=["Debug"],
        version="a0b3a02601da8c48012a4259d335be04d00818da",
    ),
]


@attr.dataclass
class BinaryPathAndInfo:
    path: Path
    binary: Binary


class BinaryGetter(abc.ABC):
    def get_binary_path_by_name(self, name: str) -> BinaryPathAndInfo:
        pass


class BinaryNotFound(Exception):
    pass


class BinaryPathNotFound(Exception):
    def __init__(self, binary: Binary):
        super().__init__(f"Could not find binary path for binary: \n{binary}")


class BinaryManager(BinaryGetter):
    """
    Implements BinaryGetter.

    An instance of BinaryManager is the main way that code accesses binaries. BinaryManger allows certain tests and/or
    devices to override binaries by passing a list of binary versions that take priority, so the correct versions are
    always used. Plus, the current platform will used when deciding which binary to download and return.

    See the Binary proto.

    _binary_list: A list of Binary with name, version, configuration. This is used to map a binary name to a Binary.
    _resolved_paths: Binary (serialized) -> Path
    _binary_artifacts: A list of all available binary artifacts/recipes.
    """

    _binary_list: List[Binary]
    _resolved_paths: Dict[bytes, Path]
    _binary_artifacts: List[Tuple[ArchiveSet, str]]

    def __init__(
        self,
        binary_list: Optional[List[Binary]] = None,
        platform: Optional[str] = None,
        binary_artifacts_prefix: Optional[str] = BUILT_IN_BINARY_RECIPES_PATH_PREFIX,
    ):
        self._binary_list = binary_list or []
        self._resolved_paths = {}
        self._platform = platform or util.get_platform()
        self._binary_artifacts = []

        if binary_artifacts_prefix:
            self._binary_artifacts.extend(
                artifact_util.binary_artifacts_find(binary_artifacts_prefix)
            )

    @staticmethod
    def get_binary_list_from_test_metadata(test_json_path: Path) -> List[Binary]:
        test_metadata = test_util.metadata_read_from_path(test_json_path)
        result: List[Binary] = []
        if test_metadata.device:
            result.extend(test_metadata.device.binaries)
        result.extend(test_metadata.binaries)
        return result

    def get_binary_path(self, binary: Binary) -> Path:
        result = self._resolved_paths.get(binary.SerializePartialToString())
        if result:
            return result
        log(f"Finding path of binary:\n{binary}")
        binary_tags = set(binary.tags)
        binary_tags.add(self._platform)
        for (archive_set, artifact_path) in self._binary_artifacts:
            for artifact_binary in archive_set.binaries:  # type: Binary
                if artifact_binary.name != binary.name:
                    continue
                if artifact_binary.version != binary.version:
                    continue
                recipe_binary_tags = set(artifact_binary.tags)
                if not binary_tags.issubset(recipe_binary_tags):
                    continue
                artifact_util.artifact_execute_recipe_if_needed(artifact_path)
                result = artifact_util.artifact_get_inner_file_path(
                    artifact_binary.path, artifact_path
                )
                self._resolved_paths[binary.SerializePartialToString()] = result
                return result
        raise BinaryPathNotFound(binary)

    @staticmethod
    def get_binary_by_name_from_list(name: str, binary_list: List[Binary]) -> Binary:
        for binary in binary_list:
            if binary.name == name:
                return binary
        raise BinaryNotFound(
            f"Could not find binary named {name} in list:\n{binary_list}"
        )

    def get_binary_path_by_name(self, name: str) -> BinaryPathAndInfo:
        binary = self.get_binary_by_name(name)
        return BinaryPathAndInfo(self.get_binary_path(binary), binary)

    def get_binary_by_name(self, name: str) -> Binary:
        return self.get_binary_by_name_from_list(name, self._binary_list)

    def get_child_binary_manager(self, binary_list: List[Binary]) -> "BinaryManager":
        result = BinaryManager(
            binary_list + self._binary_list,
            self._platform,
            binary_artifacts_prefix=None,
        )
        # pylint: disable=protected-access; This is fine since |result| is a BinaryManager.
        result._resolved_paths = self._resolved_paths
        # pylint: disable=protected-access; This is fine since |result| is a BinaryManager.
        result._binary_artifacts = self._binary_artifacts
        return result


@attr.dataclass
class ToolNameAndPath:
    name: str
    subpath: str
    add_exe_on_windows: bool = True


def get_platform_from_platform_suffix(platform_suffix: str) -> str:
    platforms = ("Linux", "Mac", "Windows")
    for platform in platforms:
        if platform in platform_suffix:
            return platform
    raise AssertionError(f"Could not guess platform of {platform_suffix}")


def add_common_tags_from_platform_suffix(tags: List[str], platform_suffix: str) -> None:
    platform = get_platform_from_platform_suffix(platform_suffix)
    tags.append(platform)
    common_tags = ["Release", "Debug", "RelWithDebInfo", "x64"]
    for common_tag in common_tags:
        if common_tag in platform_suffix:
            tags.append(common_tag)


def _get_built_in_binary_recipe_from_build_github_repo(
    project_name: str,
    version_hash: str,
    build_version_hash: str,
    platform_suffixes: List[str],
    tools: List[ToolNameAndPath],
) -> List[recipe_wrap.RecipeWrap]:

    result: List[recipe_wrap.RecipeWrap] = []

    for platform_suffix in platform_suffixes:
        tags: List[str] = []
        add_common_tags_from_platform_suffix(tags, platform_suffix)
        binaries = [
            Binary(
                name=binary.name,
                tags=tags,
                path=(
                    f"{project_name}/{(binary.subpath + '.exe') if 'Windows' in tags and binary.add_exe_on_windows else binary.subpath}"
                ),
                version=version_hash,
            )
            for binary in tools
        ]

        result.append(
            recipe_wrap.RecipeWrap(
                f"//binaries/{project_name}_{version_hash}_{platform_suffix}",
                Recipe(
                    download_and_extract_archive_set=RecipeDownloadAndExtractArchiveSet(
                        archive_set=ArchiveSet(
                            archives=[
                                Archive(
                                    url=f"https://github.com/paulthomson/build-{project_name}/releases/download/github/paulthomson/build-{project_name}/{build_version_hash}/build-{project_name}-{build_version_hash}-{platform_suffix}.zip",
                                    output_file=f"{project_name}.zip",
                                    output_directory=project_name,
                                )
                            ],
                            binaries=binaries,
                        )
                    )
                ),
            )
        )

    return result


def _get_built_in_swift_shader_version(
    version_hash: str, build_version_hash: str
) -> List[recipe_wrap.RecipeWrap]:
    return _get_built_in_binary_recipe_from_build_github_repo(
        project_name="swiftshader",
        version_hash=version_hash,
        build_version_hash=build_version_hash,
        platform_suffixes=PLATFORM_SUFFIXES_RELEASE
        + PLATFORM_SUFFIXES_DEBUG
        + PLATFORM_SUFFIXES_RELWITHDEBINFO,
        tools=[
            ToolNameAndPath(
                name="swift_shader_icd",
                subpath="lib/vk_swiftshader_icd.json",
                add_exe_on_windows=False,
            )
        ],
    )


def _get_built_in_spirv_tools_version(
    version_hash: str, build_version_hash: str
) -> List[recipe_wrap.RecipeWrap]:
    return _get_built_in_binary_recipe_from_build_github_repo(
        project_name="SPIRV-Tools",
        version_hash=version_hash,
        build_version_hash=build_version_hash,
        platform_suffixes=PLATFORM_SUFFIXES_RELEASE + PLATFORM_SUFFIXES_DEBUG,
        tools=[
            ToolNameAndPath(name="spirv-as", subpath="bin/spirv-as"),
            ToolNameAndPath(name="spirv-dis", subpath="bin/spirv-dis"),
            ToolNameAndPath(name="spirv-opt", subpath="bin/spirv-opt"),
            ToolNameAndPath(name="spirv-val", subpath="bin/spirv-val"),
        ],
    )


def _get_built_in_glslang_version(
    version_hash: str, build_version_hash: str
) -> List[recipe_wrap.RecipeWrap]:
    return _get_built_in_binary_recipe_from_build_github_repo(
        project_name="glslang",
        version_hash=version_hash,
        build_version_hash=build_version_hash,
        platform_suffixes=PLATFORM_SUFFIXES_RELEASE + PLATFORM_SUFFIXES_DEBUG,
        tools=[
            ToolNameAndPath(name="glslangValidator", subpath="bin/glslangValidator")
        ],
    )


def get_graphics_fuzz_121() -> List[recipe_wrap.RecipeWrap]:
    return [
        recipe_wrap.RecipeWrap(
            "//binaries/graphicsfuzz_v1.2.1",
            Recipe(
                download_and_extract_archive_set=RecipeDownloadAndExtractArchiveSet(
                    archive_set=ArchiveSet(
                        archives=[
                            Archive(
                                url="https://github.com/google/graphicsfuzz/releases/download/v1.2.1/graphicsfuzz.zip",
                                output_file="graphicsfuzz.zip",
                                output_directory="graphicsfuzz",
                            )
                        ],
                        binaries=[
                            #
                            # glslangValidator
                            Binary(
                                name="glslangValidator",
                                tags=["Linux", "x64", "Release"],
                                path="graphicsfuzz/bin/Linux/glslangValidator",
                                version="40c16ec0b3ad03fc170f1369a58e7bbe662d82cd",
                            ),
                            Binary(
                                name="glslangValidator",
                                tags=["Windows", "x64", "Release"],
                                path="graphicsfuzz/bin/Windows/glslangValidator.exe",
                                version="40c16ec0b3ad03fc170f1369a58e7bbe662d82cd",
                            ),
                            Binary(
                                name="glslangValidator",
                                tags=["Mac", "x64", "Release"],
                                path="graphicsfuzz/bin/Mac/glslangValidator",
                                version="40c16ec0b3ad03fc170f1369a58e7bbe662d82cd",
                            ),
                            #
                            # spirv-opt
                            Binary(
                                name="spirv-opt",
                                tags=[
                                    "Linux",
                                    "x64",
                                    "Release",
                                    SPIRV_OPT_NO_VALIDATE_AFTER_ALL_TAG,
                                ],
                                path="graphicsfuzz/bin/Linux/spirv-opt",
                                version="a2ef7be242bcacaa9127a3ce011602ec54b2c9ed",
                            ),
                            Binary(
                                name="spirv-opt",
                                tags=[
                                    "Windows",
                                    "x64",
                                    "Release",
                                    SPIRV_OPT_NO_VALIDATE_AFTER_ALL_TAG,
                                ],
                                path="graphicsfuzz/bin/Windows/spirv-opt.exe",
                                version="a2ef7be242bcacaa9127a3ce011602ec54b2c9ed",
                            ),
                            Binary(
                                name="spirv-opt",
                                tags=[
                                    "Mac",
                                    "x64",
                                    "Release",
                                    SPIRV_OPT_NO_VALIDATE_AFTER_ALL_TAG,
                                ],
                                path="graphicsfuzz/bin/Mac/spirv-opt",
                                version="a2ef7be242bcacaa9127a3ce011602ec54b2c9ed",
                            ),
                            #
                            # spirv-dis
                            Binary(
                                name="spirv-dis",
                                tags=["Linux", "x64", "Release"],
                                path="graphicsfuzz/bin/Linux/spirv-dis",
                                version="a2ef7be242bcacaa9127a3ce011602ec54b2c9ed",
                            ),
                            Binary(
                                name="spirv-dis",
                                tags=["Windows", "x64", "Release"],
                                path="graphicsfuzz/bin/Windows/spirv-dis.exe",
                                version="a2ef7be242bcacaa9127a3ce011602ec54b2c9ed",
                            ),
                            Binary(
                                name="spirv-dis",
                                tags=["Mac", "x64", "Release"],
                                path="graphicsfuzz/bin/Mac/spirv-dis",
                                version="a2ef7be242bcacaa9127a3ce011602ec54b2c9ed",
                            ),
                            #
                            # spirv-as
                            Binary(
                                name="spirv-as",
                                tags=["Linux", "x64", "Release"],
                                path="graphicsfuzz/bin/Linux/spirv-as",
                                version="a2ef7be242bcacaa9127a3ce011602ec54b2c9ed",
                            ),
                            Binary(
                                name="spirv-as",
                                tags=["Windows", "x64", "Release"],
                                path="graphicsfuzz/bin/Windows/spirv-as.exe",
                                version="a2ef7be242bcacaa9127a3ce011602ec54b2c9ed",
                            ),
                            Binary(
                                name="spirv-as",
                                tags=["Mac", "x64", "Release"],
                                path="graphicsfuzz/bin/Mac/spirv-as",
                                version="a2ef7be242bcacaa9127a3ce011602ec54b2c9ed",
                            ),
                            #
                            # spirv-val
                            Binary(
                                name="spirv-val",
                                tags=["Linux", "x64", "Release"],
                                path="graphicsfuzz/bin/Linux/spirv-val",
                                version="a2ef7be242bcacaa9127a3ce011602ec54b2c9ed",
                            ),
                            Binary(
                                name="spirv-val",
                                tags=["Windows", "x64", "Release"],
                                path="graphicsfuzz/bin/Windows/spirv-val.exe",
                                version="a2ef7be242bcacaa9127a3ce011602ec54b2c9ed",
                            ),
                            Binary(
                                name="spirv-val",
                                tags=["Mac", "x64", "Release"],
                                path="graphicsfuzz/bin/Mac/spirv-val",
                                version="a2ef7be242bcacaa9127a3ce011602ec54b2c9ed",
                            ),
                        ],
                    )
                )
            ),
        )
    ]


BUILT_IN_BINARY_RECIPES: List[recipe_wrap.RecipeWrap] = (
    _get_built_in_spirv_tools_version(
        version_hash="4a00a80c40484a6f6f72f48c9d34943cf8f180d4",
        build_version_hash="422f2fe0f0f32494fa687a12ba343d24863b330a",
    )
    + _get_built_in_glslang_version(
        version_hash="9866ad9195cec8f266f16191fb4ec2ce4896e5c0",
        build_version_hash="1586e566f4949b1957e7c32454cbf27e501ed632",
    )
    + _get_built_in_swift_shader_version(
        version_hash="a0b3a02601da8c48012a4259d335be04d00818da",
        build_version_hash="08fb8d429272ef8eedb4d610943b9fe59d336dc6",
    )
    + get_graphics_fuzz_121()
    + _get_built_in_spirv_tools_version(
        version_hash="1c1e749f0b51603032ed573acb5ee4cd6fee8d01",
        build_version_hash="7663d620a7fbdccb330d2baec138d0e3e096457c",
    )
)