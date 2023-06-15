docker build -t nginx . && docker stop nginx && docker rm nginx && docker run -d --hostname nginx --name nginx --network app -p 80:80 -p 443:443 --restart unless-stopped nginx 
