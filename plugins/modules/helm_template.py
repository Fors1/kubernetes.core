#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright: (c) 2021, Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type


DOCUMENTATION = r"""

module: helm_template

short_description: Render chart templates

author:
  - Mike Graves (@gravesm)

description:
  - Render chart templates to an output directory or as text of concatenated yaml documents.

options:
  binary_path:
    description:
      - The path of a helm binary to use.
    required: false
    type: path
  chart_ref:
    description:
      - Chart reference with repo prefix, for example, C(nginx-stable/nginx-ingress).
      - Path to a packaged chart.
      - Path to an unpacked chart directory.
      - Absolute URL.
    required: true
    type: path
  chart_repo_url:
    description:
      - Chart repository URL where the requested chart is located.
    required: false
    type: str
  chart_version:
    description:
      - Chart version to use. If this is not specified, the latest version is installed.
    required: false
    type: str
  dependency_update:
    description:
      - Run helm dependency update before the operation.
      - The I(dependency_update) option require the add of C(dependencies) block in C(Chart.yaml/requirements.yaml) file.
      - For more information please visit U(https://helm.sh/docs/helm/helm_dependency/)
    default: false
    type: bool
    aliases: [ dep_up ]
    version_added: "2.4.0"
  disable_hook:
    description:
      - Prevent hooks from running during install.
    default: False
    type: bool
    version_added: 2.4.0
  include_crds:
    description:
      - Include custom resource descriptions in rendered templates.
    required: false
    type: bool
    default: false
  output_dir:
    description:
      - Output directory where templates will be written.
      - If the directory already exists, it will be overwritten.
    required: false
    type: path
  release_name:
    description:
      - Release name to use in rendered templates.
    required: false
    aliases: [ name ]
    type: str
    version_added: 2.4.0
  release_namespace:
    description:
      - namespace scope for this request.
    required: false
    type: str
    version_added: 2.4.0
  release_values:
    description:
        - Values to pass to chart.
    required: false
    default: {}
    aliases: [ values ]
    type: dict
  show_only:
    description:
        - Only show manifests rendered from the given templates.
    required: false
    type: list
    elements: str
    version_added: 2.4.0
  values_files:
    description:
        - Value files to pass to chart.
        - Paths will be read from the target host's filesystem, not the host running ansible.
        - I(values_files) option is evaluated before I(values) option if both are used.
        - Paths are evaluated in the order the paths are specified.
    required: false
    default: []
    type: list
    elements: str
  update_repo_cache:
    description:
      - Run C(helm repo update) before the operation. Can be run as part of the template generation or as a separate step.
    default: false
    type: bool
"""

EXAMPLES = r"""
- name: Render templates to specified directory
  kubernetes.core.helm_template:
    chart_ref: stable/prometheus
    output_dir: mycharts

- name: Render templates
  kubernetes.core.helm_template:
    chart_ref: stable/prometheus
  register: result

- name: Write templates to file
  copy:
    dest: myfile.yaml
    content: "{{ result.stdout }}"

- name: Render MutatingWebhooksConfiguration for revision tag "canary", rev "1-13-0"
  kubernetes.core.helm_template:
    chart_ref: istio/istiod
    chart_version: "1.13.0"
    release_namespace: "istio-system"
    show_only:
      - "templates/revision-tags.yaml"
    release_values:
      revision: "1-13-0"
      revisionTags:
        - "canary"
  register: result

- name: Write templates to file
  copy:
    dest: myfile.yaml
    content: "{{ result.stdout }}"
"""

RETURN = r"""
stdout:
  type: str
  description: Full C(helm) command stdout. If no I(output_dir) has been provided this will contain the rendered templates as concatenated yaml documents.
  returned: always
  sample: ''
stderr:
  type: str
  description: Full C(helm) command stderr, in case you want to display it or examine the event log.
  returned: always
  sample: ''
command:
  type: str
  description: Full C(helm) command run by this module, in case you want to re-run the command outside the module or debug a problem.
  returned: always
  sample: helm template --output-dir mychart nginx-stable/nginx-ingress
"""

import tempfile
import traceback

