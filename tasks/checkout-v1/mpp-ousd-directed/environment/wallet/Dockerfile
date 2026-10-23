FROM public.ecr.aws/docker/library/python@sha256:57b29a7c050c4e679e4bea572e14b3965cf4b5839de2da49d55e49ffc4024f39
RUN pip install --no-cache-dir eth-account==0.13.7
WORKDIR /srv
COPY init.py ./
CMD ["python", "init.py"]
