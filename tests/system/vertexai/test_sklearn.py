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

import os
from unittest import mock

import vertexai
from tests.system.aiplatform import e2e_base
from vertexai.preview._workflow.executor import training
import pandas as pd
import pytest
from sklearn.datasets import load_iris
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler


# Wrap classes
StandardScaler = vertexai.preview.remote(StandardScaler)
LogisticRegression = vertexai.preview.remote(LogisticRegression)


@mock.patch.object(
    training,
    "VERTEX_AI_DEPENDENCY_PATH",
    "google-cloud-aiplatform[preview] @ git+https://github.com/googleapis/"
    f"python-aiplatform.git@{os.environ['KOKORO_GIT_COMMIT']}"
    if os.environ.get("KOKORO_GIT_COMMIT")
    else "google-cloud-aiplatform[preview] @ git+https://github.com/googleapis/python-aiplatform.git@copybara_557913723",
)
@mock.patch.object(
    training,
    "VERTEX_AI_DEPENDENCY_PATH_AUTOLOGGING",
    "google-cloud-aiplatform[preview,autologging] @ git+https://github.com/googleapis/"
    f"python-aiplatform.git@{os.environ['KOKORO_GIT_COMMIT']}"
    if os.environ.get("KOKORO_GIT_COMMIT")
    else "google-cloud-aiplatform[preview,autologging] @ git+https://github.com/googleapis/python-aiplatform.git@copybara_557913723",
)
@pytest.mark.usefixtures(
    "prepare_staging_bucket", "delete_staging_bucket", "tear_down_resources"
)
class TestRemoteExecutionSklearn(e2e_base.TestEndToEnd):

    _temp_prefix = "temp-vertexai-remote-execution"

    def test_remote_execution_sklearn(self, shared_state):
        # Initialize vertexai
        vertexai.init(
            project=e2e_base._PROJECT,
            location=e2e_base._LOCATION,
            staging_bucket=f"gs://{shared_state['staging_bucket_name']}",
        )

        # Prepare dataset
        dataset = load_iris()
        X, X_retrain, y, y_retrain = train_test_split(
            dataset.data, dataset.target, test_size=0.60, random_state=42
        )
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.20, random_state=42
        )

        # Remote fit_transform on train dataset
        vertexai.preview.init(remote=True)

        transformer = StandardScaler()
        transformer.fit_transform.vertex.set_config(
            display_name=self._make_display_name("fit-transform"),
        )
        X_train = transformer.fit_transform(X_train)

        # Remote transform on test dataset
        transformer.transform.vertex.set_config(
            display_name=self._make_display_name("transform"),
        )
        X_test = transformer.transform(X_test)

        # Local transform on retrain data
        vertexai.preview.init(remote=False)
        X_retrain = transformer.transform(X_retrain)
        # Transform retrain dataset to pandas dataframe
        X_retrain_df = pd.DataFrame(X_retrain, columns=dataset.feature_names)
        y_retrain_df = pd.DataFrame(y_retrain, columns=["class"])

        # Remote training on sklearn
        vertexai.preview.init(remote=True)

        model = LogisticRegression(warm_start=True)
        model.fit.vertex.remote_config.display_name = self._make_display_name(
            "sklearn-training"
        )
        model.fit(X_train, y_train)

        # Remote prediction on sklearn
        model.predict.vertex.remote_config.display_name = self._make_display_name(
            "sklearn-prediction"
        )
        model.predict(X_test)

        # Register trained model
        registered_model = vertexai.preview.register(model)
        shared_state["resources"] = [registered_model]

        # Load the registered model
        pulled_model = vertexai.preview.from_pretrained(
            model_name=registered_model.resource_name
        )

        # Retrain model with pandas df on Vertex
        pulled_model.fit(X_retrain_df, y_retrain_df)