try:
    import yaml

    IMP_YAML = True
    IMP_YAML_ERR = None
except ImportError:
    IMP_YAML_ERR = traceback.format_exc()
    IMP_YAML = False

from ansible.module_utils.basic import AnsibleModule, missing_required_lib
from ansible_collections.kubernetes.core.plugins.module_utils.helm import (
    run_helm,
    get_helm_binary,
)


def template(
    cmd,
    chart_ref,
    chart_repo_url=None,
    chart_version=None,
    dependency_update=None,
    disable_hook=None,
    output_dir=None,
    show_only=None,
    release_name=None,
    release_namespace=None,
    release_values=None,
    values_files=None,
    include_crds=False,
):
    cmd += " template "

    if release_name:
        cmd += release_name + " "

    cmd += chart_ref

    if dependency_update:
        cmd += " --dependency-update"

    if chart_repo_url:
        cmd += " --repo=" + chart_repo_url

    if chart_version:
        cmd += " --version=" + chart_version

    if disable_hook:
        cmd += " --no-hooks"

    if output_dir:
        cmd += " --output-dir=" + output_dir

    if show_only:
        for template in show_only:
            cmd += " -s " + template

    if values_files:
        for values_file in values_files:
            cmd += " -f=" + values_file

    if release_namespace:
        cmd += " -n " + release_namespace

    if release_values:
        fd, path = tempfile.mkstemp(suffix=".yml")
        with open(path, "w") as yaml_file:
            yaml.dump(release_values, yaml_file, default_flow_style=False)
        cmd += " -f=" + path

    if include_crds:
        cmd += " --include-crds"

    return cmd


def main():
    module = AnsibleModule(
        argument_spec=dict(
            binary_path=dict(type="path"),
            chart_ref=dict(type="path", required=True),
            chart_repo_url=dict(type="str"),
            chart_version=dict(type="str"),
            dependency_update=dict(type="bool", default=False, aliases=["dep_up"]),
            disable_hook=dict(type="bool", default=False),
            include_crds=dict(type="bool", default=False),
            release_name=dict(type="str", aliases=["name"]),
            output_dir=dict(type="path"),
            release_namespace=dict(type="str"),
            release_values=dict(type="dict", default={}, aliases=["values"]),
            show_only=dict(type="list", default=[], elements="str"),
            values_files=dict(type="list", default=[], elements="str"),
            update_repo_cache=dict(type="bool", default=False),
        ),
        supports_check_mode=True,
    )

    check_mode = module.check_mode
    chart_ref = module.params.get("chart_ref")
    chart_repo_url = module.params.get("chart_repo_url")
    chart_version = module.params.get("chart_version")
    dependency_update = module.params.get("dependency_update")
    disable_hook = module.params.get("disable_hook")
    include_crds = module.params.get("include_crds")
    release_name = module.params.get("release_name")
    output_dir = module.params.get("output_dir")
    show_only = module.params.get("show_only")
    release_namespace = module.params.get("release_namespace")
    release_values = module.params.get("release_values")
    values_files = module.params.get("values_files")
    update_repo_cache = module.params.get("update_repo_cache")

    if not IMP_YAML:
        module.fail_json(msg=missing_required_lib("yaml"), exception=IMP_YAML_ERR)

    helm_cmd = get_helm_binary(module)

    if update_repo_cache:
        update_cmd = helm_cmd + " repo update"
        run_helm(module, update_cmd)

    tmpl_cmd = template(
        helm_cmd,
        chart_ref,
        dependency_update=dependency_update,
        chart_repo_url=chart_repo_url,
        chart_version=chart_version,
        disable_hook=disable_hook,
        release_name=release_name,
        output_dir=output_dir,
        release_namespace=release_namespace,
        release_values=release_values,
        show_only=show_only,
        values_files=values_files,
        include_crds=include_crds,
    )

    if not check_mode:
        rc, out, err = run_helm(module, tmpl_cmd)
    else:
        out = err = ""
        rc = 0

    module.exit_json(
        failed=False, changed=True, command=tmpl_cmd, stdout=out, stderr=err, rc=rc
    )


if __name__ == "__main__":
    main()
