#!/bin/bash
# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

DEPLOY_DIR="$(dirname "$(readlink -f "$0")")"
FACTORY_DIR="$(readlink -f "${DEPLOY_DIR}/..")"
APPENGINE_DIR="${FACTORY_DIR}/py/hwid/service/appengine"
HW_VERIFIER_DIR="${FACTORY_DIR}/../../platform2/hardware_verifier/proto"
RT_PROBE_DIR="${FACTORY_DIR}/../../platform2/system_api/dbus/runtime_probe"
TEST_DIR="${APPENGINE_DIR}/test"
PLATFORM_DIR="$(dirname ${FACTORY_DIR})"
REGIONS_DIR="$(readlink -f "${FACTORY_DIR}/../../platform2/regions")"
TEMP_DIR="${FACTORY_DIR}/build/hwid"
DEPLOYMENT_PROD="prod"
DEPLOYMENT_STAGING="staging"
DEPLOYMENT_LOCAL="local"
DEPLOYMENT_E2E="e2e"
ENDPOINTS_SUFFIX=".appspot.com"
FACTORY_PRIVATE_DIR="${FACTORY_DIR}/../factory-private"
CLOUDSDK_APP_CLOUD_BUILD_TIMEOUT=1800

. "${FACTORY_DIR}/devtools/mk/common.sh" || exit 1
. "${FACTORY_PRIVATE_DIR}/config/hwid/service/appengine/config.sh" || exit 1

# Following variables will be assigned by `load_config <DEPLOYMENT_TYPE>`
GCP_PROJECT=

