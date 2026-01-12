#!/usr/bin/env python
import argparse
import dataclasses
import fnmatch
from enum import Enum
import json
import logging
import os
import re
from typing import Optional

logger = logging.getLogger(__name__)

class JobOs(Enum):
    UbuntuLatest = "ubuntu-latest"

class SdlPlatform(Enum):
    Switch = "switch"

@dataclasses.dataclass(slots=True)
class JobSpec:
    name: str
    os: JobOs
    platform: SdlPlatform
    artifact: Optional[str]
    container: Optional[str] = None
    no_cmake: bool = False
    lean: bool = False
    clang_cl: bool = False
    gdk: bool = False
    more_hard_deps: bool = False

JOB_SPECS = {
    "msys2-mingw32": JobSpec(name="Windows (msys2, mingw32)",               os=JobOs.WindowsLatest,     platform=SdlPlatform.Msys2,       artifact="SDL-mingw32",            msys2_platform=Msys2Platform.Mingw32, ),
    "msys2-mingw64": JobSpec(name="Windows (msys2, mingw64)",               os=JobOs.WindowsLatest,     platform=SdlPlatform.Msys2,       artifact="SDL-mingw64",            msys2_platform=Msys2Platform.Mingw64, ),
    "msys2-clang64": JobSpec(name="Windows (msys2, clang64)",               os=JobOs.WindowsLatest,     platform=SdlPlatform.Msys2,       artifact="SDL-mingw64-clang",      msys2_platform=Msys2Platform.Clang64, ),
    "msys2-ucrt64": JobSpec(name="Windows (msys2, ucrt64)",                 os=JobOs.WindowsLatest,     platform=SdlPlatform.Msys2,       artifact="SDL-mingw64-ucrt",       msys2_platform=Msys2Platform.Ucrt64, ),
    "msvc-x64": JobSpec(name="Windows (MSVC, x64)",                         os=JobOs.WindowsLatest,     platform=SdlPlatform.Msvc,        artifact="SDL-VC-x64",             msvc_arch=MsvcArch.X64,   msvc_project="VisualC/SDL.sln", ),
    "msvc-x86": JobSpec(name="Windows (MSVC, x86)",                         os=JobOs.WindowsLatest,     platform=SdlPlatform.Msvc,        artifact="SDL-VC-x86",             msvc_arch=MsvcArch.X86,   msvc_project="VisualC/SDL.sln", ),
    "msvc-clang-x64": JobSpec(name="Windows (MSVC, clang-cl x64)",          os=JobOs.WindowsLatest,     platform=SdlPlatform.Msvc,        artifact="SDL-clang-cl-x64",       msvc_arch=MsvcArch.X64,   clang_cl=True, ),
    "msvc-clang-x86": JobSpec(name="Windows (MSVC, clang-cl x86)",          os=JobOs.WindowsLatest,     platform=SdlPlatform.Msvc,        artifact="SDL-clang-cl-x86",       msvc_arch=MsvcArch.X86,   clang_cl=True, ),
    "msvc-arm64": JobSpec(name="Windows (MSVC, ARM64)",                     os=JobOs.WindowsLatest,     platform=SdlPlatform.Msvc,        artifact="SDL-VC-arm64",           msvc_arch=MsvcArch.Arm64, ),
    "msvc-gdk-x64": JobSpec(name="GDK (MSVC, x64)",                         os=JobOs.WindowsLatest,     platform=SdlPlatform.Msvc,        artifact="SDL-VC-GDK",             msvc_arch=MsvcArch.X64,   msvc_project="VisualC-GDK/SDL.sln", gdk=True, no_cmake=True, ),
    "ubuntu-22.04": JobSpec(name="Ubuntu 22.04",                            os=JobOs.Ubuntu22_04,       platform=SdlPlatform.Linux,       artifact="SDL-ubuntu22.04", ),
    "ubuntu-latest": JobSpec(name="Ubuntu (latest)",                        os=JobOs.UbuntuLatest,      platform=SdlPlatform.Linux,       artifact="SDL-ubuntu-latest", ),
    "ubuntu-24.04-arm64": JobSpec(name="Ubuntu 24.04 (ARM64)",              os=JobOs.Ubuntu24_04_arm,   platform=SdlPlatform.Linux,       artifact="SDL-ubuntu24.04-arm64", ),
    "steamrt3": JobSpec(name="Steam Linux Runtime 3.0 (x86_64)",            os=JobOs.UbuntuLatest,      platform=SdlPlatform.Linux,       artifact="SDL-steamrt3",           container="registry.gitlab.steamos.cloud/steamrt/sniper/sdk:latest" ),
    "steamrt3-arm64": JobSpec(name="Steam Linux Runtime 3.0 (arm64)",       os=JobOs.Ubuntu24_04_arm,   platform=SdlPlatform.Linux,       artifact="SDL-steamrt3-arm64",     container="registry.gitlab.steamos.cloud/steamrt/sniper/sdk/arm64:latest" ),
    "steamrt4": JobSpec(name="Steam Linux Runtime 4.0 (x86_64)",            os=JobOs.UbuntuLatest,      platform=SdlPlatform.Linux,       artifact="SDL-steamrt4",           container="registry.gitlab.steamos.cloud/steamrt/steamrt4/sdk:latest", more_hard_deps = True, ),
    "steamrt4-arm64": JobSpec(name="Steam Linux Runtime 4.0 (arm64)",       os=JobOs.Ubuntu24_04_arm,   platform=SdlPlatform.Linux,       artifact="SDL-steamrt4-arm64",     container="registry.gitlab.steamos.cloud/steamrt/steamrt4/sdk/arm64:latest", more_hard_deps = True, ),
    "ubuntu-intel-icx": JobSpec(name="Ubuntu 22.04 (Intel oneAPI)",         os=JobOs.Ubuntu22_04,       platform=SdlPlatform.Linux,       artifact="SDL-ubuntu22.04-oneapi", intel=IntelCompiler.Icx, ),
    "ubuntu-intel-icc": JobSpec(name="Ubuntu 22.04 (Intel Compiler)",       os=JobOs.Ubuntu22_04,       platform=SdlPlatform.Linux,       artifact="SDL-ubuntu22.04-icc",    intel=IntelCompiler.Icc, ),
    "macos-framework-x64":  JobSpec(name="MacOS (Framework) (x64)",         os=JobOs.Macos14,           platform=SdlPlatform.MacOS,       artifact="SDL-macos-framework",    apple_framework=True,  apple_archs={AppleArch.Aarch64, AppleArch.X86_64, }, xcode=True, ),
    "macos-framework-arm64": JobSpec(name="MacOS (Framework) (arm64)",      os=JobOs.MacosLatest,       platform=SdlPlatform.MacOS,       artifact=None,                     apple_framework=True,  apple_archs={AppleArch.Aarch64, AppleArch.X86_64, }, ),
    "macos-26-framework-arm64": JobSpec(name="MacOS 26 (Framework) (arm64)",os=JobOs.Macos26,           platform=SdlPlatform.MacOS,       artifact=None,                     apple_framework=True,  apple_archs={AppleArch.Aarch64, AppleArch.X86_64, }, ),
    "macos-gnu-arm64": JobSpec(name="MacOS (GNU prefix)",                   os=JobOs.MacosLatest,       platform=SdlPlatform.MacOS,       artifact="SDL-macos-arm64-gnu",    apple_framework=False, apple_archs={AppleArch.Aarch64, },  ),
    "ios": JobSpec(name="iOS (CMake & xcode)",                              os=JobOs.MacosLatest,       platform=SdlPlatform.Ios,         artifact="SDL-ios-arm64",          xcode=True, ),
    "tvos": JobSpec(name="tvOS (CMake & xcode)",                            os=JobOs.MacosLatest,       platform=SdlPlatform.Tvos,        artifact="SDL-tvos-arm64",         xcode=True, ),
    "android-cmake": JobSpec(name="Android (CMake)",                        os=JobOs.UbuntuLatest,      platform=SdlPlatform.Android,     artifact="SDL-android-arm64",      android_abi="arm64-v8a", android_arch="aarch64", android_platform=23, ),
    "android-cmake-lean": JobSpec(name="Android (CMake, lean)",             os=JobOs.UbuntuLatest,      platform=SdlPlatform.Android,     artifact="SDL-lean-android-arm64", android_abi="arm64-v8a", android_arch="aarch64", android_platform=23, lean=True, ),
    "android-mk": JobSpec(name="Android (Android.mk)",                      os=JobOs.UbuntuLatest,      platform=SdlPlatform.Android,     artifact=None,                     no_cmake=True, android_mk=True, ),
    "android-gradle": JobSpec(name="Android (Gradle)",                      os=JobOs.UbuntuLatest,      platform=SdlPlatform.Android,     artifact=None,                     no_cmake=True, android_gradle=True, ),
    "emscripten": JobSpec(name="Emscripten",                                os=JobOs.UbuntuLatest,      platform=SdlPlatform.Emscripten,  artifact="SDL-emscripten", ),
    "haiku": JobSpec(name="Haiku",                                          os=JobOs.UbuntuLatest,      platform=SdlPlatform.Haiku,       artifact="SDL-haiku-x64",          container="ghcr.io/haiku/cross-compiler:x86_64-r1beta5", ),
    "loongarch64": JobSpec(name="LoongArch64",                              os=JobOs.UbuntuLatest,      platform=SdlPlatform.LoongArch64, artifact="SDL-loongarch64", ),
    "n3ds": JobSpec(name="Nintendo 3DS",                                    os=JobOs.UbuntuLatest,      platform=SdlPlatform.N3ds,        artifact="SDL-n3ds",               container="devkitpro/devkitarm:latest", ),
    "ppc": JobSpec(name="PowerPC",                                          os=JobOs.UbuntuLatest,      platform=SdlPlatform.PowerPC,     artifact="SDL-ppc",                container="dockcross/linux-ppc:latest", ),
    "ppc64": JobSpec(name="PowerPC64",                                      os=JobOs.UbuntuLatest,      platform=SdlPlatform.PowerPC64,   artifact="SDL-ppc64le",            container="dockcross/linux-ppc64le:latest", ),
    "ps2": JobSpec(name="Sony PlayStation 2",                               os=JobOs.UbuntuLatest,      platform=SdlPlatform.Ps2,         artifact="SDL-ps2",                container="ps2dev/ps2dev:latest", ),
    "psp": JobSpec(name="Sony PlayStation Portable",                        os=JobOs.UbuntuLatest,      platform=SdlPlatform.Psp,         artifact="SDL-psp",                container="pspdev/pspdev:latest", ),
    "vita-pib": JobSpec(name="Sony PlayStation Vita (GLES w/ pib)",         os=JobOs.UbuntuLatest,      platform=SdlPlatform.Vita,        artifact="SDL-vita-pib",           container="vitasdk/vitasdk:latest", vita_gles=VitaGLES.Pib,  ),
    "vita-pvr": JobSpec(name="Sony PlayStation Vita (GLES w/ PVR_PSP2)",    os=JobOs.UbuntuLatest,      platform=SdlPlatform.Vita,        artifact="SDL-vita-pvr",           container="vitasdk/vitasdk:latest", vita_gles=VitaGLES.Pvr, ),
    "riscos": JobSpec(name="RISC OS",                                       os=JobOs.UbuntuLatest,      platform=SdlPlatform.Riscos,      artifact="SDL-riscos",             container="riscosdotinfo/riscos-gccsdk-4.7:latest", ),
    "netbsd": JobSpec(name="NetBSD",                                        os=JobOs.UbuntuLatest,      platform=SdlPlatform.NetBSD,      artifact="SDL-netbsd-x64", ),
    "openbsd": JobSpec(name="OpenBSD",                                      os=JobOs.UbuntuLatest,      platform=SdlPlatform.OpenBSD,     artifact="SDL-openbsd-x64", ),
    "freebsd": JobSpec(name="FreeBSD",                                      os=JobOs.UbuntuLatest,      platform=SdlPlatform.FreeBSD,     artifact="SDL-freebsd-x64", ),
    "ngage": JobSpec(name="N-Gage",                                         os=JobOs.WindowsLatest,     platform=SdlPlatform.NGage,       artifact="SDL-ngage", ),
    "switch": JobSpec(name="Nintendo Switch",                               os=JobOs.UbuntuLatest,      platform=SdlPlatform.Switch,      artifact="SDL-switch",             container="devkitpro/devkita64:latest", ),
}


