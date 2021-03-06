# Copyright 2020 Cortex Labs, Inc.
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

import os
import json

from cortex.lib.type import get_spec
from cortex.lib.storage import S3, LocalStorage
from cortex.lib.checkers.pod import wait_neuron_rtd


def load_tensorflow_serving_models():
    # get TFS address-specific details
    model_dir = os.environ["CORTEX_MODEL_DIR"]
    tf_serving_host = os.getenv("CORTEX_TF_SERVING_HOST", "localhost")
    tf_base_serving_port = int(os.getenv("CORTEX_TF_BASE_SERVING_PORT", "9000"))

    # get models from environment variable
    models = os.environ["CORTEX_MODELS"].split(",")
    models = [model.strip() for model in models]

    from cortex.lib.server.tensorflow import TensorFlowServing

    # determine if multiple TF processes are required
    num_processes = 1
    has_multiple_servers = os.getenv("CORTEX_MULTIPLE_TF_SERVERS")
    if has_multiple_servers:
        num_processes = int(os.environ["CORTEX_PROCESSES_PER_REPLICA"])

    # initialize models for each TF process
    base_paths = [os.path.join(model_dir, name) for name in models]
    for w in range(int(num_processes)):
        tfs = TensorFlowServing(f"{tf_serving_host}:{tf_base_serving_port+w}")
        tfs.add_models_config(models, base_paths, replace_models=False)


def main():
    # wait until neuron-rtd sidecar is ready
    uses_inferentia = os.getenv("CORTEX_ACTIVE_NEURON")
    if uses_inferentia:
        wait_neuron_rtd()

    # strictly for Inferentia
    has_multiple_servers = os.getenv("CORTEX_MULTIPLE_TF_SERVERS")
    if has_multiple_servers:
        base_serving_port = int(os.environ["CORTEX_TF_BASE_SERVING_PORT"])
        num_processes = int(os.environ["CORTEX_PROCESSES_PER_REPLICA"])
        used_ports = {}
        for w in range(int(num_processes)):
            used_ports[str(base_serving_port + w)] = False
        with open("/run/used_ports.json", "w+") as f:
            json.dump(used_ports, f)

    # get API spec
    cache_dir = os.environ["CORTEX_CACHE_DIR"]
    provider = os.environ["CORTEX_PROVIDER"]
    spec_path = os.environ["CORTEX_API_SPEC"]
    if provider == "local":
        storage = LocalStorage(os.getenv("CORTEX_CACHE_DIR"))
    else:
        storage = S3(bucket=os.environ["CORTEX_BUCKET"], region=os.environ["AWS_REGION"])
    raw_api_spec = get_spec(provider, storage, cache_dir, spec_path)

    # load tensorflow models into TFS
    if raw_api_spec["predictor"]["type"] == "tensorflow":
        load_tensorflow_serving_models()


if __name__ == "__main__":
    main()