check_docker() {
  if ! type docker >/dev/null 2>&1; then
    die "Docker not installed, abort."
  fi
  DOCKER="docker"
  if [ "$(id -un)" != "root" ]; then
    if ! echo "begin $(id -Gn) end" | grep -q " docker "; then
      echo "You are neither root nor in the docker group,"
      echo "so you'll be asked for root permission..."
      DOCKER="sudo docker"
    fi
  fi

  # Check Docker version
  local docker_version="$(${DOCKER} version --format '{{.Server.Version}}' \
                          2>/dev/null)"
  if [ -z "${docker_version}" ]; then
    # Old Docker (i.e., 1.6.2) does not support --format.
    docker_version="$(${DOCKER} version | sed -n 's/Server version: //p')"
  fi
  local error_message=""
  error_message+="Require Docker version >= ${DOCKER_VERSION} but you have "
  error_message+="${docker_version}"
  local required_version=(${DOCKER_VERSION//./ })
  local current_version=(${docker_version//./ })
  for ((i = 0; i < ${#required_version[@]}; ++i)); do
    if (( ${#current_version[@]} <= i )); then
      die "${error_message}"  # the current version array is not long enough
    elif (( ${required_version[$i]} < ${current_version[$i]} )); then
      break
    elif (( ${required_version[$i]} > ${current_version[$i]} )); then
      die "${error_message}"
    fi
  done
}

check_gcloud() {
  if ! type gcloud >/dev/null 2>&1; then
    die "Cannot find gcloud, please install gcloud first"
  fi
}

check_credentials() {
  check_gcloud

  ids="$(gcloud auth list --filter=status:ACTIVE --format="value(account)")"
  for id in ${ids}; do
    if [[ "${id}" =~ .*"@google.com" ]]; then
      return 0
    fi
  done
  project="$1"
  gcloud auth application-default --project "${project}" login
}

run_in_temp() {
  (cd "${TEMP_DIR}"; "$@")
}

prepare_cros_regions() {
  cros_regions="${TEMP_DIR}/resource/cros-regions.json"
  ${REGIONS_DIR}/regions.py --format=json --all --notes > "${cros_regions}"
  add_temp "${cros_regions}"
}

prepare_protobuf() {
  local protobuf_out="${TEMP_DIR}/protobuf_out"
  mkdir -p "${protobuf_out}"
  protoc \
    -I="${RT_PROBE_DIR}" \
    -I="${HW_VERIFIER_DIR}" \
    --python_out="${protobuf_out}" \
    "${HW_VERIFIER_DIR}/hardware_verifier.proto" \
    "${RT_PROBE_DIR}/runtime_probe.proto"

  protobuf_out="${TEMP_DIR}/cros/factory/hwid/service/appengine/proto/"
  mkdir -p "${protobuf_out}"
  protoc \
    -I="${APPENGINE_DIR}/proto" \
    --python_out="${protobuf_out}" \
    "${APPENGINE_DIR}/proto/hwid_api_messages.proto" \
    "${APPENGINE_DIR}/proto/ingestion.proto"
}

do_make_build_folder() {
  mkdir -p "${TEMP_DIR}"
  add_temp "${TEMP_DIR}"
  # Change symlink to hard link due to b/70037640.
  local cp_files=(cron.yaml requirements.txt .gcloudignore)
  for file in "${cp_files[@]}"; do
    cp -l "${APPENGINE_DIR}/${file}" "${TEMP_DIR}"
  done
  cp -lr "${FACTORY_DIR}/py_pkg/cros" "${TEMP_DIR}"
  if [ -d "${FACTORY_PRIVATE_DIR}" ]; then
    mkdir -p "${TEMP_DIR}/resource"
    cp -l "\
${FACTORY_PRIVATE_DIR}/config/hwid/service/appengine/configurations.yaml" \
      "${TEMP_DIR}/resource"
  fi

  prepare_protobuf
  prepare_cros_regions
}

do_deploy() {
  local deployment_type="$1"
  shift
  local appengine_env="flexible"
  if [[ $# -gt 0 ]] ; then
    appengine_env="$1"
    shift
  fi
  check_gcloud
  check_credentials "${GCP_PROJECT}"

  if [ "${deployment_type}" == "${DEPLOYMENT_PROD}" ]; then
    do_test
  fi
  case "${appengine_env}" in
    standard|flexible)
      echo "Deploy HWID Service to App Engine in ${appengine_env}" \
        "environment."
      ;;
    *)
      die "Unavailable environment: \"${appengine_env}\".  Available" \
        "environments: \"standard\" or \"flexible\"."
      ;;
  esac

  do_make_build_folder

  local common_envs=(
    GCP_PROJECT="${GCP_PROJECT}"
    VPC_CONNECTOR_REGION="${VPC_CONNECTOR_REGION}"
    VPC_CONNECTOR_NAME="${VPC_CONNECTOR_NAME}"
    REDIS_HOST="${REDIS_HOST}"
    REDIS_PORT="${REDIS_PORT}"
    ENDPOINTS_SERVICE_NAME="${GCP_PROJECT}${ENDPOINTS_SUFFIX}"
    REDIS_CACHE_URL="${REDIS_CACHE_URL}"
    DOLLAR='$'
  )

  # Fill in env vars in app.*.yaml.template
  env "${common_envs[@]}" SERVICE=default \
    envsubst < "${APPENGINE_DIR}/app.${appengine_env}.yaml.template" > \
    "${TEMP_DIR}/app.yaml"

  case "${deployment_type}" in
    "${DEPLOYMENT_LOCAL}")
      run_in_temp dev_appserver.py "${@}" app.yaml
      ;;
    "${DEPLOYMENT_E2E}")
      CLOUDSDK_APP_CLOUD_BUILD_TIMEOUT="$CLOUDSDK_APP_CLOUD_BUILD_TIMEOUT" \
        run_in_temp gcloud --project="${GCP_PROJECT}" app deploy --no-promote \
        --version=e2e-test app.yaml
      ;;
    *)
      env "${common_envs[@]}" SERVICE=cron \
        envsubst < "${APPENGINE_DIR}/app.standard.yaml.template" > \
        "${TEMP_DIR}/app.cron.yaml"
      CLOUDSDK_APP_CLOUD_BUILD_TIMEOUT="$CLOUDSDK_APP_CLOUD_BUILD_TIMEOUT" \
        run_in_temp gcloud --project="${GCP_PROJECT}" app deploy app.yaml \
        app.cron.yaml cron.yaml
      ;;
  esac
}

do_build() {
  check_docker

  local dockerfile="${TEST_DIR}/Dockerfile"

  do_make_build_folder

  ${DOCKER} build \
    --file "${dockerfile}" \
    --tag "appengine_integration" \
    "${TEMP_DIR}"
}

do_test() {
  # Compile proto to *_pb2.py for e2e test.
  protoc \
    -I="${APPENGINE_DIR}/proto" \
    --python_out="${APPENGINE_DIR}/proto" \
    "${APPENGINE_DIR}/proto/hwid_api_messages.proto" \
    "${APPENGINE_DIR}/proto/ingestion.proto"
  add_temp "${APPENGINE_DIR}/proto/hwid_api_messages_pb2.py"
  add_temp "${APPENGINE_DIR}/proto/ingestion_pb2.py"

  # Runs all executables in the test folder.
  for test_exec in $(find "${TEST_DIR}" -executable -type f); do
    echo Running "${test_exec}"
    "${FACTORY_DIR}/bin/factory_env" "${test_exec}"
  done
}

usage() {
  cat << __EOF__
Chrome OS HWID Service Deployment Script

commands:
  $0 help
      Shows this help message.
      More about HWIDService: go/factory-git/py/hwid/service/appengine/README.md

  $0 deploy [prod|staging] [flexible|standard]
      Deploys HWID Service to the given environment by gcloud command.  The
      last argument is for deploying different App Engine environment which
      defaults to flexible.

  $0 deploy local [args...]
      Deploys HWID Service locally via dep_appserver.py tool.  Arguments will
      be delegated to the tool.

  $0 deploy e2e
      Deploys HWID Service to the staging server with specific version
      "e2e-test" which would not be affected with versions under development
      but just for end-to-end testing purpose.

  $0 build
      Builds docker image for AppEngine integration test.

  $0 test
      Runs all executables in the test directory.

__EOF__
}

main() {
  case "$1" in
    deploy)
      shift
      [ $# -gt 0 ] || (usage && exit 1);
      local deployment_type="$1"
      shift
      if ! load_config "${deployment_type}" ; then
        usage
        die "Unsupported deployment type: \"${deployment_type}\"."
      fi
      do_deploy "${deployment_type}" "${@}"
       ;;
    build)
      do_build
      ;;
    test)
      do_test
      ;;
    *)
      usage
      exit 1
      ;;
  esac

  mk_success
}

main "$@"
