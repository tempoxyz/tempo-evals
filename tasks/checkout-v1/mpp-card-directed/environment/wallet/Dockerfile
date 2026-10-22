FROM python:3.13-slim
RUN pip install --no-cache-dir eth-account==0.13.7
WORKDIR /srv
COPY init.py ./
CMD ["python", "init.py"]