class StaticLibType(Enum):
    A = "libSDL3.a"

@dataclasses.dataclass(slots=True)
class JobDetails:
    name: str
    key: str
    os: str
    platform: str
    artifact: str
    no_cmake: bool
    ccache: bool = False
    build_tests: bool = True
    container: str = ""
    cmake_build_type: str = "RelWithDebInfo"
    shell: str = "sh"
    sudo: str = "sudo"
    cmake_config_emulator: str = ""
    apt_packages: list[str] = dataclasses.field(default_factory=list)
    cmake_toolchain_file: str = ""
    cmake_arguments: list[str] = dataclasses.field(default_factory=list)
    cmake_generator: str = "Ninja"
    cmake_build_arguments: list[str] = dataclasses.field(default_factory=list)
    clang_tidy: bool = True
    cppflags: list[str] = dataclasses.field(default_factory=list)
    cc: str = ""
    cxx: str = ""
    cflags: list[str] = dataclasses.field(default_factory=list)
    cxxflags: list[str] = dataclasses.field(default_factory=list)
    ldflags: list[str] = dataclasses.field(default_factory=list)
    pollute_directories: list[str] = dataclasses.field(default_factory=list)
    use_cmake: bool = True
    shared: bool = True
    static: bool = True
    static_lib: Optional[StaticLibType] = None
    run_tests: bool = True
    test_pkg_config: bool = True
    cc_from_cmake: bool = False
    source_cmd: str = ""
    pretest_cmd: str = ""
    minidump: bool = False
    werror: bool = True
    setup_ninja: bool = False
    setup_libusb_arch: str = ""
    cpactions: bool = False
    setup_gdk_folder: str = ""
    cpactions_os: str = ""
    cpactions_version: str = ""
    cpactions_arch: str = ""
    cpactions_setup_cmd: str = ""
    cpactions_install_cmd: str = ""
    setup_vita_gles_type: str = ""
    check_sources: bool = False
    setup_python: bool = False
    pypi_packages: list[str] = dataclasses.field(default_factory=list)
    setup_gage_sdk_path: str = ""
    binutils_strings: str = "strings"

    def to_workflow(self, enable_artifacts: bool) -> dict[str, str|bool]:
        data = {
            "name": self.name,
            "key": self.key,
            "os": self.os,
            "ccache": self.ccache,
            "container": self.container if self.container else "",
            "platform": self.platform,
            "artifact": self.artifact,
            "enable-artifacts": enable_artifacts,
            "shell": self.shell,
            "apt-packages": my_shlex_join(self.apt_packages),
            "test-pkg-config": self.test_pkg_config,
            "pollute-directories": my_shlex_join(self.pollute_directories),
            "no-cmake": self.no_cmake,
            "build-tests": self.build_tests,
            "source-cmd": self.source_cmd,
            "pretest-cmd": self.pretest_cmd,
            "cmake-config-emulator": self.cmake_config_emulator,
            "cc": self.cc,
            "cxx": self.cxx,
            "cflags": my_shlex_join(self.cppflags + self.cflags),
            "cxxflags": my_shlex_join(self.cppflags + self.cxxflags),
            "ldflags": my_shlex_join(self.ldflags),
            "cmake-generator": self.cmake_generator,
            "cmake-toolchain-file": self.cmake_toolchain_file,
            "clang-tidy": self.clang_tidy,
            "cmake-arguments": my_shlex_join(self.cmake_arguments),
            "cmake-build-arguments": my_shlex_join(self.cmake_build_arguments),
            "shared": self.shared,
            "static": self.static,
            "static-lib": self.static_lib.value if self.static_lib else None,
            "cmake-build-type": self.cmake_build_type,
            "run-tests": self.run_tests,
            "werror": self.werror,
            "sudo": self.sudo,
            "setup-ninja": self.setup_ninja,
            "setup-libusb-arch": self.setup_libusb_arch,
            "cc-from-cmake": self.cc_from_cmake,
            "cpactions": self.cpactions,
            "cpactions-os": self.cpactions_os,
            "cpactions-version": self.cpactions_version,
            "cpactions-arch": self.cpactions_arch,
            "cpactions-setup-cmd": self.cpactions_setup_cmd,
            "cpactions-install-cmd": self.cpactions_install_cmd,
            "setup-gdk-folder": self.setup_gdk_folder,
            "check-sources": self.check_sources,
            "setup-python": self.setup_python,
            "pypi-packages": my_shlex_join(self.pypi_packages),
            "binutils-strings": self.binutils_strings,
        }
        return {k: v for k, v in data.items() if v != ""}


