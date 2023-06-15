# 


FROM python:3.9

# 

ENV TERM xterm
WORKDIR /code

# 


COPY ./requirements.txt /code/requirements.txt

# 


RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

# 


COPY ./app /code/app

# 
ENV PYTHONPATH=/code/app
COPY ./jobcontrol.bash /code/jobcontrol.bash
#CMD ["bash","jobcontrol.bash"]
#CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "80"]

CMD ["gunicorn", "app.main:app", "--workers", "12", "--timeout", "300", "--forwarded-allow-ips=\"nginx, http://nginx\"", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8080"]

EXPOSE 8080