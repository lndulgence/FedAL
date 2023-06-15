# FedAL
FedAL is my master's thesis, which consists of a RESTful API-based federated learning framework that can be used either via weight federation (FedAVG for independent models is computed on a master machine) or batch accumulated gradient federation (gradients are calculated in worker nodes, then retrieved and accumulated, then propagated in the master node)

## Usage
In each worker, the APIenv, workerenv (V1 for weight federation, V2 for batch gradient federation), and nginxenv must be placed within the same folder. The worker.py file must be altered to contain the IP of the node its run on in its IP variable.
The deploy.sh script must be run in order to deploy the service in each of the workers.
For the master node, simply import the corresponding version of fedlearner. Example notebooks are available for each version.
The db parameters file must be altered as well, to contain proper directions to a database. Db parameters being passed in the API request is considered, but not yet implemented due to time constraints.

## Requirements
Worker nodes must have docker installed, as well as CUDA and the nvidia container toolkit. It is recommended that the master node also runs CUDA in order to accelerate weight averaging and gradient propagation, as well as model evaluation.

## Considerations
Experimentally, batch federation has been found to perform much more stably, and yield models whose performance is a lot better over validation data. However, due to I/O delay on the API request and writing to the DB, as well as evaluation, batch federation is also very impractical as of right now, taking around 10 seconds to propagate the gradient of 1 batch. This makes epochs take a very long time to run even on powerful GPUS.
Batch federation also allows to take advantage of the memory of all the GPUs in the cluster, sacrificing speed for memory. However, due to the I/O time being the greatest delay, batch federation is expected to work very efficiently for large datasets distributed on large clusters, allowing for very high nominal batch sizes.