def my_shlex_join(s):
    def escape(s):
        if s[:1] == "'" and s[-1:] == "'":
            return s
        if set(s).intersection(set("; \t")):
            return f'"{s}"'
        return s

    return " ".join(escape(s))


def spec_to_job(spec: JobSpec, key: str, trackmem_symbol_names: bool) -> JobDetails:
    job = JobDetails(
        name=spec.name,
        key=key,
        os=spec.os.value,
        artifact=spec.artifact or "",
        container=spec.container or "",
        platform=spec.platform.value,
        sudo="sudo",
        no_cmake=spec.no_cmake,
    )
    if job.os.startswith("ubuntu"):
        job.apt_packages.extend([
            "ninja-build",
            "pkg-config",
        ])
    pretest_cmd = []
    if trackmem_symbol_names:
        pretest_cmd.append("export SDL_TRACKMEM_SYMBOL_NAMES=1")
    else:
        pretest_cmd.append("export SDL_TRACKMEM_SYMBOL_NAMES=0")
    fpic = None
    build_parallel = True
    if spec.lean:
        job.cppflags.append("-DSDL_LEAN_AND_MEAN=1")
    match spec.platform:
        case SdlPlatform.Switch:
            job.cmake_generator = "Unix Makefiles"
            job.cmake_build_arguments.append("-j$(nproc)")
            job.cmake_arguments.extend((
                "-DEGL_NO_PLATFORM_SPECIFIC_TYPES=true",
            ))
            job.ccache = False
            job.shared = False
            job.apt_packages = []
            job.clang_tidy = False
            job.run_tests = False
            job.cc_from_cmake = True
            job.cmake_toolchain_file = "${DEVKITPRO}/cmake/Switch.cmake"
            job.binutils_strings = "/opt/devkitpro/devkitA64/bin/aarch64-none-elf-strings"
            job.static_lib = StaticLibType.A
        case _:
            raise ValueError(f"Unsupported platform={spec.platform}")

    if "ubuntu" in spec.name.lower():
        job.check_sources = True
        job.setup_python = True

    if job.ccache:
        job.cmake_arguments.extend((
            "-DCMAKE_C_COMPILER_LAUNCHER=ccache",
            "-DCMAKE_CXX_COMPILER_LAUNCHER=ccache",
        ))
    if not build_parallel:
        job.cmake_build_arguments.append("-j1")
    if job.cflags or job.cppflags:
        job.cmake_arguments.append(f"-DCMAKE_C_FLAGS=\"{my_shlex_join(job.cflags + job.cppflags)}\"")
    if job.cxxflags or job.cppflags:
        job.cmake_arguments.append(f"-DCMAKE_CXX_FLAGS=\"{my_shlex_join(job.cxxflags + job.cppflags)}\"")
    if job.ldflags:
        job.cmake_arguments.append(f"-DCMAKE_SHARED_LINKER_FLAGS=\"{my_shlex_join(job.ldflags)}\"")
        job.cmake_arguments.append(f"-DCMAKE_EXE_LINKER_FLAGS=\"{my_shlex_join(job.ldflags)}\"")
    job.pretest_cmd = "\n".join(pretest_cmd)
    def tf(b):
        return "ON" if b else "OFF"

    if fpic is not None:
        job.cmake_arguments.append(f"-DCMAKE_POSITION_INDEPENDENT_CODE={tf(fpic)}")

    if job.no_cmake:
        job.cmake_arguments = []

    return job


