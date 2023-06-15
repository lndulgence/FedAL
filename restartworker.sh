cd workerenv
docker build -t worker .
docker stop worker && docker rm worker
cd ..
docker run -d --name worker --hostname worker  --network app --volume ~/FedService/data/:/data/ --gpus all --restart unless-stopped worker
