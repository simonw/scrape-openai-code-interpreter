load("//project/bazel/rules:python.bzl", "oai_py_library")

oai_py_library(
    name = "ace_tools",
    srcs = [
        "ace_tools/__init__.py",
        "setup.py",
    ],
    deps = [
        "//project/ace/applied/applied-ace-client:applied_ace_client",
        "@pypi//pandas:pkg",
        "@pypi//requests:pkg",
    ],
    data = [
        "@applied_encodings//:encodings_dir",
    ],
    imports = [
        ".",
    ],
    visibility = [
        "//visibility:public",
    ],
)