def spec_to_platform(spec: JobSpec, key: str, enable_artifacts: bool, trackmem_symbol_names: bool) -> dict[str, str|bool]:
    logger.info("spec=%r", spec)
    job = spec_to_job(spec, key=key, trackmem_symbol_names=trackmem_symbol_names)
    logger.info("job=%r", job)
    platform = job.to_workflow(enable_artifacts=enable_artifacts)
    logger.info("platform=%r", platform)
    return platform


def main():
    parser = argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument("--github-variable-prefix", default="platforms")
    parser.add_argument("--github-ci", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--commit-message-file")
    parser.add_argument("--no-artifact", dest="enable_artifacts", action="store_false")
    parser.add_argument("--trackmem-symbol-names", dest="trackmem_symbol_names", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING)

    remaining_keys = set(JOB_SPECS.keys())

    all_level_keys = (
        # Level 1
        (
            "switch",
        ),
    )

    filters = []
    if args.commit_message_file:
        with open(args.commit_message_file, "r") as f:
            commit_message = f.read()
            for m in re.finditer(r"\[sdl-ci-filter (.*)]", commit_message, flags=re.M):
                filters.append(m.group(1).strip(" \t\n\r\t'\""))

            if re.search(r"\[sdl-ci-artifacts?]", commit_message, flags=re.M):
                args.enable_artifacts = True

            if re.search(r"\[sdl-ci-(full-)?trackmem(-symbol-names)?]", commit_message, flags=re.M):
                args.trackmem_symbol_names = True

    if not filters:
        filters.append("*")

    logger.info("filters: %r", filters)

    all_level_platforms = {}

    all_platforms = {key: spec_to_platform(spec, key=key, enable_artifacts=args.enable_artifacts, trackmem_symbol_names=args.trackmem_symbol_names) for key, spec in JOB_SPECS.items()}

    for level_i, level_keys in enumerate(all_level_keys, 1):
        level_key = f"level{level_i}"
        logger.info("Level %d: keys=%r", level_i, level_keys)
        assert all(k in remaining_keys for k in level_keys)
        level_platforms = tuple(all_platforms[key] for key in level_keys)
        remaining_keys.difference_update(level_keys)
        all_level_platforms[level_key] = level_platforms
        logger.info("=" * 80)

    logger.info("Keys before filter: %r", remaining_keys)

    filtered_remaining_keys = set()
    for filter in filters:
        filtered_remaining_keys.update(fnmatch.filter(remaining_keys, filter))

    logger.info("Keys after filter: %r", filtered_remaining_keys)

    remaining_keys = filtered_remaining_keys

    logger.info("Remaining: %r", remaining_keys)
    all_level_platforms["others"] = tuple(all_platforms[key] for key in remaining_keys)

    if args.github_ci:
        for level, platforms in all_level_platforms.items():
            platforms_json = json.dumps(platforms)
            txt = f"{args.github_variable_prefix}-{level}={platforms_json}"
            logger.info("%s", txt)
            if "GITHUB_OUTPUT" in os.environ:
                with open(os.environ["GITHUB_OUTPUT"], "a") as f:
                    f.write(txt)
                    f.write("\n")
            else:
                logger.warning("GITHUB_OUTPUT not defined")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
