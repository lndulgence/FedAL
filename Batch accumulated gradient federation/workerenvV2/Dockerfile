# 


FROM  nvcr.io/nvidia/tensorflow:22.01-tf2-py3 


# 


WORKDIR /code

# 


COPY ./requirements.txt /code/requirements.txt

#
RUN mkdir /data/ 
RUN apt update
RUN apt install -y pip
RUN apt-get update && apt-get install ffmpeg libsm6 libxext6  -y

RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

# 
#RUN python -c "import tensorflow as tf; print(tf.config.list_physical_devices('GPU'))"

COPY ./app /code/app

WORKDIR /code/app
# 
#CMD ["bash","jobcontrol.bash"]
#CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "80"]

ENTRYPOINT ["python", "worker.py"]

