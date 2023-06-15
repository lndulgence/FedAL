docker run -d --hostname rabbitmq --network app    --name rabbitmq -p 15672:15672  --volume ~/FedService/rabbitmqdata:/var/lib/rabbitmq/mnesia/ --restart unless-stopped rabbitmq:3-management 
docker run -d --name worker --hostname worker  --network app --volume ~/FedService/data/:/data/ --gpus all --restart unless-stopped worker
docker run -d --name api --hostname api --network app  --volume ~/FedService/data/:/data/  --restart unless-stopped api
docker run -d --hostname nginx --name nginx --network app -p 80:80 -p 443:443 --restart unless-stopped nginx 
