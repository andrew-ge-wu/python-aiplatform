# -*- coding: utf-8 -*-
# Copyright 2023 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import importlib

from google.api_core import operation as ga_operation
from google.cloud import aiplatform
import vertexai
from google.cloud.aiplatform_v1beta1.services.persistent_resource_service import (
    PersistentResourceServiceClient,
)
from google.cloud.aiplatform_v1beta1.types import persistent_resource_service
from google.cloud.aiplatform_v1beta1.types.persistent_resource import (
    PersistentResource,
)
from google.cloud.aiplatform_v1beta1.types.persistent_resource import (
    ResourcePool,
)
from vertexai.preview._workflow.executor import (
    persistent_resource_util,
)
from vertexai.preview._workflow.shared import configs
import mock
import pytest


_TEST_PROJECT = "test-project"
_TEST_LOCATION = "us-central1"
_TEST_PARENT = f"projects/{_TEST_PROJECT}/locations/{_TEST_LOCATION}"
_TEST_CLUSTER_NAME = "test-cluster"
_TEST_CLUSTER_CONFIG = configs.PersistentResourceConfig(name=_TEST_CLUSTER_NAME)
_TEST_CLUSTER_RESOURCE_NAME = f"{_TEST_PARENT}/persistentResources/{_TEST_CLUSTER_NAME}"


_TEST_PERSISTENT_RESOURCE_ERROR = PersistentResource()
_TEST_PERSISTENT_RESOURCE_ERROR.state = "ERROR"

_TEST_REQUEST_RUNNING_DEFAULT = PersistentResource()
resource_pool = ResourcePool()
resource_pool.machine_spec.machine_type = "n1-standard-4"
resource_pool.replica_count = 1
resource_pool.disk_spec.boot_disk_type = "pd-ssd"
resource_pool.disk_spec.boot_disk_size_gb = 100
_TEST_REQUEST_RUNNING_DEFAULT.resource_pools = [resource_pool]


_TEST_PERSISTENT_RESOURCE_RUNNING = PersistentResource()
_TEST_PERSISTENT_RESOURCE_RUNNING.state = "RUNNING"


@pytest.fixture
def persistent_resource_running_mock():
    with mock.patch.object(
        PersistentResourceServiceClient,
        "get_persistent_resource",
    ) as persistent_resource_running_mock:
        persistent_resource_running_mock.return_value = (
            _TEST_PERSISTENT_RESOURCE_RUNNING
        )
        yield persistent_resource_running_mock


@pytest.fixture
def persistent_resource_exception_mock():
    with mock.patch.object(
        PersistentResourceServiceClient,
        "get_persistent_resource",
    ) as persistent_resource_exception_mock:
        persistent_resource_exception_mock.side_effect = Exception
        yield persistent_resource_exception_mock


@pytest.fixture
def create_persistent_resource_default_mock():
    with mock.patch.object(
        PersistentResourceServiceClient,
        "create_persistent_resource",
    ) as create_persistent_resource_default_mock:
        create_persistent_resource_lro_mock = mock.Mock(ga_operation.Operation)
        create_persistent_resource_lro_mock.result.return_value = (
            _TEST_REQUEST_RUNNING_DEFAULT
        )
        create_persistent_resource_default_mock.return_value = (
            create_persistent_resource_lro_mock
        )
        yield create_persistent_resource_default_mock


@pytest.fixture
def persistent_resource_error_mock():
    with mock.patch.object(
        PersistentResourceServiceClient,
        "get_persistent_resource",
    ) as persistent_resource_error_mock:
        persistent_resource_error_mock.return_value = _TEST_PERSISTENT_RESOURCE_ERROR
        yield persistent_resource_error_mock


@pytest.fixture
def create_persistent_resource_exception_mock():
    with mock.patch.object(
        PersistentResourceServiceClient,
        "create_persistent_resource",
    ) as create_persistent_resource_exception_mock:
        create_persistent_resource_exception_mock.side_effect = Exception
        yield create_persistent_resource_exception_mock


@pytest.mark.usefixtures("google_auth_mock")
class TestPersistentResourceUtils:
    def setup_method(self):
        importlib.reload(vertexai.preview.initializer)
        importlib.reload(vertexai.preview)

    def teardown_method(self):
        aiplatform.initializer.global_pool.shutdown(wait=True)

    def test_check_persistent_resource_true(self, persistent_resource_running_mock):
        expected = persistent_resource_util.check_persistent_resource(
            _TEST_CLUSTER_RESOURCE_NAME
        )

        assert expected

        request = persistent_resource_service.GetPersistentResourceRequest(
            name=_TEST_CLUSTER_RESOURCE_NAME,
        )
        persistent_resource_running_mock.assert_called_once_with(request)

    def test_check_persistent_resource_false(self, persistent_resource_exception_mock):
        with pytest.raises(Exception):
            expected = persistent_resource_util.check_persistent_resource(
                _TEST_CLUSTER_RESOURCE_NAME
            )

            assert not expected

        request = persistent_resource_service.GetPersistentResourceRequest(
            name=_TEST_CLUSTER_RESOURCE_NAME,
        )
        persistent_resource_exception_mock.assert_called_once_with(request)

    @pytest.mark.usefixtures("persistent_resource_error_mock")
    def test_check_persistent_resource_error(self):
        with pytest.raises(ValueError) as e:
            persistent_resource_util.check_persistent_resource(
                _TEST_CLUSTER_RESOURCE_NAME
            )

        e.match(
            regexp=r'(\'The existing cluster `\', \'projects/test-project/locations/us-central1/persistentResources/test-cluster\', "` isn\'t running, please specify a different cluster_name.")'
        )

    @pytest.mark.usefixtures("persistent_resource_running_mock")
    def test_create_persistent_resource_default_success(
        self, create_persistent_resource_default_mock
    ):
        persistent_resource_util.create_persistent_resource(_TEST_CLUSTER_RESOURCE_NAME)

        request = persistent_resource_service.CreatePersistentResourceRequest(
            parent=_TEST_PARENT,
            persistent_resource=_TEST_REQUEST_RUNNING_DEFAULT,
            persistent_resource_id=_TEST_CLUSTER_NAME,
        )

        create_persistent_resource_default_mock.assert_called_with(
            request,
        )

    @pytest.mark.usefixtures("create_persistent_resource_exception_mock")
    def test_create_ray_cluster_state_error(self):
        with pytest.raises(ValueError) as e:
            persistent_resource_util.create_persistent_resource(
                _TEST_CLUSTER_RESOURCE_NAME
            )

        e.match(regexp=r"Failed in cluster creation due to: ")
