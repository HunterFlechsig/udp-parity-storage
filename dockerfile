FROM python:3.11-slim

# set working dir
WORKDIR /app

# copy all your DSS code (manager.py, user.py, disk.py)
COPY . .

# install any dependencies (none required for stdlib: socket/json/select/etc.)
# RUN pip install -r requirements.txt

CMD [ "python3"]